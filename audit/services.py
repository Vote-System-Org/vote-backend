from django.utils import timezone
from django.contrib.auth.models import User
import hashlib
import json


class AuditService:
    """
    Service centralisé de journalisation.
    Chaque log contient le hash du log précédent (hash chain — RG14).
    """

    @staticmethod
    def log(action: str, acteur: User = None, details: dict = None, request=None):
        from .models import LogAudit
        from django.db import transaction

        with transaction.atomic():
            # Récupérer le dernier log avec verrou
            dernier = LogAudit.objects.select_for_update().order_by('-id').first()
            hash_precedent = dernier.hash_courant if dernier else '0' * 64

            now = timezone.now()

            # Enrichir les détails avec l'IP
            details_enrichis = details or {}
            if request:
                ip = request.META.get('HTTP_X_FORWARDED_FOR',
                                      request.META.get('REMOTE_ADDR', ''))
                details_enrichis['ip'] = ip.split(',')[0].strip() if ip else 'unknown'

            # Calculer le hash SHA-256
            payload = json.dumps({
                'action':         action,
                'acteur_id':      acteur.id if acteur else None,
                'details':        details_enrichis,
                'hash_precedent': hash_precedent,
                'timestamp':      str(now),
            }, sort_keys=True, ensure_ascii=False)

            hash_courant = hashlib.sha256(payload.encode('utf-8')).hexdigest()

            LogAudit.objects.create(
                action         = action,
                acteur         = acteur,
                details        = details_enrichis,
                hash_precedent = hash_precedent,
                hash_courant   = hash_courant,
            )