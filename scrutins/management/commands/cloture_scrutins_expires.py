from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clôture automatiquement les scrutins dont date_fin est dépassée (RG06)'

    def handle(self, *args, **options):
        from scrutins.models import Scrutin
        from audit.services import AuditService

        scrutins_expires = Scrutin.objects.filter(
            statut='OUVERT',
            date_fin__lte=timezone.now()
        )

        count = scrutins_expires.count()

        if count == 0:
            self.stdout.write("Aucun scrutin à clôturer.")
            return

        for scrutin in scrutins_expires:
            try:
                scrutin.statut = 'CLOTURE'
                scrutin.save(update_fields=['statut'])

                # Invalider le cache
                cache.delete(f"candidats_scrutin_{scrutin.id}")
                cache.delete(f"resultats_public_{scrutin.id}")
                cache.delete(f"resultats_electeur_{scrutin.id}")
                cache.delete("scrutins_clotures_public")
                try:
                    cache.delete_pattern("scrutins_eligibles_*")
                except Exception:
                    pass

                # Log audit
                AuditService.log(
                    action='CLOTURE_SCRUTIN',
                    acteur_id=None,
                    details={
                        'scrutin_id':  scrutin.id,
                        'titre':       scrutin.titre,
                        'declencheur': 'CRON_GITHUB_ACTIONS',
                    }
                )

                # Envoyer emails résultats
                self._envoyer_emails(scrutin)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Scrutin {scrutin.id} '{scrutin.titre}' clôturé."
                    )
                )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Erreur scrutin {scrutin.id} : {e}")
                )
                logger.error(f"Erreur clôture scrutin {scrutin.id} : {e}")

        self.stdout.write(f"{count} scrutin(s) clôturé(s).")

    def _envoyer_emails(self, scrutin):
        try:
            from votes.models import Vote
            from django.core.mail import send_mail
            from django.conf import settings

            candidats = scrutin.candidats.filter(
                est_vote_blanc=False
            ).exclude(email='').exclude(email__isnull=True)

            total_votes = Vote.objects.filter(scrutin=scrutin).count()

            for candidat in candidats:
                nb_voix     = Vote.objects.filter(
                    scrutin=scrutin, candidat=candidat
                ).count()
                pourcentage = round(
                    (nb_voix / total_votes * 100), 1
                ) if total_votes > 0 else 0

                send_mail(
                    subject=f"Résultats — {scrutin.titre}",
                    message=(
                        f"Bonjour {candidat.prenom} {candidat.nom},\n\n"
                        f"Le scrutin '{scrutin.titre}' est clôturé.\n\n"
                        f"Vos résultats :\n"
                        f"  Voix : {nb_voix} / {total_votes} "
                        f"({pourcentage}%)\n\n"
                        f"Cordialement,\nL'équipe VoteSystem"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[candidat.email],
                    fail_silently=True,
                )
        except Exception as e:
            logger.error(f"Erreur emails scrutin {scrutin.id} : {e}")