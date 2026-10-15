"""EchoBreast — application Streamlit.

Lancer :  streamlit run app/app.py
"""
from __future__ import annotations

import hashlib
import html
import io
import json
import sys
from pathlib import Path

import streamlit as st
from PIL import Image

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(APP_DIR))
from echobreast.core import APP_NAME, APP_TAGLINE, LEVELS, MODELS_DIR, priority_key  # noqa: E402
import ui  # noqa: E402

DEMO_DIR = APP_DIR / "demo"
STATIC = APP_DIR / "static"

st.set_page_config(page_title=f"{APP_NAME} · {APP_TAGLINE}", page_icon=str(STATIC / "ribbon.png"),
                   layout="wide", initial_sidebar_state="auto")


# --------------------------------------------------------------------------
# Données et calculs (mis en cache par image)
# --------------------------------------------------------------------------
@st.cache_resource(show_spinner="Chargement des modèles…")
def get_analyzer():
    from echobreast.inference import Analyzer

    return Analyzer() if Analyzer.available() else None


def _cache() -> dict:
    return st.session_state.setdefault("cache", {})


def analyze_bytes(data: bytes):
    key = hashlib.sha1(data).hexdigest()
    c = _cache()
    if key not in c:
        raw = Image.open(io.BytesIO(data))
        raw.load()
        c[key] = {"raw": raw, "res": get_analyzer().analyze(raw), "size": len(data)}
    return key, c[key]


def viewer_assets(key: str):
    """Vues d'affichage (originale, Netteté), carte d'attention et zones — calculées une seule fois."""
    from echobreast.inference import enhance_for_display, find_zones, heat_rgba

    entry = _cache()[key]
    if "zones" not in entry:
        raw, res = entry["raw"], entry["res"]
        heat = get_analyzer().gradcam(raw)
        entry["heat"] = heat_rgba(heat)
        entry["base"] = enhance_for_display(raw, 1024)
        entry["sharp"] = enhance_for_display(raw, 1024, sharp=True)
        entry["zones"] = find_zones(res.mask, heat if res.level != "vert" else None, (raw.height, raw.width))
    return entry


def demo_cases() -> list[dict]:
    f = DEMO_DIR / "demo.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def load_metrics() -> dict | None:
    f = MODELS_DIR / "metrics.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def top(page: str):
    an = get_analyzer()
    version = an.settings.model_version if an else "absent"
    ui.topbar(page, version, "SYNTH" in version.upper())


def need_models() -> bool:
    if get_analyzer() is None:
        st.markdown(f"<div class='eb-card'><h3>{ui.icon('info', 18, ui.WINE)} Modèles introuvables</h3>"
                    "Entraînez les modèles (voir le README), placez-les dans <code>models/</code> puis relancez.</div>",
                    unsafe_allow_html=True)
        return True
    return False


def meta(entry: dict, demo: bool) -> str:
    raw = entry["raw"]
    return f"{raw.width}×{raw.height} px · {entry['size'] / 1024:.0f} Ko · {'cas de démonstration' if demo else 'importé'}"


# --------------------------------------------------------------------------
# Page : Analyser
# --------------------------------------------------------------------------
def page_analyse():
    top("Analyser")
    h, ctl = st.columns([1.25, 1], vertical_alignment="bottom")
    with h:
        ui.header("Lecture assistée", "Analyser une échographie",
                  "Estimation du niveau de priorité et repérage des zones à inspecter. La décision reste au professionnel.")
    if need_models():
        return
    an = get_analyzer()
    cases = demo_cases()
    labels = [c["file"] for c in cases]
    opened = st.session_state.pop("open_case", None)
    data, name, truth = None, None, None
    with ctl:
        src = st.segmented_control("Source", ["Cas de démo", "Importer"], default="Cas de démo" if cases else "Importer",
                                   key="src", label_visibility="collapsed")
        if opened:
            name, data = opened["name"], opened["data"]
            truth = next((c for c in cases if c["file"] == name), None)
            st.caption(f"Ouvert depuis la file de priorité : **{name}**")
        elif src == "Cas de démo" and cases:
            pick = st.selectbox("Cas de démonstration", labels, key="demo_pick", label_visibility="collapsed",
                                format_func=lambda f: f"Cas {labels.index(f) + 1:02d} · {f}")
            truth = cases[labels.index(pick)]
            data, name = (DEMO_DIR / pick).read_bytes(), pick
        elif src == "Importer":
            up = st.file_uploader("Échographie (PNG ou JPG)", type=["png", "jpg", "jpeg"], label_visibility="collapsed")
            if up:
                data, name = up.getvalue(), up.name

    if data is None:
        st.markdown(f"<div class='eb-card' style='text-align:center;padding:3rem'>{ui.icon('image-up', 40, ui.WINE, 1.5)}"
                    "<h3 style='justify-content:center;margin-top:.8rem'>Déposez une échographie mammaire</h3>"
                    "<span style='color:var(--muted)'>PNG ou JPG · traitée localement, jamais conservée</span></div>",
                    unsafe_allow_html=True)
        return
    try:
        key, entry = analyze_bytes(data)
    except Exception:
        st.error("Fichier illisible : merci de fournir une image PNG ou JPG valide.")
        return
    raw, res = entry["raw"], entry["res"]
    st.markdown(f"<div class='eb-mono' style='color:var(--muted);font-size:.8rem;margin:-.2rem 0 .7rem'>"
                f"{html.escape(name)} · {meta(entry, truth is not None)}</div>", unsafe_allow_html=True)
    for w in res.warnings:
        st.warning(w, icon=":material/warning:")

    left, right = st.columns([1.7, 1], gap="medium")
    with left:
        with st.spinner("Préparation de la visionneuse…"):
            assets = viewer_assets(key)
        from viewer import render_viewer

        render_viewer(assets["base"], assets["sharp"], assets["heat"], assets["zones"], raw.size,
                      LEVELS[res.level]["color"], height=760)
    with right:
        ui.triage_card(res, an.settings)
        ui.probs_card(res, an.settings)
        from echobreast.inference import draw_contour
        from echobreast.report import build_pdf

        st.write("")
        st.download_button("Télécharger la fiche PDF", build_pdf(draw_contour(raw, res.mask, res.level), res,
                                                                  an.settings.model_version, name),
                           file_name=f"echobreast_{Path(name).stem}.pdf", mime="application/pdf", type="primary",
                           icon=":material/download:", use_container_width=True)
        if truth:
            with st.popover("Voir la vérité terrain (démo)", icon=":material/fact_check:", use_container_width=True):
                st.markdown(f"Étiquette du jeu BUSI : **{truth['verite']}**")
                if truth.get("erreur_du_modele"):
                    st.markdown("Ce cas est montré **volontairement** : le modèle s'y trompe. "
                                "C'est pour cela que la décision reste au professionnel.")
        with st.popover("Comment lire ce résultat ?", icon=":material/help:", use_container_width=True):
            st.markdown(f"""
- **Probabilité de malignité** : sortie calibrée du modèle, pas un diagnostic.
- **Rouge** si elle dépasse {an.settings.t_red:.0%} ; **orange** au-delà du seuil de prudence ({an.settings.t_orange:.0%}),
  fixé pour viser au moins 95 % des cas malins signalés, ou si la confiance est faible ; **vert** sinon.
- **Zone suspecte** : contour proposé par le modèle de segmentation.
- **Zone d'attention** : région qui a pesé dans la décision, hors contour, à vérifier à l'œil.
- **Netteté / Comparer** : amélioration **visuelle uniquement** ; l'analyse porte toujours sur l'image originale.""")


# --------------------------------------------------------------------------
# Page : File de priorité
# --------------------------------------------------------------------------
FILTERS = {"Tous": None, "Prioritaire": "rouge", "À relire": "orange", "Risque faible": "vert", "Relus": "relu"}


def page_priorite():
    top("File de priorité")
    ui.header("Tri de la file", "File de priorité",
              "Examens classés du plus au moins urgent à relire, selon le niveau puis la probabilité de malignité.")
    if need_models():
        return
    an = get_analyzer()
    reviewed: set = st.session_state.setdefault("reviewed", set())

    with st.container(border=True):
        a, b, c = st.columns([2.2, 1.2, 1], vertical_alignment="center")
        ups = a.file_uploader("Déposez des échographies", type=["png", "jpg", "jpeg"], accept_multiple_files=True,
                              label_visibility="collapsed")
        use_demo = b.toggle("Inclure les cas de démonstration", value=bool(demo_cases()))
    demo_names = {d["file"] for d in demo_cases()}
    items = [(u.name, u.getvalue()) for u in ups or []]
    if use_demo:
        items += [(d["file"], (DEMO_DIR / d["file"]).read_bytes()) for d in demo_cases()]
    if not items:
        st.info("Déposez des échographies ou incluez les cas de démonstration.")
        return

    from echobreast.inference import draw_contour, find_zones, thumbnail
    from viewer import data_uri

    rows = []
    with st.spinner(f"Analyse de {len(items)} examen(s)…"):
        for n, data in items:
            key, entry = analyze_bytes(data)
            res = entry["res"]
            if "thumb" not in entry:
                entry["preview"] = draw_contour(entry["raw"], res.mask, res.level, target=640)
                entry["thumb"] = data_uri(thumbnail(entry["preview"], 160), "JPEG")
            rows.append({"key": key, "sort": priority_key(res.level, res.probs), "name": n, "data": data, "res": res,
                         "entry": entry, "demo": n in demo_names, "relu": key in reviewed})
    rows.sort(key=lambda r: (r["relu"], r["sort"]))

    with c:
        from echobreast.report import build_queue_pdf

        st.download_button("Exporter la file (PDF)", build_queue_pdf(
            [{"name": r["name"], "level": r["res"].level, "p": r["res"].p_malignant, "conf": r["res"].confidence,
              "relu": r["relu"]} for r in rows], an.settings.model_version),
            file_name="echobreast_file_priorite.pdf", mime="application/pdf", icon=":material/ios_share:",
            use_container_width=True)

    counts = {k: (len(rows) if v is None else sum(r["relu"] for r in rows) if v == "relu"
                  else sum(r["res"].level == v and not r["relu"] for r in rows)) for k, v in FILTERS.items()}
    f1, f2 = st.columns([1.6, 1], vertical_alignment="center")
    flt = f1.segmented_control("Filtre", list(FILTERS), default="Tous", key="qfilter", label_visibility="collapsed",
                               format_func=lambda k: f"{k}  {counts[k]}") or "Tous"
    query = f2.text_input("Rechercher", placeholder="Rechercher un examen…", label_visibility="collapsed",
                          icon=":material/search:")
    want = FILTERS[flt]
    shown = [r for r in rows if (want is None or (want == "relu" and r["relu"]) or (r["res"].level == want and not r["relu"]))
             and query.lower() in r["name"].lower()]

    sel_key = st.session_state.get("qsel")
    if sel_key not in {r["key"] for r in rows}:
        sel_key = shown[0]["key"] if shown else rows[0]["key"]
    left, right = st.columns([1.75, 1], gap="medium")
    with left:
        st.markdown("<div class='eb-qhead'><span>Rang</span><span>Coupe</span><span>Examen</span>"
                    "<span class='st'>Statut IA</span><span class='pm'>p(maligne)</span><span></span></div>",
                    unsafe_allow_html=True)
        if not shown:
            st.caption("Aucun examen pour ce filtre.")
        for r in shown:
            res, lv = r["res"], LEVELS[r["res"].level]
            rank = rows.index(r) + 1
            conf_lbl, conf_key = ui.confidence_level(res.confidence, an.settings.min_confidence)
            sel = r["key"] == sel_key
            with st.container(border=True):
                a, b = st.columns([12, 1], vertical_alignment="center")
                a.markdown(f"""<div class='eb-q {'eb-done' if r['relu'] else ''}' style='--c:{lv['color']}'>
<span class='rk {'top' if rank == 1 else ''}'>{rank:02d}</span><img src='{r['entry']['thumb']}' alt='Miniature'>
<div style='min-width:0'><div class='ref'>{html.escape(r['name'])}{' ✓' if r['relu'] else ''}</div><div class='meta'>{meta(r['entry'], r['demo'])}</div></div>
<div class='st'>{ui.badge(res.level, 'sm')}</div>
<div class='pm'><b>{res.p_malignant * 100:.0f} %</b> <span class='eb-chip {conf_key}'>{conf_lbl}</span>
<div class='eb-track'><div style='width:{res.p_malignant * 100:.0f}%;background:{lv['color']}'></div></div></div><span></span></div>""",
                           unsafe_allow_html=True)
                if b.button("›" if not sel else "●", key=f"sel_{r['key']}", type="primary" if sel else "secondary",
                            help="Aperçu rapide"):
                    st.session_state["qsel"] = r["key"]
                    st.rerun()
        avg = sum(r["res"].p_malignant for r in rows) / len(rows)
        st.markdown(f"<div style='color:var(--muted);font-size:.85rem;margin-top:.4rem'>Affichage de <b>{len(shown)}</b> sur "
                    f"{len(rows)} examens · <span class='eb-mono'>moyenne p(maligne) : {avg:.1%}</span></div>",
                    unsafe_allow_html=True)

    with right:
        r = next(x for x in rows if x["key"] == sel_key)
        res, lv, entry = r["res"], LEVELS[r["res"].level], r["entry"]
        n_zones = len(find_zones(res.mask, None, (entry["raw"].height, entry["raw"].width)))
        crit = "".join(f"<div class='eb-crit'>{ui.icon('triangle-alert', 16, lv['color'])}<span>{html.escape(x)}</span></div>"
                       for x in res.reasons)
        with st.container(border=True):
            st.markdown(f"<div class='eb-label'>Inspection instantanée</div><h3 class='eb-serif' style='margin:.2rem 0 .7rem;"
                        f"font-size:1.2rem'>Aperçu rapide · {html.escape(r['name'])}</h3>", unsafe_allow_html=True)
            st.image(entry["preview"], use_container_width=True)
            st.markdown(f"""<div class='eb-row' style='margin-top:.6rem'>{ui.badge(res.level, 'sm')}
<span class='eb-big' style='font-size:2rem'>{res.p_malignant * 100:.0f}&thinsp;%</span></div>{crit}
<div class='eb-row' style='margin-top:.8rem;color:var(--muted);font-size:.86rem'><span>{n_zones} zone(s) suspecte(s) détourée(s)</span>
<span class='eb-mono'>confiance {res.confidence:.2f}</span></div>""", unsafe_allow_html=True)
            st.write("")
            if st.button("Ouvrir dans la visionneuse complète", type="primary", icon=":material/open_in_new:",
                         use_container_width=True):
                st.session_state["open_case"] = {"name": r["name"], "data": r["data"]}
                st.switch_page(PAGES["analyse"])
            if st.button("Annuler « relu »" if r["relu"] else "Marquer comme relu", icon=":material/task_alt:",
                         use_container_width=True):
                (reviewed.discard if r["relu"] else reviewed.add)(r["key"])
                st.rerun()
        st.caption("Tri inspiré de l'essai MASAI (mammographie, Suède). "
                   f"{APP_NAME} n'en a ni l'échelle ni la validation. Le statut « relu » n'est gardé que pendant la session.")


# --------------------------------------------------------------------------
# Page : Fiabilité et limites
# --------------------------------------------------------------------------
def pct(x, d=1):
    return "—" if x is None else f"{x * 100:.{d}f} %"


def page_limites():
    top("Fiabilité & limites")
    m = load_metrics()
    an = get_analyzer()
    ui.header("Transparence et évaluation", "Fiabilité & limites",
              "Ce que le modèle sait faire, mesuré une seule fois sur un jeu de test jamais vu — et ce qu'il ne faut pas lui demander.")
    if m is None:
        st.info("Mesures pas encore calculées (`scripts/evaluate.py`). Aucun chiffre n'est affiché tant qu'il n'est pas mesuré.")
    else:
        a, ci = m["alerte_orange_ou_rouge"], m.get("ic95", {})
        tag = "<span class='eb-tag'>Test interne</span>"
        cols = st.columns(4)
        cards = [
            ui.stat("Sensibilité", pct(a["sensibilite_maligne"]), ci.get("sensibilite"),
                    "Part des cas malins signalés orange ou rouge.", tag),
            ui.stat("Spécificité", pct(a["specificite"]), ci.get("specificite"),
                    "Part des cas non malins laissés en vert."),
            ui.stat("AUC-ROC", f"{m['auc_maligne']:.3f}", None, "Capacité à classer les malins avant les autres."),
            ui.stat("Indice Dice", "—" if m["dice"] is None else f"{m['dice']:.3f}", None,
                    "Recouvrement entre contour prédit et contour de référence."),
        ]
        for col, card in zip(cols, cards):
            col.markdown(card, unsafe_allow_html=True)
        st.write("")

        mx = m.get("matrice_alerte")
        with st.container(border=True):
            st.markdown(f"<div class='eb-row'><h3 class='eb-serif' style='margin:0;font-size:1.35rem'>Matrice de confusion & calibration</h3>"
                        f"<span class='eb-tag'>N = {m['n_test']}</span></div><div style='color:var(--muted);font-size:.9rem;margin:.2rem 0 .9rem'>"
                        f"Jeu de test BUSI séparé avant l'entraînement ({', '.join(f'{k} : {v}' for k, v in m['n_test_par_classe'].items())}), "
                        f"mesuré le {m['date']}.</div>", unsafe_allow_html=True)
            l, r = st.columns(2, gap="large")
            with l:
                if mx:
                    tp, fn, fp, tn = mx["vp"], mx["fn"], mx["fp"], mx["vn"]
                    P, N = tp + fn, fp + tn
                    st.markdown(f"""<div class='eb-row' style='margin-bottom:.5rem'><b style='font-weight:600'>Décision au seuil de prudence</b>
<span class='eb-mono' style='font-size:.8rem;color:var(--muted)'>seuil {m['seuils']['t_orange']:.2f}</span></div>
<div class='eb-mx'><span class='h'>Réel \\ Signalé</span><span class='h' style='color:var(--wine)'>Orange/rouge</span><span class='h'>Vert</span><span class='h tot'>Total</span>
<span>Maligne</span><span class='c' style='background:#8E1D4A;color:#fff'>{tp}<small>VP ({tp / max(P, 1):.1%})</small></span>
<span class='c' style='background:#F7DDE6;color:#C8264E'>{fn}<small>FN ({fn / max(P, 1):.1%})</small></span><span class='tot eb-mono'>{P}</span>
<span>Bénigne / normale</span><span class='c' style='background:#EADCF0;color:#5B2A6E'>{fp}<small>FP ({fp / max(N, 1):.1%})</small></span>
<span class='c' style='background:#F4EAF5;color:#2A1F2C'>{tn}<small>VN ({tn / max(N, 1):.1%})</small></span><span class='tot eb-mono'>{N}</span></div>
<p style='color:var(--muted);font-size:.86rem;margin:.7rem 0 0'>Les faux négatifs (FN) sont les cancers que le modèle aurait laissés en vert :
c'est le chiffre à surveiller en priorité.</p>""", unsafe_allow_html=True)
            with r:
                import altair as alt
                import pandas as pd

                cal = pd.DataFrame(m.get("calibration_maligne", []))
                st.markdown(f"<div class='eb-row'><b style='font-weight:600'>Calibration des probabilités</b>"
                            f"<span class='eb-mono' style='font-size:.8rem;color:var(--wine)'>Brier : {m.get('brier_maligne', float('nan')):.3f}</span></div>",
                            unsafe_allow_html=True)
                diag = alt.Chart(pd.DataFrame({"x": [0, 1], "y": [0, 1]})).mark_line(strokeDash=[4, 4], color="#CDB7C6").encode(
                    x=alt.X("x", title="Probabilité prédite", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
                    y=alt.Y("y", title="Fréquence observée", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")))
                chart = diag
                if not cal.empty:
                    base = alt.Chart(cal).encode(x="predite", y="observee", tooltip=["predite", "observee", "n"])
                    chart = diag + base.mark_line(color=ui.WINE, strokeWidth=2.5) + base.mark_circle(color=ui.WINE, size=70)
                st.altair_chart(chart.properties(height=230).configure_view(strokeWidth=0)
                                .configure_axis(labelColor="#6F6271", titleColor="#6F6271", gridColor="#F1E6EE"),
                                use_container_width=True)
                st.caption(f"Plus la courbe suit la diagonale, plus les pourcentages affichés sont fiables. "
                           f"ECE : {m['ece_avant_calibration']:.3f} avant → {m['ece_apres_calibration']:.3f} après calibration.")

    st.write("")
    with st.container(border=True):
        st.markdown(f"<h3 class='eb-serif' style='margin:0 0 .3rem;font-size:1.35rem;display:flex;gap:.5rem;align-items:center'>"
                    f"{ui.icon('database', 20, ui.WINE)} Jeu de données</h3><div style='color:var(--muted);font-size:.92rem;margin-bottom:.8rem'>"
                    "Entraînement et évaluation sur un seul jeu public, sans aucune donnée locale.</div>", unsafe_allow_html=True)
        cols = st.columns(3)
        minis = [("Source", "BUSI · Le Caire (Égypte)", "780 images collectées en 2018 auprès d'environ 600 patientes de 25 à 75 ans "
                  "(Al-Dhabyani et al., 2020). 133 normales, 437 bénignes, 210 malignes."),
                 ("Nettoyage", "Curated BUSI + dédoublonnage", "Version corrigée (Zenodo) ; nos scripts regroupent en plus les images "
                  "quasi identiques dans un même sous-ensemble. Séparation 70/15/15 avant toute augmentation."),
                 ("Représentativité", "Aucune donnée d'Afrique de l'Ouest", "Un seul pays, un seul centre, un seul constructeur "
                  "d'appareil. Les performances sur des patientes burkinabè sont inconnues.")]
        for col, (k, t, d) in zip(cols, minis):
            col.markdown(f"<div class='eb-mini'><div class='eb-label'>{k}</div><h5 style='color:var(--ink);margin:.2rem 0 .4rem'>{t}</h5>"
                         f"<p>{d}</p></div>", unsafe_allow_html=True)

    st.write("")
    with st.container(border=True):
        st.markdown(f"<h3 class='eb-serif' style='margin:0 0 .8rem;font-size:1.35rem;display:flex;gap:.5rem;align-items:center'>"
                    f"{ui.icon('triangle-alert', 20, ui.WINE)} Biais identifiés & limites</h3>", unsafe_allow_html=True)
        lim = [("users", "Pas d'identifiant patiente", "Des images d'une même patiente peuvent se trouver en entraînement et en test : "
                "les performances sont probablement optimistes."),
               ("scale", "Biais documentés", "Des études rapportent plus de faux positifs de certains systèmes d'IA en imagerie "
                "mammaire chez les femmes noires et les patientes plus âgées."),
               ("ruler", "Pas de mesure en mm", "L'échelle de l'image est inconnue : aucune taille réelle n'est calculée."),
               ("eye", "Zones d'attention", "Elles montrent ce qui a influencé le modèle, pas une lésion confirmée."),
               ("image-up", "Netteté = affichage", "Réduction du grain et agrandissement pour l'œil humain uniquement ; "
                "l'analyse porte sur l'image originale."),
               ("info", "Petit jeu déséquilibré", "Seulement 210 images malignes : les intervalles de confiance sont larges.")]
        for i in range(0, len(lim), 3):
            cols = st.columns(3)
            for col, (ic, t, d) in zip(cols, lim[i:i + 3]):
                col.markdown(f"<div class='eb-mini' style='margin-bottom:.7rem'><h5>{ui.icon(ic, 16, ui.WINE)} {t}</h5><p>{d}</p></div>",
                             unsafe_allow_html=True)

    st.markdown(f"""<div class='eb-card' style='background:#FCEFF4;border-color:#F2D3DF;margin-top:1rem'>
<div class='eb-row'><h3 class='eb-serif' style='margin:0;font-size:1.3rem;color:var(--wine)'>{ui.icon('shield-alert', 20, ui.WINE)} Cadre d'usage & interdictions</h3>
<span class='eb-tag' style='background:var(--wine);color:#fff'>Non dispositif médical</span></div>
<ul class='eb-ban'>
<li>{ui.icon('ban', 17, ui.WINE)}<span><b>Pas de diagnostic :</b> l'outil ne pose aucun diagnostic et ne décide d'aucun traitement.</span></li>
<li>{ui.icon('ban', 17, ui.WINE)}<span><b>Pas d'usage clinique :</b> prototype de hackathon, non validé cliniquement ; ne pas utiliser en pratique réelle.</span></li>
<li>{ui.icon('ban', 17, ui.WINE)}<span><b>Pas d'images réelles sans cadre :</b> aucune image de patiente sans autorisation, consentement et anonymisation validés.</span></li>
<li>{ui.icon('circle-check', 17, '#2F8F62')}<span><b>Confidentialité :</b> traitement local, aucune image conservée, aucun compte.</span></li>
</ul></div>""", unsafe_allow_html=True)

    if m is not None:
        st.write("")
        a, b = st.columns([3, 1], vertical_alignment="center")
        a.markdown("<b>Mesures brutes</b><br><span style='color:var(--muted);font-size:.88rem'>Toutes les valeurs ci-dessus, "
                   "telles que calculées par <code>scripts/evaluate.py</code>.</span>", unsafe_allow_html=True)
        b.download_button("Télécharger (JSON)", (MODELS_DIR / "metrics.json").read_bytes(), file_name="echobreast_mesures.json",
                          mime="application/json", type="primary", icon=":material/download:", use_container_width=True)
    with st.expander("Références"):
        st.markdown(f"""
- Al-Dhabyani W. et al. (2020), *Dataset of breast ultrasound images*, Data in Brief — jeu BUSI ; version corrigée Curated BUSI (Zenodo).
- Essai **MASAI** (Université de Lund, *The Lancet*) : triage de mammographies par score de risque assisté par IA.
- **Koios DS Breast** : aide à l'interprétation d'échographies mammaires autorisée par la FDA.
- Selvaraju et al. (2017) Grad-CAM · Ronneberger et al. (2015) U-Net · Tan & Le (2019) EfficientNet · OMS.

*Inspirations conceptuelles : {APP_NAME} est un prototype de hackathon, sans commune mesure avec des produits validés.*""")


# --------------------------------------------------------------------------
# Page : Octobre Rose (grand public)
# --------------------------------------------------------------------------
QUESTIONS = [
    "Quel examen me recommandez-vous et pourquoi ?",
    "Combien de temps pour avoir les résultats ?",
    "Faut-il un prélèvement (biopsie) ? Comment cela se passe-t-il ?",
    "Quels sont les coûts et les prises en charge possibles ?",
    "Qui contacter si j'ai une question après le rendez-vous ?",
    "Mes antécédents familiaux changent-ils quelque chose ?",
    "Comment faire l'auto-examen des seins ?",
]


def page_octobre_rose():
    top("Octobre Rose")
    a, b = st.columns([1.3, 1], gap="large", vertical_alignment="center")
    with a:
        ui.header("Octobre Rose · grand public", "S'informer, se faire examiner tôt",
                  "Détecté tôt, le cancer du sein se soigne beaucoup mieux. Quelques repères simples et sourcés.")
    with b:
        if (STATIC / "illustration.png").exists():
            st.image(str(STATIC / "illustration.png"), use_container_width=True)
    t1, t2, t3 = st.tabs(["Comprendre", "Ressources locales", "Préparer ma consultation"])
    with t1:
        c1, c2 = st.columns(2, gap="large")
        c1.markdown("""<div class='eb-card'><h3>Les signes qui doivent amener à consulter</h3><ul style='margin:0;padding-left:1.1rem;line-height:1.75'>
<li>une boule ou un épaississement dans le sein ou sous le bras ;</li><li>un changement de taille ou de forme du sein ;</li>
<li>une peau qui se rétracte, rougit ou prend l'aspect d'une peau d'orange ;</li><li>un écoulement anormal ou un mamelon qui se rétracte.</li></ul>
<p style='color:var(--muted);font-size:.85rem;margin:.7rem 0 0'>Source : OMS. La plupart des boules ne sont pas des cancers, mais toute anomalie mérite un avis médical.</p></div>""",
                    unsafe_allow_html=True)
        c2.markdown("""<div class='eb-card'><h3>Le parcours de soins</h3><ol style='margin:0;padding-left:1.1rem;line-height:1.85'>
<li>Examen clinique</li><li><b style='color:#8E1D4A'>Imagerie : échographie, mammographie</b></li><li>Prélèvement si l'image est suspecte</li>
<li>Analyse en laboratoire</li><li>Décision de traitement</li></ol>
<p style='color:var(--muted);font-size:.85rem;margin:.7rem 0 0'>Chiffres clés : à compléter avec des données vérifiées (OMS, ministère de la Santé), source et année.</p></div>""",
                    unsafe_allow_html=True)
    with t2:
        st.caption("Aucune coordonnée n'est affichée avant vérification.")
        res_file = APP_DIR / "ressources.json"
        res = json.loads(res_file.read_text(encoding="utf-8")) if res_file.exists() else []
        cols = st.columns(2)
        for i, r in enumerate(res):
            ok = bool(r.get("verifie_le"))
            tag = (f"<span class='eb-badge sm' style='--c:#2F8F62;--soft:#E2F3EA'><span class='dot'></span>Vérifié le {r['verifie_le']}</span>"
                   if ok else "<span class='eb-badge sm' style='--c:#8C7A88;--soft:#F3EEF2'><span class='dot'></span>À confirmer</span>")
            cols[i % 2].markdown(f"<div class='eb-card'><h3>{html.escape(r['nom'])}</h3><div style='color:var(--muted);margin-bottom:.6rem'>"
                                 f"{html.escape(r.get('ville', ''))}</div>{tag}{'<p>' + html.escape(r.get('contact', '')) + '</p>' if ok else ''}</div>",
                                 unsafe_allow_html=True)
    with t3:
        st.write("Cochez les questions à poser, puis téléchargez votre liste.")
        chosen = [q for q in QUESTIONS if st.checkbox(q)]
        extra = st.text_area("Mes questions personnelles")
        text = "Mes questions pour la consultation\n\n" + "\n".join(
            f"- {q}" for q in chosen + [l for l in extra.splitlines() if l.strip()])
        st.download_button("Télécharger ma liste", text, file_name="mes_questions.txt", icon=":material/download:")


# --------------------------------------------------------------------------
# Navigation : 3 liens principaux, Octobre Rose dans l'encart du bas
# --------------------------------------------------------------------------
PAGES = {
    "analyse": st.Page(page_analyse, title="Analyser", icon=":material/center_focus_strong:", default=True),
    "file": st.Page(page_priorite, title="File de priorité", icon=":material/format_list_numbered:", url_path="priorites"),
    "limites": st.Page(page_limites, title="Fiabilité & limites", icon=":material/verified_user:", url_path="fiabilite"),
    "rose": st.Page(page_octobre_rose, title="Octobre Rose", icon=":material/volunteer_activism:", url_path="octobre-rose"),
}

ui.inject_css()
nav = st.navigation(list(PAGES.values()), position="hidden")
with st.sidebar:
    ui.brand()
    for k in ("analyse", "file", "limites"):
        st.page_link(PAGES[k], use_container_width=True)
    st.markdown(f"<div class='eb-foot'>{ui.icon('lock', 14)} Traitement local · aucune image conservée</div>",
                unsafe_allow_html=True)
    st.page_link(PAGES["rose"], label="Octobre Rose · Informations", icon=":material/volunteer_activism:",
                 use_container_width=True)
nav.run()
