"""Envoie les modèles et les cas de démonstration dans un dépôt « modèle » Hugging Face (gratuit).

La version en ligne d'EchoBreast (Streamlit Cloud) les télécharge au démarrage, car les fichiers .pt
sont trop lourds pour GitHub.

Depuis la racine du projet, environnement activé :
    pip install huggingface_hub
    python deploy/streamlit/envoyer_modeles.py VOTRE_PSEUDO/echobreast-modeles

Relancez-le seulement si vous ré-entraînez le modèle.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi, login

ROOT = Path(__file__).resolve().parents[2]
FICHIERS = ["models/classifier.pt", "models/segmenter.pt", "models/settings.json", "models/metrics.json"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("depot", help="pseudo/nom-du-depot, par exemple Lollmoon/echobreast-modeles")
    args = ap.parse_args()

    liste = [f for f in FICHIERS if (ROOT / f).exists()]
    if "models/classifier.pt" not in liste:
        raise SystemExit("models/classifier.pt introuvable : lancez le script depuis le projet, avec votre modèle entraîné.")
    demo = ROOT / "app" / "demo"
    liste += [p.relative_to(ROOT).as_posix() for p in sorted(demo.glob("*")) if p.is_file()]

    api = HfApi()
    try:
        api.whoami()
    except Exception:
        login()
        api = HfApi()
    api.create_repo(args.depot, repo_type="model", exist_ok=True, private=False)
    ops = [CommitOperationAdd(path_in_repo=f, path_or_fileobj=str(ROOT / f)) for f in liste]
    print(f"Envoi de {len(ops)} fichiers (le segmenteur pèse environ 100 Mo, patience)…")
    api.create_commit(args.depot, operations=ops, commit_message="Modèles et cas de démonstration EchoBreast")
    print(f"\nC'est envoyé : https://huggingface.co/{args.depot}")
    print(f'Dans les secrets Streamlit Cloud, écrivez : EB_MODELS_REPO = "{args.depot}"')


if __name__ == "__main__":
    main()
