"""Design system EchoBreast : styles, icônes vectorielles et composants HTML."""
from __future__ import annotations

import base64
import html
from functools import lru_cache
from pathlib import Path

import streamlit as st

from echobreast.core import APP_NAME, CLASSES, LEVELS

WINE = "#8E1D4A"
INK = "#2A1F2C"
MUTED = "#6F6271"
CLASS_COLORS = {"normale": "#2F8F62", "bénigne": "#A08BC0", "maligne": "#8E1D4A"}
STATIC = Path(__file__).resolve().parent / "static"

# Icônes au trait (style Lucide, licence ISC), 24×24.
ICONS = {
    "circle-check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "triangle-alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "octagon-alert": '<polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "shield-alert": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "lock": '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "image-up": '<path d="M10.3 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10l-3.1-3.1a2 2 0 0 0-2.814.014L6 21"/><path d="m14 19.5 3-3 3 3"/><path d="M17 22v-5.5"/><circle cx="9" cy="9" r="2"/>',
    "ban": '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>',
    "scale": '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "ruler": '<path d="M21.3 15.3a2.4 2.4 0 0 1 0 3.4l-2.6 2.6a2.4 2.4 0 0 1-3.4 0L2.7 8.7a2.41 2.41 0 0 1 0-3.4l2.6-2.6a2.41 2.41 0 0 1 3.4 0Z"/><path d="m14.5 12.5 2-2"/><path d="m11.5 9.5 2-2"/><path d="m8.5 6.5 2-2"/><path d="m17.5 15.5 2-2"/>',
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
}


def icon(name: str, size: int = 18, color: str = "currentColor", stroke: float = 2) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


@lru_cache
def ribbon_uri() -> str:
    return "data:image/png;base64," + base64.b64encode((STATIC / "ribbon.png").read_bytes()).decode()


CSS = """
<style>
:root{ --wine:#8E1D4A; --wine-2:#A62A5C; --bg:#FBF4F8; --lav:#F4EAF5; --lav-2:#EADCF0; --line:#EFE1EA;
       --ink:#2A1F2C; --muted:#6F6271; --radius:16px; --shadow:0 1px 2px rgba(80,20,50,.05),0 10px 30px -18px rgba(110,25,70,.35);
       --serif:'Newsreader',Georgia,'Times New Roman',serif; --mono:'IBM Plex Mono',ui-monospace,Menlo,monospace; }
h1,h2,h3,.eb-serif{ font-family:var(--serif) !important; font-weight:500 !important; letter-spacing:-.01em; color:var(--ink); }
h4{ color:var(--ink); }
.block-container{ padding-top:1.1rem; padding-bottom:3rem; max-width:1320px; }
[data-testid="stAppViewContainer"]{ background:var(--bg); }
[data-testid="stHeader"]{ background:transparent; height:2.6rem; }
[data-testid="stSidebar"]{ background:#FFFFFF; border-right:1px solid var(--line); }
[data-testid="stSidebar"] [data-testid="stPageLink"] a{ border-radius:12px; padding:.5rem .75rem; }
[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover{ background:var(--lav); }
[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"],
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"]{ background:var(--lav); }
[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] p,
[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] span{ color:var(--wine) !important; font-weight:600; }

/* Boutons */
.stButton>button, .stDownloadButton>button, [data-testid="stPopover"] button{ border-radius:12px; font-weight:600; min-height:44px;
  border:1px solid var(--line); background:#fff; transition:background .15s, box-shadow .2s, transform .15s; }
.stButton>button[kind="primary"], .stDownloadButton>button[kind="primary"]{ background:var(--wine); border-color:var(--wine); color:#fff;
  box-shadow:0 10px 24px -12px rgba(142,29,74,.8); }
.stButton>button[kind="primary"]:hover, .stDownloadButton>button[kind="primary"]:hover{ background:var(--wine-2); transform:translateY(-1px); }
.stButton>button[kind="secondary"]:hover{ background:var(--lav); border-color:var(--lav-2); color:var(--wine); }
.stButton>button[kind="tertiary"]{ color:var(--wine); font-weight:600; }
[data-testid="stFileUploaderDropzone"]{ border:1px dashed #D9BFD0; background:#fff; border-radius:var(--radius); }
[data-testid="stExpander"], [data-testid="stVerticalBlockBorderWrapper"]{ border-radius:var(--radius); }
div[data-baseweb="select"]>div, [data-testid="stTextInput"] input{ border-radius:12px; background:#fff; }
[data-testid="stSegmentedControl"] button{ min-height:40px; }

/* Barre du haut */
.eb-top{ display:flex; align-items:center; justify-content:space-between; gap:.8rem; flex-wrap:wrap; padding:.2rem 0 .9rem;
  border-bottom:1px solid var(--line); margin-bottom:1.1rem; }
.eb-crumb{ color:var(--muted); font-size:.92rem; } .eb-crumb b{ color:var(--ink); font-weight:600; }
.eb-top-r{ display:flex; gap:.5rem; align-items:center; flex-wrap:wrap; }
.eb-pill-info{ display:inline-flex; gap:.4rem; align-items:center; border:1px solid #E9C9D6; background:#fff; color:var(--wine);
  border-radius:10px; padding:.28rem .7rem; font-size:.85rem; }
.eb-tag{ font-family:var(--mono); font-size:.8rem; background:var(--lav-2); color:#5B2A6E; border-radius:8px; padding:.22rem .55rem; }
.eb-tag.warn{ background:#FCEFDF; color:#8A4B12; }

/* En-têtes de page */
.eb-eyebrow{ color:var(--wine); font-weight:600; font-size:.74rem; letter-spacing:.12em; text-transform:uppercase; display:flex; gap:.45rem; align-items:center; }
.eb-eyebrow::before{ content:""; width:6px; height:6px; border-radius:50%; background:var(--wine); }
.eb-title{ font-family:var(--serif); font-size:clamp(1.8rem,3vw,2.35rem); font-weight:500; color:var(--ink); margin:.25rem 0 .3rem; line-height:1.1; }
.eb-sub{ color:var(--muted); font-size:1rem; max-width:720px; margin-bottom:1rem; }

/* Cartes */
.eb-card{ background:#fff; border:1px solid var(--line); border-radius:var(--radius); padding:1.15rem 1.25rem; box-shadow:var(--shadow); }
.eb-card + .eb-card{ margin-top:.8rem; }
.eb-card h3{ font-size:1.25rem; margin:0 0 .35rem; display:flex; gap:.5rem; align-items:center; }
.eb-label{ font-size:.72rem; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); font-weight:600; }
.eb-mono{ font-family:var(--mono); }
.eb-row{ display:flex; justify-content:space-between; align-items:center; gap:.6rem; }

/* Badge de niveau (pastille lumineuse) */
.eb-badge{ --c:#999; display:inline-flex; align-items:center; gap:.45rem; padding:.28rem .75rem .28rem .6rem; border-radius:999px;
  font-weight:600; font-size:.88rem; color:var(--c); background:var(--soft); white-space:nowrap;
  box-shadow:0 0 0 1px color-mix(in srgb,var(--c) 22%,transparent), 0 6px 18px -8px color-mix(in srgb,var(--c) 70%,transparent); }
.eb-badge .dot{ width:8px; height:8px; border-radius:50%; background:var(--c); }
.eb-badge svg{ margin-left:-.1rem; }
.eb-badge.sm{ font-size:.8rem; padding:.2rem .6rem .2rem .5rem; }

/* Légende et guide */
.st-key-legend_box{ background:#fff; box-shadow:var(--shadow); margin-bottom:.6rem; }
[class*='st-key-decision_box']{ background:#fff; box-shadow:var(--shadow); margin-top:.8rem; }
.st-key-guide_btn{ display:flex; justify-content:flex-end; }
.st-key-guide_btn button{ min-height:38px; padding:.35rem 1rem; }
.eb-legend{ background:#fff; border:1px solid var(--line); border-radius:var(--radius); padding:.8rem 1rem; box-shadow:var(--shadow); }
.eb-leg{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:.5rem 1.2rem; }
.eb-leg2{ margin-top:.6rem; padding-top:.6rem; border-top:1px dashed var(--line); }
.eb-leg-i{ display:flex; gap:.6rem; align-items:center; font-size:.88rem; color:var(--ink); }
.eb-leg-i{ align-items:flex-start; } .eb-leg-i .eb-badge{ flex:none; min-width:7.2rem; } .eb-leg-i svg{ margin-top:5px; }
.eb-leg-i svg{ flex:none; width:34px; }
.eb-guide{ display:flex; gap:.6rem; align-items:flex-start; background:#FAF5FA; border-radius:12px; padding:.7rem .8rem; margin-top:.8rem;
  font-size:.86rem; color:#4A3F4C; line-height:1.5; }
.eb-guide svg{ flex:none; margin-top:2px; } .eb-guide b{ display:block; color:var(--ink); margin-bottom:.15rem; }

/* Carte de triage */
.eb-big{ font-family:var(--serif); font-size:3.3rem; line-height:1; color:var(--ink); }
.eb-big small{ font-family:inherit; font-size:.9rem; color:var(--muted); margin-left:.5rem; font-family:'Inter',sans-serif; }
.eb-thr{ position:relative; margin:1.6rem 0 .35rem; height:10px; border-radius:99px; background:var(--lav); }
.eb-thr .fill{ position:absolute; left:0; top:0; bottom:0; border-radius:99px; background:linear-gradient(90deg,#C25A85,var(--wine)); box-shadow:0 0 12px rgba(142,29,74,.35); }
.eb-thr .mk{ position:absolute; top:-6px; bottom:-6px; width:2px; background:var(--ink); border-radius:2px; }
.eb-thr .mk span{ position:absolute; bottom:calc(100% + 2px); left:50%; transform:translateX(-50%); font-family:var(--mono); font-size:.68rem; color:var(--wine); font-weight:600; white-space:nowrap; }
.eb-scale{ display:flex; justify-content:space-between; font-family:var(--mono); font-size:.72rem; color:var(--muted); }
.eb-alert{ display:flex; gap:.55rem; align-items:center; background:var(--soft); color:var(--c); border-radius:12px; padding:.6rem .8rem; margin-top:.9rem; font-weight:600; }
.eb-crit{ display:flex; gap:.6rem; align-items:flex-start; background:#FAF5FA; border-radius:12px; padding:.55rem .75rem; margin-top:.45rem; font-size:.92rem; color:var(--ink); }
.eb-crit svg{ flex:none; margin-top:2px; }

/* Probabilités */
.eb-prob{ margin:.55rem 0; }
.eb-prob .eb-row{ font-size:.95rem; }
.eb-prob b{ font-family:var(--mono); font-weight:600; }
.eb-track{ height:6px; border-radius:99px; background:var(--lav); overflow:hidden; margin-top:.3rem; }
.eb-track>div{ height:100%; border-radius:99px; }
.eb-seg{ display:grid; grid-template-columns:repeat(3,1fr); gap:.35rem; margin:.5rem 0 .4rem; }
.eb-seg span{ text-align:center; padding:.42rem 0; border-radius:10px; font-size:.86rem; color:var(--muted); background:#FAF5FA; }
.eb-seg span.on{ background:var(--c); color:#fff; font-weight:600; box-shadow:0 6px 16px -8px var(--c); }

/* Tuiles de fiabilité */
.eb-stat{ background:#fff; border:1px solid var(--line); border-radius:var(--radius); padding:1rem 1.1rem; box-shadow:var(--shadow); height:100%; }
.eb-stat .v{ font-family:var(--mono); font-size:1.9rem; font-weight:600; color:var(--ink); margin:.35rem 0 .15rem; }
.eb-stat .ci{ font-family:var(--mono); font-size:.76rem; color:var(--muted); }
.eb-stat p{ color:var(--muted); font-size:.86rem; margin:.6rem 0 0; }
.eb-mx{ display:grid; grid-template-columns:auto 1fr 1fr auto; gap:.4rem; align-items:center; background:#FAF5FA; border-radius:14px; padding:.8rem; font-size:.88rem; }
.eb-mx .h{ color:var(--muted); font-size:.8rem; text-align:center; }
.eb-mx .c{ border-radius:10px; text-align:center; padding:.55rem .3rem; font-family:var(--mono); font-weight:600; font-size:1.15rem; }
.eb-mx .c small{ display:block; font-family:'Inter',sans-serif; font-weight:400; font-size:.68rem; opacity:.85; }
.eb-mini{ background:#FAF5FA; border-radius:14px; padding:.9rem 1rem; height:100%; }
.eb-mini h5{ margin:0 0 .35rem; font-size:.95rem; color:var(--wine); display:flex; gap:.4rem; align-items:center; }
.eb-mini p{ margin:0; color:var(--muted); font-size:.86rem; line-height:1.5; }
.eb-ban li{ list-style:none; display:flex; gap:.55rem; margin:.45rem 0; font-size:.92rem; }
.eb-ban{ padding:0; margin:.4rem 0 0; }

/* File de priorité */
.eb-q{ display:grid; grid-template-columns:2.4rem 76px minmax(0,1fr); gap:.9rem; align-items:center; }
.eb-q .info{ min-width:0; }
.eb-q .line{ display:flex; flex-wrap:wrap; align-items:center; gap:.4rem .8rem; margin-top:.5rem; }
.eb-q .risk{ display:inline-flex; align-items:center; gap:.5rem; }
.eb-q .risk b{ font-family:var(--mono); font-size:.95rem; min-width:2.8rem; }
.eb-q .risk .eb-track{ display:block; width:90px; margin:0; }
.eb-q .risk .eb-track>span{ display:block; height:100%; border-radius:99px; }
.eb-q .eb-chip{ white-space:nowrap; }
.eb-q .rk{ font-family:var(--mono); color:var(--muted); font-size:.95rem; }
.eb-q .rk.top{ color:var(--wine); font-weight:600; }
.eb-q img{ width:76px; height:56px; object-fit:cover; border-radius:8px; border:1.5px solid var(--c); }
.eb-q .ref{ font-family:var(--mono); font-size:.86rem; color:var(--ink); font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.eb-q .meta{ color:var(--muted); font-size:.8rem; }
.eb-chip{ display:inline-block; font-size:.78rem; padding:.18rem .55rem; border-radius:8px; background:var(--lav); color:#5B2A6E; }
.eb-chip.faible{ background:#FCEFDF; color:#8A4B12; } .eb-chip.elevee{ background:#E2F3EA; color:#1F6B47; }
.eb-done{ opacity:.55; }
.eb-qhead{ display:grid; grid-template-columns:2.4rem 76px minmax(0,1fr); gap:.9rem;
  font-size:.72rem; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); font-weight:600; padding:0 1rem .2rem; }

/* Barre latérale */
.eb-brand{ display:flex; gap:.7rem; align-items:center; padding:.2rem .2rem 1.1rem; }
.eb-brand img{ height:44px; filter:drop-shadow(0 4px 8px rgba(214,51,132,.25)); }
.eb-brand b{ font-family:var(--serif); font-weight:500; font-size:1.45rem; color:var(--wine); display:block; line-height:1.05; letter-spacing:-.01em; }
.eb-brand span{ color:var(--muted); font-size:.8rem; }
.eb-foot{ background:var(--lav); border-radius:14px; padding:.75rem .85rem; font-size:.82rem; color:var(--muted); line-height:1.45; margin-top:1.2rem; }

[data-testid="stHeaderActionElements"]{ display:none !important; }
@media (max-width: 640px){
  .block-container{ padding-left:1rem; padding-right:1rem; }
  .eb-qhead{ display:none; }
  .eb-q, .eb-qhead{ grid-template-columns:1.8rem 56px minmax(0,1fr); }
  .eb-q img{ width:56px; height:44px; }
  .eb-big{ font-size:2.6rem; }
  .eb-mx{ grid-template-columns:auto 1fr 1fr; } .eb-mx .tot{ display:none; }
}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def brand():
    st.markdown(f"<div class='eb-brand'><img src='{ribbon_uri()}' alt='Ruban rose'>"
                f"<div><b>{APP_NAME}</b><span>Aide à la priorisation</span></div></div>", unsafe_allow_html=True)


def topbar(page: str, version: str, synthetic: bool):
    tag = ("<span class='eb-tag warn'>Modèle de test · synthétique</span>" if synthetic
           else f"<span class='eb-tag'>Modèle {html.escape(version)}</span>")
    st.markdown(f"<div class='eb-top'><div class='eb-crumb'>{APP_NAME} / <b>{page}</b></div><div class='eb-top-r'>"
                f"<span class='eb-pill-info'>{icon('info', 15)} Aide à la lecture, pas un diagnostic</span>{tag}</div></div>",
                unsafe_allow_html=True)


def header(eyebrow: str, title: str, sub: str = ""):
    st.markdown(f"<div class='eb-eyebrow'>{eyebrow}</div><div class='eb-title'>{title}</div>"
                + (f"<div class='eb-sub'>{sub}</div>" if sub else ""), unsafe_allow_html=True)


def badge(level: str, size: str = "") -> str:
    lv = LEVELS[level]
    return (f"<span class='eb-badge {size}' style='--c:{lv['color']};--soft:{lv['soft']}' role='status'>"
            f"<span class='dot'></span>{lv['label']}</span>")


def pct(p: float, sep: str = " ") -> str:
    """Pourcentage court : « <1 % » et « >99 % » plutôt que 0 % ou 100 %."""
    if p < 0.005:
        return f"&lt;1{sep}%"
    if p > 0.995:
        return f"&gt;99{sep}%"
    return f"{p * 100:.0f}{sep}%"


def legend():
    """Légende permanente : signification des couleurs et des contours."""
    items = "".join(
        f"<div class='eb-leg-i'>{badge(k, 'sm')}<span>{t}</span></div>"
        for k, t in (("rouge", "très évocateur d'un cancer : à relire en premier"),
                     ("orange", "incertain ou à surveiller : à relire rapidement"),
                     ("vert", "peu de signes inquiétants, ce n'est pas un « normal » garanti")))
    lines = ("<div class='eb-leg-i'><svg width='34' height='12'><path d='M2 6h30' stroke='#8E1D4A' stroke-width='3' "
             "stroke-linecap='round'/></svg><span><b>Trait plein</b> : contour de la lésion repérée</span></div>"
             "<div class='eb-leg-i'><svg width='34' height='12'><path d='M2 6h30' stroke='#F472B6' stroke-width='2.5' "
             "stroke-dasharray='6 4' stroke-linecap='round'/></svg><span><b>Pointillés</b> : zone qui a beaucoup pesé "
             "dans le calcul de l'IA, à vérifier</span></div>"
             "<div class='eb-leg-i'><svg width='34' height='12'><rect width='34' height='12' rx='3' fill='#2A1F2C'/><path d='M4 6h26' stroke='#FFFFFF' stroke-width='6' "
             "stroke-linecap='round'/><path d='M4 6h26' stroke='#D9822B' stroke-width='2.5' stroke-linecap='round'/></svg>"
             "<span><b>Bordé de blanc, « Soignant »</b> : zone ajoutée par le professionnel</span></div>")
    st.markdown(f"<div class='eb-leg'>{items}</div><div class='eb-leg eb-leg2'>{lines}</div>", unsafe_allow_html=True)


def triage_card(res, settings):
    lv = LEVELS[res.level]
    p = res.p_malignant
    mk = "".join(f"<div class='mk' style='left:{min(99.5, t * 100):.1f}%'><span>{t:.0%}</span></div>"
                 for t in (settings.t_orange, settings.t_red))
    headline = {"rouge": "À relire en premier", "orange": "À relire rapidement",
                "vert": "Peu de signes inquiétants"}[res.level]
    crit = []
    for r in res.reasons:
        ic = ("shield-alert", "#D9822B") if "hésite" in r else ("triangle-alert", lv["color"])
        crit.append(f"<div class='eb-crit'>{icon(ic[0], 17, ic[1])}<span>{html.escape(r)}</span></div>")
    st.markdown(f"""<div class='eb-card'>
<div class='eb-row'><span class='eb-label'>Résultat de l'IA</span>{badge(res.level)}</div>
<div style='margin-top:.7rem' class='eb-big'>{pct(p, '&thinsp;')}<small>risque estimé de cancer</small></div>
<div class='eb-thr' aria-label='Risque estimé {p:.0%}, seuil de vigilance {settings.t_orange:.0%}, seuil prioritaire {settings.t_red:.0%}'>
<div class='fill' style='width:{p * 100:.1f}%'></div>{mk}</div>
<div class='eb-scale'><span>0 %</span><span>100 %</span></div>
<div style='font-size:.84rem;color:var(--muted);margin-top:.3rem;line-height:1.5'>Au-delà de <b style='color:var(--wine)'>{settings.t_orange:.0%}</b> (seuil de vigilance) l'examen passe en orange,
au-delà de <b style='color:var(--wine)'>{settings.t_red:.0%}</b> (seuil prioritaire) en rouge.</div>
<div class='eb-alert' style='--c:{lv['color']};--soft:{lv['soft']}'>{icon(lv['icon'], 18, lv['color'])}{headline}</div>
<div class='eb-label' style='margin-top:1.1rem'>Pourquoi cette couleur ?</div>{''.join(crit)}
</div>""", unsafe_allow_html=True)


CLASS_HELP = {"normale": "aucune lésion visible", "bénigne": "lésion non cancéreuse", "maligne": "lésion évocatrice de cancer"}


def probs_card(res):
    rows = "".join(
        f"<div class='eb-prob'><div class='eb-row'><span><span style='color:{CLASS_COLORS[c] if c == 'maligne' else INK}'>{c.capitalize()}</span>"
        f" <span style='color:var(--muted);font-size:.82rem'>· {CLASS_HELP[c]}</span></span>"
        f"<b>{pct(p)}</b></div><div class='eb-track'><div style='width:{p * 100:.1f}%;background:{CLASS_COLORS[c]}'></div></div></div>"
        for c, p in zip(CLASSES, res.probs))
    st.markdown(f"""<div class='eb-card'>
<div class='eb-label'>Ce que le modèle voit dans l'image</div>{rows}
<div class='eb-guide'>{icon('info', 16, WINE)}<div><b>Comment lire ces pourcentages ?</b>
Les trois chiffres se partagent 100 %. Ils disent à quoi l'image ressemble le plus pour le modèle.
Par exemple, « maligne 30 % » veut dire que, lors des tests, sur 100 images ayant ce score,
environ 30 étaient réellement des cancers. C'est une estimation, pas une certitude.</div></div></div>""", unsafe_allow_html=True)


def stat(label: str, value: str, ci: list | None, desc: str, tag: str = "") -> str:
    ci_txt = f"Fourchette probable : {ci[0] * 100:.0f} à {ci[1] * 100:.0f} %" if ci else "&nbsp;"
    return (f"<div class='eb-stat'><div class='eb-row'><span style='font-size:.88rem'>{label}</span>{tag}</div>"
            f"<div class='v'>{value}</div><div class='ci'>{ci_txt}</div><p>{desc}</p></div>")
