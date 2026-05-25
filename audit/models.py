# import hashlib
import hashlib
import json
from django.db import models
from django.contrib.auth.models import User


class LogAudit(models.Model):

    ACTIONS = [
        ('CONNEXION',            'Connexion'),
        ('INSCRIPTION',          'Inscription'),
        ('VOTE',                 'Vote'),
        ('CREATION_SCRUTIN',     'Création scrutin'),
        ('OUVERTURE_SCRUTIN',    'Ouverture scrutin'),
        ('CLOTURE_SCRUTIN',      'Clôture scrutin'),
        ('SUSPENSION_ELECTEUR',  'Suspension électeur'),
        ('VALIDATION_ELECTEUR',  'Validation électeur'),
        ('IMPORT_LISTE_BLANCHE', 'Import liste blanche'),
    ]

    action         = models.CharField(max_length=50, choices=ACTIONS)
    acteur         = models.ForeignKey(User, on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name='logs')
    details        = models.JSONField(null=True, blank=True)
    hash_precedent = models.CharField(max_length=64)
    hash_courant   = models.CharField(max_length=64)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table            = 'log_audit'
        verbose_name        = 'Log d\'audit'
        verbose_name_plural = 'Logs d\'audit'
        ordering            = ['-created_at']

    def __str__(self):
        return f"[{self.action}] {self.acteur} — {self.created_at}"

    @staticmethod
    def calculer_hash(action, acteur_id, details, hash_precedent, timestamp):
        payload = json.dumps({
            'action':         action,
            'acteur_id':      acteur_id,
            'details':        details,
            'hash_precedent': hash_precedent,
            'timestamp':      str(timestamp),
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()