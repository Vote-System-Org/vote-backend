from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    InscriptionView, ConnexionView, DeconnexionView,
    CaptchaRefreshView, MonProfilView,
    ResetPasswordRequestView, ResetPasswordConfirmView,
    VerificationOTPView, RenvoyerOTPView,
)

urlpatterns = [
    path('inscription/',                     InscriptionView.as_view(),          name='inscription'),
    path('inscription/verification-otp/',    VerificationOTPView.as_view(),      name='verification_otp'),
    path('inscription/renvoyer-otp/',        RenvoyerOTPView.as_view(),          name='renvoyer_otp'),
    path('login/',                           ConnexionView.as_view(),            name='login'),
    path('logout/',                          DeconnexionView.as_view(),          name='logout'),
    path('token/refresh/',                   TokenRefreshView.as_view(),         name='token_refresh'),
    path('captcha/',                         CaptchaRefreshView.as_view(),       name='captcha'),
    path('profil/',                          MonProfilView.as_view(),            name='mon_profil'),
    path('password/reset/',                  ResetPasswordRequestView.as_view(), name='password_reset'),
    path('password/confirm/',                ResetPasswordConfirmView.as_view(), name='password_confirm'),
]