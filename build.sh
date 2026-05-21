#!/usr/bin/env bash
# Script de build pour Render

set -o errexit  # Arrête le script si une commande échoue

# Installer les dépendances
pip install -r requirements.txt

# Collecter les fichiers statiques
python manage.py collectstatic --no-input

# Appliquer les migrations
python manage.py migrate