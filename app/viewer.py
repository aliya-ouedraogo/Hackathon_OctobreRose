"""Visionneuse d'échographie (composant Streamlit) : zoom, loupe, avant / après IA, Netteté, zones,
et annotations du professionnel renvoyées à l'application."""
from __future__ import annotations

import base64
import io
from pathlib import Path

import streamlit.components.v1 as components
from PIL import Image


def data_uri(img: Image.Image, fmt: str = "PNG", quality: int = 92) -> str:
    buf = io.BytesIO()
    if fmt == "JPEG":
        img.convert("RGB").save(buf, format="JPEG", quality=quality)
    else:
        img.save(buf, format="PNG", optimize=True)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()


_COMPONENT = components.declare_component("eb_viewer", path=str(Path(__file__).resolve().parent / "viewer_component"))


def render_viewer(base: Image.Image, sharp: Image.Image, heat: Image.Image | None, zones: list[dict],
                  natural_size: tuple[int, int], level: str, img_key: str, saved: list[dict] | None = None,
                  stage_height: int = 600):
    """Affiche la visionneuse. Renvoie la dernière valeur envoyée par le professionnel :
    {"img_key", "annotations": [{"level", "points"}], "ts"} quand il enregistre ses annotations, sinon None."""
    from echobreast.core import LEVELS

    w, h = natural_size
    return _COMPONENT(base=data_uri(base, "JPEG"), sharp=data_uri(sharp, "JPEG"),
                      heat=data_uri(heat) if heat is not None else "", zones=zones, w=w, h=h, level=level,
                      color=LEVELS[level]["color"], lesion=LEVELS[level]["zone"], img_key=img_key,
                      saved=saved or [], stage_h=stage_height, key=f"viewer_{img_key}", default=None)
