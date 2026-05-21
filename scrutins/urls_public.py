from django.urls import path
from .views import ResultatsPublicView

urlpatterns = [
    path('scrutins/<int:pk>/resultats/',
         ResultatsPublicView.as_view(),
         name='resultats_public'),
]