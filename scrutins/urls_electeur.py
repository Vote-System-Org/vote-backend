from django.urls import path
from .views import (
    ScrutinsEligiblesView, CandidatsScrutinView, ResultatsElecteurView,
)
from .views import ScrutinsEligiblesView, CandidatsScrutinView, ResultatsElecteurView, ScrutinsClotures

urlpatterns = [
    path('scrutins/',
         ScrutinsEligiblesView.as_view(),
         name='scrutins_eligibles'),
    path('scrutins/<int:pk>/candidats/',
         CandidatsScrutinView.as_view(),
         name='candidats_scrutin'),
    path('scrutins/<int:pk>/resultats/',
         ResultatsElecteurView.as_view(),
         name='resultats_electeur'),
    
    path('scrutins/',
         ScrutinsEligiblesView.as_view(),
         name='scrutins_eligibles'),
    path('scrutins/clotures/',
         ScrutinsClotures.as_view(),
         name='scrutins_clotures'),
    path('scrutins/<int:pk>/candidats/',
         CandidatsScrutinView.as_view(),
         name='candidats_scrutin'),
    path('scrutins/<int:pk>/resultats/',
         ResultatsElecteurView.as_view(),
         name='resultats_electeur'),
]



