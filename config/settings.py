from pathlib import Path
from datetime import timedelta
from decouple import config, Csv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Sécurité ──────────────────────────────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY')
DEBUG      = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost', cast=Csv())

# ── Applications ──────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'captcha',
    'django_filters',
    'cloudinary_storage',
    'cloudinary',
    'drf_spectacular',
    # Nos applications
    'accounts',
    'scrutins',
    'votes',
    'audit',
    # Scalabilité
    'django_celery_beat',
    'django_celery_results',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
     'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

WSGI_APPLICATION = 'config.wsgi.application'

# ── Base de données ───────────────────────────────────────────────────────────
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL'),
        conn_max_age=600,
    )
}

# ── Django REST Framework ─────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': ('rest_framework.renderers.JSONRenderer',),
    # Gestion centralisée des erreurs
    'EXCEPTION_HANDLER': 'utils.exceptions.custom_exception_handler',
    # Documentation automatique avec drf-spectacular
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}


# Configuration de drf-spectacular pour la documentation OpenAPI/Swagger
SPECTACULAR_SETTINGS = {
    'TITLE':       'VoteSystem API',
    'DESCRIPTION': 'API REST du système de vote électronique sécurisé — Licence GL 2025-2026',
    'VERSION':     '1.0.0',
    'CONTACT':     {'name': 'KENMATIO Vicens', 'email': 'kenmatiov@gmail.com'},
    'LICENSE':     {'name': 'Projet académique — Université'},
    'SERVERS':     [
        {'url': 'https://vote-backend-api.onrender.com', 'description': 'Production'},
        {'url': 'http://localhost:8000',                 'description': 'Développement'},
    ],
}

# ── JWT ───────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(
        minutes=config('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=15, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        days=config('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=7, cast=int)),
    'ROTATE_REFRESH_TOKENS':    True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN':        True,
    'ALGORITHM':                'HS256',
    'AUTH_HEADER_TYPES':        ('Bearer',),
}

# ── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:5173', cast=Csv())
CORS_ALLOW_CREDENTIALS = True

# ── Internationalisation ──────────────────────────────────────────────────────
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE     = 'Africa/Douala'
USE_I18N      = True
USE_TZ        = True

# ── Fichiers statiques & médias ───────────────────────────────────────────────
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL   = '/media/'
MEDIA_ROOT  = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── RSA 2048 ─────────────────────────────────────────────────────────────────
RSA_PRIVATE_KEY_PATH = config('RSA_PRIVATE_KEY_PATH', default='keys/private.pem')
RSA_PUBLIC_KEY_PATH  = config('RSA_PUBLIC_KEY_PATH',  default='keys/public.pem')

# ── WhiteNoise (fichiers statiques production) ────────────────────────────────
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'



# ── CAPTCHA ───────────────────────────────────────────────────────────────────
CAPTCHA_TEST_MODE = DEBUG  # En DEBUG, le CAPTCHA accepte n'importe quelle valeur




# ── Cloudinary ────────────────────────────────────────────────────────────────
# import cloudinary

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME'),
    'API_KEY':    config('CLOUDINARY_API_KEY'),
    'API_SECRET': config('CLOUDINARY_API_SECRET'),
}

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'



# ── Email via SendGrid ────────────────────────────────────────────────────────

SENDGRID_API_KEY    = config('SENDGRID_API_KEY', default='')
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = 'smtp.sendgrid.net'
EMAIL_PORT          = 465
EMAIL_USE_TLS       = False
EMAIL_USE_SSL       = True
EMAIL_HOST_USER     = 'apikey'
EMAIL_HOST_PASSWORD = SENDGRID_API_KEY
DEFAULT_FROM_EMAIL  = 'kenmatiov@gmail.com'


# ── Redis Cache (Niveau 2 — Scalabilité) ──────────────────────────────────────
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "IGNORE_EXCEPTIONS": True,  # Si Redis down → pas de crash
        },
        "KEY_PREFIX": "vote",
        "TIMEOUT": 300,  # 5 minutes par défaut
    }
}

# Sessions via Redis (plus rapide que base de données)
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# ── Celery (Niveau 1 — Workers asynchrones) ───────────────────────────────────
CELERY_BROKER_URL              = config('REDIS_URL', default=f'db+postgresql://{config("DATABASE_URL", default="")}')
CELERY_RESULT_BACKEND          = 'django-db'
CELERY_CACHE_BACKEND           = 'default'
CELERY_ACCEPT_CONTENT          = ['json']
CELERY_TASK_SERIALIZER         = 'json'
CELERY_RESULT_SERIALIZER       = 'json'
CELERY_TIMEZONE                = 'Africa/Douala'
CELERY_TASK_TRACK_STARTED      = True
CELERY_TASK_TIME_LIMIT         = 30 * 60   # 30 minutes max par tâche
CELERY_BEAT_SCHEDULER          = 'django_celery_beat.schedulers:DatabaseScheduler'

# ── Gunicorn — Workers gevent (Niveau 1) ──────────────────────────────────────
# Configuré dans docker-compose.yml et Dockerfile via la commande CMD
# gunicorn config.wsgi:application --worker-class gevent --workers 4

# ── Cache des scrutins (durées) ───────────────────────────────────────────────
CACHE_SCRUTINS_ELIGIBLES = 30      # 30 secondes
CACHE_RESULTATS_PUBLICS  = 60      # 60 secondes
CACHE_LISTE_CANDIDATS    = 120     # 2 minutes