# VoteSystem — Backend API

Système de vote électronique sécurisé — Backend Django REST Framework

[![Python](https://img.shields.io/badge/Python-3.10-blue)](https://python.org)
[![Django](https://img.shields.io/badge/Django-4.2-green)](https://djangoproject.com)
[![Tests](https://img.shields.io/badge/Tests-46%20passed-brightgreen)](https://pytest.org)
[![License](https://img.shields.io/badge/License-Academic-orange)](LICENSE)

---

## Présentation

Plateforme de vote électronique sécurisée développée dans le cadre d'un projet tutoré de Licence Génie Logiciel.

|               |                        |
| ------------- | ---------------------- |
| **Backend**   | KENMATIO Vicens        |
| **Frontend**  | FOUOGUE Gabriela       |
| **Encadreur** | Ing. KUEDA             |
| **Promotion** | Licence GL — 2025-2026 |

---

## Stack technique

| Élément           | Technologie                          |
| ----------------- | ------------------------------------ |
| Framework         | Django 4.2 + Django REST Framework   |
| Base de données   | PostgreSQL 15                        |
| Authentification  | JWT (djangorestframework-simplejwt)  |
| Chiffrement votes | RSA 2048                             |
| Emails            | SendGrid                             |
| Stockage photos   | Cloudinary                           |
| Documentation API | drf-spectacular (Swagger/OpenAPI)    |
| Tests             | pytest + pytest-django + factory-boy |
| Déploiement       | Render                               |

---

## URLs de production

| Ressource             | URL                                                                                                            |
| --------------------- | -------------------------------------------------------------------------------------------------------------- |
| API                   | [https://vote-backend-api.onrender.com](https://vote-backend-api.onrender.com)                                 |
| Documentation Swagger | [https://vote-backend-api.onrender.com/api/docs/](https://vote-backend-api.onrender.com/api/docs/)             |
| ReDoc                 | [https://vote-backend-api.onrender.com/api/docs/redoc/](https://vote-backend-api.onrender.com/api/docs/redoc/) |

---

## Installation locale

### Prérequis

* Python 3.10+
* PostgreSQL 15+
* pip

### Étapes

### 1. Cloner le dépôt

```bash
git clone https://github.com/Vote-System-Org/vote-backend.git
cd vote-backend
```

### 2. Créer l'environnement virtuel

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Configurer les variables d'environnement

```bash
cp .env.example .env
# Modifier .env avec vos valeurs
```

### 5. Appliquer les migrations

```bash
python manage.py migrate
```

### 6. Créer un superutilisateur

```bash
python manage.py create_admin
```

### 7. Lancer le serveur

```bash
python manage.py runserver
```

L'API est accessible sur : `http://localhost:8000/api/v1/`

---

## Tests

### Lancer tous les tests

```bash
pytest tests/ -v
```

### Lancer avec couverture

```bash
pytest tests/ -v --cov=. --cov-report=html
```

### Résultats attendus

```text
46 passed in ~37s
```

### Structure des tests

| Fichier                | Description                                    | Tests |
| ---------------------- | ---------------------------------------------- | ----- |
| `tests/test_models.py` | Tests unitaires — modèles et règles de gestion | 15    |
| `tests/test_api.py`    | Tests d'intégration — endpoints API            | 20    |
| `tests/test_vote.py`   | Tests flux complet de vote                     | 11    |

---

## Architecture du projet

```text
vote-backend/
├── config/                 # Configuration Django
│   ├── settings.py         # Paramètres de l'application
│   ├── urls.py             # Routes principales
│   └── wsgi.py             # Point d'entrée WSGI
├── accounts/               # Module électeurs
│   ├── models.py           # Electeur, ListeBlancheReference
│   ├── views.py            # API authentification
│   └── serializers.py
├── scrutins/               # Module scrutins + candidats
│   ├── models.py           # Scrutin, Candidat
│   ├── views.py            # API scrutins
│   └── serializers.py
├── votes/                  # Module vote
│   ├── models.py           # Vote, ElecteurScrutinVote
│   └── views.py            # API vote
├── audit/                  # Module audit
│   ├── models.py           # LogAudit
│   └── services.py         # Hash chain SHA-256
├── tests/                  # Tests automatisés
│   ├── factories.py        # Factories de test
│   ├── test_models.py      # Tests unitaires
│   ├── test_api.py         # Tests d'intégration
│   └── test_vote.py        # Tests flux vote
├── requirements.txt        # Dépendances Python
├── pytest.ini              # Configuration pytest
├── .env.example            # Variables d'environnement (modèle)
└── API_DOCUMENTATION.md    # Documentation API complète
```

---

## Règles de gestion implémentées

| ID   | Règle                                             | Test |
| ---- | ------------------------------------------------- | ---- |
| RG01 | Un électeur ne vote qu'une seule fois par scrutin | ✅    |
| RG02 | Un vote correspond à exactement un candidat       | ✅    |
| RG03 | Le vote blanc est toujours disponible             | ✅    |
| RG04 | Les votes sont strictement anonymes               | ✅    |
| RG05 | Le scrutin peut être ouvert ou fermé              | ✅    |
| RG06 | Clôture automatique à date_fin                    | ✅    |
| RG07 | Résultats protégés avant clôture                  | ✅    |
| RG08 | Profil académique infalsifiable                   | ✅    |
| RG09 | Un matricule = un seul compte                     | ✅    |
| RG10 | Éligibilité vérifiée côté serveur                 | ✅    |
| RG11 | Aucun candidat modifiable sur scrutin ouvert      | ✅    |
| RG12 | Minimum 1 candidat réel pour ouvrir               | ✅    |
| RG13 | Électeur suspendu ne peut pas voter               | ✅    |
| RG14 | Logs d'audit immuables                            | ✅    |

---

## Sécurité

| Menace            | Mesure                                           |
| ----------------- | ------------------------------------------------ |
| Double vote       | Contrainte UNIQUE en base + vérification serveur |
| Anonymat          | Séparation tables Vote et Electeur — aucune FK   |
| Injection SQL     | ORM Django — aucune requête brute                |
| XSS               | Échappement automatique Django                   |
| CSRF              | SameSite=Strict cookie                           |
| Brute force       | Blocage après 5 tentatives + CAPTCHA             |
| Altération logs   | Hash chain SHA-256                               |
| Chiffrement votes | RSA 2048                                         |

---

## Contribution

```bash
# Créer une branche feature
git checkout -b feature/ma-fonctionnalite

# Développer et tester
pytest tests/ -v

# Merger via develop
git checkout develop
git merge feature/ma-fonctionnalite
git push origin develop
```

---

*Projet tutoré 2025-2026 — Université — Filière Génie Logiciel*

✅
