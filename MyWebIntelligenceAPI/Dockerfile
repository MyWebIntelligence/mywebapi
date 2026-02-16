FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

# Définir le répertoire de travail
WORKDIR /app
ENV PYTHONPATH=/app

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    gcc \
    g++ \
    libpq-dev \
    libmagic1 \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de dépendances
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Télécharger les données NLTK (punkt et punkt_tab pour tokenisation)
RUN python -m nltk.downloader punkt punkt_tab || python -m nltk.downloader punkt

# Copier le code de l'application
COPY . .

# Créer les répertoires nécessaires
RUN mkdir -p /data/uploads /data/exports /data/media

# L'image Playwright fournit déjà l'utilisateur non-root `pwuser`
RUN chown -R pwuser:pwuser /app /data

# Utiliser l'utilisateur non-root par défaut
USER pwuser

# Exposer le port
EXPOSE 8000

# Commande par défaut
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
