from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    InscriptionView, ConnexionView, DeconnexionView,
    CaptchaRefreshView, MonProfilView,
    ResetPasswordRequestView, ResetPasswordConfirmView,
)

urlpatterns = [
    path('inscription/',          InscriptionView.as_view(),        name='inscription'),
    path('login/',                ConnexionView.as_view(),           name='login'),
    path('logout/',               DeconnexionView.as_view(),         name='logout'),
    path('token/refresh/',        TokenRefreshView.as_view(),        name='token_refresh'),
    path('captcha/',              CaptchaRefreshView.as_view(),      name='captcha'),
    path('profil/',               MonProfilView.as_view(),           name='mon_profil'),
    path('password/reset/',       ResetPasswordRequestView.as_view(), name='password_reset'),
    path('password/confirm/',     ResetPasswordConfirmView.as_view(), name='password_confirm'),
]