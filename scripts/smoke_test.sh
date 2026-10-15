#!/usr/bin/env bash
# Test de bout en bout SANS les vraies données (≈ 5 min sur CPU).
# Génère de fausses images, entraîne des modèles d'essai, évalue, puis lancez l'app.
# Les modèles produits sont marqués « SYNTHÉTIQUE » et ne doivent jamais être présentés.
set -e
cd "$(dirname "$0")/.."
python scripts/make_synthetic_data.py --out data/synthetic_busi
python scripts/prepare_data.py --src data/synthetic_busi
python scripts/train_classifier.py --no-pretrained --epochs-head 1 --epochs-ft 12 --patience 12 --batch 16 --workers 0
python scripts/train_segmentation.py --no-pretrained --epochs 10 --patience 10 --batch 8 --workers 0
python scripts/evaluate.py --version-label "SYNTHÉTIQUE - test technique"
echo "OK. Lancez maintenant :  streamlit run app/app.py"
