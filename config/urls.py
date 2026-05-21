from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── API v1 ────────────────────────────────────────────────────────────────
    path('api/v1/auth/',     include('accounts.urls')),
    path('api/v1/electeur/', include('votes.urls_electeur')),
    path('api/v1/electeur/', include('scrutins.urls_electeur')),
    path('api/v1/admin/',    include('accounts.urls_admin')),
    path('api/v1/admin/',    include('scrutins.urls_admin')),
    path('api/v1/admin/',    include('audit.urls')),
    path('api/v1/public/',   include('scrutins.urls_public')),

    # ── CAPTCHA ───────────────────────────────────────────────────────────────
    path('captcha/', include('captcha.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)