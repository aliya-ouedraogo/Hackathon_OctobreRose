"""Publie EchoBreast sur Hugging Face Spaces, en une commande.

Depuis la racine du projet, environnement activé :
    pip install huggingface_hub
    python deploy/huggingface/publier.py VOTRE_PSEUDO/echobreast
    python deploy/huggingface/publier.py VOTRE_PSEUDO/echobreast --avis https://forms.gle/xxxx

Le script demande votre jeton Hugging Face (droit « Write ») la première fois.
Relancez la même commande après chaque modification : l'application en ligne est mise à jour.
"""
from __future__ import annotations

import argparse
import fnmatch
from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi, login

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

# Ce qui ne part jamais en ligne : environnements, données, historique, archives, brouillons.
EXCLUS = ["env/*", ".venv/*", "venv/*", ".git/*", "data/*", "notebooks/*", "docs/*", "scripts/*",
          "*__pycache__*", "*.pyc", "*.zip", ".ipynb_checkpoints/*", ".vscode/*", ".idea/*", ".DS_Store",
          "README.md", "deploy/huggingface/README.md", "deploy/huggingface/Dockerfile",
          "deploy/huggingface/publier.py"]
OBLIGATOIRES = ["models/classifier.pt", "models/settings.json", "app/app.py"]


def fichiers() -> list[str]:
    # Tout dossier d'environnement Python (quel que soit son nom) est reconnu à son fichier pyvenv.cfg.
    envs = [d.parent for d in ROOT.rglob("pyvenv.cfg")]
    out = []
    for p in sorted(ROOT.rglob("*")):
        if p.is_file() and not any(e in p.parents for e in envs):
            rel = p.relative_to(ROOT).as_posix()
            if not any(fnmatch.fnmatch(rel, motif) for motif in EXCLUS):
                out.append(rel)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("space", help="pseudo/nom-du-space, par exemple blossom/echobreast")
    ap.add_argument("--avis", default="", help="lien du questionnaire (bouton « Donner mon avis »)")
    args = ap.parse_args()

    manquants = [f for f in OBLIGATOIRES if not (ROOT / f).exists()]
    if manquants:
        raise SystemExit(f"Fichiers manquants : {', '.join(manquants)}. Lancez le script depuis le projet complet.")

    api = HfApi()
    try:
        api.whoami()
    except Exception:
        login()
        api = HfApi()

    api.create_repo(args.space, repo_type="space", space_sdk="docker", exist_ok=True, private=False)
    liste = fichiers()
    ops = [CommitOperationAdd(path_in_repo=f, path_or_fileobj=str(ROOT / f)) for f in liste]
    ops += [CommitOperationAdd(path_in_repo="README.md", path_or_fileobj=str(HERE / "README.md")),
            CommitOperationAdd(path_in_repo="Dockerfile", path_or_fileobj=str(HERE / "Dockerfile"))]
    print(f"Envoi de {len(ops)} fichiers (dont les modèles, cela peut prendre quelques minutes)…")
    api.create_commit(args.space, repo_type="space", operations=ops, commit_message="Mise à jour d'EchoBreast")
    if args.avis:
        api.add_space_variable(args.space, "EB_FEEDBACK_URL", args.avis)

    print("\nC'est envoyé. Hugging Face construit maintenant l'application (5 à 10 minutes la première fois).")
    print(f"Suivi de la construction : https://huggingface.co/spaces/{args.space}")
    pseudo, nom = args.space.split("/")
    print(f"Lien à partager : https://{pseudo.lower()}-{nom.lower().replace('_', '-').replace('.', '-')}.hf.space")


if __name__ == "__main__":
    main()
