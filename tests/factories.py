import factory
from django.contrib.auth.models import User
from accounts.models import Electeur, ListeBlancheReference
from scrutins.models import Scrutin, Candidat


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username  = factory.Sequence(lambda n: f'user{n}')
    email     = factory.Sequence(lambda n: f'user{n}@test.com')
    password  = factory.PostGenerationMethodCall('set_password', 'password123')
    is_active = True


class ListeBlancheFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ListeBlancheReference

    matricule          = factory.Sequence(lambda n: f'21GL{n:04d}')
    nom                = factory.Faker('last_name')
    prenom             = factory.Faker('first_name')
    email              = factory.Sequence(lambda n: f'etudiant{n}@univ.cm')
    filiere            = 'GL'
    niveau             = 'L3'
    a_cree_son_compte  = False


class ElecteurFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Electeur

    user     = factory.SubFactory(UserFactory)
    matricule = factory.Sequence(lambda n: f'21GL{n:04d}')
    filiere  = 'GL'
    niveau   = 'L3'
    statut   = 'ELIGIBLE'
    a_vote   = False


class ScrutinFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Scrutin

    titre        = factory.Sequence(lambda n: f'Scrutin {n}')
    description  = 'Scrutin de test'
    date_debut   = factory.Faker('past_datetime', tzinfo=None)
    date_fin     = factory.Faker('future_datetime', tzinfo=None)
    statut       = 'OUVERT'
    filiere_cible = None
    niveau_cible  = None
    created_by   = factory.SubFactory(UserFactory)


class CandidatFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Candidat

    scrutin        = factory.SubFactory(ScrutinFactory)
    nom            = factory.Faker('last_name')
    prenom         = factory.Faker('first_name')
    est_vote_blanc = False