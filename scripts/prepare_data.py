"""Prépare le jeu BUSI (ou Curated BUSI) : fusion des masques, dédoublonnage, séparation.

Usage :
    python scripts/prepare_data.py --src chemin/vers/Dataset_BUSI_with_GT

Attend un dossier contenant les sous-dossiers normal/, benign/, malignant/
avec des fichiers du type « benign (1).png », « benign (1)_mask.png »,
« benign (1)_mask_1.png ». Produit data/processed/ :
    images/   copies des images
    masks/    un seul masque binaire par image (masques multiples fusionnés)
    splits.csv  colonnes : id, image, mask, label, split, group

La séparation 70/15/15 est stratifiée par classe, avec une graine fixe, et
faite AVANT toute augmentation. Les images quasi identiques (même empreinte
perceptuelle) sont gardées dans le même sous-ensemble pour éviter les fuites.
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from echobreast.core import CLASSES, FOLDERS, ROOT  # noqa: E402

IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp"}


def dhash(img: Image.Image, size: int = 8) -> int:
    """Empreinte perceptuelle (difference hash) pour repérer les doublons."""
    a = np.asarray(img.convert("L").resize((size + 1, size), Image.BILINEAR), dtype=np.int16)
    bits = (a[:, 1:] > a[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def collect(src: Path):
    items = []
    for label, folder in enumerate(FOLDERS):
        d = src / folder
        if not d.is_dir():
            sys.exit(f"Dossier manquant : {d}")
        files = sorted(p for p in d.iterdir() if p.suffix.lower() in IMG_EXT)
        images = [p for p in files if "_mask" not in p.stem]
        for img in images:
            masks = [p for p in files if p.stem.startswith(img.stem + "_mask")]
            items.append({"path": img, "masks": masks, "label": label})
    return items


def group_duplicates(items, max_dist: int):
    """Union-find : relie les images dont les empreintes sont très proches."""
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    hashes = [dhash(Image.open(it["path"])) for it in items]
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if hamming(hashes[i], hashes[j]) <= max_dist:
                parent[find(i)] = find(j)
    return [find(i) for i in range(len(items))]


def rel(p: Path) -> str:
    p = p.resolve()
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.as_posix()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "processed")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dup-dist", type=int, default=2,
                    help="distance de Hamming max entre empreintes pour considérer un doublon")
    ap.add_argument("--drop-duplicates", action="store_true",
                    help="ne garder qu'une image par groupe de doublons")
    args = ap.parse_args()

    items = collect(args.src)
    print("Images trouvées :", {CLASSES[k]: sum(it["label"] == k for it in items) for k in range(3)})

    groups = group_duplicates(items, args.dup_dist)
    n_groups = len(set(groups))
    print(f"Groupes après dédoublonnage : {n_groups} (≈ {len(items) - n_groups} doublons probables)")

    # Un groupe qui mélange plusieurs classes = étiquette douteuse : on le signale.
    by_group = defaultdict(list)
    for i, g in enumerate(groups):
        by_group[g].append(i)
    conflicts = [g for g, idx in by_group.items() if len({items[i]["label"] for i in idx}) > 1]
    if conflicts:
        print(f"⚠ {len(conflicts)} groupes de doublons avec des étiquettes différentes (exclus).")
    keep_groups = [g for g in by_group if g not in conflicts]

    # Séparation stratifiée par classe, au niveau des groupes.
    rng = random.Random(args.seed)
    split_of = {}
    for label in range(3):
        gs = sorted(g for g in keep_groups if items[by_group[g][0]]["label"] == label)
        rng.shuffle(gs)
        n = len(gs)
        n_tr, n_va = round(0.70 * n), round(0.15 * n)
        for k, g in enumerate(gs):
            split_of[g] = "train" if k < n_tr else "val" if k < n_tr + n_va else "test"

    (args.out / "images").mkdir(parents=True, exist_ok=True)
    (args.out / "masks").mkdir(parents=True, exist_ok=True)
    rows = []
    for g in keep_groups:
        idx = by_group[g][:1] if args.drop_duplicates else by_group[g]
        for i in idx:
            it = items[i]
            uid = f"{FOLDERS[it['label']]}_{it['path'].stem.split('(')[-1].rstrip(')').strip() or i}"
            img = Image.open(it["path"]).convert("L")
            img_out = args.out / "images" / f"{uid}.png"
            img.save(img_out)
            mask = np.zeros((img.height, img.width), dtype=bool)
            for m in it["masks"]:
                mask |= np.asarray(Image.open(m).convert("L").resize(img.size, Image.NEAREST)) > 127
            mask_out = args.out / "masks" / f"{uid}.png"
            Image.fromarray((mask * 255).astype(np.uint8)).save(mask_out)
            rows.append({"id": uid, "image": rel(img_out), "mask": rel(mask_out),
                         "label": it["label"], "split": split_of[g], "group": g})

    with open(args.out / "splits.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["id"]))

    for s in ("train", "val", "test"):
        counts = [sum(r["split"] == s and r["label"] == k for r in rows) for k in range(3)]
        print(f"{s:5s} : " + ", ".join(f"{CLASSES[k]}={c}" for k, c in enumerate(counts)))
    print("→", args.out / "splits.csv")


if __name__ == "__main__":
    main()
