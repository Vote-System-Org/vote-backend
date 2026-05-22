from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ScrutinAdminViewSet, CandidatAdminViewSet

router = DefaultRouter()
router.register(r'scrutins', ScrutinAdminViewSet, basename='scrutin-admin')
router.register(r'candidats', CandidatAdminViewSet, basename='candidat-admin')

urlpatterns = [
    path('', include(router.urls)),
]