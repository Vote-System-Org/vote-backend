from django.core.management.base import BaseCommand
from accounts.models import ListeBlancheReference

class Command(BaseCommand):
    help = 'Met à jour les emails de la liste blanche pour les tests'

    def handle(self, *args, **kwargs):
        emails = {
            '21GL0001': 'kenmatiov@gmail.com',
            '21GL0002': 'kenmatiovicens23@gmail.com',
            '21GL0003': 'kenmatiov@gmail.com',
            '21GL0004': 'kenmatiovicens23@gmail.com',
            '21GL0005': 'kenmatiov@gmail.com',
            '21GL0006': 'kenmatiovicens23@gmail.com',
            '21GL0007': 'kenmatiov@gmail.com',
            '21GL0008': 'kenmatiovicens23@gmail.com',
            '21GL0009': 'kenmatiov@gmail.com',
            '21GL0010': 'kenmatiovicens23@gmail.com',
            '21GL0011': 'kenmatiov@gmail.com',
            '21GL0012': 'kenmatiovicens23@gmail.com',
            '21RSI0001': 'kenmatiovicens23@gmail.com',
            '21RSI0002': 'kenmatiov@gmail.com',
            '21RSI0003': 'kenmatiovicens23@gmail.com',
            '21RSI0004': 'kenmatiov@gmail.com',
            '21RSI0005': 'kenmatiovicens23@gmail.com',
            '21RSI0006': 'kenmatiov@gmail.com',
            '21RSI0007': 'kenmatiovicens23@gmail.com',
        }

        for matricule, email in emails.items():
            updated = ListeBlancheReference.objects.filter(
                matricule=matricule
            ).update(email=email)
            status = 'OK' if updated else 'NON TROUVE'
            self.stdout.write(f"{matricule} → {email} ({status})")

        self.stdout.write(self.style.SUCCESS('Emails mis à jour.'))