from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def cloture_automatique_scrutin(self, scrutin_id):
    """
    Tâche Celery — Clôture automatique d'un scrutin à date_fin.
    Planifiée à la création du scrutin via django-celery-beat.
    RG06 — Clôture automatique à date_fin.
    """
    try:
        from scrutins.models import Scrutin
        from audit.services import AuditService

        scrutin = Scrutin.objects.get(id=scrutin_id)

        if scrutin.statut != 'OUVERT':
            logger.info(f"Scrutin {scrutin_id} déjà clôturé ou non ouvert.")
            return

        # Clôturer le scrutin
        scrutin.statut = 'CLOTURE'
        scrutin.save(update_fields=['statut'])

        # Invalider le cache lié à ce scrutin
        cache.delete(f"scrutins_eligibles_*")
        cache.delete(f"resultats_scrutin_{scrutin_id}")
        cache.delete(f"candidats_scrutin_{scrutin_id}")

        # Journaliser dans l'audit
        AuditService.log(
            action='CLOTURE_SCRUTIN',
            acteur_id=None,
            details={
                'scrutin_id':   scrutin_id,
                'titre':        scrutin.titre,
                'declencheur':  'AUTOMATIQUE_CELERY',
            }
        )

        # Déclencher l'envoi des emails de résultats
        envoyer_emails_resultats.delay(scrutin_id)

        logger.info(f"Scrutin {scrutin_id} clôturé automatiquement.")

    except Exception as exc:
        logger.error(f"Erreur clôture scrutin {scrutin_id} : {exc}")
        raise self.retry(exc=exc, countdown=60)  # Retry dans 60s


@shared_task(bind=True, max_retries=3)
def envoyer_emails_resultats(self, scrutin_id):
    """
    Tâche Celery — Envoie les résultats par email à chaque candidat
    après la clôture du scrutin.
    """
    try:
        from scrutins.models import Scrutin, Candidat
        from django.core.mail import send_mail
        from django.conf import settings

        scrutin  = Scrutin.objects.get(id=scrutin_id)
        candidats = Candidat.objects.filter(
            scrutin=scrutin,
            est_vote_blanc=False,
            email__isnull=False
        ).exclude(email='')

        # Calculer les résultats
        from votes.models import Vote
        total_votes = Vote.objects.filter(scrutin=scrutin).count()

        for candidat in candidats:
            nb_voix = Vote.objects.filter(
                scrutin=scrutin,
                candidat=candidat
            ).count()

            pourcentage = (nb_voix / total_votes * 100) if total_votes > 0 else 0

            sujet = f"Résultats — {scrutin.titre}"
            message = (
                f"Bonjour {candidat.prenom} {candidat.nom},\n\n"
                f"Le scrutin '{scrutin.titre}' est désormais clôturé.\n\n"
                f"Vos résultats :\n"
                f"  Voix obtenues : {nb_voix}\n"
                f"  Total votes    : {total_votes}\n"
                f"  Pourcentage    : {pourcentage:.1f}%\n\n"
                f"Cordialement,\n"
                f"L'équipe Vote Électronique"
            )

            send_mail(
                subject=sujet,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[candidat.email],
                fail_silently=True,
            )

        logger.info(f"Emails résultats envoyés pour scrutin {scrutin_id}.")

    except Exception as exc:
        logger.error(f"Erreur envoi emails scrutin {scrutin_id} : {exc}")
        raise self.retry(exc=exc, countdown=120)


@shared_task
def invalider_cache_scrutins():
    """
    Tâche périodique — Invalide le cache des scrutins toutes les 60s.
    Garantit la cohérence des données affichées.
    """
    from django.core.cache import cache
    cache.delete_pattern("vote:scrutins_*")
    logger.info("Cache scrutins invalidé.")


@shared_task
def verifier_scrutins_expires():
    """
    Tâche périodique — Vérifie toutes les minutes les scrutins
    dont date_fin est dépassée et les clôture si nécessaire.
    Filet de sécurité en cas d'échec de la tâche planifiée.
    """
    from scrutins.models import Scrutin

    scrutins_expires = Scrutin.objects.filter(
        statut='OUVERT',
        date_fin__lte=timezone.now()
    )

    for scrutin in scrutins_expires:
        logger.warning(
            f"Scrutin {scrutin.id} expiré non clôturé — "
            f"déclenchement clôture d'urgence."
        )
        cloture_automatique_scrutin.delay(scrutin.id)

    return f"{scrutins_expires.count()} scrutins clôturés."