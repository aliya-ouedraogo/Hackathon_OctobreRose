"""Calibration, seuils de couleur, évaluation finale et sélection des cas de démo.

1. VALIDATION : mise à l'échelle de la température, puis choix des seuils
   - t_orange : le plus haut seuil donnant une sensibilité ≥ --target-sens
     (par défaut 95 %) sur les cas malins ;
   - t_red    : seuil donnant une spécificité ≥ --red-spec (par défaut 90 %).
2. TEST (une seule fois, en fin de projet) : AUC, matrice de confusion,
   sensibilité/spécificité aux deux seuils, calibration (ECE), Dice/IoU,
   répartition des couleurs par classe réelle.
3. Copie 8 cas de test dans app/demo/, dont au moins une erreur du modèle.

Écrit models/settings.json et models/metrics.json (lus par l'application).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from seinsur.core import (CLASSES, MALIGNE, MODELS_DIR, ROOT, Settings, risk_level,  # noqa: E402
                          softmax)
from seinsur.data import read_split  # noqa: E402
from seinsur.inference import Analyzer  # noqa: E402


def fit_temperature(logits: np.ndarray, y: np.ndarray) -> float:
    t = torch.zeros(1, requires_grad=True)  # log-température
    lg, yt = torch.from_numpy(logits), torch.from_numpy(y)
    opt = torch.optim.LBFGS([t], lr=0.1, max_iter=200)

    def closure():
        opt.zero_grad()
        loss = torch.nn.functional.cross_entropy(lg / t.exp(), yt)
        loss.backward()
        return loss

    opt.step(closure)
    return float(t.detach().exp().clamp(0.05, 20))


def ece(probs: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    conf, pred = probs.max(1), probs.argmax(1)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (conf > lo) & (conf <= hi)
        if sel.any():
            total += sel.mean() * abs((pred[sel] == y[sel]).mean() - conf[sel].mean())
    return float(total)


def sens_spec(alert: np.ndarray, is_mal: np.ndarray) -> tuple[float, float]:
    sens = float(alert[is_mal].mean()) if is_mal.any() else float("nan")
    spec = float((~alert[~is_mal]).mean()) if (~is_mal).any() else float("nan")
    return sens, spec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-sens", type=float, default=0.95)
    ap.add_argument("--red-spec", type=float, default=0.90)
    ap.add_argument("--min-confidence", type=float, default=0.35)
    ap.add_argument("--n-demo", type=int, default=8)
    ap.add_argument("--version-label", default=None, help="étiquette de version affichée dans l'app")
    args = ap.parse_args()

    an = Analyzer()

    def run(split):
        rows = read_split(split)
        imgs = [Image.open(ROOT / r["image"]).convert("L") for r in rows]
        lg = np.stack([an.logits(im) for im in imgs]).astype(np.float32)
        return rows, imgs, lg, np.array([int(r["label"]) for r in rows])

    # ---------------- Validation : calibration et seuils ----------------
    _, _, lg_val, y_val = run("val")
    T = fit_temperature(lg_val, y_val)
    p_val = softmax(lg_val, T)
    is_mal_val = y_val == MALIGNE
    pm = p_val[:, MALIGNE]
    # plus haut seuil gardant la sensibilité visée
    cands = np.sort(np.unique(pm[is_mal_val]))[::-1]
    t_orange = float(cands[-1]) if len(cands) else 0.1
    for c in cands:
        if (pm[is_mal_val] >= c).mean() >= args.target_sens:
            t_orange = float(c)
            break
    t_orange = max(min(t_orange, 0.5), 0.01) - 1e-6
    neg = np.sort(pm[~is_mal_val])
    t_red = float(np.quantile(neg, args.red_spec)) if len(neg) else 0.5
    t_red = max(t_red, t_orange + 0.05, 0.3)

    s = an.settings
    s.temperature, s.t_orange, s.t_red, s.min_confidence = T, t_orange, t_red, args.min_confidence
    s.model_version = args.version_label or dt.date.today().isoformat()
    an.settings = s
    print(f"Température={T:.2f}  t_orange={t_orange:.3f}  t_red={t_red:.3f}")

    # ---------------- Test : mesures finales ----------------
    rows, imgs, lg_te, y_te = run("test")
    p_raw, p_te = softmax(lg_te, 1.0), softmax(lg_te, T)
    is_mal = y_te == MALIGNE
    levels = [risk_level(p, s)[0] for p in p_te]
    alert = np.array([lv != "vert" for lv in levels])
    red = np.array([lv == "rouge" for lv in levels])
    sens_o, spec_o = sens_spec(alert, is_mal)
    sens_r, spec_r = sens_spec(red, is_mal)
    fpr, tpr, _ = roc_curve(is_mal, p_te[:, MALIGNE])
    cm = confusion_matrix(y_te, p_te.argmax(1), labels=[0, 1, 2])
    per_class = {}
    for k, name in enumerate(CLASSES):
        tp = cm[k, k]
        per_class[name] = {"sensibilite": float(tp / max(cm[k].sum(), 1)),
                           "specificite": float((cm.sum() - cm[k].sum() - cm[:, k].sum() + tp) / max(cm.sum() - cm[k].sum(), 1))}
    color_table = {CLASSES[k]: {lv: int(sum(1 for lvl, yy in zip(levels, y_te) if yy == k and lvl == lv))
                                for lv in ("vert", "orange", "rouge")} for k in range(3)}

    dice, iou = [], []
    if an.seg is not None:
        for r, im in zip(rows, imgs):
            if int(r["label"]) == 0:
                continue
            gt = np.asarray(Image.open(ROOT / r["mask"]).convert("L")) > 127
            pr = an.segment(im)
            inter = (pr & gt).sum()
            dice.append(2 * inter / max(pr.sum() + gt.sum(), 1))
            iou.append(inter / max((pr | gt).sum(), 1))

    metrics = {
        "date": dt.date.today().isoformat(),
        "n_test": int(len(y_te)), "n_test_par_classe": {CLASSES[k]: int((y_te == k).sum()) for k in range(3)},
        "auc_maligne": float(roc_auc_score(is_mal, p_te[:, MALIGNE])),
        "roc": {"fpr": fpr.round(4).tolist(), "tpr": tpr.round(4).tolist()},
        "exactitude_3_classes": float((p_te.argmax(1) == y_te).mean()),
        "matrice_confusion": cm.tolist(),
        "par_classe": per_class,
        "alerte_orange_ou_rouge": {"sensibilite_maligne": sens_o, "specificite": spec_o},
        "alerte_rouge": {"sensibilite_maligne": sens_r, "specificite": spec_r},
        "malins_classes_vert": int(sum(1 for lvl, m in zip(levels, is_mal) if m and lvl == "vert")),
        "couleurs_par_classe_reelle": color_table,
        "ece_avant_calibration": ece(p_raw, y_te), "ece_apres_calibration": ece(p_te, y_te),
        "dice": float(np.mean(dice)) if dice else None, "iou": float(np.mean(iou)) if iou else None,
        "seuils": {"temperature": T, "t_orange": t_orange, "t_red": t_red,
                   "sensibilite_visee_validation": args.target_sens},
    }
    s.save()
    (MODELS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in metrics.items() if k != "roc"}, indent=2, ensure_ascii=False))

    # ---------------- Cas de démonstration ----------------
    demo_dir = ROOT / "app" / "demo"
    shutil.rmtree(demo_dir, ignore_errors=True)
    demo_dir.mkdir(parents=True)
    rng = np.random.default_rng(0)
    pred = p_te.argmax(1)
    chosen = []
    errors = [i for i in range(len(y_te)) if (is_mal[i] and levels[i] == "vert") or pred[i] != y_te[i]]
    errors.sort(key=lambda i: (not (is_mal[i] and levels[i] == "vert"), rng.random()))
    chosen += errors[:1]  # au moins un cas où le modèle se trompe, présenté honnêtement
    for lv, k in [("rouge", 2), ("rouge", 2), ("orange", 1), ("orange", 2), ("vert", 0), ("vert", 1), ("vert", 0)]:
        pool = [i for i in range(len(y_te)) if levels[i] == lv and y_te[i] == k and i not in chosen]
        if pool:
            chosen.append(int(rng.choice(pool)))
    rest = [i for i in rng.permutation(len(y_te)).tolist() if i not in chosen]
    chosen = (chosen + rest)[: args.n_demo]  # compléter si certaines couleurs manquent
    demo = []
    for n, i in enumerate(chosen, 1):
        name = f"cas_{n:02d}.png"
        shutil.copy(ROOT / rows[i]["image"], demo_dir / name)
        demo.append({"file": name, "verite": CLASSES[y_te[i]], "id": rows[i]["id"],
                     "erreur_du_modele": bool(i in errors)})
    (demo_dir / "demo.json").write_text(json.dumps(demo, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(demo)} cas de démonstration → {demo_dir}")


if __name__ == "__main__":
    main()
