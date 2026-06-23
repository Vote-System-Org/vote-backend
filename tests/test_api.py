import pytest
from rest_framework.test import APIClient
from tests.factories import (
    UserFactory, ElecteurFactory, ScrutinFactory,
    CandidatFactory, ListeBlancheFactory
)
from scrutins.models import Scrutin, Candidat


@pytest.mark.django_db
class TestAuthentification:
    """Tests d'intégration — Authentification"""

    def test_captcha_endpoint(self):
        """GET /auth/captcha/ retourne un captcha"""
        client   = APIClient()
        response = client.get('/api/v1/auth/captcha/')
        assert response.status_code == 200
        assert 'captcha_key' in response.data

    def test_inscription_matricule_inconnu(self):
        """ERR_MATRICULE_INCONNU — Matricule absent de la liste blanche"""
        client   = APIClient()
        response = client.post('/api/v1/auth/inscription/', {
            'matricule':        'INCONNU999',
            'email':            'test@test.com',
            'password':         'password123',
            'password_confirm': 'password123',
            'captcha_key':      'test',
            'captcha_value':    'test',
        }, format='json')
        assert response.status_code == 400

    def test_inscription_succes(self):
        """Matricule dans liste blanche — structure validée"""
        lb = ListeBlancheFactory(
            matricule='21GL1234',
            email='etudiant@test.com',
            a_cree_son_compte=False,
        )
        assert lb.matricule == '21GL1234'
        assert lb.a_cree_son_compte == False

    def test_profil_non_authentifie(self):
        """GET /auth/profil/ retourne 401 sans token"""
        client   = APIClient()
        response = client.get('/api/v1/auth/profil/')
        assert response.status_code == 401


@pytest.mark.django_db
class TestScrutinsElecteur:
    """Tests d'intégration — Scrutins électeur"""

    def test_liste_scrutins_non_authentifie(self):
        """GET /electeur/scrutins/ retourne 401 sans token"""
        client   = APIClient()
        response = client.get('/api/v1/electeur/scrutins/')
        assert response.status_code == 401

    def test_liste_scrutins_electeur_eligible(self):
        """Électeur ELIGIBLE voit les scrutins ouverts éligibles"""
        electeur = ElecteurFactory(statut='ELIGIBLE')
        client   = APIClient()
        client.force_authenticate(user=electeur.user)
        ScrutinFactory(statut='OUVERT', filiere_cible=None, niveau_cible=None)
        response = client.get('/api/v1/electeur/scrutins/')
        assert response.status_code == 200

    def test_scrutin_filiere_non_eligible(self):
        """Électeur GL ne voit pas les scrutins RSI"""
        electeur = ElecteurFactory(statut='ELIGIBLE', filiere='GL')
        client   = APIClient()
        client.force_authenticate(user=electeur.user)
        ScrutinFactory(statut='OUVERT', filiere_cible='RSI')
        response = client.get('/api/v1/electeur/scrutins/')
        assert response.status_code == 200
        scrutins = response.data.get('results', response.data)
        for s in scrutins:
            assert s.get('filiere_cible') != 'RSI'


@pytest.mark.django_db
class TestVoteAPI:
    """Tests d'intégration — Vote (RG01, RG04, RG10)"""

    def test_vote_sans_authentification(self):
        """Vote impossible sans authentification"""
        client   = APIClient()
        response = client.post('/api/v1/electeur/vote/', {
            'scrutin_id':  1,
            'candidat_id': 1,
        }, format='json')
        assert response.status_code == 401

    def test_vote_succes(self):
        """RG01 — Vote réussi retourne un reçu hash"""
        electeur = ElecteurFactory(statut='ELIGIBLE')
        scrutin  = ScrutinFactory(statut='OUVERT', filiere_cible=None, niveau_cible=None)
        candidat = CandidatFactory(scrutin=scrutin, est_vote_blanc=False)
        client   = APIClient()
        client.force_authenticate(user=electeur.user)
        response = client.post('/api/v1/electeur/vote/', {
            'scrutin_id':  scrutin.id,
            'candidat_id': candidat.id,
        }, format='json')
        assert response.status_code == 200
        assert 'recu' in response.data.get('data', {})

    def test_double_vote_interdit(self):
        """RG01 — Double vote retourne ERR_DOUBLE_VOTE (409)"""
        electeur = ElecteurFactory(statut='ELIGIBLE')
        scrutin  = ScrutinFactory(statut='OUVERT', filiere_cible=None, niveau_cible=None)
        candidat = CandidatFactory(scrutin=scrutin, est_vote_blanc=False)
        client   = APIClient()
        client.force_authenticate(user=electeur.user)

        client.post('/api/v1/electeur/vote/', {
            'scrutin_id':  scrutin.id,
            'candidat_id': candidat.id,
        }, format='json')

        response = client.post('/api/v1/electeur/vote/', {
            'scrutin_id':  scrutin.id,
            'candidat_id': candidat.id,
        }, format='json')
        assert response.status_code == 409

    def test_vote_scrutin_ferme(self):
        """RG05 — Vote impossible sur scrutin clôturé"""
        electeur = ElecteurFactory(statut='ELIGIBLE')
        scrutin  = ScrutinFactory(statut='CLOTURE')
        candidat = CandidatFactory(scrutin=scrutin)
        client   = APIClient()
        client.force_authenticate(user=electeur.user)
        response = client.post('/api/v1/electeur/vote/', {
            'scrutin_id':  scrutin.id,
            'candidat_id': candidat.id,
        }, format='json')
        assert response.status_code == 403

    def test_vote_electeur_suspendu(self):
        """RG13 — Électeur suspendu ne peut pas voter"""
        electeur = ElecteurFactory(statut='SUSPENDU')
        scrutin  = ScrutinFactory(statut='OUVERT')
        candidat = CandidatFactory(scrutin=scrutin)
        client   = APIClient()
        client.force_authenticate(user=electeur.user)
        response = client.post('/api/v1/electeur/vote/', {
            'scrutin_id':  scrutin.id,
            'candidat_id': candidat.id,
        }, format='json')
        assert response.status_code == 403



@pytest.mark.django_db
class TestAdminAPI:
    """Tests d'intégration — Administration"""

    def test_scrutins_admin_non_authentifie(self):
        """GET /admin/scrutins/ retourne 401 sans token"""
        client   = APIClient()
        response = client.get('/api/v1/admin/scrutins/')
        assert response.status_code == 401

    def test_scrutins_admin_electeur(self):
        """GET /admin/scrutins/ retourne 403 pour un électeur"""
        electeur = ElecteurFactory(statut='ELIGIBLE')
        client   = APIClient()
        client.force_authenticate(user=electeur.user)
        response = client.get('/api/v1/admin/scrutins/')
        assert response.status_code == 403

    def test_creation_scrutin_admin(self):
        """Admin peut créer un scrutin"""
        user   = UserFactory(is_staff=True, is_superuser=True)
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.post('/api/v1/admin/scrutins/', {
            'titre':      'Élection Test',
            'date_debut': '2025-01-01T08:00:00Z',
            'date_fin':   '2025-12-31T18:00:00Z',
        }, format='json')
        assert response.status_code == 201

    def test_resultats_admin(self):
        """Admin peut voir les résultats en temps réel"""
        user    = UserFactory(is_staff=True, is_superuser=True)
        scrutin = ScrutinFactory(statut='OUVERT', created_by=user)
        client  = APIClient()
        client.force_authenticate(user=user)
        response = client.get(f'/api/v1/admin/scrutins/{scrutin.id}/resultats/')
        assert response.status_code == 200
        assert 'nb_votants' in response.data.get('data', {})

    def test_export_csv_admin(self):
        """Admin peut exporter les résultats en CSV"""
        user    = UserFactory(is_staff=True, is_superuser=True)
        scrutin = ScrutinFactory(statut='CLOTURE', created_by=user)
        client  = APIClient()
        client.force_authenticate(user=user)
        response = client.get(f'/api/v1/admin/scrutins/{scrutin.id}/resultats/export/')
        assert response.status_code == 200
        assert 'text/csv' in response.get('Content-Type', '')


@pytest.mark.django_db
class TestResultatsPublics:
    """Tests d'intégration — Résultats publics"""

    def test_resultats_public_scrutin_ouvert(self):
        """RG07 — Résultats non disponibles avant clôture"""
        scrutin  = ScrutinFactory(statut='OUVERT')
        client   = APIClient()
        response = client.get(f'/api/v1/public/scrutins/{scrutin.id}/resultats/')
        assert response.status_code == 404

    def test_resultats_public_scrutin_cloture(self):
        """Résultats disponibles après clôture"""
        scrutin  = ScrutinFactory(statut='CLOTURE')
        client   = APIClient()
        response = client.get(f'/api/v1/public/scrutins/{scrutin.id}/resultats/')
        assert response.status_code == 200

    def test_verification_hash_invalide(self):
        """Hash invalide retourne 404"""
        client   = APIClient()
        response = client.get('/api/v1/public/vote/verification/hashfake123/')
        assert response.status_code == 404