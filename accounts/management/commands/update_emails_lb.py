from django.core.management.base import BaseCommand
from accounts.models import ListeBlancheReference

class Command(BaseCommand):
    help = 'Met à jour les emails de la liste blanche pour les tests'

    def handle(self, *args, **kwargs):
        emails = {
            '21GL0001': 'badifa.murielle@gmail.com',
            '21GL0002': 'bakang.yves@gmail.com',
            '21GL0003': 'dieumou.hursel@gmail.com',
            '21GL0004': 'djiometio.hurish@gmail.com',
            '21GL0005': 'dongmo.stephie@gmail.com',
            '21GL0006': 'kenmatiovicens23@gmail.com',   # FOUOGUE GABRIELA — conservé
            '21GL0007': 'kenmatiov@gmail.com',          # KENMATIO VICENS — conservé
            '21GL0008': 'motso.liticia@gmail.com',
            '21GL0009': 'nanfa.jackin@gmail.com',
            '21GL0010': 'ngoko.melissa@gmail.com',
            '21GL0011': 'ngouadjio.tresor@gmail.com',
            '21GL0012': 'noubissi.kevin@gmail.com',
            '21RSI0001': 'bonfeu.miel@gmail.com',
            '21RSI0002': 'gonne.frederic@gmail.com',
            '21RSI0003': 'malontsob.manuela@gmail.com',
            '21RSI0004': 'ndoue.joseph@gmail.com',
            '21RSI0005': 'ngadak.arthur@gmail.com',
            '21RSI0006': 'nouyadjam.fernandez@gmail.com',
            '21RSI0007': 'simo.therese@gmail.com',
        }

        for matricule, email in emails.items():
            try:
                updated = ListeBlancheReference.objects.filter(
                    matricule=matricule
                ).update(email=email)
                status = 'OK' if updated else 'NON TROUVE'
                self.stdout.write(f"{matricule} → {email} ({status})")
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"{matricule} → ERREUR : {e}")
                )

        self.stdout.write(self.style.SUCCESS('Terminé.'))