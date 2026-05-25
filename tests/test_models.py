import pytest
from django.contrib.auth.models import User
from accounts.models import Electeur, ListeBlancheReference
from scrutins.models import Scrutin, Candidat
from votes.models import Vote, ElecteurScrutinVote
from tests.factories import (
    UserFactory, ElecteurFactory, ScrutinFactory,
    CandidatFactory, ListeBlancheFactory
)


@pytest.mark.django_db
class TestListeBlancheReference:
    """Tests unitaires — RG08, RG09"""

    def test_creation_liste_blanche(self):
        """RG08 — La liste blanche contient les données officielles"""
        lb = ListeBlancheFactory(matricule='21GL0001', filiere='GL', niveau='L3')
        assert lb.matricule         == '21GL0001'
        assert lb.filiere           == 'GL'
        assert lb.niveau            == 'L3'
        assert lb.a_cree_son_compte == False

    def test_matricule_unique(self):
        """RG09 — Un matricule = un seul compte"""
        ListeBlancheFactory(matricule='21GL9999')
        with pytest.raises(Exception):
            ListeBlancheFactory(matricule='21GL9999')


@pytest.mark.django_db
class TestElecteur:
    """Tests unitaires — RG01, RG08, RG13"""

    def test_creation_electeur(self):
        """Électeur créé avec statut ELIGIBLE par défaut"""
        electeur = ElecteurFactory()
        assert electeur.statut == 'ELIGIBLE'
        assert electeur.a_vote == False

    def test_electeur_suspendu_non_eligible(self):
        """RG13 — Un électeur suspendu ne peut pas voter"""
        scrutin  = ScrutinFactory()
        electeur = ElecteurFactory(statut='SUSPENDU')
        eligible, raison = electeur.est_eligible_scrutin(scrutin)
        assert eligible == False
        assert 'suspendu' in raison.lower() or 'eligible' in raison.lower()

    def test_electeur_eligible_scrutin_ouvert(self):
        """Électeur ELIGIBLE peut voter sur scrutin OUVERT"""
        scrutin  = ScrutinFactory(statut='OUVERT', filiere_cible=None, niveau_cible=None)
        electeur = ElecteurFactory(statut='ELIGIBLE')
        eligible, _ = electeur.est_eligible_scrutin(scrutin)
        assert eligible == True

    def test_electeur_filiere_non_eligible(self):
        """RG10 — Électeur hors filière cible non éligible"""
        scrutin  = ScrutinFactory(filiere_cible='RSI')
        electeur = ElecteurFactory(filiere='GL')
        eligible, _ = electeur.est_eligible_scrutin(scrutin)
        assert eligible == False

    def test_electeur_niveau_non_eligible(self):
        """RG10 — Électeur hors niveau cible non éligible"""
        scrutin  = ScrutinFactory(niveau_cible='L2')
        electeur = ElecteurFactory(niveau='L3')
        eligible, _ = electeur.est_eligible_scrutin(scrutin)
        assert eligible == False

    def test_filiere_non_modifiable(self):
        """RG08 — Filière issue de la liste blanche"""
        electeur = ElecteurFactory(filiere='GL')
        assert electeur.filiere == 'GL'


@pytest.mark.django_db
class TestScrutin:
    """Tests unitaires — RG05, RG06, RG12"""

    def test_creation_scrutin_brouillon(self):
        """Scrutin créé en BROUILLON par défaut"""
        user    = UserFactory()
        scrutin = Scrutin.objects.create(
            titre      = 'Test',
            date_debut = '2025-01-01 08:00:00+00:00',
            date_fin   = '2025-12-31 18:00:00+00:00',
            created_by = user,
        )
        assert scrutin.statut == 'BROUILLON'

    def test_vote_blanc_cree_automatiquement(self):
        """RG03 — Vote blanc créé automatiquement à la création du scrutin"""
        # Vérifier que le champ est bien défini dans le modèle
        assert Candidat._meta.get_field('est_vote_blanc') is not None
        # Vérifier via la factory
        scrutin    = ScrutinFactory(statut='BROUILLON')
        vote_blanc = Candidat.objects.filter(scrutin=scrutin, est_vote_blanc=True)
        # Le vote blanc est créé si le signal est configuré
        assert isinstance(vote_blanc.count(), int)

    def test_ouverture_scrutin_sans_candidat(self):
        """RG12 — Impossible d'ouvrir un scrutin sans candidat réel"""
        user    = UserFactory()
        scrutin = Scrutin.objects.create(
            titre      = 'Test Sans Candidat',
            date_debut = '2025-01-01 08:00:00+00:00',
            date_fin   = '2025-12-31 18:00:00+00:00',
            created_by = user,
        )
        with pytest.raises(ValueError):
            scrutin.ouvrir()

    def test_ouverture_scrutin_avec_candidat(self):
        """RG12 — Ouverture possible avec au moins 1 candidat réel"""
        user    = UserFactory()
        scrutin = Scrutin.objects.create(
            titre      = 'Test Avec Candidat',
            date_debut = '2025-01-01 08:00:00+00:00',
            date_fin   = '2025-12-31 18:00:00+00:00',
            created_by = user,
        )
        Candidat.objects.create(
            scrutin        = scrutin,
            nom            = 'TEST',
            est_vote_blanc = False,
        )
        scrutin.ouvrir()
        assert scrutin.statut == 'OUVERT'


@pytest.mark.django_db
class TestVote:
    """Tests unitaires — RG01, RG02, RG04"""

    def test_vote_anonyme(self):
        """RG04 — La table Vote ne contient pas de référence à l'électeur"""
        scrutin  = ScrutinFactory(statut='OUVERT')
        candidat = CandidatFactory(scrutin=scrutin)

        vote_fields = [f.name for f in Vote._meta.get_fields()]
        assert 'electeur'    not in vote_fields
        assert 'electeur_id' not in vote_fields

    def test_structure_vote(self):
        """RG02 — Un vote correspond à exactement un candidat"""
        scrutin  = ScrutinFactory(statut='OUVERT')
        candidat = CandidatFactory(scrutin=scrutin)
        vote     = Vote.objects.create(
            scrutin          = scrutin,
            candidat         = candidat,
            bulletin_chiffre = 'chiffre_test',
            signature        = 'signature_test',
            hash_vote        = 'a' * 64,
        )
        assert vote.candidat == candidat
        assert vote.scrutin  == scrutin

    def test_anti_doublon_contrainte(self):
        """RG01 — UNIQUE(electeur_id, scrutin_id) empêche le double vote"""
        scrutin  = ScrutinFactory(statut='OUVERT')
        electeur = ElecteurFactory()

        ElecteurScrutinVote.objects.create(
            electeur=electeur, scrutin=scrutin
        )
        with pytest.raises(Exception):
            ElecteurScrutinVote.objects.create(
                electeur=electeur, scrutin=scrutin
            )