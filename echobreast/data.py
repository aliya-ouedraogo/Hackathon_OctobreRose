"""Jeux de données PyTorch construits à partir de data/processed/splits.csv."""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

from .core import CLS_SIZE, MEAN, ROOT, SEG_SIZE, STD


def read_split(split: str, csv_path: Path = ROOT / "data" / "processed" / "splits.csv"):
    with open(csv_path, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["split"] == split]


def train_augment(size: int, with_mask: bool):
    """Augmentations réalistes, appliquées à l'entraînement uniquement."""
    import albumentations as A

    return A.Compose([
        A.Resize(size, size),
        A.HorizontalFlip(p=0.5),
        A.Affine(rotate=(-10, 10), scale=(0.95, 1.1), p=0.7),
        A.RandomBrightnessContrast(0.1, 0.1, p=0.5),
    ])


def _normalize(gray: np.ndarray) -> torch.Tensor:
    x = gray.astype(np.float32) / 255.0
    x = np.repeat(x[None], 3, axis=0)
    x = (x - MEAN[:, None, None]) / STD[:, None, None]
    return torch.from_numpy(x)


class BusiDataset(Dataset):
    def __init__(self, split: str, task: str = "cls", augment: bool = False):
        assert task in {"cls", "seg"}
        self.rows = read_split(split)
        if task == "seg":  # la segmentation n'apprend que sur les images avec lésion
            self.rows = [r for r in self.rows if int(r["label"]) != 0]
        self.task = task
        self.size = CLS_SIZE if task == "cls" else SEG_SIZE
        self.aug = train_augment(self.size, task == "seg") if augment else None

    def __len__(self):
        return len(self.rows)

    def labels(self):
        return [int(r["label"]) for r in self.rows]

    def __getitem__(self, i):
        r = self.rows[i]
        img = np.asarray(Image.open(ROOT / r["image"]).convert("L"))
        mask = np.asarray(Image.open(ROOT / r["mask"]).convert("L")) > 127
        mask = mask.astype(np.uint8)
        if self.aug is not None:
            out = self.aug(image=img, mask=mask)
            img, mask = out["image"], out["mask"]
        else:
            img = np.asarray(Image.fromarray(img).resize((self.size, self.size), Image.BILINEAR))
            mask = np.asarray(Image.fromarray(mask).resize((self.size, self.size), Image.NEAREST))
        x = _normalize(img)
        if self.task == "cls":
            return x, int(r["label"])
        return x, torch.from_numpy(mask[None].astype(np.float32))
