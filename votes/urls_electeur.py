from django.urls import path
from .views import VoteView, VerificationRecuView

urlpatterns = [
    path('vote/',
         VoteView.as_view(),
         name='voter'),
    path('vote/confirmation/<str:hash_vote>/',
         VerificationRecuView.as_view(),
         name='verif_recu'),
]