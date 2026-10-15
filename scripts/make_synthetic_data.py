"""Génère un FAUX jeu au format BUSI pour tester le pipeline sans les vraies données.

Ces images ne sont pas des échographies : elles servent uniquement à vérifier
que les scripts et l'application fonctionnent de bout en bout.

    python scripts/make_synthetic_data.py --out data/synthetic_busi
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def lesion(draw, rng, size, irregular):
    cx, cy = rng.integers(size // 4, 3 * size // 4, 2)
    r = rng.integers(size // 12, size // 6)
    n = 40
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    jitter = rng.uniform(0.55, 1.45, n) if irregular else rng.uniform(0.9, 1.1, n)
    rx, ry = r * rng.uniform(1.0, 1.6), r
    pts = [(cx + rx * j * np.cos(a), cy + ry * j * np.sin(a)) for a, j in zip(ang, jitter)]
    draw.polygon(pts, fill=255)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data/synthetic_busi"))
    ap.add_argument("--n", type=int, nargs=3, default=[40, 60, 50], help="normal benign malignant")
    ap.add_argument("--size", type=int, default=300)
    args = ap.parse_args()
    rng = np.random.default_rng(0)
    for folder, n in zip(["normal", "benign", "malignant"], args.n):
        d = args.out / folder
        d.mkdir(parents=True, exist_ok=True)
        for i in range(1, n + 1):
            s = args.size
            base = rng.gamma(2.0, 30.0, (s, s)) * np.linspace(1.2, 0.5, s)[:, None]
            img = Image.fromarray(base.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
            mask = Image.new("L", (s, s), 0)
            if folder != "normal":
                lesion(ImageDraw.Draw(mask), rng, s, irregular=folder == "malignant")
                m = np.asarray(mask.filter(ImageFilter.GaussianBlur(2))) / 255.0
                arr = np.asarray(img, dtype=np.float32) * (1 - 0.8 * m)
                img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
            img.save(d / f"{folder} ({i}).png")
            if folder != "normal" or rng.random() < 1.0:
                mask.save(d / f"{folder} ({i})_mask.png")
    print("Jeu synthétique →", args.out)


if __name__ == "__main__":
    main()
