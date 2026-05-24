# VoteSystem — Documentation API REST

**Version** : 1.0.0
**Base URL** : `https://vote-backend-api.onrender.com/api/v1`
**Documentation interactive** : [https://vote-backend-api.onrender.com/api/docs/](https://vote-backend-api.onrender.com/api/docs/)
**ReDoc** : [https://vote-backend-api.onrender.com/api/docs/redoc/](https://vote-backend-api.onrender.com/api/docs/redoc/)

---

## Authentification

L'API utilise **JWT (JSON Web Token)**. Toute requête protégée doit inclure le header :

```http
Authorization: Bearer {access_token}
```

### Obtenir un token

```http
POST /auth/login/
Content-Type: application/json

{
  "username": "21GL0001",
  "password": "monmotdepasse",
  "captcha_key": "abc123",
  "captcha_value": "XKCD"
}
```

### Réponse

```json
{
  "status": "success",
  "data": {
    "access": "eyJhbGciOiJIUzI1NiJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiJ9...",
    "is_staff": false
  }
}
```

### Renouveler le token

```http
POST /auth/token/refresh/
Content-Type: application/json

{
  "refresh": "eyJhbGciOiJIUzI1NiJ9..."
}
```

---

## Format standard des réponses

### Succès

```json
{
  "status": "success",
  "message": "Description de l'action",
  "data": {}
}
```

### Erreur

```json
{
  "status": "error",
  "code": "ERR_CODE",
  "message": "Description lisible de l'erreur",
  "details": {}
}
```

---

## Codes d'erreur métier

| Code                         | HTTP | Description                                  |
| ---------------------------- | ---- | -------------------------------------------- |
| ERR_MATRICULE_INCONNU        | 400  | Matricule non trouvé dans la liste blanche   |
| ERR_COMPTE_EXISTANT          | 400  | Matricule déjà associé à un compte           |
| ERR_EMAIL_MISMATCH           | 400  | Email ne correspond pas au matricule         |
| ERR_CAPTCHA_INVALIDE         | 400  | Réponse CAPTCHA incorrecte                   |
| ERR_CREDENTIALS_INVALIDES    | 401  | Email ou mot de passe incorrect              |
| ERR_COMPTE_SUSPENDU          | 403  | Compte suspendu par l'administrateur         |
| ERR_NON_ELIGIBLE             | 403  | Électeur hors cible du scrutin               |
| ERR_SCRUTIN_FERME            | 403  | Scrutin non ouvert au moment du vote         |
| ERR_DOUBLE_VOTE              | 409  | L'électeur a déjà voté pour ce scrutin       |
| ERR_SCRUTIN_MODIF_IMPOSSIBLE | 403  | Modification d'un scrutin ouvert/clôturé     |
| ERR_CANDIDAT_VOTE_BLANC      | 403  | Suppression du candidat vote blanc interdite |

---

## Endpoints

### Authentification

| Méthode | Endpoint                  | Auth | Description                                 |
| ------- | ------------------------- | ---- | ------------------------------------------- |
| POST    | `/auth/inscription/`      | Non  | Créer un compte électeur                    |
| POST    | `/auth/login/`            | Non  | Connexion — retourne access + refresh token |
| POST    | `/auth/token/refresh/`    | Non  | Renouveler l'access token                   |
| POST    | `/auth/logout/`           | Oui  | Déconnexion — blackliste le refresh token   |
| GET     | `/auth/captcha/`          | Non  | Obtenir un CAPTCHA                          |
| GET     | `/auth/profil/`           | Oui  | Profil de l'électeur connecté               |
| PUT     | `/auth/profil/`           | Oui  | Modifier l'email de l'électeur              |
| POST    | `/auth/password/reset/`   | Non  | Demande réinitialisation mot de passe       |
| POST    | `/auth/password/confirm/` | Non  | Confirmer réinitialisation avec token       |

---

### Électeur

| Méthode | Endpoint                              | Auth     | Description                   |
| ------- | ------------------------------------- | -------- | ----------------------------- |
| GET     | `/electeur/scrutins/`                 | Électeur | Scrutins ouverts et éligibles |
| GET     | `/electeur/scrutins/clotures/`        | Électeur | Scrutins clôturés éligibles   |
| GET     | `/electeur/scrutins/{id}/candidats/`  | Électeur | Candidats d'un scrutin        |
| GET     | `/electeur/scrutins/{id}/resultats/`  | Électeur | Résultats post-clôture        |
| POST    | `/electeur/vote/`                     | Électeur | Émettre un vote               |
| GET     | `/electeur/vote/confirmation/{hash}/` | Électeur | Vérifier son reçu de vote     |

### Exemple — Émettre un vote

```http
POST /electeur/vote/
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "scrutin_id": 1,
  "candidat_id": 3
}
```

### Réponse

```json
{
  "status": "success",
  "message": "Vote enregistré avec succès.",
  "data": {
    "recu": "0405a7d0ec010afc9797aec3d721751f..."
  }
}
```

---

### Public (sans authentification)

| Méthode | Endpoint                            | Auth | Description                            |
| ------- | ----------------------------------- | ---- | -------------------------------------- |
| GET     | `/public/scrutins/clotures/`        | Non  | Liste des scrutins clôturés            |
| GET     | `/public/scrutins/{id}/resultats/`  | Non  | Résultats publics d'un scrutin clôturé |
| GET     | `/public/vote/verification/{hash}/` | Non  | Vérifier un reçu de vote               |

### Exemple — Résultats publics

```http
GET /public/scrutins/1/resultats/
```

### Réponse

```json
{
  "status": "success",
  "data": {
    "titre": "Élection Délégué GL-L3 2025",
    "nb_eligibles": 15,
    "nb_votants": 12,
    "nb_abstentions": 3,
    "taux_participation": 80.0,
    "resultats": [
      {
        "candidat_id": 1,
        "nom": "DUPONT",
        "prenom": "Jean",
        "nb_voix": 7,
        "pourcentage": 58.3,
        "est_vote_blanc": false
      },
      {
        "candidat_id": 2,
        "nom": "MARTIN",
        "prenom": "Marie",
        "nb_voix": 4,
        "pourcentage": 33.3,
        "est_vote_blanc": false
      },
      {
        "candidat_id": 3,
        "nom": "Vote Blanc",
        "prenom": "",
        "nb_voix": 1,
        "pourcentage": 8.3,
        "est_vote_blanc": true
      }
    ]
  }
}
```

---

### Administration (admin uniquement)

#### Gestion des électeurs

| Méthode | Endpoint                                | Description                                |
| ------- | --------------------------------------- | ------------------------------------------ |
| POST    | `/admin/liste-blanche/import/`          | Importer CSV liste blanche                 |
| GET     | `/admin/electeurs/`                     | Lister les électeurs (filtres disponibles) |
| GET     | `/admin/electeurs/{id}/`                | Détail d'un électeur                       |
| PUT     | `/admin/electeurs/{id}/`                | Modifier email / nom / prénom              |
| PATCH   | `/admin/electeurs/{id}/statut/`         | Changer le statut (ELIGIBLE / SUSPENDU)    |
| DELETE  | `/admin/electeurs/{id}/`                | Supprimer (si a_vote = FALSE)              |
| POST    | `/admin/electeurs/{id}/reset-password/` | Déclencher reset mot de passe              |

#### Gestion des scrutins

| Méthode | Endpoint                                 | Description                      |
| ------- | ---------------------------------------- | -------------------------------- |
| POST    | `/admin/scrutins/`                       | Créer un scrutin                 |
| GET     | `/admin/scrutins/`                       | Lister tous les scrutins         |
| GET     | `/admin/scrutins/{id}/`                  | Détail d'un scrutin              |
| PUT     | `/admin/scrutins/{id}/`                  | Modifier (BROUILLON uniquement)  |
| DELETE  | `/admin/scrutins/{id}/`                  | Supprimer (BROUILLON uniquement) |
| POST    | `/admin/scrutins/{id}/ouvrir/`           | Passer en statut OUVERT          |
| POST    | `/admin/scrutins/{id}/cloturer/`         | Passer en statut CLOTURE         |
| GET     | `/admin/scrutins/{id}/resultats/`        | Résultats temps réel             |
| GET     | `/admin/scrutins/{id}/resultats/export/` | Export CSV des résultats         |

#### Gestion des candidats

| Méthode | Endpoint                 | Description           |
| ------- | ------------------------ | --------------------- |
| POST    | `/admin/candidats/`      | Ajouter un candidat   |
| GET     | `/admin/candidats/`      | Lister les candidats  |
| PUT     | `/admin/candidats/{id}/` | Modifier un candidat  |
| DELETE  | `/admin/candidats/{id}/` | Supprimer un candidat |

#### Audit

| Méthode | Endpoint                  | Description                       |
| ------- | ------------------------- | --------------------------------- |
| GET     | `/admin/audit/logs/`      | Consulter les logs d'audit        |
| GET     | `/admin/audit/integrite/` | Vérifier l'intégrité de la chaîne |

---

## Exemple complet — Intégration React

```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: 'https://vote-backend-api.onrender.com/api/v1',
});

// Intercepteur — ajoute le token JWT automatiquement
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

// Intercepteur — renouvelle le token si expiré
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const refresh = localStorage.getItem('refresh_token');

      if (refresh) {
        const res = await axios.post(
          'https://vote-backend-api.onrender.com/api/v1/auth/token/refresh/',
          { refresh }
        );

        localStorage.setItem('access_token', res.data.access);

        error.config.headers.Authorization = `Bearer ${res.data.access}`;

        return api(error.config);
      }
    }

    return Promise.reject(error);
  }
);

export default api;
```

---

## Sécurité

| Menace            | Mesure                                               |
| ----------------- | ---------------------------------------------------- |
| Brute force       | Blocage après 5 tentatives + CAPTCHA                 |
| Double vote       | Contrainte UNIQUE en base + vérification serveur     |
| Anonymat          | Séparation tables Vote et Electeur — aucune FK       |
| Injection SQL     | ORM Django — aucune requête brute                    |
| XSS               | Échappement automatique React + CSP headers          |
| CSRF              | SameSite=Strict cookie + vérification Origin         |
| Session hijacking | access_token en mémoire + refresh en httpOnly cookie |
| Altération logs   | Hash chain SHA-256                                   |
| Chiffrement votes | RSA 2048                                             |

---

## Stack technique

| Élément              | Technologie                         |
| -------------------- | ----------------------------------- |
| Backend              | Django 4.2 + Django REST Framework  |
| Frontend             | React 18 + Vite + TypeScript        |
| Base de données      | PostgreSQL 15                       |
| Authentification     | JWT (djangorestframework-simplejwt) |
| Chiffrement votes    | RSA 2048                            |
| Stockage photos      | Cloudinary                          |
| Emails               | SendGrid                            |
| Déploiement backend  | Render                              |
| Déploiement frontend | Vercel                              |
| Documentation API    | drf-spectacular (Swagger/OpenAPI)   |

---

*Projet tutoré 2025-2026 — Licence Génie Logiciel*
*KENMATIO Vicens (Backend/Chef) • FOUOGUE Gabriela (Frontend)*
*Encadreur : Ing. KUEDA*

