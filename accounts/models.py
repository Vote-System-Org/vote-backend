from django.db import models
from django.contrib.auth.models import User
import random
from django.utils import timezone
from datetime import timedelta


class ListeBlancheReference(models.Model):

    FILIERES = [
        ('MECA',    'Mecatronique'),
        ('GTS', 'Genie telecommunication et systeme'),
        ('BAT',   'Genie civil -Batiments'),
        ('IIA',     'Informatique industriel et automatisme'),
        ('RSI',     'Reseaux et securite informatique'),
        ('GL',      'Génie Logiciel'),
        ('AUTRE',   'Autre'),
    ]
    NIVEAUX = [
        ('L1', 'Licence 1'),
        ('L2', 'Licence 2'),
        ('L3', 'Licence 3'),
        ('M1', 'Master 1'),
        ('M2', 'Master 2'),
    ]

    matricule         = models.CharField(max_length=20, unique=True)
    nom               = models.CharField(max_length=100)
    prenom            = models.CharField(max_length=100)
    email             = models.EmailField(max_length=150, unique=True)
    filiere           = models.CharField(max_length=20, choices=FILIERES)
    niveau            = models.CharField(max_length=5, choices=NIVEAUX)
    a_cree_son_compte = models.BooleanField(default=False)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table            = 'liste_blanche_reference'
        verbose_name        = 'Référence liste blanche'
        verbose_name_plural = 'Références liste blanche'
        ordering            = ['nom', 'prenom']

    def __str__(self):
        return f"{self.matricule} — {self.nom} {self.prenom} ({self.filiere}/{self.niveau})"


class Electeur(models.Model):

    STATUTS = [
        ('EN_ATTENTE', 'En attente de validation'),
        ('ELIGIBLE',   'Eligible'),
        ('SUSPENDU',   'Suspendu'),
    ]

    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='electeur')
    matricule  = models.CharField(max_length=20, unique=True)
    filiere    = models.CharField(max_length=20)
    niveau     = models.CharField(max_length=5)
    statut     = models.CharField(max_length=20, choices=STATUTS, default='EN_ATTENTE')
    a_vote     = models.BooleanField(default=False)
    date_vote  = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table            = 'electeur'
        verbose_name        = 'Électeur'
        verbose_name_plural = 'Électeurs'
        ordering            = ['matricule']

    def __str__(self):
        return f"{self.matricule} — {self.user.get_full_name()} [{self.statut}]"

    def est_eligible_scrutin(self, scrutin):
        from votes.models import ElecteurScrutinVote

        if self.statut != 'ELIGIBLE':
            return False, 'ERR_COMPTE_NON_ELIGIBLE'
        if scrutin.statut != 'OUVERT':
            return False, 'ERR_SCRUTIN_FERME'
        if ElecteurScrutinVote.objects.filter(electeur=self, scrutin=scrutin).exists():
            return False, 'ERR_DOUBLE_VOTE'
        if scrutin.filiere_cible and self.filiere != scrutin.filiere_cible:
            return False, 'ERR_NON_ELIGIBLE'
        if scrutin.niveau_cible and self.niveau != scrutin.niveau_cible:
            return False, 'ERR_NON_ELIGIBLE'

        return True, None





class OTPInscription(models.Model):
    """
    Code OTP temporaire envoyé par email lors de l'inscription.
    Valable 10 minutes. Maximum 3 tentatives.
    """
    matricule   = models.CharField(max_length=20)
    email       = models.EmailField()
    code        = models.CharField(max_length=6)
    tentatives  = models.IntegerField(default=0)
    utilise     = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    expire_at   = models.DateTimeField()

    class Meta:
        db_table     = 'otp_inscription'
        verbose_name = 'OTP Inscription'

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expire_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)

    def est_valide(self):
        return (
            not self.utilise
            and self.tentatives < 3
            and timezone.now() < self.expire_at
        )

    @classmethod
    def generer(cls, matricule, email):
        """Supprime les anciens OTP et génère un nouveau code à 6 chiffres."""
        cls.objects.filter(matricule=matricule, utilise=False).delete()
        code = f"{random.randint(0, 999999):06d}"
        return cls.objects.create(
            matricule = matricule,
            email     = email,
            code      = code,
        )

    def __str__(self):
        return f"OTP {self.matricule} — expire {self.expire_at}"