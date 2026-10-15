"""Entraîne le U-Net de segmentation de la zone suspecte.

Perte combinée Dice + entropie croisée binaire, Adam, arrêt anticipé sur
le Dice de validation. Seules les images avec lésion (bénigne / maligne)
servent à l'apprentissage du contour.

Usage :
    python scripts/train_segmentation.py --encoder resnet34
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from echobreast.core import MODELS_DIR, build_segmenter  # noqa: E402
from echobreast.data import BusiDataset  # noqa: E402


def dice_loss(logits, target, eps=1.0):
    p = torch.sigmoid(logits)
    inter = (p * target).sum((1, 2, 3))
    union = p.sum((1, 2, 3)) + target.sum((1, 2, 3))
    return 1 - ((2 * inter + eps) / (union + eps)).mean()


def dice_iou(logits, target, eps=1e-6):
    pred = (torch.sigmoid(logits) > 0.5).float()
    inter = (pred * target).sum((1, 2, 3))
    s = pred.sum((1, 2, 3)) + target.sum((1, 2, 3))
    dice = (2 * inter + eps) / (s + eps)
    iou = (inter + eps) / (s - inter + eps)
    return dice.tolist(), iou.tolist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--encoder", default="resnet34")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--patience", type=int, default=8)
    ap.add_argument("--no-pretrained", action="store_true", help="test hors ligne uniquement")
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()

    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    train = BusiDataset("train", "seg", augment=True)
    val = BusiDataset("val", "seg")
    tl = DataLoader(train, args.batch, shuffle=True, num_workers=args.workers, drop_last=len(train) > args.batch)
    vl = DataLoader(val, args.batch, num_workers=args.workers)

    model = build_segmenter(args.encoder, pretrained=not args.no_pretrained).to(device)
    bce = nn.BCEWithLogitsLoss()
    opt = torch.optim.Adam(model.parameters(), lr=3e-4)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode="max", patience=3, factor=0.5)
    out_path = MODELS_DIR / "segmenter.pt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    best, wait = -1.0, 0

    for ep in range(args.epochs):
        model.train()
        tot = 0.0
        for x, m in tl:
            x, m = x.to(device), m.to(device)
            out = model(x)
            loss = dice_loss(out, m) + bce(out, m)
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += loss.item() * len(x)
        model.eval()
        dices, ious = [], []
        with torch.no_grad():
            for x, m in vl:
                d, i = dice_iou(model(x.to(device)), m.to(device))
                dices += d
                ious += i
        vd, vi = sum(dices) / len(dices), sum(ious) / len(ious)
        sched.step(vd)
        mark = ""
        if vd > best:
            best, wait, mark = vd, 0, " ✓ sauvegardé"
            torch.save({"encoder": args.encoder, "state_dict": model.state_dict()}, out_path)
        else:
            wait += 1
        print(f"{ep+1:02d} loss={tot/len(train):.3f} | val Dice={vd:.3f} IoU={vi:.3f}{mark}")
        if wait >= args.patience:
            print("Arrêt anticipé.")
            break
    print(f"Meilleur Dice validation : {best:.3f} → {out_path}")


if __name__ == "__main__":
    main()
