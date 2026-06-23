from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ElecteurViewSet, ImportListeBlancheView, ListeBlancheListView,
    ListeBlancheDetailView,
)

router = DefaultRouter()
router.register(r'electeurs', ElecteurViewSet, basename='electeur')

urlpatterns = [
    path('', include(router.urls)),
    path('liste-blanche/import/', ImportListeBlancheView.as_view(),
         name='import_liste_blanche'),
    path('liste-blanche/',        ListeBlancheListView.as_view(),
         name='liste_blanche'),
    path('liste-blanche/<int:pk>/', ListeBlancheDetailView.as_view(),
         name='liste_blanche_detail'),
]