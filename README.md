# vote-backend
API Django du système de vote


# 🗳️ Vote Électronique Sécurisé — Backend Django

## Stack
- **Django 4.2** + **Django REST Framework 3.15**
- **PostgreSQL 15**
- **JWT** (djangorestframework-simplejwt)
- **RSA 2048** (PyCryptodome)
- **Celery** + Redis (clôture automatique)

---

## ⚡ Installation rapide

```bash
# 1. Cloner et entrer dans le projet
cd vote_backend

# 2. Environnement virtuel
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Dépendances
pip install -r requirements.txt

# 4. Variables d'environnement
cp .env.example .env
# → Éditer .env avec vos valeurs

# 5. Générer les clés RSA 2048
mkdir keys
python manage.py shell -c "from utils.rsa_service import RSAVoteService; RSAVoteService.generer_cles()"

# 6. Base de données
createdb vote_electronique_db   # PostgreSQL
python manage.py migrate

# 7. Superuser admin
python manage.py createsuperuser

# 8. Lancer le serveur
python manage.py runserver
```

---

## 🔑 Endpoints API

### Authentification (`/api/auth/`)
| Méthode | URL | Description |
|---------|-----|-------------|
| `POST` | `/api/auth/inscription/` | Inscription via liste blanche |
| `POST` | `/api/auth/login/` | Connexion (JWT + CAPTCHA) |
| `POST` | `/api/auth/logout/` | Déconnexion (blacklist token) |
| `POST` | `/api/auth/token/refresh/` | Rafraîchir l'access token |
| `GET`  | `/api/auth/captcha/` | Générer un CAPTCHA |
| `GET/PUT` | `/api/auth/profil/` | Mon profil |

### Électeur (`/api/electeur/`)
| Méthode | URL | Description |
|---------|-----|-------------|
| `GET`  | `/api/electeur/scrutins/` | Mes scrutins éligibles |
| `GET`  | `/api/electeur/scrutins/{id}/candidats/` | Candidats d'un scrutin |
| `POST` | `/api/electeur/vote/` | **Voter** |
| `GET`  | `/api/electeur/vote/confirmation/{hash}/` | Vérifier mon reçu |
| `GET`  | `/api/electeur/scrutins/{id}/resultats/` | Résultats (après clôture) |

### Admin (`/api/admin/`)
| Méthode | URL | Description |
|---------|-----|-------------|
| `POST` | `/api/admin/liste-blanche/import/` | Importer CSV |
| `GET`  | `/api/admin/liste-blanche/` | Lister la liste blanche |
| `GET/PUT/DELETE` | `/api/admin/electeurs/{id}/` | Gérer électeurs |
| `PATCH`| `/api/admin/electeurs/{id}/statut/` | Changer statut |
| `POST` | `/api/admin/scrutins/` | Créer un scrutin |
| `POST` | `/api/admin/scrutins/{id}/ouvrir/` | Ouvrir |
| `POST` | `/api/admin/scrutins/{id}/cloturer/` | Clôturer |
| `GET`  | `/api/admin/scrutins/{id}/resultats/` | Résultats temps réel |
| `GET`  | `/api/admin/scrutins/{id}/resultats/export/` | Export CSV |
| `GET`  | `/api/admin/audit/logs/` | Logs d'audit |
| `GET`  | `/api/admin/audit/integrite/` | Vérifier hash chain |

### Public (`/api/public/`)
| Méthode | URL | Description |
|---------|-----|-------------|
| `GET` | `/api/public/scrutins/{id}/resultats/` | Résultats publics |

---

## 🚀 Celery (clôture automatique)

```bash
# Terminal 1 — Worker Celery
celery -A config worker --loglevel=info

# Terminal 2 — Beat Scheduler (toutes les 60s)
celery -A config beat --loglevel=info
```

---

## 🗂️ Structure du projet

```
vote_backend/
├── config/
│   ├── settings.py       # Configuration Django
│   ├── urls.py           # Routes principales
│   ├── celery.py         # Config Celery
│   └── wsgi.py
├── apps/
│   ├── accounts/         # M1+M2 : Électeurs + Auth
│   │   ├── models.py     # ListeBlancheReference, Electeur
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py       # /api/auth/
│   │   └── urls_admin.py # /api/admin/electeurs/
│   ├── scrutins/         # M3+M4 : Scrutins + Candidats
│   │   ├── models.py     # Scrutin, Candidat
│   │   ├── views.py
│   │   ├── tasks.py      # Celery : clôture auto
│   │   ├── urls_admin.py
│   │   ├── urls_electeur.py
│   │   └── urls_public.py
│   ├── votes/            # M5 : Vote sécurisé
│   │   ├── models.py     # Vote (anonyme), ElecteurScrutinVote
│   │   ├── views.py      # VoteView (RSA 2048)
│   │   └── urls.py
│   └── audit/            # M6 : Audit + Résultats
│       ├── models.py     # LogAudit (hash chain)
│       ├── services.py   # AuditService
│       └── views.py
├── utils/
│   ├── permissions.py    # IsAdmin, IsElecteur
│   ├── exceptions.py     # Format erreur standard
│   └── rsa_service.py    # RSA 2048 chiffrement
├── keys/
│   ├── private.pem       # ⚠️ NE PAS COMMITER
│   └── public.pem
├── manage.py
├── requirements.txt
└── .env.example
```

---

## 🔒 Sécurité — Points clés

| Règle | Implémentation |
|-------|---------------|
| **RG01** Anti-doublon | `UNIQUE(electeur_id, scrutin_id)` dans `ElecteurScrutinVote` |
| **RG04** Anonymat | Table `vote` sans FK vers `electeur` |
| **RG06** Clôture auto | Celery Beat toutes les 60 secondes |
| **RG08** Profil infalsifiable | `filiere`/`niveau` copiés depuis liste blanche, non exposés |
| **RG10** Éligibilité serveur | `Electeur.est_eligible_scrutin()` appelé avant chaque vote |
| **RG14** Logs immuables | Hash chain SHA-256 dans `LogAudit` |
