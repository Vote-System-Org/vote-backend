from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Créer le superuser admin'

    def handle(self, *args, **kwargs):
        if not User.objects.filter(username='Vicens').exists():
            User.objects.create_superuser(
                username  = 'Vicens',
                email     = 'kenmatiovicens@icloud.com',
                password  = '212005',
            )
            self.stdout.write('Superuser créé !')
        else:
            self.stdout.write('Superuser existe déjà.')