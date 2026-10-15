"""Briques communes : modèles, prétraitement, calibration, code couleur.

Utilisé à la fois par les scripts d'entraînement et par l'application,
pour garantir que l'image est traitée exactement de la même façon.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

CLASSES = ["normale", "bénigne", "maligne"]
FOLDERS = ["normal", "benign", "malignant"]  # noms des dossiers BUSI
MALIGNE = 2

CLS_SIZE = 224
SEG_SIZE = 256
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"


# --------------------------------------------------------------------------
# Prétraitement (F2)
# --------------------------------------------------------------------------
def load_gray(path_or_file) -> Image.Image:
    return Image.open(path_or_file).convert("L")


def to_tensor_input(img: Image.Image, size: int) -> np.ndarray:
    """Image niveaux de gris -> tableau (3, size, size) normalisé ImageNet."""
    arr = np.asarray(img.convert("L").resize((size, size), Image.BILINEAR), dtype=np.float32) / 255.0
    arr = np.repeat(arr[None], 3, axis=0)
    return (arr - MEAN[:, None, None]) / STD[:, None, None]


def quality_warnings(raw: Image.Image) -> list[str]:
    """Contrôles simples pour signaler une image manifestement inadaptée."""
    warnings = []
    w, h = raw.size
    if min(w, h) < 128:
        warnings.append(f"Image très petite ({w}×{h} px) : résultat peu fiable.")
    rgb = np.asarray(raw.convert("RGB"), dtype=np.float32)
    if np.abs(rgb[..., 0] - rgb[..., 1]).mean() + np.abs(rgb[..., 1] - rgb[..., 2]).mean() > 20:
        warnings.append("Image en couleur : une échographie est normalement en niveaux de gris.")
    mean = rgb.mean()
    if mean < 15:
        warnings.append("Image très sombre.")
    elif mean > 200:
        warnings.append("Image très claire : est-ce bien une échographie ?")
    return warnings


# --------------------------------------------------------------------------
# Modèles
# --------------------------------------------------------------------------
def build_classifier(arch: str = "efficientnet_b0", pretrained: bool = True):
    import timm

    return timm.create_model(arch, pretrained=pretrained, num_classes=len(CLASSES))


def build_segmenter(encoder: str = "resnet34", pretrained: bool = True):
    import segmentation_models_pytorch as smp

    return smp.Unet(
        encoder_name=encoder,
        encoder_weights="imagenet" if pretrained else None,
        in_channels=3,
        classes=1,
    )


# --------------------------------------------------------------------------
# Calibration, confiance et code couleur (F5, F7)
# --------------------------------------------------------------------------
def softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    z = logits / temperature
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


def confidence(probs: np.ndarray) -> float:
    """1 - entropie normalisée : 1 = certain, 0 = totalement indécis."""
    p = np.clip(probs, 1e-12, 1.0)
    return float(1.0 - (-(p * np.log(p)).sum()) / math.log(len(p)))


@dataclass
class Settings:
    """Réglages fixés sur le jeu de VALIDATION par scripts/evaluate.py."""

    temperature: float = 1.0
    t_orange: float = 0.10   # seuil de vigilance : p(maligne) au-delà de laquelle on relit (sensibilité ≥ 95 %)
    t_red: float = 0.50      # p(maligne) au-delà de laquelle c'est prioritaire
    min_confidence: float = 0.35
    cls_arch: str = "efficientnet_b0"
    seg_encoder: str = "resnet34"
    model_version: str = "non entraîné"
    extra: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path = MODELS_DIR / "settings.json") -> "Settings":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self, path: Path = MODELS_DIR / "settings.json") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.__dict__, indent=2, ensure_ascii=False), encoding="utf-8")


APP_NAME = "EchoBreast"
APP_TAGLINE = "Aide à la priorisation des échographies mammaires"

# Couleur = toujours doublée d'une icône et d'un libellé (accessibilité).
LEVELS = {
    "rouge": {"rank": 0, "icon": "octagon-alert", "label": "Prioritaire", "zone": "Zone suspecte", "color": "#C8264E",
              "soft": "#FCE7EC", "short": "Prioritaire",
              "text": "Le modèle trouve cette image très évocatrice d'un cancer : à relire en premier."},
    "orange": {"rank": 1, "icon": "triangle-alert", "label": "À relire", "zone": "Zone à vérifier", "color": "#D9822B",
               "soft": "#FCEFDF", "short": "À relire",
               "text": "Résultat incertain ou à surveiller : à relire rapidement."},
    "vert": {"rank": 2, "icon": "circle-check", "label": "Risque faible", "zone": "Lésion d'aspect bénin", "color": "#2F8F62",
             "soft": "#E2F3EA", "short": "Risque faible",
             "text": "Peu de signes inquiétants pour le modèle. Cela ne prouve pas l'absence de maladie."},
}


def fmt_pct(p: float) -> str:
    """Pourcentage lisible : « moins de 1 % » plutôt qu'un « 0 % » trompeur."""
    if p < 0.005:
        return "moins de 1 %"
    if p > 0.995:
        return "plus de 99 %"
    return f"{p:.0%}".replace("%", " %")


def risk_level(probs: np.ndarray, s: Settings) -> tuple[str, list[str]]:
    """Règle prudente : en cas de doute, on classe en orange."""
    reasons = []
    p_mal = float(probs[MALIGNE])
    conf = confidence(probs)
    if p_mal >= s.t_red:
        return "rouge", [f"Le modèle estime à {fmt_pct(p_mal)} la probabilité d'une lésion maligne. "
                         f"C'est au-dessus de {s.t_red:.0%}, le niveau à partir duquel l'examen passe en priorité."]
    if p_mal >= s.t_orange:
        reasons.append(f"Le modèle estime à {fmt_pct(p_mal)} la probabilité d'une lésion maligne. C'est au-dessus de "
                       f"{s.t_orange:.0%}, le seuil de vigilance choisi pour ne laisser passer presque aucun cancer.")
    if conf < s.min_confidence:
        reasons.append("Le modèle hésite entre plusieurs réponses : son résultat est peu sûr, "
                       "une relecture est conseillée.")
    if reasons:
        return "orange", reasons
    return "vert", [f"Le modèle estime à {fmt_pct(p_mal)} la probabilité d'une lésion maligne, "
                    f"en dessous du seuil de vigilance ({s.t_orange:.0%})."
                    + (" La lésion repérée a plutôt l'aspect d'une lésion bénigne (non cancéreuse) pour le modèle."
                       if int(probs.argmax()) == 1 else "")]


def priority_key(level: str, probs: np.ndarray) -> tuple:
    """Tri de la liste de priorité : couleur d'abord, puis p(maligne) décroissante."""
    return (LEVELS[level]["rank"], -float(probs[MALIGNE]))
