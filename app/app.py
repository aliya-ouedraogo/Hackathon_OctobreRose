"""EchoBreast : application Streamlit.

Lancer :  streamlit run app/app.py
"""
from __future__ import annotations

import hashlib
import html
import io
import json
import os
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


def setting(name: str, default: str = "") -> str:
    """Réglage de la version en ligne : secrets Streamlit Cloud, sinon variable d'environnement."""
    try:
        if name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:  # pas de fichier secrets.toml en local : normal
        pass
    return os.environ.get(name, default).strip()


# Version en ligne : EB_DEMO=1 affiche le bandeau de démonstration ; EB_FEEDBACK_URL ajoute le bouton
# vers le questionnaire ; EB_MODELS_REPO est le dépôt Hugging Face d'où télécharger modèles et cas de démo.
ONLINE = setting("EB_DEMO") == "1"
FEEDBACK_URL = setting("EB_FEEDBACK_URL")
MODELS_REPO = setting("EB_MODELS_REPO")
STATIC = APP_DIR / "static"

st.set_page_config(page_title=f"{APP_NAME} · {APP_TAGLINE}", page_icon=str(STATIC / "ribbon.png"),
                   layout="wide", initial_sidebar_state="auto")


# --------------------------------------------------------------------------
# Données et calculs (mis en cache par image)
# --------------------------------------------------------------------------
@st.cache_resource(show_spinner="Chargement des modèles…")
def get_analyzer():
    from echobreast.inference import Analyzer

    if not Analyzer.available() and MODELS_REPO:
        # En ligne, les modèles ne sont pas dans GitHub : on les récupère une fois au démarrage.
        from huggingface_hub import snapshot_download

        with st.spinner("Premier démarrage : téléchargement des modèles (environ 1 minute)…"):
            snapshot_download(MODELS_REPO, local_dir=str(ROOT), allow_patterns=["models/*", "app/demo/*"])
    return Analyzer() if Analyzer.available() else None


def _cache() -> dict:
    return st.session_state.setdefault("cache", {})


@st.cache_resource
def _shared_cache() -> dict:
    """Analyses des cas de démonstration, calculées une fois et partagées entre tous les visiteurs
    (en ligne, chacun ouvre les mêmes cas : on évite de tout recalculer et stocker par personne)."""
    return {}


def demo_keys() -> set[str]:
    return {hashlib.sha1(f.read_bytes()).hexdigest() for f in DEMO_DIR.glob("*.png")}


def _cache_for(key: str) -> dict:
    # Une image importée reste dans la session de la personne, et disparaît avec elle.
    return _shared_cache() if key in demo_keys() else _cache()


def analyze_bytes(data: bytes):
    key = hashlib.sha1(data).hexdigest()
    c = _cache_for(key)
    if key not in c:
        raw = Image.open(io.BytesIO(data))
        raw.load()
        c[key] = {"raw": raw, "res": get_analyzer().analyze(raw), "size": len(data)}
    return key, c[key]


def viewer_assets(key: str):
    """Vues d'affichage (originale, Netteté), carte des zones qui ont pesé, et zones, calculées une seule fois."""
    from echobreast.inference import enhance_for_display, find_zones, heat_rgba

    entry = _cache_for(key)[key]
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
    if ONLINE:
        b, f = st.columns([4, 1], vertical_alignment="center")
        b.markdown(f"<div class='eb-demo'>{ui.icon('triangle-alert', 16, '#9A5410')}<span><b>Version de démonstration en ligne.</b> "
                   "Utilisez les cas de démonstration ou des images anonymisées : n'importez aucune image permettant "
                   "d'identifier une patiente. Les images sont analysées sans être enregistrées.</span></div>",
                   unsafe_allow_html=True)
        if FEEDBACK_URL:
            f.link_button("Donner mon avis", FEEDBACK_URL, icon=":material/rate_review:", type="primary",
                          use_container_width=True)


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
# Guide de lecture (fenêtre)
# --------------------------------------------------------------------------
@st.dialog("Comment lire un résultat", width="medium")
def reading_guide(settings):
    st.markdown(f"""
#### 1. La couleur : le niveau d'alerte
| | Signification | Que faire |
|---|---|---|
| **Alerte forte** (rouge) | Le modèle trouve l'image très évocatrice d'une lésion maligne. | Relecture approfondie, prélèvement à discuter. |
| **À examiner de près** (orange) | Résultat incertain, ou probabilité au-dessus du seuil de relecture. | Relecture approfondie. |
| **Peu de signes** (vert) | Peu de signes inquiétants pour le modèle. | Lecture habituelle. Ce n'est pas un « normal » garanti. |

#### 2. Le pourcentage : la probabilité de malignité estimée sur l'image
Il indique à quel point l'image ressemble aux images de lésions malignes apprises par le modèle, comme la probabilité de malignité du BI-RADS.
Il porte sur l'image, pas sur la patiente : seul un prélèvement confirme ou écarte un cancer. Avec **30 %**, cela veut dire que lors des tests,
sur 100 images ayant ce score, environ 30 étaient réellement des cancers. Ce n'est **pas** un diagnostic.

#### 3. Les deux seuils
- **Seuil de relecture ({settings.t_orange:.0%})** : au-dessus, l'image passe en orange. Il est volontairement bas pour ne laisser
  passer presque aucun cancer, quitte à créer des fausses alertes.
- **Seuil d'alerte forte ({settings.t_red:.0%})** : au-dessus, l'image passe en rouge.
- Si le modèle **hésite** (par exemple « bénigne 40 % » contre « maligne 35 % »), l'examen passe en orange par prudence,
  même avec un faible pourcentage. Causes fréquentes : image différente de celles de l'apprentissage (autre appareil,
  mammographie…), mauvaise qualité, lésion d'aspect intermédiaire, lésion coupée par le bord de l'image.

#### 4. Les tracés sur l'image
- **Trait plein** (couleur du niveau) : contour de la lésion repérée par le modèle. Son nom suit la couleur :
  « Zone suspecte » en rouge, « Zone à vérifier » en orange, « Lésion d'aspect bénin » en vert.
  Un contour en vert ne signale donc pas un danger : le modèle a vu une lésion qu'il juge plutôt bénigne.
- **Pointillés roses**, bouton « Zones qui ont pesé » : l'IA regarde **toute** l'image, mais certains endroits comptent
  plus que d'autres dans son calcul. Ce calque montre ceux qui ont le plus fait monter son estimation de la probabilité de malignité.
  On n'affiche que les plus marqués, d'où des zones précises plutôt que toute l'image.
  **À quoi ça sert ?** À contrôler l'IA. Si ces zones tombent sur du tissu mammaire ou la lésion, son raisonnement est cohérent.
  Si elles tombent **hors du sein** (fond noir, bord, texte, mesures incrustées), le résultat est peu crédible : l'image est
  sans doute trop différente de celles que l'IA a apprises. Ces zones ne sont pas des lésions confirmées.

#### 5. Vos propres annotations
Une zone vous semble suspecte et l'IA ne l'a pas entourée ? Cliquez sur **Annoter**, choisissez la couleur qui vous semble
adaptée (Alerte forte, À examiner de près, Peu de signes), puis entourez la zone sur l'image. Vos tracés sont **bordés de blanc** et
portent l'étiquette **« Soignant »** ; ceux de l'IA portent l'étiquette **« IA »**. Rien n'est gardé tant que vous n'avez pas
cliqué sur **Enregistrer** ; « Annuler les modifications » revient à la dernière version enregistrée. Les zones enregistrées
apparaissent dans la fiche PDF, à côté de celles de l'IA. Elles sont gardées le temps de la session, jamais envoyées ailleurs.

#### 6. Avant / après IA, et Netteté
- **Avant / après IA** : un curseur sépare l'image brute (à gauche, sans aucun tracé) et la même image avec l'analyse de l'IA
  (à droite, contours et zones). Faites-le glisser pour vérifier ce que l'IA a ajouté.
- **Netteté** : réduit le grain de l'échographie pour mieux voir. Elle sert **uniquement à l'œil** : le modèle analyse
  toujours l'image originale.

#### 7. Ce que l'outil ne fait pas
Il ne pose pas de diagnostic, ne mesure pas la taille en mm et n'a pas été validé sur des patientes du Burkina Faso.
**La décision appartient toujours au professionnel de santé.**""")


# --------------------------------------------------------------------------
# Page : Analyser
# --------------------------------------------------------------------------
DECISION_ITEMS = {"relu": "Relecture effectuée", "complement": "Examen complémentaire demandé",
                  "prelevement": "Prélèvement indiqué"}


def decision_card(key: str):
    """Cases et commentaire facultatifs du professionnel, reportés tels quels dans la fiche PDF.
    Gardés en mémoire de session seulement. « Relecture effectuée » est la même information que
    « Marquer comme relu » dans la vue d'ensemble."""
    store = st.session_state.setdefault("decisions", {}).setdefault(key, {})
    reviewed: set = st.session_state.setdefault("reviewed", set())
    store["relu"] = key in reviewed

    def save(field: str):
        value = st.session_state[f"dec_{field}_{key}"]
        store[field] = value
        if field == "relu":
            (reviewed.add if value else reviewed.discard)(key)

    with st.container(border=True, key=f"decision_box_{key[:12]}"):
        st.markdown("<div class='eb-label'>Décision du professionnel</div>"
                    "<div style='color:var(--muted);font-size:.85rem;margin:.25rem 0 .4rem'>Facultatif. Ce que vous "
                    "cochez ou écrivez apparaît dans la fiche PDF. Ce qui reste vide sera à compléter à la main.</div>",
                    unsafe_allow_html=True)
        st.session_state[f"dec_reference_{key}"] = store.get("reference", "")
        st.text_input("Référence de l'examen (facultatif)", key=f"dec_reference_{key}", on_change=save,
                      args=("reference",), max_chars=40, placeholder="N° interne du dossier, jamais le nom",
                      help="Imprimée sur la fiche PDF pour la rattacher au bon dossier. "
                           "N'écrivez ni le nom ni la date de naissance de la patiente.")
        for field, label in DECISION_ITEMS.items():
            st.session_state[f"dec_{field}_{key}"] = bool(store.get(field, False))
            st.checkbox(label, key=f"dec_{field}_{key}", on_change=save, args=(field,))
        st.session_state[f"dec_comment_{key}"] = store.get("comment", "")
        st.text_area("Commentaire", key=f"dec_comment_{key}", on_change=save, args=("comment",), max_chars=400,
                     height=90, placeholder="Votre commentaire (facultatif)")
    # Renvoie une fonction : la fiche PDF lit la décision au moment du clic, pas au dernier affichage.
    return lambda: {**{f: bool(store.get(f, False)) for f in DECISION_ITEMS}, "comment": store.get("comment", "").strip(),
                    "reference": store.get("reference", "").strip()}


IMPRESSIONS = ["vert", "orange", "rouge"]


def impression_card(key: str, impressions: dict, revealed: set):
    """Mode « Lire d'abord » : le professionnel note son impression, puis affiche l'analyse de l'IA."""
    with st.container(border=True, key=f"impression_box_{key[:12]}"):
        st.markdown("<div class='eb-label'>Lire d'abord sans l'IA</div>"
                    "<div style='margin:.35rem 0 .2rem;font-size:.95rem'>Regardez l'image seule. "
                    "Quelle est votre première impression ?</div>"
                    "<div style='color:var(--muted);font-size:.85rem;margin-bottom:.5rem'>L'analyse de l'IA reste "
                    "cachée jusqu'à votre choix, pour ne pas influencer votre lecture.</div>", unsafe_allow_html=True)
        pick = st.radio("Votre impression", IMPRESSIONS, index=None, key=f"imp_{key}",
                        format_func=lambda k: LEVELS[k]["label"], label_visibility="collapsed")
        if st.button("Afficher l'analyse de l'IA", icon=":material/visibility:", type="primary",
                     use_container_width=True, key=f"reveal_{key}"):
            if pick is None:
                st.warning("Choisissez d'abord votre impression, ou passez cette étape.", icon=":material/touch_app:")
            else:
                impressions[key] = pick
                revealed.add(key)
                st.rerun()
        if st.button("Passer sans noter d'impression", key=f"skip_{key}", type="tertiary", use_container_width=True):
            impressions.pop(key, None)
            revealed.add(key)
            st.rerun()


def _blind_changed():
    # Réactiver « Lire d'abord » cache de nouveau l'analyse, même pour une image déjà dévoilée.
    if st.session_state.get("blind"):
        st.session_state.setdefault("revealed", set()).clear()


def page_analyse():
    top("Analyser")
    ui.header("Lecture assistée", "Analyser une échographie",
              "L'IA apporte un regard complémentaire et montre les zones à regarder. La décision reste au professionnel.")
    if need_models():
        return
    an = get_analyzer()
    cases = demo_cases()
    labels = [c["file"] for c in cases]
    opened = st.session_state.pop("open_case", None)
    data, name, truth = None, None, None
    with st.container(border=True, key="source_box"):
        c_pick, c_blind = st.columns([2.2, 1.3], gap="large", vertical_alignment="top")
        with c_pick:
            st.markdown("<div class='eb-label'>Image à analyser</div>", unsafe_allow_html=True)
            src = st.segmented_control("Source", ["Cas de démo", "Importer"],
                                       default="Cas de démo" if cases else "Importer",
                                       key="src", label_visibility="collapsed")
            if opened:
                name, data = opened["name"], opened["data"]
                truth = next((c for c in cases if c["file"] == name), None)
                st.caption(f"Ouvert depuis la vue d'ensemble : **{name}**")
            elif src == "Cas de démo" and cases:
                pick = st.selectbox("Cas de démonstration", labels, key="demo_pick", label_visibility="collapsed",
                                    format_func=lambda f: f"Cas {labels.index(f) + 1:02d} · {f}")
                truth = cases[labels.index(pick)]
                data, name = (DEMO_DIR / pick).read_bytes(), pick
                st.caption("8 échographies du jeu de test, jamais vues par le modèle.")
            elif src == "Importer":
                up = st.file_uploader("Échographie (PNG ou JPG)", type=["png", "jpg", "jpeg"],
                                      label_visibility="collapsed")
                if up:
                    data, name = up.getvalue(), up.name
                st.caption("Gardée le temps de votre visite seulement : actualiser la page l'efface.")
        with c_blind:
            with st.container(key="blind_box"):
                st.markdown(f"<div class='eb-blind-t'>{ui.icon('eye-off', 18, ui.WINE)}<b>Lire d'abord sans l'IA</b></div>"
                            "<div class='eb-blind-d'>Lisez l'image seule et notez votre impression, "
                            "puis découvrez l'analyse de l'IA.</div>", unsafe_allow_html=True)
                st.toggle("Activer", key="blind", on_change=_blind_changed)

    if data is None:
        st.markdown(f"<div class='eb-card' style='text-align:center;padding:3rem'>{ui.icon('image-up', 40, ui.WINE, 1.5)}"
                    "<h3 style='justify-content:center;margin-top:.8rem'>Déposez une échographie mammaire</h3>"
                    f"<span style='color:var(--muted)'>PNG ou JPG · {'analysée sans être enregistrée' if ONLINE else 'traitée localement, jamais conservée'}</span></div>",
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

    g_txt, g_btn = st.columns([3, 1], vertical_alignment="center")
    g_txt.markdown("<div class='eb-guide-hint'>Couleurs, pourcentage, tracés : le guide explique comment lire chaque "
                   "élément du résultat.</div>", unsafe_allow_html=True)
    with g_btn:
        if st.button("Guide de lecture", icon=":material/arrow_forward:", icon_position="right", type="primary",
                     key="guide_btn", use_container_width=True):
            reading_guide(an.settings)
    with st.container(border=True, key="legend_box"):
        st.markdown("<div class='eb-label'>Légende</div>", unsafe_allow_html=True)
        ui.legend()

    revealed: set = st.session_state.setdefault("revealed", set())
    impressions: dict = st.session_state.setdefault("impressions", {})
    hidden = st.session_state.get("blind", False) and key not in revealed
    left, right = st.columns([1.7, 1], gap="medium")
    with left:
        with st.spinner("Préparation de la visionneuse…"):
            assets = viewer_assets(key)
        from viewer import render_viewer

        store = st.session_state.setdefault("annotations", {})
        # Lecture sans l'IA : même visionneuse, sans contour ni carte, avec sa propre clé pour repartir de zéro ensuite.
        vkey = f"{key}-seule" if hidden else key
        val = render_viewer(assets["base"], assets["sharp"], None if hidden else assets["heat"],
                            [] if hidden else assets["zones"], raw.size, res.level, img_key=vkey,
                            saved=store.get(key, []), stage_height=600)
        if val and val.get("img_key") == vkey:
            store[key] = val.get("annotations", [])
        if not hidden:
            ui.probs_card(res)
    with right:
        if hidden:
            impression_card(key, impressions, revealed)
            return
        if key in impressions:
            ui.impression_compare(impressions[key], res.level)
        ui.triage_card(res, an.settings)
        from echobreast.inference import draw_contour
        from echobreast.report import build_pdf

        anns = st.session_state.get("annotations", {}).get(key, [])
        if anns:
            items = " · ".join(f"Soignant {i} : {LEVELS[x['level']]['label']}" for i, x in enumerate(anns, 1))
            st.markdown(f"<div class='eb-card' style='border-left:4px solid #8E1D4A'><div class='eb-label'>Annotations du professionnel</div>"
                        f"<div style='margin-top:.4rem;font-size:.92rem'>{len(anns)} zone(s) ajoutée(s) à la main, incluse(s) dans la fiche PDF.</div>"
                        f"<div style='color:var(--muted);font-size:.85rem;margin-top:.3rem'>{html.escape(items)}</div></div>",
                        unsafe_allow_html=True)
        decision = decision_card(key)
        st.write("")
        version = an.settings.model_version
        # PDF construit au clic : il reprend les cases et le commentaire tels qu'ils sont à ce moment-là.
        st.download_button("Télécharger la fiche PDF",
                           lambda: build_pdf(draw_contour(raw, res.mask, res.level, annotations=anns, labels=True),
                                             res, version, decision().get("reference") or name, annotations=anns,
                                             decision=decision(), impression=impressions.get(key)),
                           file_name=f"echobreast_{Path(name).stem}.pdf", mime="application/pdf", type="primary",
                           icon=":material/download:", use_container_width=True)
        if truth:
            with st.popover("Voir la vérité terrain (démo)", icon=":material/fact_check:", use_container_width=True):
                st.markdown(f"Étiquette du jeu BUSI : **{truth['verite']}**")
                if truth.get("erreur_du_modele"):
                    st.markdown("Ce cas est montré **volontairement** : le modèle s'y trompe. "
                                "C'est pour cela que la décision reste au professionnel.")


# --------------------------------------------------------------------------
# Page : Vue d'ensemble
# --------------------------------------------------------------------------
FILTERS = {"Tous": None, "Alerte forte": "rouge", "À examiner de près": "orange", "Peu de signes": "vert", "Relus": "relu"}


def page_priorite():
    top("Vue d'ensemble")
    ui.header("Tous les examens", "Vue d'ensemble",
              "Chaque image mérite la même attention. Celles qui demandent une relecture approfondie apparaissent en tête, selon le niveau d'alerte puis la probabilité de malignité.")
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

        st.download_button("Exporter la liste (PDF)", build_queue_pdf(
            [{"name": r["name"], "level": r["res"].level, "p": r["res"].p_malignant, "relu": r["relu"]} for r in rows], an.settings.model_version),
            file_name="echobreast_vue_ensemble.pdf", mime="application/pdf", icon=":material/ios_share:",
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
        st.markdown("<div class='eb-qhead'><span>Rang</span><span>Coupe</span>"
                    "<span>Examen · niveau · probabilité de malignité</span></div>", unsafe_allow_html=True)
        if not shown:
            st.caption("Aucun examen pour ce filtre.")
        for r in shown:
            res, lv = r["res"], LEVELS[r["res"].level]
            rank = rows.index(r) + 1
            sel = r["key"] == sel_key
            with st.container(border=True):
                a, b = st.columns([9, 1.1], vertical_alignment="center")
                a.markdown(f"""<div class='eb-q {'eb-done' if r['relu'] else ''}' style='--c:{lv['color']}'>
<span class='rk {'top' if rank == 1 else ''}'>{rank:02d}</span><img src='{r['entry']['thumb']}' alt='Miniature'>
<div class='info'><div class='ref'>{html.escape(r['name'])}{' ✓' if r['relu'] else ''}</div><div class='meta'>{meta(r['entry'], r['demo'])}</div>
<div class='line'>{ui.badge(res.level, 'sm')}<span class='risk'><b>{ui.pct(res.p_malignant)}</b>
<span class='eb-track'><span style='width:{res.p_malignant * 100:.0f}%;background:{lv['color']}'></span></span></span></div></div></div>""",
                           unsafe_allow_html=True)
                if b.button("›" if not sel else "●", key=f"sel_{r['key']}", type="primary" if sel else "secondary",
                            help="Aperçu rapide"):
                    st.session_state["qsel"] = r["key"]
                    st.rerun()
        avg = sum(r["res"].p_malignant for r in rows) / len(rows)
        st.markdown(f"<div style='color:var(--muted);font-size:.85rem;margin-top:.4rem'>Affichage de <b>{len(shown)}</b> sur "
                    f"{len(rows)} examens · <span class='eb-mono'>probabilité moyenne : {avg:.0%}</span></div>",
                    unsafe_allow_html=True)

    with right:
        r = next(x for x in rows if x["key"] == sel_key)
        res, lv, entry = r["res"], LEVELS[r["res"].level], r["entry"]
        n_zones = len(find_zones(res.mask, None, (entry["raw"].height, entry["raw"].width)))
        n_ann = len(st.session_state.get("annotations", {}).get(r["key"], []))
        n_ann_txt = f" · {n_ann} zone(s) ajoutée(s) par le soignant" if n_ann else ""
        crit = "".join(f"<div class='eb-crit'>{ui.icon('triangle-alert', 16, lv['color'])}<span>{html.escape(x)}</span></div>"
                       for x in res.reasons)
        with st.container(border=True):
            st.markdown(f"<div class='eb-label'>Inspection instantanée</div><h3 class='eb-serif' style='margin:.2rem 0 .7rem;"
                        f"font-size:1.2rem'>Aperçu rapide · {html.escape(r['name'])}</h3>", unsafe_allow_html=True)
            st.image(entry["preview"], use_container_width=True)
            st.markdown(f"""<div class='eb-row' style='margin-top:.6rem'>{ui.badge(res.level, 'sm')}
<span class='eb-big' style='font-size:2rem'>{ui.pct(res.p_malignant, '&thinsp;')}</span></div>{crit}
<div style='margin-top:.8rem;color:var(--muted);font-size:.86rem'>{n_zones} lésion(s) repérée(s) par l'IA{n_ann_txt}</div>""", unsafe_allow_html=True)
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
    return "n.d." if x is None else f"{x * 100:.{d}f} %"


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [max(0.0, c - h), min(1.0, c + h)]


def complete_metrics(m: dict) -> dict:
    """Complète un metrics.json produit par une ancienne version d'evaluate.py.

    La matrice « signalé / pas signalé » et les fourchettes se déduisent des couleurs par classe réelle.
    La courbe de calibration, elle, demande de relancer l'évaluation.
    """
    m = dict(m)
    col = m.get("couleurs_par_classe_reelle")
    if "matrice_alerte" not in m and col:
        mal = col.get("maligne", {})
        others = [v for k, v in col.items() if k != "maligne"]
        tp = mal.get("orange", 0) + mal.get("rouge", 0)
        fn = mal.get("vert", 0)
        fp = sum(o.get("orange", 0) + o.get("rouge", 0) for o in others)
        tn = sum(o.get("vert", 0) for o in others)
        m["matrice_alerte"] = {"vp": tp, "fn": fn, "fp": fp, "vn": tn}
    mx = m.get("matrice_alerte")
    if "ic95" not in m and mx:
        m["ic95"] = {"sensibilite": wilson(mx["vp"], mx["vp"] + mx["fn"]),
                     "specificite": wilson(mx["vn"], mx["vn"] + mx["fp"])}
    return m


def page_limites():
    top("Fiabilité & limites")
    m = load_metrics()
    m = complete_metrics(m) if m else None
    an = get_analyzer()
    ui.header("Transparence et évaluation", "Fiabilité & limites",
              "Ce que le modèle sait faire, mesuré une seule fois sur un jeu de test jamais vu, et ce qu'il ne faut pas lui demander.")
    if m is None:
        st.info("Mesures pas encore calculées (`scripts/evaluate.py`). Aucun chiffre n'est affiché tant qu'il n'est pas mesuré.")
    else:
        a, ci = m["alerte_orange_ou_rouge"], m.get("ic95", {})
        tag = "<span class='eb-tag'>Test interne</span>"
        cols = st.columns(4)
        cards = [
            ui.stat("Cancers signalés (sensibilité)", pct(a["sensibilite_maligne"], 0), ci.get("sensibilite"),
                    "Sur 100 cancers, combien l'outil met en orange ou en rouge.", tag),
            ui.stat("Images saines laissées en vert (spécificité)", pct(a["specificite"], 0), ci.get("specificite"),
                    "Sur 100 images sans cancer, combien ne déclenchent pas d'alerte."),
            ui.stat("Qualité du tri (AUC)", f"{m['auc_maligne']:.2f}".replace(".", ","), None,
                    "Capacité à placer les cancers avant les autres images. 1 = tri parfait, 0,5 = hasard."),
            ui.stat("Précision du contour (Dice)", "n.d." if m["dice"] is None else f"{m['dice']:.2f}".replace(".", ","), None,
                    "Ressemblance entre le contour tracé par l'IA et celui de l'expert. 1 = identique."),
        ]
        for col, card in zip(cols, cards):
            col.markdown(card, unsafe_allow_html=True)
        st.write("")

        mx = m.get("matrice_alerte")
        with st.container(border=True):
            st.markdown(f"<div class='eb-row'><h3 class='eb-serif' style='margin:0;font-size:1.35rem'>Résultats détaillés sur les images de test</h3>"
                        f"<span class='eb-tag'>N = {m['n_test']}</span></div><div style='color:var(--muted);font-size:.9rem;margin:.2rem 0 .9rem'>"
                        f"Jeu de test BUSI séparé avant l'entraînement ({', '.join(f'{k} : {v}' for k, v in m['n_test_par_classe'].items())}), "
                        f"mesuré le {m['date']}.</div>", unsafe_allow_html=True)
            l, r = st.columns(2, gap="large")
            with l:
                if mx:
                    tp, fn, fp, tn = mx["vp"], mx["fn"], mx["fp"], mx["vn"]
                    P, N = tp + fn, fp + tn
                    st.markdown(f"""<div class='eb-row' style='margin-bottom:.5rem'><b style='font-weight:600'>Ce que l'outil a signalé</b>
<span style='font-size:.8rem;color:var(--muted)'>au seuil de relecture ({m['seuils']['t_orange']:.0%})</span></div>
<div class='eb-mx'><span class='h'>Réalité \\ Couleur</span><span class='h' style='color:var(--wine)'>Orange ou rouge</span><span class='h'>Vert</span><span class='h tot'>Total</span>
<span>Cancer</span><span class='c' style='background:#8E1D4A;color:#fff'>{tp}<small>bien signalés</small></span>
<span class='c' style='background:#F7DDE6;color:#C8264E'>{fn}<small>manqués</small></span><span class='tot eb-mono'>{P}</span>
<span>Pas de cancer</span><span class='c' style='background:#EADCF0;color:#5B2A6E'>{fp}<small>fausses alertes</small></span>
<span class='c' style='background:#F4EAF5;color:#2A1F2C'>{tn}<small>bien laissés en vert</small></span><span class='tot eb-mono'>{N}</span></div>
<p style='color:var(--muted);font-size:.86rem;margin:.7rem 0 0'>Les cancers « manqués » sont ceux que l'outil aurait laissés en vert : c'est le chiffre le plus important.
Les fausses alertes coûtent une relecture de plus, mais ne font pas rater de cancer.</p>""", unsafe_allow_html=True)
            with r:
                import altair as alt
                import pandas as pd

                cal = pd.DataFrame(m.get("calibration_maligne", []))
                st.markdown(f"<div class='eb-row'><b style='font-weight:600'>Les pourcentages annoncés sont-ils justes ?</b>"
                            "</div>",
                            unsafe_allow_html=True)
                diag = alt.Chart(pd.DataFrame({"x": [0, 1], "y": [0, 1]})).mark_line(strokeDash=[4, 4], color="#CDB7C6").encode(
                    x=alt.X("x", title="Probabilité annoncée par l'IA", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
                    y=alt.Y("y", title="Cancers réellement observés", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")))
                if cal.empty:
                    st.markdown(f"<div class='eb-guide' style='margin-top:.6rem'>{ui.icon('info', 16, ui.WINE)}<div>"
                                "<b>Courbe non disponible</b>Ces mesures ont été calculées avec une ancienne version du script "
                                "d'évaluation. Relancez <code>scripts/evaluate.py</code> (sans réentraîner) pour obtenir la courbe.</div></div>",
                                unsafe_allow_html=True)
                else:
                    base = alt.Chart(cal).encode(
                        x="predite", y="observee",
                        tooltip=[alt.Tooltip("predite", title="Probabilité annoncée", format=".0%"),
                                 alt.Tooltip("observee", title="Cancers observés", format=".0%"),
                                 alt.Tooltip("n", title="Nombre d'images")])
                    chart = diag + base.mark_line(color=ui.WINE, strokeWidth=2.5) + base.mark_circle(color=ui.WINE, size=70)
                    st.altair_chart(chart.properties(height=260).configure_view(strokeWidth=0)
                                    .configure_axis(labelColor="#6F6271", titleColor="#6F6271", gridColor="#F1E6EE"),
                                    use_container_width=True)
                st.caption(f"Si la courbe suit la diagonale, une probabilité annoncée de 30 % correspond bien à environ 30 cancers sur 100 images. "
                           f"Écart moyen constaté : {m['ece_apres_calibration'] * 100:.0f} points.")

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
               ("eye", "Zones qui ont pesé", "Elles montrent ce qui a le plus compté dans le calcul de l'IA, pas une lésion confirmée."),
               ("image-up", "Netteté = affichage", "Réduction du grain et agrandissement pour l'œil humain uniquement ; "
                "l'analyse porte sur l'image originale."),
               ("info", "Petit jeu déséquilibré", "Seulement 210 images de cancers : les chiffres ont une marge d'incertitude importante.")]
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
- Al-Dhabyani W. et al. (2020), *Dataset of breast ultrasound images*, Data in Brief : jeu BUSI ; version corrigée Curated BUSI (Zenodo).
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
    "Dois-je faire un dépistage du cancer du col de l'utérus ? À quel rythme ?",
    "Ma fille peut-elle être vaccinée contre le papillomavirus (HPV) ?",
]


def info_card(title: str, body: str, note: str = "") -> str:
    return (f"<div class='eb-card' style='height:100%'><h3>{title}</h3>{body}"
            + (f"<p style='color:var(--muted);font-size:.85rem;margin:.7rem 0 0'>{note}</p>" if note else "") + "</div>")


def ul(items: list[str]) -> str:
    return "<ul style='margin:0;padding-left:1.1rem;line-height:1.75'>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def page_infos():
    top("Informations santé")
    a, b = st.columns([1.3, 1], gap="large", vertical_alignment="center")
    with a:
        ui.header("Octobre Rose · santé des femmes", "S'informer, se faire examiner tôt",
                  "Le cancer du sein et le cancer du col de l'utérus se soignent beaucoup mieux quand ils sont découverts tôt. "
                  "Quelques repères simples, tirés des fiches de l'OMS.")
    with b:
        if (STATIC / "illustration.png").exists():
            st.image(str(STATIC / "illustration.png"), use_container_width=True)
    t1, t2, t3, t4 = st.tabs(["Cancer du sein", "Cancer du col de l'utérus", "Ressources locales", "Préparer ma consultation"])
    with t1:
        c1, c2 = st.columns(2, gap="large")
        c1.markdown(info_card("Les signes qui doivent amener à consulter", ul([
            "une boule ou un épaississement dans le sein ou sous le bras ;",
            "un changement de taille ou de forme du sein ;",
            "une peau qui se rétracte, rougit ou prend l'aspect d'une peau d'orange ;",
            "un écoulement anormal ou un mamelon qui se rétracte."]),
            "Source : OMS. La plupart des boules ne sont pas des cancers, mais toute anomalie mérite un avis médical."),
            unsafe_allow_html=True)
        c2.markdown(info_card("Le parcours de soins", "<ol style='margin:0;padding-left:1.1rem;line-height:1.85'>"
            "<li>Examen clinique</li><li><b style='color:#8E1D4A'>Imagerie : échographie, mammographie</b></li>"
            "<li>Prélèvement si l'image est suspecte</li><li>Analyse en laboratoire</li><li>Décision de traitement</li></ol>",
            "EchoBreast intervient à l'étape de l'imagerie, pour aider le professionnel à approfondir son analyse et à décider s'il faut un prélèvement."),
            unsafe_allow_html=True)
    with t2:
        c1, c2 = st.columns(2, gap="large")
        c1.markdown(info_card("Comprendre", ul([
            "Il est causé dans la grande majorité des cas par une infection persistante à <b>papillomavirus humain (HPV)</b>, "
            "un virus très courant qui se transmet lors des rapports sexuels.",
            "La plupart des infections disparaissent seules. Quand elles persistent, des lésions peuvent apparaître puis, "
            "<b>lentement</b>, évoluer vers un cancer : souvent 15 à 20 ans, moins chez les femmes dont l'immunité est affaiblie (VIH par exemple).",
            "Ce délai laisse le temps de <b>repérer et traiter les lésions avant qu'elles deviennent un cancer</b>."]),
            "Source : OMS, fiche « Cancer du col de l'utérus »."), unsafe_allow_html=True)
        c2.markdown(info_card("Se protéger", ul([
            "<b>La vaccination contre le HPV</b>, recommandée par l'OMS pour les filles de 9 à 14 ans, avant le début de la vie sexuelle.",
            "<b>Le dépistage</b> régulier à partir de 30 ans (dès 25 ans pour les femmes vivant avec le VIH) : test HPV ou "
            "inspection visuelle à l'acide acétique (IVA), un examen simple et peu coûteux.",
            "<b>Le traitement des lésions</b> découvertes au dépistage, souvent possible le jour même."]),
            "Calendrier exact et lieux de dépistage : à vérifier auprès des services de santé locaux."), unsafe_allow_html=True)
        st.write("")
        c3, c4 = st.columns(2, gap="large")
        c3.markdown(info_card("Les signes qui doivent amener à consulter", ul([
            "des saignements entre les règles, après un rapport sexuel ou après la ménopause ;",
            "des pertes inhabituelles, parfois malodorantes ;",
            "des douleurs dans le bas du ventre ou pendant les rapports."]),
            "Au début, il n'y a souvent <b>aucun symptôme</b> : c'est pour cela que le dépistage est important même quand tout va bien."),
            unsafe_allow_html=True)
        c4.markdown(info_card("Et EchoBreast ?", "<p style='margin:0;line-height:1.6'>EchoBreast analyse uniquement des "
            "<b>échographies du sein</b>. La même démarche (trier les examens, montrer les zones à regarder, annoncer honnêtement ses limites) "
            "pourrait plus tard aider au dépistage du col de l'utérus, par exemple à partir de photos d'IVA. "
            "Cela demanderait des données dédiées, collectées dans un cadre éthique, et une validation par des soignants.</p>",
            "Piste de travail, pas une fonction disponible aujourd'hui."), unsafe_allow_html=True)
        st.caption("L'OMS vise l'élimination de ce cancer avec trois objectifs pour 2030 : 90 % des filles vaccinées avant 15 ans, "
                   "70 % des femmes dépistées avec un test performant à 35 et 45 ans, 90 % des femmes atteintes correctement traitées.")
    with t3:
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
    with t4:
        st.write("Cochez les questions à poser, puis téléchargez votre liste.")
        chosen = [q for q in QUESTIONS if st.checkbox(q)]
        extra = st.text_area("Mes questions personnelles")
        text = "Mes questions pour la consultation\n\n" + "\n".join(
            f"- {q}" for q in chosen + [l for l in extra.splitlines() if l.strip()])
        st.download_button("Télécharger ma liste", text, file_name="mes_questions.txt", icon=":material/download:")


# --------------------------------------------------------------------------
# Navigation : 3 liens principaux, informations santé dans l'encart du bas
# --------------------------------------------------------------------------
PAGES = {
    "analyse": st.Page(page_analyse, title="Analyser", icon=":material/center_focus_strong:", default=True),
    "file": st.Page(page_priorite, title="Vue d'ensemble", icon=":material/format_list_numbered:", url_path="priorites"),
    "limites": st.Page(page_limites, title="Fiabilité & limites", icon=":material/verified_user:", url_path="fiabilite"),
    "rose": st.Page(page_infos, title="Informations santé", icon=":material/volunteer_activism:", url_path="informations"),
}

ui.inject_css()
nav = st.navigation(list(PAGES.values()), position="hidden")
with st.sidebar:
    ui.brand()
    for k in ("analyse", "file", "limites"):
        st.page_link(PAGES[k], use_container_width=True)
    st.markdown(f"<div class='eb-foot'>{ui.icon('lock', 14)} "
                f"{'Version en ligne · aucune image enregistrée' if ONLINE else 'Traitement local · aucune image conservée'}</div>",
                unsafe_allow_html=True)
    st.page_link(PAGES["rose"], label="Informations santé", icon=":material/volunteer_activism:",
                 use_container_width=True)
nav.run()
