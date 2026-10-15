"""Analyse d'une image : probabilités calibrées, niveau, contour, Grad-CAM."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFilter

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


class Analyzer:
    def __init__(self, models_dir: Path = MODELS_DIR):
        torch.set_num_threads(max(1, torch.get_num_threads()))
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
        mask = Image.fromarray((prob > 0.5).astype(np.uint8) * 255).resize(img.size, Image.NEAREST)
        return np.asarray(mask) > 127

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
        """Carte de chaleur (0-1) à la taille de l'image, pour la classe « maligne »."""
        from pytorch_grad_cam import GradCAM
        from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget

        layer = _last_conv(self.cls)
        x = torch.from_numpy(to_tensor_input(raw, CLS_SIZE))[None]
        with GradCAM(model=self.cls, target_layers=[layer]) as cam:
            heat = cam(input_tensor=x, targets=[ClassifierOutputTarget(MALIGNE)])[0]
        return np.asarray(Image.fromarray((heat * 255).astype(np.uint8)).resize(raw.size, Image.BILINEAR)) / 255.0


def _last_conv(model):
    last = None
    for m in model.modules():
        if isinstance(m, torch.nn.Conv2d):
            last = m
    return last


# --------------------------------------------------------------------------
# Rendus visuels
# --------------------------------------------------------------------------
def draw_contour(raw: Image.Image, mask: np.ndarray | None, level: str, width: int = 3) -> Image.Image:
    out = raw.convert("RGB")
    if mask is None:
        return out
    m = Image.fromarray(mask.astype(np.uint8) * 255)
    edge = np.asarray(m.filter(ImageFilter.FIND_EDGES)) > 0
    if width > 1:
        edge = np.asarray(Image.fromarray(edge.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(2 * (width // 2) + 1))) > 0
    arr = np.asarray(out).copy()
    color = tuple(int(LEVELS[level]["color"][i:i + 2], 16) for i in (1, 3, 5))
    arr[edge] = color
    return Image.fromarray(arr)


def heat_overlay(raw: Image.Image, heat: np.ndarray, alpha: float = 0.45) -> Image.Image:
    base = np.asarray(raw.convert("RGB"), dtype=np.float32)
    h = np.clip(heat, 0, 1)
    # palette simple bleu -> jaune -> rouge, sans dépendance supplémentaire
    color = np.stack([np.clip(2 * h, 0, 1), np.clip(2 - 2 * np.abs(2 * h - 1) - 0.6, 0, 1), np.clip(1 - 2 * h, 0, 1)], -1) * 255
    out = (1 - alpha * h[..., None]) * base + alpha * h[..., None] * color
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def thumbnail_with_badge(img: Image.Image, level: str, size: int = 160) -> Image.Image:
    t = img.convert("RGB").copy()
    t.thumbnail((size, size))
    d = ImageDraw.Draw(t)
    d.rectangle([0, 0, t.width - 1, t.height - 1], outline=LEVELS[level]["color"], width=5)
    return t
