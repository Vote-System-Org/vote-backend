from django.urls import path
from .views import ResultatsPublicView, ScrutinsCloturesPublicView

urlpatterns = [
    path('scrutins/<int:pk>/resultats/',
         ResultatsPublicView.as_view(),
         name='resultats_public'),
    path('scrutins/clotures/',
         ScrutinsCloturesPublicView.as_view(),
         name='scrutins_clotures_public'),
]