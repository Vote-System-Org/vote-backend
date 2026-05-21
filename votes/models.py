from django.db import models
from scrutins.models import Scrutin, Candidat


class Vote(models.Model):
    """
    Bulletin de vote anonyme.
    RÈGLE ABSOLUE (RG04) : Aucune référence vers la table Electeur.
    """
    scrutin          = models.ForeignKey(Scrutin,  on_delete=models.PROTECT, related_name='votes')
    candidat         = models.ForeignKey(Candidat, on_delete=models.PROTECT, related_name='votes_recus')
    bulletin_chiffre = models.TextField()
    signature        = models.TextField()
    hash_vote        = models.CharField(max_length=64)
    created_at       = models.DateTimeField(auto_now_add=True)

    # !! PAS DE electeur_id !! — Anonymat garanti (RG04)

    class Meta:
        db_table            = 'vote'
        verbose_name        = 'Vote'
        verbose_name_plural = 'Votes'

    def __str__(self):
        return f"Vote #{self.id} — Scrutin: {self.scrutin.titre} — Hash: {self.hash_vote[:16]}..."


class ElecteurScrutinVote(models.Model):
    """
    Table anti-doublon (RG01).
    Enregistre QUI a voté à QUEL scrutin — sans révéler POUR QUI.
    """
    electeur  = models.ForeignKey('accounts.Electeur', on_delete=models.PROTECT,
                                   related_name='participations')
    scrutin   = models.ForeignKey(Scrutin, on_delete=models.PROTECT,
                                   related_name='participations')
    date_vote = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'electeur_scrutin_vote'
        unique_together = ('electeur', 'scrutin')  # Contrainte anti-doublon (RG01)
        verbose_name        = 'Participation électeur'
        verbose_name_plural = 'Participations électeurs'

    def __str__(self):
        return f"Électeur #{self.electeur_id} — Scrutin: {self.scrutin.titre}"