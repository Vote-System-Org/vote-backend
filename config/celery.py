import os
from celery import Celery
from django.conf import settings

# Définir le module de settings Django pour Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('vote_system')

# Charger la configuration depuis Django settings (clés préfixées CELERY_)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Découverte automatique des tâches dans tous les apps Django
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')