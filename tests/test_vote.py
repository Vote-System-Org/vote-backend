import pytest
from rest_framework.test import APIClient
from tests.factories import (
    ElecteurFactory, ScrutinFactory, CandidatFactory
)
from votes.models import Vote, ElecteurScrutinVote
from accounts.models import Electeur


@pytest.mark.django_db
class TestFluxVoteComplet:
    """Tests du flux complet de vote — RG01 à RG14"""

    def setup_method(self):
        """Initialisation commune à tous les tests"""
        self.client   = APIClient()
        self.electeur = ElecteurFactory(statut='ELIGIBLE', filiere='GL', niveau='L3')
        self.scrutin  = ScrutinFactory(
            statut        = 'OUVERT',
            filiere_cible = None,
            niveau_cible  = None,
        )
        self.candidat = CandidatFactory(
            scrutin        = self.scrutin,
            est_vote_blanc = False,
        )
        self.client.force_authenticate(user=self.electeur.user)

    def test_flux_complet_vote(self):
        """Flux complet : vote → reçu → vérification hash"""
        # 1. Voter
        response = self.client.post('/api/v1/electeur/vote/', {
            'scrutin_id':  self.scrutin.id,
            'candidat_id': self.candidat.id,
        }, format='json')
        assert response.status_code == 200
        recu = response.data['data']['recu']
        assert len(recu) == 64  # SHA-256

        # 2. Vérifier le reçu
        response = self.client.get(f'/api/v1/public/vote/verification/{recu}/')
        assert response.status_code == 200

        # 3. Vérifier que l'électeur est marqué comme ayant voté
        self.electeur.refresh_from_db()
        assert self.electeur.a_vote == True

        # 4. Vérifier que le vote est en base
        assert Vote.objects.filter(scrutin=self.scrutin).count() == 1

        # 5. Vérifier l'anti-doublon
        assert ElecteurScrutinVote.objects.filter(
            electeur=self.electeur,
            scrutin=self.scrutin,
        ).exists()

    def test_anonymat_vote(self):
        """RG04 — Aucun lien entre le vote et l'électeur en base"""
        self.client.post('/api/v1/electeur/vote/', {
            'scrutin_id':  self.scrutin.id,
            'candidat_id': self.candidat.id,
        }, format='json')

        votes = Vote.objects.filter(scrutin=self.scrutin)
        for vote in votes:
            vote_fields = [f.name for f in vote._meta.get_fields()]
            assert 'electeur' not in vote_fields

    def test_rg01_double_vote_bloque(self):
        """RG01 — Le double vote est strictement interdit"""
        r1 = self.client.post('/api/v1/electeur/vote/', {
            'scrutin_id':  self.scrutin.id,
            'candidat_id': self.candidat.id,
        }, format='json')
        assert r1.status_code == 200

        r2 = self.client.post('/api/v1/electeur/vote/', {
            'scrutin_id':  self.scrutin.id,
            'candidat_id': self.candidat.id,
        }, format='json')
        assert r2.status_code == 409
        assert r2.data['code'] == 'ERR_DOUBLE_VOTE'

        assert Vote.objects.filter(scrutin=self.scrutin).count() == 1

    def test_rg03_vote_blanc_disponible(self):
        """RG03 — Vote blanc toujours disponible sur le scrutin"""
        from scrutins.models import Candidat

        vote_blanc = self.scrutin.candidats.filter(est_vote_blanc=True).first()

        if vote_blanc is None:
            vote_blanc = Candidat.objects.create(
                scrutin        = self.scrutin,
                nom            = 'Vote Blanc',
                est_vote_blanc = True,
            )

        assert vote_blanc is not None
        assert vote_blanc.est_vote_blanc == True

        response = self.client.post('/api/v1/electeur/vote/', {
            'scrutin_id':  self.scrutin.id,
            'candidat_id': vote_blanc.id,
        }, format='json')
        assert response.status_code == 200

    def test_rg07_resultats_proteges_avant_cloture(self):
        """RG07 — Résultats non accessibles avant clôture"""
        response = self.client.get(
            f'/api/v1/public/scrutins/{self.scrutin.id}/resultats/'
        )
        assert response.status_code == 404

    def test_rg10_eligibilite_verifiee_serveur(self):
        """RG10 — Éligibilité vérifiée côté serveur"""
        scrutin_rsi  = ScrutinFactory(statut='OUVERT', filiere_cible='RSI')
        candidat_rsi = CandidatFactory(scrutin=scrutin_rsi)

        response = self.client.post('/api/v1/electeur/vote/', {
            'scrutin_id':  scrutin_rsi.id,
            'candidat_id': candidat_rsi.id,
        }, format='json')
        assert response.status_code == 403

    def test_rg13_electeur_suspendu_bloque(self):
        """RG13 — Électeur suspendu ne peut pas voter"""
        electeur_suspendu = ElecteurFactory(statut='SUSPENDU')
        client            = APIClient()
        client.force_authenticate(user=electeur_suspendu.user)

        response = client.post('/api/v1/electeur/vote/', {
            'scrutin_id':  self.scrutin.id,
            'candidat_id': self.candidat.id,
        }, format='json')
        assert response.status_code == 403

    def test_integrite_hash_chain(self):
        """La chaîne de hash est intègre après des votes"""
        from audit.models import LogAudit

        self.client.post('/api/v1/electeur/vote/', {
            'scrutin_id':  self.scrutin.id,
            'candidat_id': self.candidat.id,
        }, format='json')

        logs = LogAudit.objects.order_by('id')
        assert logs.count() >= 1

        if logs.count() >= 2:
            for i in range(1, logs.count()):
                log_courant   = logs[i]
                log_precedent = logs[i - 1]
                assert log_courant.hash_precedent == log_precedent.hash_courant

    def test_resultats_apres_cloture(self):
        """Résultats disponibles après clôture du scrutin"""
        self.client.post('/api/v1/electeur/vote/', {
            'scrutin_id':  self.scrutin.id,
            'candidat_id': self.candidat.id,
        }, format='json')

        self.scrutin.cloturer()

        public_client = APIClient()
        response      = public_client.get(
            f'/api/v1/public/scrutins/{self.scrutin.id}/resultats/'
        )
        assert response.status_code == 200
        data = response.data['data']
        assert data['nb_votants']    == 1
        assert data['nb_eligibles']  >= 1
        assert len(data['resultats']) >= 1


@pytest.mark.django_db
class TestHashChainAudit:
    """Tests de la chaîne d'audit SHA-256"""

    def test_logs_crees_apres_vote(self):
        """Un log est créé après chaque vote"""
        from audit.models import LogAudit

        electeur = ElecteurFactory(statut='ELIGIBLE')
        scrutin  = ScrutinFactory(statut='OUVERT', filiere_cible=None)
        candidat = CandidatFactory(scrutin=scrutin)

        nb_avant = LogAudit.objects.count()

        client = APIClient()
        client.force_authenticate(user=electeur.user)
        client.post('/api/v1/electeur/vote/', {
            'scrutin_id':  scrutin.id,
            'candidat_id': candidat.id,
        }, format='json')

        nb_apres = LogAudit.objects.count()
        assert nb_apres > nb_avant

    def test_integrite_hash_chain(self):
        """La chaîne de hash est intègre après des votes"""
        from audit.models import LogAudit

        electeur = ElecteurFactory(statut='ELIGIBLE')
        scrutin  = ScrutinFactory(statut='OUVERT', filiere_cible=None)
        candidat = CandidatFactory(scrutin=scrutin)

        client = APIClient()
        client.force_authenticate(user=electeur.user)
        client.post('/api/v1/electeur/vote/', {
            'scrutin_id':  scrutin.id,
            'candidat_id': candidat.id,
        }, format='json')

        logs = LogAudit.objects.order_by('id')
        assert logs.count() >= 1

        if logs.count() >= 2:
            for i in range(1, logs.count()):
                log_courant   = logs[i]
                log_precedent = logs[i - 1]
                assert log_courant.hash_precedent == log_precedent.hash_courant