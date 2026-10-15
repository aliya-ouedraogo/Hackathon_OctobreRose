"""Entraîne le classifieur 3 classes (normale / bénigne / maligne).

Transfert d'apprentissage en deux phases :
  1. tête seule (réseau gelé),
  2. dégel complet avec un faible taux d'apprentissage.
Perte d'entropie croisée pondérée par classe, Adam, arrêt anticipé sur la
validation (critère : AUC « maligne contre le reste »).

Usage (Colab / Kaggle, GPU conseillé) :
    python scripts/train_classifier.py --arch efficientnet_b0
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import roc_auc_score
from torch import nn
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from seinsur.core import MALIGNE, MODELS_DIR, build_classifier  # noqa: E402
from seinsur.data import BusiDataset  # noqa: E402


def run_epoch(model, loader, device, loss_fn, opt=None):
    model.train(opt is not None)
    total, logits_all, y_all = 0.0, [], []
    with torch.set_grad_enabled(opt is not None):
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            out = model(x)
            loss = loss_fn(out, y)
            if opt is not None:
                opt.zero_grad()
                loss.backward()
                opt.step()
            total += loss.item() * len(y)
            logits_all.append(out.detach().cpu())
            y_all.append(y.cpu())
    logits = torch.cat(logits_all).numpy()
    y = torch.cat(y_all).numpy()
    p_mal = torch.softmax(torch.from_numpy(logits), 1)[:, MALIGNE].numpy()
    auc = roc_auc_score(y == MALIGNE, p_mal) if len(set(y == MALIGNE)) > 1 else float("nan")
    acc = float((logits.argmax(1) == y).mean())
    return total / len(y), acc, auc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", default="efficientnet_b0")
    ap.add_argument("--epochs-head", type=int, default=5)
    ap.add_argument("--epochs-ft", type=int, default=30)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--patience", type=int, default=6)
    ap.add_argument("--no-pretrained", action="store_true", help="test hors ligne uniquement")
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()

    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("Appareil :", device)

    train = BusiDataset("train", "cls", augment=True)
    val = BusiDataset("val", "cls")
    tl = DataLoader(train, args.batch, shuffle=True, num_workers=args.workers, drop_last=len(train) > args.batch)
    vl = DataLoader(val, args.batch, num_workers=args.workers)

    counts = np.bincount(train.labels(), minlength=3).astype(np.float32)
    weights = torch.tensor(counts.sum() / (3 * np.maximum(counts, 1)), device=device)
    print("Poids des classes :", weights.cpu().numpy().round(2))
    loss_fn = nn.CrossEntropyLoss(weight=weights)

    model = build_classifier(args.arch, pretrained=not args.no_pretrained).to(device)
    out_path = MODELS_DIR / "classifier.pt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    best, wait = -1.0, 0

    def save_if_best(auc):
        nonlocal best, wait
        score = 0.0 if np.isnan(auc) else auc
        if score > best:
            best, wait = score, 0
            torch.save({"arch": args.arch, "state_dict": model.state_dict()}, out_path)
            return " ✓ sauvegardé"
        wait += 1
        return ""

    # Phase 1 : tête seule
    for p in model.parameters():
        p.requires_grad = False
    for p in model.get_classifier().parameters():
        p.requires_grad = True
    opt = torch.optim.Adam(model.get_classifier().parameters(), lr=1e-3)
    for ep in range(args.epochs_head):
        tr = run_epoch(model, tl, device, loss_fn, opt)
        va = run_epoch(model, vl, device, loss_fn)
        print(f"[tête] {ep+1:02d} train loss={tr[0]:.3f} acc={tr[1]:.2f} | val loss={va[0]:.3f} "
              f"acc={va[1]:.2f} AUC(maligne)={va[2]:.3f}{save_if_best(va[2])}")

    # Phase 2 : dégel avec faible taux d'apprentissage
    for p in model.parameters():
        p.requires_grad = True
    opt = torch.optim.Adam(model.parameters(), lr=1e-4, weight_decay=1e-5)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs_ft)
    wait = 0
    for ep in range(args.epochs_ft):
        tr = run_epoch(model, tl, device, loss_fn, opt)
        va = run_epoch(model, vl, device, loss_fn)
        sched.step()
        print(f"[fine] {ep+1:02d} train loss={tr[0]:.3f} acc={tr[1]:.2f} | val loss={va[0]:.3f} "
              f"acc={va[1]:.2f} AUC(maligne)={va[2]:.3f}{save_if_best(va[2])}")
        if wait >= args.patience:
            print("Arrêt anticipé.")
            break
    print(f"Meilleure AUC validation : {best:.3f} → {out_path}")


if __name__ == "__main__":
    main()
