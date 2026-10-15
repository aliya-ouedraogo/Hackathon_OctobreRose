"""SeinSûr — application Streamlit.

Lancer :  streamlit run app/app.py
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from seinsur.core import CLASSES, LEVELS, MODELS_DIR, priority_key  # noqa: E402

DEMO_DIR = ROOT / "app" / "demo"
DISCLAIMER = "⚕️ **Outil d'information et d'orientation, pas un diagnostic.** Prototype de hackathon, non validé cliniquement."

st.set_page_config(page_title="SeinSûr", page_icon="🎗️", layout="wide")
st.markdown("""
<style>
html, body, [class*="css"] { font-size: 16px; }
.seinsur-banner { background:#FCE4EC; border-left:6px solid #C2185B; padding:.7rem 1rem; border-radius:8px; margin-bottom:1rem; color:#3a3a3a; }
.level-card { border-radius:12px; padding:1rem 1.2rem; color:white; margin-bottom:.6rem; }
.level-card h3 { color:white; margin:0 0 .3rem 0; }
.prob-row { display:flex; align-items:center; gap:.6rem; margin:.25rem 0; }
.prob-bar { flex:1; background:#FCE4EC; border-radius:6px; height:18px; overflow:hidden; }
.prob-fill { background:#C2185B; height:100%; }
</style>""", unsafe_allow_html=True)


# --------------------------------------------------------------------------
@st.cache_resource(show_spinner="Chargement des modèles…")
def get_analyzer():
    from seinsur.inference import Analyzer

    return Analyzer() if Analyzer.available() else None


def analyze_bytes(data: bytes):
    key = hashlib.sha1(data).hexdigest()
    cache = st.session_state.setdefault("results", {})
    if key not in cache:
        raw = Image.open(io.BytesIO(data))
        raw.load()
        cache[key] = (raw, get_analyzer().analyze(raw))
    return cache[key]


def demo_cases() -> list[dict]:
    f = DEMO_DIR / "demo.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def load_metrics() -> dict | None:
    f = MODELS_DIR / "metrics.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def level_card(level: str, reasons: list[str]):
    lv = LEVELS[level]
    st.markdown(f"<div class='level-card' style='background:{lv['color']}'><h3>{lv['icon']} {level.upper()} — {lv['label']}</h3>"
                f"{lv['text']}</div>", unsafe_allow_html=True)
    for r in reasons:
        st.caption("• " + r)


def prob_bars(probs):
    html = "".join(f"<div class='prob-row'><span style='width:80px'>{c.capitalize()}</span>"
                   f"<div class='prob-bar'><div class='prob-fill' style='width:{p*100:.1f}%'></div></div>"
                   f"<b style='width:48px;text-align:right'>{p:.0%}</b></div>" for c, p in zip(CLASSES, probs))
    st.markdown(html, unsafe_allow_html=True)


def to_data_uri(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def need_models() -> bool:
    if get_analyzer() is None:
        st.warning("Aucun modèle trouvé dans `models/`. Entraînez-les (voir README) puis relancez l'application.")
        return True
    return False


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
def page_accueil():
    st.title("🎗️ SeinSûr")
    st.subheader("Aider les professionnels à décider quoi relire en premier — sans jamais décider à leur place.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 👩‍⚕️ Professionnels de l'imagerie")
        st.write("Analyse d'une échographie mammaire : niveau de risque en trois couleurs, contour de la zone "
                 "suspecte, explication visuelle, liste de priorité et fiche PDF.")
        if st.button("Ouvrir la console d'analyse", type="primary"):
            st.session_state.page = "🔬 Analyse"
            st.rerun()
    with c2:
        st.markdown("#### 💗 Grand public — Octobre Rose")
        st.write("Informations sourcées, ressources locales et préparation de sa consultation.")
        if st.button("Voir les informations"):
            st.session_state.page = "💗 Octobre Rose"
            st.rerun()
    st.divider()
    cols = st.columns(3)
    for col, lv in zip(cols, ["vert", "orange", "rouge"]):
        d = LEVELS[lv]
        col.markdown(f"**{d['icon']} {lv.capitalize()} — {d['label']}**  \n{d['text']}")
    st.caption("Règle prudente : en cas de doute, le système classe en orange. La couleur est toujours "
               "accompagnée d'une icône et d'un libellé.")


def page_analyse():
    st.title("🔬 Console d'analyse")
    if need_models():
        return
    an = get_analyzer()
    cases = demo_cases()
    src = st.radio("Source de l'image", ["Cas de démonstration", "Importer une image"], horizontal=True,
                   index=0 if cases else 1)
    data, name, truth = None, None, None
    if src == "Cas de démonstration":
        if not cases:
            st.info("Pas de cas de démonstration : lancez `scripts/evaluate.py`.")
            return
        labels = [c["file"] for c in cases]
        pick = st.selectbox("Cas", labels)
        case = cases[labels.index(pick)]
        data, name, truth = (DEMO_DIR / case["file"]).read_bytes(), case["file"], case
    else:
        up = st.file_uploader("Échographie (PNG ou JPG)", type=["png", "jpg", "jpeg"])
        if up:
            data, name = up.getvalue(), up.name
    if data is None:
        return
    try:
        raw, res = analyze_bytes(data)
    except Exception:
        st.error("Fichier illisible : merci de fournir une image PNG ou JPG valide.")
        return

    from seinsur.inference import draw_contour, heat_overlay

    for w in res.warnings:
        st.warning("⚠️ " + w)
    left, right = st.columns([3, 2])
    with left:
        show_cam = st.toggle("Afficher l'explication visuelle (Grad-CAM)", value=False)
        annotated = draw_contour(raw, res.mask, res.level)
        c1, c2 = st.columns(2)
        c1.image(raw.convert("RGB"), caption="Image d'origine", use_container_width=True)
        if show_cam:
            c2.image(heat_overlay(raw, an.gradcam(raw)), caption="Zones ayant influencé le modèle (pas la position exacte de la lésion)",
                     use_container_width=True)
        else:
            c2.image(annotated, caption="Zone suspecte (contour)" if res.mask is not None else "Aucun contour affiché",
                     use_container_width=True)
    with right:
        level_card(res.level, res.reasons)
        st.markdown("**Probabilités calibrées**")
        prob_bars(res.probs)
        st.progress(res.confidence, text=f"Confiance du modèle : {res.confidence:.0%}")
        if res.confidence < an.settings.min_confidence:
            st.warning("Résultat peu fiable : relecture prioritaire.")
        from seinsur.report import build_pdf

        st.download_button("📄 Télécharger la fiche de synthèse (PDF)", build_pdf(annotated, res, an.settings.model_version, name),
                           file_name=f"seinsur_{Path(name).stem}.pdf", mime="application/pdf", type="primary")
        if truth:
            with st.expander("Révéler la vérité terrain (cas de démonstration)"):
                st.write(f"Étiquette du jeu BUSI : **{truth['verite']}**")
                if truth.get("erreur_du_modele"):
                    st.error("Ce cas est volontairement montré : le modèle s'y trompe. C'est pour cela que "
                             "la décision reste au professionnel.")


def page_priorite():
    st.title("📋 Liste de priorité")
    if need_models():
        return
    st.write("Importez plusieurs échographies : elles sont triées de la plus à la moins prioritaire à relire.")
    ups = st.file_uploader("Échographies", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
    use_demo = st.checkbox("Utiliser tous les cas de démonstration", value=not ups and bool(demo_cases()))
    items = [(u.name, u.getvalue()) for u in ups or []]
    if use_demo:
        items += [(c["file"], (DEMO_DIR / c["file"]).read_bytes()) for c in demo_cases()]
    if not items:
        return
    from seinsur.inference import draw_contour, thumbnail_with_badge

    rows = []
    with st.spinner(f"Analyse de {len(items)} image(s)…"):
        for n, data in items:
            raw, res = analyze_bytes(data)
            thumb = thumbnail_with_badge(draw_contour(raw, res.mask, res.level, width=5), res.level)
            rows.append({"_key": priority_key(res.level, res.probs), "Aperçu": to_data_uri(thumb),
                         "Examen": n, "Niveau": f"{LEVELS[res.level]['icon']} {res.level.capitalize()} — {LEVELS[res.level]['label']}",
                         "p(maligne)": 100 * float(res.p_malignant), "Confiance": float(res.confidence), "_level": res.level})
    rows.sort(key=lambda r: r["_key"])
    for i, r in enumerate(rows, 1):
        r["Rang"] = i
    keep = st.multiselect("Filtrer par couleur", ["rouge", "orange", "vert"], default=["rouge", "orange", "vert"])
    df = pd.DataFrame([r for r in rows if r["_level"] in keep])
    if df.empty:
        return
    counts = {lv: sum(r["_level"] == lv for r in rows) for lv in ("rouge", "orange", "vert")}
    st.markdown(" · ".join(f"{LEVELS[k]['icon']} **{v}** {k}" for k, v in counts.items()))
    st.dataframe(df[["Rang", "Aperçu", "Examen", "Niveau", "p(maligne)", "Confiance"]], hide_index=True,
                 use_container_width=True, row_height=90,
                 column_config={"Aperçu": st.column_config.ImageColumn(width="small"),
                                "p(maligne)": st.column_config.ProgressColumn(format="%.0f %%", min_value=0, max_value=100),
                                "Confiance": st.column_config.NumberColumn(format="%.2f")})
    st.caption("Inspiré du tri par score de risque évalué dans l'essai MASAI (mammographie, Suède). "
               "SeinSûr n'en a ni l'échelle ni la validation.")


def pct(x):
    return "—" if x is None else f"{x:.0%}"


def page_limites():
    st.title("⚖️ Limites et sources")
    m = load_metrics()
    st.header("Performances mesurées sur le jeu de test")
    if m is None:
        st.info("Les mesures n'ont pas encore été calculées (`scripts/evaluate.py`). Aucun chiffre n'est affiché tant "
                "qu'il n'a pas été mesuré.")
    else:
        st.caption(f"Calculées une seule fois le {m['date']} sur {m['n_test']} images de test jamais vues "
                   f"({', '.join(f'{k} : {v}' for k, v in m['n_test_par_classe'].items())}). Chiffres non arrondis en notre faveur.")
        a = m["alerte_orange_ou_rouge"]
        c = st.columns(4)
        c[0].metric("Sensibilité (malins en orange/rouge)", pct(a["sensibilite_maligne"]))
        c[1].metric("Spécificité correspondante", pct(a["specificite"]))
        c[2].metric("AUC (maligne vs reste)", f"{m['auc_maligne']:.3f}")
        c[3].metric("Dice du contour", "—" if m["dice"] is None else f"{m['dice']:.2f}")
        st.error(f"Cas malins classés **vert** (faux négatifs) sur le test : **{m['malins_classes_vert']}**")
        l, r = st.columns(2)
        with l:
            st.markdown("**Matrice de confusion** (lignes = vérité, colonnes = prédiction)")
            st.dataframe(pd.DataFrame(m["matrice_confusion"], index=CLASSES, columns=CLASSES))
            st.markdown("**Couleur attribuée selon la classe réelle**")
            st.dataframe(pd.DataFrame(m["couleurs_par_classe_reelle"]).T)
        with r:
            st.markdown("**Courbe ROC (maligne vs reste)**")
            st.line_chart(pd.DataFrame({"Taux de vrais positifs": m["roc"]["tpr"]}, index=m["roc"]["fpr"]).rename_axis("Taux de faux positifs"))
            st.caption(f"Calibration (ECE) : {m['ece_avant_calibration']:.3f} avant → {m['ece_apres_calibration']:.3f} après. "
                       f"Seuils fixés sur la validation : orange ≥ {m['seuils']['t_orange']:.0%}, rouge ≥ {m['seuils']['t_red']:.0%}.")
    st.header("Données")
    st.markdown("""
- **BUSI** — Al-Dhabyani W. et al. (2020), *Dataset of breast ultrasound images*, Data in Brief. 780 images, Le Caire (Égypte), 2018, ~600 patientes de 25 à 75 ans.
- Version corrigée **Curated BUSI** (Zenodo) : doublons retirés, étiquettes et masques corrigés. En plus, nos scripts regroupent les images quasi identiques dans le même sous-ensemble.
- Séparation 70 / 15 / 15 stratifiée, graine fixe, faite avant toute augmentation. Le test n'a servi qu'une fois.""")
    st.header("Limites et biais connus")
    st.markdown("""
- **Une seule source** (un pays, un type d'appareil). **Rien ne prouve que le modèle fonctionne sur des patientes burkinabè.**
- Pas d'identifiant de patiente : des images d'une même patiente peuvent se trouver en entraînement et en test → performances probablement **optimistes**.
- Petit jeu de données, déséquilibré (210 malignes sur 780).
- Des études rapportent plus de faux positifs de certains systèmes d'IA en imagerie mammaire chez les femmes noires et les patientes plus âgées.
- Pas de mesure en millimètres (échelle inconnue). La carte Grad-CAM n'indique pas la position exacte de la lésion.""")
    st.header("Usages interdits")
    st.markdown("""
- ❌ Poser un diagnostic ou décider d'un traitement.
- ❌ Usage en pratique clinique : ce prototype **n'est pas un dispositif médical**.
- ❌ Importer des images de patientes réelles sans autorisation, consentement et anonymisation validés.
- ✅ Aucune image n'est conservée ; aucun compte, aucune donnée personnelle.""")
    st.header("Références et inspirations")
    st.markdown("""
- Essai **MASAI** (Université de Lund, *The Lancet*) : triage de mammographies par score de risque assisté par IA.
- **Koios DS Breast** : aide à l'interprétation d'échographies mammaires autorisée par la FDA.
- Selvaraju et al. (2017) Grad-CAM · Ronneberger et al. (2015) U-Net · Tan & Le (2019) EfficientNet.
- OMS : fiches d'information sur le cancer du sein.

*Inspirations conceptuelles : SeinSûr est un prototype de hackathon, sans commune mesure avec des produits validés cliniquement.*""")


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
    st.title("💗 Octobre Rose — s'informer")
    tab1, tab2, tab3 = st.tabs(["Comprendre", "Ressources locales", "Préparer ma consultation"])
    with tab1:
        st.markdown("""
#### Pourquoi en parler ?
Le cancer du sein est l'un des cancers les plus fréquents chez les femmes dans le monde. **Détecté tôt, il se soigne beaucoup mieux.**
*Source : OMS, fiche « Cancer du sein » — chiffres à insérer après vérification (source et année).*

#### Les signes qui doivent amener à consulter
- une boule ou un épaississement dans le sein ou sous le bras ;
- un changement de taille ou de forme du sein ;
- une peau qui se rétracte, rougit ou prend l'aspect d'une peau d'orange ;
- un écoulement anormal du mamelon, ou un mamelon qui se rétracte.

*Source : OMS. La plupart des boules ne sont pas des cancers, mais toute anomalie mérite un avis médical.*

#### Le parcours de soins
Examen clinique → imagerie (échographie, mammographie) → prélèvement si l'image est suspecte → analyse en laboratoire → décision de traitement.""")
    with tab2:
        st.info("Aucune coordonnée n'est affichée avant vérification. Chaque structure porte un badge « Vérifié le … » ou « À confirmer ».")
        res_file = ROOT / "app" / "ressources.json"
        res = json.loads(res_file.read_text(encoding="utf-8")) if res_file.exists() else []
        for r in res:
            with st.container(border=True):
                badge = f"✅ Vérifié le {r['verifie_le']}" if r.get("verifie_le") else "⏳ À confirmer"
                st.markdown(f"**{r['nom']}** — {r.get('ville', '')}  \n{badge}")
                if r.get("verifie_le"):
                    st.write(r.get("contact", ""))
    with tab3:
        st.write("Cochez les questions que vous souhaitez poser, puis imprimez ou enregistrez la liste.")
        chosen = [q for q in QUESTIONS if st.checkbox(q)]
        extra = st.text_area("Mes questions personnelles")
        text = "Mes questions pour la consultation\n\n" + "\n".join(f"- {q}" for q in chosen + [l for l in extra.splitlines() if l.strip()])
        st.download_button("⬇️ Télécharger ma liste", text, file_name="mes_questions.txt")


PAGES = {"🏠 Accueil": page_accueil, "🔬 Analyse": page_analyse, "📋 Liste de priorité": page_priorite,
         "⚖️ Limites et sources": page_limites, "💗 Octobre Rose": page_octobre_rose}

st.markdown(f"<div class='seinsur-banner'>{DISCLAIMER.replace('**', '')}</div>", unsafe_allow_html=True)
_an = get_analyzer()
if _an and "SYNTH" in _an.settings.model_version.upper():
    st.error("🧪 Modèles d'ESSAI entraînés sur des images synthétiques : résultats sans valeur, à ne jamais présenter. "
             "Entraînez sur BUSI (voir README).")
with st.sidebar:
    st.markdown("## 🎗️ SeinSûr")
    page = st.radio("Navigation", list(PAGES), key="page", label_visibility="collapsed")
    st.divider()
    st.caption("Aucune image n'est conservée. Traitement local, sans compte.")
    an = get_analyzer()
    st.caption(f"Modèle : {an.settings.model_version if an else 'absent'}")
PAGES[page]()
