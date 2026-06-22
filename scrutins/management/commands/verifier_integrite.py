from django.core.management.base import BaseCommand
from audit.models import LogAudit


class Command(BaseCommand):
    help = 'Verifie l integrite de la chaine SHA-256 des logs d audit'

    def handle(self, *args, **kwargs):
        logs = LogAudit.objects.order_by('id')
        total = logs.count()

        if total == 0:
            self.stdout.write('Aucun log d audit trouve.')
            return

        self.stdout.write(f'\n=== VERIFICATION INTEGRITE CHAINE SHA-256 ===')
        self.stdout.write(f'Nombre de logs a verifier : {total}\n')

        chaine_valide = True

        for i, log in enumerate(logs):
            if i > 0:
                log_precedent = logs[i - 1]
                if log.hash_precedent != log_precedent.hash_courant:
                    chaine_valide = False
                    self.stdout.write(
                        self.style.ERROR(
                            f'ALERTE : chaine rompue au log ID={log.id} '
                            f'(attendu={log_precedent.hash_courant[:16]}... '
                            f'trouve={log.hash_precedent[:16]}...)'
                        )
                    )

        if chaine_valide:
            self.stdout.write(self.style.SUCCESS(
                f'INTEGRITE CONFIRMEE : {total} logs verifies, chaine intacte.'
            ))
        else:
            self.stdout.write(self.style.ERROR(
                'INTEGRITE COMPROMISE : des logs ont ete modifies.'
            ))