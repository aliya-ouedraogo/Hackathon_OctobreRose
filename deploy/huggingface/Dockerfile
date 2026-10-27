# Image de l'application EchoBreast pour Hugging Face Spaces (SDK Docker, processeur seul).
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/user \
    EB_DEMO=1

# Hugging Face lance le conteneur avec l'utilisateur 1000.
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

# PyTorch en version CPU (bien plus légère, la carte graphique est inutile ici).
# Si l'index CPU de PyTorch ne répond pas, on se rabat sur la version standard de PyPI.
COPY deploy/huggingface/requirements.txt /tmp/requirements.txt
RUN (pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.1 torchvision==0.29.1 \
     || pip install torch==2.14.1 torchvision==0.29.1) \
 && pip install -r /tmp/requirements.txt

COPY --chown=user . .
USER user

EXPOSE 7860
# XSRF et CORS désactivés : nécessaire pour importer une image quand l'application est
# affichée dans la page Hugging Face (cadre intégré).
CMD ["streamlit", "run", "app/app.py", \
     "--server.port=7860", "--server.address=0.0.0.0", "--server.headless=true", \
     "--server.enableXsrfProtection=false", "--server.enableCORS=false"]
