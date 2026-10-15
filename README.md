# 🎗️ SeinSûr

Aide à la **priorisation** des échographies mammaires (jeu public BUSI) — prototype du hackathon
« Technologies et IA contre le cancer du sein », Octobre Rose.

> **Outil d'information et d'orientation, pas un diagnostic.** Non validé cliniquement, n'est pas un dispositif médical.

## Ce que fait le prototype

| ID | Fonction | Où |
|---|---|---|
| F1–F2 | Import + prétraitement + contrôles qualité | `seinsur/core.py` |
| F3 | Classification normale / bénigne / maligne (EfficientNet-B0) | `scripts/train_classifier.py` |
| F4 | Contour de la zone suspecte (U-Net ResNet34) | `scripts/train_segmentation.py` |
| F5, F7 | Code couleur prudent + indicateur de confiance | `seinsur/core.py` (`risk_level`) |
| F6 | Grad-CAM | `seinsur/inference.py` |
| F8 | Liste de priorité | page « Liste de priorité » |
| F9 | Fiche PDF | `seinsur/report.py` |
| F10 | Cas de démo (dont un cas d'erreur) | générés par `scripts/evaluate.py` |
| F11–F15 | Accueil, Octobre Rose, ressources, consultation, Limites et sources | `app/app.py` |

Règle de couleur : **rouge** si p(maligne) ≥ `t_red` ; **orange** si p(maligne) ≥ `t_orange` *ou* confiance faible ;
**vert** sinon. `t_orange` est fixé sur la validation pour atteindre ≥ 95 % de sensibilité sur les malins.

## Arborescence

```
seinsur/      code partagé (prétraitement, modèles, règle de couleur, PDF)
scripts/      préparation des données, entraînement, évaluation
app/          application Streamlit (+ app/demo/ généré)
models/       classifier.pt, segmenter.pt, settings.json, metrics.json
docs/PITCH.md script minuté du pitch de 5 min
```

## 0. Tester sur son ordinateur (VS Code conseillé)

Prérequis : **Python 3.10 à 3.12** (python.org) et VS Code avec l'extension « Python ».

```bash
# Dans le terminal de VS Code, dossier seinsur ouvert
python -m venv .venv
# Windows :  .venv\Scripts\activate      Mac/Linux :  source .venv/bin/activate
pip install -r requirements.txt          # ~2 Go, 5 à 15 min
```

Test technique sans les vraies données (≈ 5 min, fausses images, modèles marqués « SYNTHÉTIQUE ») :

```bash
# Mac/Linux :
bash scripts/smoke_test.sh
# Windows (une ligne après l'autre) :
python scripts/make_synthetic_data.py --out data/synthetic_busi
python scripts/prepare_data.py --src data/synthetic_busi
python scripts/train_classifier.py --no-pretrained --epochs-head 1 --epochs-ft 12 --patience 12 --batch 16 --workers 0
python scripts/train_segmentation.py --no-pretrained --epochs 10 --patience 10 --batch 8 --workers 0
python scripts/evaluate.py --version-label "SYNTHETIQUE - test technique"

streamlit run app/app.py                 # ouvre http://localhost:8501
```

## 1. Entraîner (Google Colab ou Kaggle, GPU) — ~30 min

Le plus simple : ouvrir `notebooks/entrainement_colab.ipynb` dans Colab. Ou à la main :

```bash
git clone <votre-depot> seinsur && cd seinsur
pip install -r requirements.txt
# Télécharger Curated BUSI (Zenodo) ou BUSI d'origine, puis :
python scripts/prepare_data.py --src /chemin/Dataset_BUSI_with_GT
python scripts/train_classifier.py --arch efficientnet_b0      # ~10 min sur GPU
python scripts/train_segmentation.py --encoder resnet34         # ~15 min sur GPU
python scripts/evaluate.py                                      # calibration, seuils, mesures TEST, cas de démo
```

Récupérer ensuite `models/*.pt`, `models/settings.json`, `models/metrics.json` et `app/demo/`
(modèles ≈ 16 Mo + 100 Mo ; utiliser Git LFS ou les déposer sur Hugging Face).

⚠️ `evaluate.py` mesure sur le **test** : ne le relancer qu'une fois les modèles figés. Pour régler le modèle,
regarder uniquement les scores de validation affichés pendant l'entraînement.

> Pour vérifier que tout fonctionne **sans** les vraies données :
> `python scripts/make_synthetic_data.py --out data/synthetic_busi` puis `prepare_data.py --src data/synthetic_busi`
> et les scripts d'entraînement avec `--no-pretrained --epochs…` réduits. Ces faux résultats ne doivent jamais être présentés.

## 2. Lancer l'application (CPU, en local)

```bash
pip install -r requirements.txt
streamlit run app/app.py
```

Déploiement gratuit : Streamlit Community Cloud ou Hugging Face Spaces (SDK Streamlit). Garder la version locale
et une vidéo de secours pour le jour J.

## Plan de repli (voir doc de conception §13)

- Contour peu fiable → ne pas livrer `segmenter.pt` : l'app n'affiche alors pas de contour et Grad-CAM sert d'explication.
- Classification faible → annoncer honnêtement les chiffres (page « Limites et sources »).

## Références

Al-Dhabyani et al. (2020) BUSI · Curated BUSI (Zenodo) · Essai MASAI (The Lancet) · Selvaraju et al. (2017) Grad-CAM ·
Ronneberger et al. (2015) U-Net · Tan & Le (2019) EfficientNet · OMS, fiches cancer du sein.
