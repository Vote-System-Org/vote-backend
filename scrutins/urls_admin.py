from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ScrutinAdminViewSet, CandidatAdminViewSet

router = DefaultRouter()
router.register(r'scrutins', ScrutinAdminViewSet, basename='scrutin-admin')

urlpatterns = [
    path('', include(router.urls)),
]