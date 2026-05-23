from django.urls import path
from .views import ResultatsPublicView, ScrutinsCloturesPublicView
from votes.views import VerificationRecuPublicView

urlpatterns = [
    path('scrutins/<int:pk>/resultats/',
         ResultatsPublicView.as_view(),
         name='resultats_public'),
    path('scrutins/clotures/',
         ScrutinsCloturesPublicView.as_view(),
         name='scrutins_clotures_public'),
    path('vote/verification/<str:hash_vote>/',
         VerificationRecuPublicView.as_view(),
         name='verification_recu_public'),
]