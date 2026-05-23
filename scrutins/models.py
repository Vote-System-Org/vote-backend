from django.db import models
from django.contrib.auth.models import User


class Scrutin(models.Model):

    STATUTS = [
        ('BROUILLON', 'Brouillon'),
        ('OUVERT',    'Ouvert'),
        ('CLOTURE',   'Clôturé'),
    ]

    titre         = models.CharField(max_length=200)
    description   = models.TextField(blank=True, null=True)
    date_debut    = models.DateTimeField()
    date_fin      = models.DateTimeField()
    statut        = models.CharField(max_length=20, choices=STATUTS, default='BROUILLON')
    filiere_cible = models.CharField(max_length=20, blank=True, null=True)
    niveau_cible  = models.CharField(max_length=5, blank=True, null=True)
    created_by    = models.ForeignKey(User, on_delete=models.PROTECT, related_name='scrutins_crees')
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table            = 'scrutin'
        verbose_name        = 'Scrutin'
        verbose_name_plural = 'Scrutins'
        ordering            = ['-created_at']

    def __str__(self):
        return f"{self.titre} [{self.statut}]"

    def est_ouvert(self):
        return self.statut == 'OUVERT'

    def get_nb_eligibles(self):
        from accounts.models import Electeur
        qs = Electeur.objects.filter(statut='ELIGIBLE')
        if self.filiere_cible:
            qs = qs.filter(filiere=self.filiere_cible)
        if self.niveau_cible:
            qs = qs.filter(niveau=self.niveau_cible)
        return qs.count()

    def ouvrir(self):
        if self.statut != 'BROUILLON':
            raise ValueError('Seul un scrutin en BROUILLON peut être ouvert.')
        if not self.candidats.filter(est_vote_blanc=False).exists():
            raise ValueError('Le scrutin doit avoir au moins 1 candidat réel (RG12).')
        self.statut = 'OUVERT'
        self.save()

    def cloturer(self):
        if self.statut != 'OUVERT':
            raise ValueError('Seul un scrutin OUVERT peut être clôturé.')
        self.statut = 'CLOTURE'
        self.save()

    def get_resultats(self):
        from votes.models import Vote, ElecteurScrutinVote
        nb_eligibles  = self.get_nb_eligibles()
        nb_votants    = ElecteurScrutinVote.objects.filter(scrutin=self).count()
        taux_particip = round((nb_votants / nb_eligibles * 100), 2) if nb_eligibles > 0 else 0

        resultats_candidats = []
        for candidat in self.candidats.all():
            nb_voix = Vote.objects.filter(scrutin=self, candidat=candidat).count()
            resultats_candidats.append({
                'candidat_id':    candidat.id,
                'nom':            candidat.nom,
                'prenom':         candidat.prenom,
                'est_vote_blanc': candidat.est_vote_blanc,
                'nb_voix':        nb_voix,
                'pourcentage':    round((nb_voix / nb_votants * 100), 2) if nb_votants > 0 else 0,
            })

        return {
            'scrutin_id':         self.id,
            'titre':              self.titre,
            'statut':             self.statut,
            'nb_eligibles':       nb_eligibles,
            'nb_votants':         nb_votants,
            'nb_abstentions':     nb_eligibles - nb_votants,
            'taux_participation': taux_particip,
            'resultats':          resultats_candidats,
        }


class Candidat(models.Model):

    scrutin        = models.ForeignKey(Scrutin, on_delete=models.CASCADE, related_name='candidats')
    nom            = models.CharField(max_length=100)
    prenom         = models.CharField(max_length=100, blank=True, null=True)
    email        = models.EmailField(max_length=150, blank=True, null=True)
    photo          = models.ImageField(upload_to='candidats/', blank=True, null=True)
    programme      = models.TextField(blank=True, null=True)
    est_vote_blanc = models.BooleanField(default=False)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table            = 'candidat'
        verbose_name        = 'Candidat'
        verbose_name_plural = 'Candidats'
        ordering            = ['est_vote_blanc', 'nom']

    def __str__(self):
        if self.est_vote_blanc:
            return f"[Vote Blanc] — Scrutin: {self.scrutin.titre}"
        return f"{self.nom} {self.prenom or ''} — Scrutin: {self.scrutin.titre}"