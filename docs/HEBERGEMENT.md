# Mettre EchoBreast en ligne (Streamlit Community Cloud, gratuit)

Résultat : un lien public, par exemple `https://echobreast.streamlit.app`, que n'importe qui peut ouvrir
depuis n'importe quel pays, sans compte et sans rien installer.

Principe : le code est sur GitHub, mais les modèles (`.pt`, trop lourds pour GitHub) sont rangés dans un
dépôt « modèle » Hugging Face, gratuit. L'application en ligne les télécharge à son premier démarrage.

## Étape 1 : envoyer les modèles sur Hugging Face (une seule fois)

Dans le terminal de VS Code, depuis le dossier du projet, environnement activé :
```
pip install huggingface_hub
python deploy/streamlit/envoyer_modeles.py Lollmoon/echobreast-modeles
```
Vous êtes déjà connectée à Hugging Face : rien ne devrait vous être demandé. Si on vous demande de vous
connecter, choisissez « Log in with your browser », comme la dernière fois.
À la fin, le script affiche `https://huggingface.co/Lollmoon/echobreast-modeles`.

À refaire uniquement si vous ré-entraînez le modèle.

## Étape 2 : envoyer le code sur GitHub

```
git add .
git status
```
Vérifiez dans la liste qu'aucun fichier `.pt`, aucun dossier `env/` et aucun `secrets.toml` n'apparaît
(le fichier `.gitignore` les exclut). Puis :
```
git commit -m "Version en ligne : bandeau de démo, mode Lire d'abord, référence d'examen"
git push
```

## Étape 3 : créer l'application sur Streamlit Cloud (une seule fois)

1. Ouvrez **https://share.streamlit.io** et connectez-vous avec **GitHub** (compte `aliya-ouedraogo`).
   Acceptez que Streamlit accède à vos dépôts.
2. Cliquez sur **Create app**, puis **Deploy a public app from GitHub**.
3. Remplissez :
   - **Repository** : votre dépôt EchoBreast ;
   - **Branch** : `main` ;
   - **Main file path** : `app/app.py` ;
   - **App URL** : par exemple `echobreast` (donnera `echobreast.streamlit.app`, s'il est libre).
4. Cliquez sur **Advanced settings** :
   - **Python version** : `3.12` ;
   - **Secrets** : collez ces lignes (modèle aussi dans `deploy/streamlit/secrets_exemple.toml`) :
     ```
     EB_DEMO = "1"
     EB_MODELS_REPO = "Lollmoon/echobreast-modeles"
     EB_FEEDBACK_URL = ""
     ```
     Quand le questionnaire existera, mettez son lien entre les guillemets de `EB_FEEDBACK_URL`.
5. **Save**, puis **Deploy**. L'installation prend 5 à 10 minutes la première fois, puis le premier
   affichage environ 1 minute de plus (téléchargement des modèles).

## Mettre à jour plus tard

Il suffit de faire `git push` : Streamlit Cloud met l'application à jour tout seul.
Les secrets se modifient dans l'application : **⋮** › **Settings** › **Secrets**.

## À savoir

- **Public** : tout le monde peut ouvrir l'application, et le dépôt de modèles Hugging Face est public
  (les fichiers du modèle sont téléchargeables).
- **Confidentialité** : en ligne, l'image importée est envoyée au serveur pour être analysée. Elle
  n'est pas enregistrée et disparaît à la fermeture de la page. Un bandeau rappelle de n'importer
  aucune image permettant d'identifier une patiente.
- **Mise en veille** : sans visite pendant un moment, l'application s'endort. Le visiteur voit alors un
  bouton pour la réveiller (une à deux minutes). Ouvrez le lien vous-même avant une démo.
- **Mémoire** : l'application utilise environ 1 Go ; Streamlit Cloud en permet au plus 2,7 Go. Si le
  message « This app has gone over its resource limits » apparaît, redémarrez-la (**⋮** › **Reboot app**).
- **En cas d'erreur** : en bas à droite de l'application, **Manage app** affiche le journal. Envoyez-moi
  les dernières lignes.
