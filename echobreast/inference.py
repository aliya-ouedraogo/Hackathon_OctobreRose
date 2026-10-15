"""Analyse d'une image : probabilités calibrées, niveau, contour, zones à inspecter, Grad-CAM."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

from .core import (CLS_SIZE, LEVELS, MALIGNE, MODELS_DIR, SEG_SIZE, Settings, build_classifier,
                   build_segmenter, confidence, quality_warnings, risk_level, softmax,
                   to_tensor_input)


@dataclass
class Result:
    probs: np.ndarray            # 3 probabilités calibrées, somme = 1
    level: str                   # vert / orange / rouge
    reasons: list[str]
    confidence: float
    mask: np.ndarray | None      # masque binaire à la taille de l'image d'origine
    warnings: list[str]

    @property
    def p_malignant(self) -> float:
        return float(self.probs[MALIGNE])


def _resize_float(a: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """Agrandissement bilinéaire d'une carte de probabilités (évite les contours en escalier)."""
    return cv2.resize(a.astype(np.float32), size, interpolation=cv2.INTER_LINEAR)


class Analyzer:
    def __init__(self, models_dir: Path = MODELS_DIR):
        self.settings = Settings.load(models_dir / "settings.json")
        ck = torch.load(models_dir / "classifier.pt", map_location="cpu", weights_only=False)
        self.cls = build_classifier(ck["arch"], pretrained=False)
        self.cls.load_state_dict(ck["state_dict"])
        self.cls.eval()
        self.seg = None
        seg_path = models_dir / "segmenter.pt"
        if seg_path.exists():
            ck = torch.load(seg_path, map_location="cpu", weights_only=False)
            self.seg = build_segmenter(ck["encoder"], pretrained=False)
            self.seg.load_state_dict(ck["state_dict"])
            self.seg.eval()

    @staticmethod
    def available(models_dir: Path = MODELS_DIR) -> bool:
        return (models_dir / "classifier.pt").exists()

    @torch.no_grad()
    def logits(self, img: Image.Image) -> np.ndarray:
        x = torch.from_numpy(to_tensor_input(img, CLS_SIZE))[None]
        return self.cls(x)[0].numpy()

    @torch.no_grad()
    def segment(self, img: Image.Image) -> np.ndarray | None:
        if self.seg is None:
            return None
        x = torch.from_numpy(to_tensor_input(img, SEG_SIZE))[None]
        prob = torch.sigmoid(self.seg(x))[0, 0].numpy()
        return _resize_float(prob, img.size) > 0.5

    def analyze(self, raw: Image.Image) -> Result:
        warnings = quality_warnings(raw)
        img = raw.convert("L")
        probs = softmax(self.logits(img), self.settings.temperature)
        level, reasons = risk_level(probs, self.settings)
        mask = None
        if int(probs.argmax()) != 0 or level != "vert":  # pas de contour pour une image « normale »
            mask = self.segment(img)
            # masque vide ou envahissant toute l'image = segmentation non fiable : pas de contour
            if mask is not None and not (0.001 * mask.size < mask.sum() < 0.5 * mask.size):
                mask = None
        return Result(probs, level, reasons, confidence(probs), mask, warnings)

    def gradcam(self, raw: Image.Image) -> np.ndarray:
        """Carte d'attention (0-1) à la taille de l'image, pour la classe « maligne »."""
        from pytorch_grad_cam import GradCAM
        from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget

        x = torch.from_numpy(to_tensor_input(raw, CLS_SIZE))[None]
        with GradCAM(model=self.cls, target_layers=[_last_conv(self.cls)]) as cam:
            heat = cam(input_tensor=x, targets=[ClassifierOutputTarget(MALIGNE)])[0]
        return np.clip(_resize_float(heat, raw.size), 0, 1)


def _last_conv(model):
    last = None
    for m in model.modules():
        if isinstance(m, torch.nn.Conv2d):
            last = m
    return last


# --------------------------------------------------------------------------
# Zones à inspecter
# --------------------------------------------------------------------------
def _polygons(binary: np.ndarray, eps_ratio: float = 0.004) -> list[list[list[int]]]:
    cnts, _ = cv2.findContours(binary.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    eps = eps_ratio * max(binary.shape)
    return [cv2.approxPolyDP(c, eps, True)[:, 0, :].tolist() for c in cnts if len(c) >= 3]


def find_zones(mask: np.ndarray | None, heat: np.ndarray | None, shape: tuple[int, int],
               heat_threshold: float = 0.6, max_attention: int = 2) -> list[dict]:
    """Zones à inspecter, de la plus à la moins importante.

    - « lesion »    : composantes du contour prédit par le U-Net ;
    - « attention » : zones où le classifieur a le plus regardé (Grad-CAM) mais
                      situées hors du contour ; à vérifier par le professionnel.
    """
    h, w = shape
    total = float(h * w)
    zones = []
    if mask is not None:
        n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
        for k in range(1, n):
            x, y, bw, bh, area = stats[k]
            if area < 0.002 * total:
                continue
            zones.append({"kind": "lesion", "bbox": [int(x), int(y), int(bw), int(bh)],
                          "paths": _polygons(lab == k), "area_pct": 100 * area / total, "score": float(area)})
        zones.sort(key=lambda z: -z["score"])
    if heat is not None:
        hot = (heat >= heat_threshold).astype(np.uint8)
        n, lab, stats, _ = cv2.connectedComponentsWithStats(hot, connectivity=8)
        att = []
        for k in range(1, n):
            x, y, bw, bh, area = stats[k]
            comp = lab == k
            if area < 0.003 * total:
                continue
            if mask is not None and (comp & mask).sum() > 0.3 * area:
                continue  # déjà couvert par le contour de lésion
            att.append({"kind": "attention", "bbox": [int(x), int(y), int(bw), int(bh)],
                        "paths": _polygons(comp), "area_pct": 100 * area / total,
                        "score": float(heat[comp].mean())})
        att.sort(key=lambda z: -z["score"])
        zones += att[:max_attention]
    return zones


# --------------------------------------------------------------------------
# Amélioration de l'AFFICHAGE (jamais utilisée pour l'analyse)
# --------------------------------------------------------------------------
def enhance_for_display(raw: Image.Image, target: int = 1024, sharp: bool = False) -> Image.Image:
    """Image d'AFFICHAGE agrandie proprement (Lanczos).

    sharp=False : vue « Originale », simple agrandissement fidèle.
    sharp=True  : vue « Netteté » : réduction du grain de l'échographie (speckle, filtre
                  non local), contraste local doux (CLAHE) et léger renforcement des bords.
    Ce n'est pas une « super-résolution » par IA : aucun détail n'est inventé. Le modèle
    analyse toujours l'image d'origine, jamais cette vue.
    """
    g = np.asarray(raw.convert("L"))
    if sharp:
        g = cv2.fastNlMeansDenoising(g, None, h=7, templateWindowSize=7, searchWindowSize=21)
        g = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8)).apply(g)
    scale = target / max(g.shape)
    if scale > 1:
        g = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
    if sharp:
        blur = cv2.GaussianBlur(g, (0, 0), 1.5)
        g = cv2.addWeighted(g, 1.4, blur, -0.4, 0)
    return Image.fromarray(g)


def heat_rgba(heat: np.ndarray) -> Image.Image:
    """Carte d'attention en calque transparent (rose → ambre), alpha = intensité."""
    h = np.clip(heat, 0, 1).astype(np.float32)
    lo, hi = np.array([168, 85, 247], np.float32), np.array([244, 114, 182], np.float32)
    rgb = lo + (hi - lo) * h[..., None]
    alpha = np.clip((h - 0.25) / 0.75, 0, 1) * 200
    return Image.fromarray(np.dstack([rgb, alpha]).astype(np.uint8), "RGBA")


def _hex(c: str) -> tuple[int, int, int]:
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def draw_contour(raw: Image.Image, mask: np.ndarray | None, level: str, width: int | None = None,
                 target: int = 1024) -> Image.Image:
    """Image agrandie + contour lissé, anticrénelé, avec halo lumineux (PDF, vignettes)."""
    base = enhance_for_display(raw, target)
    out = np.asarray(base.convert("RGB")).copy()
    if mask is None:
        return Image.fromarray(out)
    sx = base.width / raw.width
    big = cv2.resize(mask.astype(np.uint8), base.size, interpolation=cv2.INTER_NEAREST)
    cnts, _ = cv2.findContours(big, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cnts = [cv2.approxPolyDP(c, 1.5 * sx, True) for c in cnts]
    col = _hex(LEVELS[level]["color"])
    wd = width or max(2, round(base.width / 300))
    glow = np.zeros_like(out)
    cv2.drawContours(glow, cnts, -1, col, wd * 5, cv2.LINE_AA)
    glow = cv2.GaussianBlur(glow, (0, 0), wd * 2.5)
    out = np.clip(out.astype(np.int16) + glow.astype(np.int16) * 0.8, 0, 255).astype(np.uint8)
    cv2.drawContours(out, cnts, -1, col, wd, cv2.LINE_AA)
    return Image.fromarray(out)


def thumbnail(img: Image.Image, size: int = 220) -> Image.Image:
    t = img.convert("RGB").copy()
    t.thumbnail((size, size), Image.LANCZOS)
    return t
