# Changelog — VoteSystem Backend

Toutes les modifications notables de ce projet sont documentées ici.
Format basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

---

## [1.0.0] — Juillet 2025

### Ajouté

* Module `accounts` — Gestion des électeurs et liste blanche
* Module `scrutins` — Gestion des scrutins et candidats
* Module `votes` — Vote chiffré RSA 2048 + anonymat garanti
* Module `audit` — Journalisation chaînée SHA-256
* Authentification JWT (access 15min + refresh 7j)
* CAPTCHA anti-bot sur connexion et inscription
* Chiffrement RSA 2048 des bulletins de vote
* Anonymat total — aucune FK entre Vote et Electeur
* Hash chain SHA-256 pour l'intégrité des logs
* Export CSV des résultats
* Envoi emails automatiques via SendGrid

  * Email reçu de vote avec hash SHA-256
  * Email résultats aux candidats à la clôture
* Documentation API Swagger/OpenAPI (drf-spectacular)
* 46 tests automatisés (unitaires + intégration)
* Déploiement sur Render
* Support Cloudinary pour les photos candidats

### Règles de gestion

* RG01 — Anti double vote (UNIQUE constraint + vérification serveur)
* RG02 — Un vote = un candidat
* RG03 — Vote blanc automatique par scrutin
* RG04 — Anonymat total des votes
* RG05 — Cycle de vie des scrutins (BROUILLON → OUVERT → CLOTURE)
* RG06 — Clôture automatique à date_fin
* RG07 — Résultats protégés avant clôture
* RG08 — Profil académique infalsifiable (liste blanche)
* RG09 — Un matricule = un seul compte
* RG10 — Éligibilité vérifiée côté serveur
* RG11 — Candidats non modifiables sur scrutin ouvert
* RG12 — Minimum 1 candidat réel pour ouvrir
* RG13 — Électeur suspendu bloqué
* RG14 — Logs d'audit immuables

### Sécurité

* Protection OWASP Top 10
* Blocage brute force après 5 tentatives
* Protection XSS, CSRF, injection SQL
* Séparation stricte tables Vote et Electeur

---

## [0.3.0] — Juin 2025

### Ajouté

* Endpoint vérification hash public `/public/vote/verification/{hash}/`
* Pagination sur les électeurs et logs d'audit
* Email résultats candidats à la clôture du scrutin
* Champ email optionnel sur le modèle Candidat

### Modifié

* Amélioration du moteur d'éligibilité
* Optimisation des requêtes PostgreSQL

---

## [0.2.0] — Juin 2025

### Ajouté

* Module audit avec hash chain SHA-256
* Export CSV des résultats
* Endpoint résultats temps réel admin
* Gestion des candidats avec photos Cloudinary
* Vote blanc automatique à la création du scrutin

### Modifié

* Amélioration de la sécurité JWT
* Refactoring des serializers

---

## [0.1.0] — Mai 2025

### Ajouté

* Initialisation du projet Django
* Configuration PostgreSQL
* Modèles de base (Electeur, Scrutin, Vote)
* API REST de base
* Authentification JWT
* Déploiement initial sur Render


