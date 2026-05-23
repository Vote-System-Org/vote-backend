from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status, generics, viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from captcha.models import CaptchaStore
from captcha.helpers import captcha_image_url
from django_filters.rest_framework import DjangoFilterBackend

from utils.permissions import IsAdmin
from utils.exceptions import api_error
from audit.services import AuditService
from .models import ListeBlancheReference, Electeur
from .serializers import (
    InscriptionSerializer, ElecteurSerializer, ElecteurStatutSerializer,
    ListeBlancheSerializer, ImportCSVSerializer,
)

from django.conf import settings
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

class InscriptionView(generics.CreateAPIView):
    """POST /api/auth/inscription/"""
    serializer_class   = InscriptionSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        # Valider le CAPTCHA (désactivé en mode DEBUG)
        if not settings.DEBUG:
            captcha_key   = request.data.get('captcha_key', '')
            captcha_value = request.data.get('captcha_value', '').upper()
            try:
                store = CaptchaStore.objects.get(hashkey=captcha_key)
                if store.response.upper() != captcha_value:
                    return api_error('ERR_CAPTCHA_INVALIDE', 'Code CAPTCHA incorrect.', 400)
            except CaptchaStore.DoesNotExist:
                return api_error('ERR_CAPTCHA_INVALIDE', 'CAPTCHA expiré ou invalide.', 400)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        electeur = serializer.save()

        AuditService.log(
            action  = 'INSCRIPTION',
            acteur  = electeur.user,
            details = {'matricule': electeur.matricule},
            request = request,
        )

        return Response({
            'status':  'success',
            'message': 'Compte créé avec succès.',
            'data':    {'matricule': electeur.matricule, 'statut': electeur.statut},
        }, status=status.HTTP_201_CREATED)

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Ajouter is_staff dans le token
        token['is_staff'] = user.is_staff
        return token


class ConnexionView(TokenObtainPairView):
    """POST /api/auth/login/"""
    serializer_class   = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        # Valider le CAPTCHA (désactivé en mode DEBUG)
        if not settings.DEBUG:
            captcha_key   = request.data.get('captcha_key', '')
            captcha_value = request.data.get('captcha_value', '').upper()
            try:
                store = CaptchaStore.objects.get(hashkey=captcha_key)
                if store.response.upper() != captcha_value:
                    return api_error('ERR_CAPTCHA_INVALIDE', 'Code CAPTCHA incorrect.', 400)
            except CaptchaStore.DoesNotExist:
                return api_error('ERR_CAPTCHA_INVALIDE', 'CAPTCHA expiré ou invalide.', 400)

        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            user = User.objects.filter(
                username=request.data.get('username')).first()
            if user:
                AuditService.log(
                    action  = 'CONNEXION',
                    acteur  = user,
                    request = request,
                )

        return response
    

class DeconnexionView(generics.GenericAPIView):
    """POST /api/auth/logout/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'status': 'success', 'message': 'Déconnexion réussie.'})
        except Exception:
            return api_error('ERR_TOKEN_INVALIDE', 'Token invalide ou expiré.', 400)


class CaptchaRefreshView(generics.GenericAPIView):
    """GET /api/auth/captcha/"""
    permission_classes = [AllowAny]

    def get(self, request):
        new_key = CaptchaStore.generate_key()
        return Response({
            'captcha_key':       new_key,
            'captcha_image_url': request.build_absolute_uri(
                captcha_image_url(new_key)),
        })


class MonProfilView(generics.RetrieveUpdateAPIView):
    """GET/PUT /api/auth/profil/"""
    serializer_class   = ElecteurSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        # Si l'utilisateur est admin, retourner une réponse minimale
        if self.request.user.is_staff:
            return None

        try:
            return self.request.user.electeur
        except Exception:
            raise

    def retrieve(self, request, *args, **kwargs):
        if request.user.is_staff:
            return Response({
                'id':        request.user.id,
                'matricule': 'ADMIN',
                'nom':       request.user.last_name or 'Admin',
                'prenom':    request.user.first_name or '',
                'email':     request.user.email,
                'filiere':   '',
                'niveau':    '',
                'statut':    'ELIGIBLE',
                'a_vote':    False,
                'date_vote': None,
                'created_at': str(request.user.date_joined),
            })
        return super().retrieve(request, *args, **kwargs)


class ElecteurViewSet(viewsets.ModelViewSet):
    """CRUD électeurs — admin uniquement"""
    queryset           = Electeur.objects.select_related('user').all()
    serializer_class   = ElecteurSerializer
    permission_classes = [IsAdmin]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields   = ['filiere', 'niveau', 'statut']
    search_fields      = ['matricule', 'user__last_name',
                          'user__first_name', 'user__email']

    def destroy(self, request, *args, **kwargs):
        electeur = self.get_object()
        if electeur.a_vote:
            return api_error(
                'ERR_SUPPRESSION_IMPOSSIBLE',
                'Impossible de supprimer un électeur ayant déjà voté.',
                403,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['patch'], url_path='statut')
    def changer_statut(self, request, pk=None):
        electeur   = self.get_object()
        serializer = ElecteurStatutSerializer(
            electeur, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        AuditService.log(
            action  = 'SUSPENSION_ELECTEUR'
                      if request.data.get('statut') == 'SUSPENDU'
                      else 'VALIDATION_ELECTEUR',
            acteur  = request.user,
            details = {'electeur_id': electeur.id,
                       'nouveau_statut': request.data.get('statut')},
            request = request,
        )
        return Response(ElecteurSerializer(electeur).data)

    @action(detail=True, methods=['post'], url_path='reset-password')
    def reset_password(self, request, pk=None):
        electeur = self.get_object()
        return Response({
            'status':  'success',
            'message': f'Email de réinitialisation envoyé à {electeur.user.email}.'
        })


class ImportListeBlancheView(generics.CreateAPIView):
    """POST /api/admin/liste-blanche/import/"""
    serializer_class   = ImportCSVSerializer
    permission_classes = [IsAdmin]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stats = serializer.process()

        AuditService.log(
            action  = 'IMPORT_LISTE_BLANCHE',
            acteur  = request.user,
            details = stats,
            request = request,
        )

        return Response({
            'status':  'success',
            'message': f"{stats['importes']} entrées importées.",
            'data':    stats,
        }, status=status.HTTP_201_CREATED)


class ListeBlancheListView(generics.ListAPIView):
    """GET /api/admin/liste-blanche/"""
    queryset           = ListeBlancheReference.objects.all()
    serializer_class   = ListeBlancheSerializer
    permission_classes = [IsAdmin]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields   = ['filiere', 'niveau', 'a_cree_son_compte']
    search_fields      = ['matricule', 'nom', 'prenom', 'email']



import requests
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.conf import settings as django_settings


def envoyer_email_reset(destinataire: str, prenom: str, reset_url: str, api_key: str):
    response = requests.post(
        'https://api.sendgrid.com/v3/mail/send',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json={
            'personalizations': [{
                'to': [{'email': destinataire}],
                'subject': 'Réinitialisation de votre mot de passe — VoteSystem',
            }],
            'from': {'email': 'kenmatiov@gmail.com', 'name': 'VoteSystem'},
            'content': [{
                'type': 'text/plain',
                'value': f"""Bonjour {prenom},

Vous avez demandé la réinitialisation de votre mot de passe VoteSystem.

Cliquez sur le lien ci-dessous pour créer un nouveau mot de passe :
{reset_url}

Ce lien est valable 24 heures.

Si vous n'avez pas fait cette demande, ignorez cet email.

— L'équipe VoteSystem""",
            }],
        }
    )
    return response.status_code


class ResetPasswordRequestView(generics.GenericAPIView):
    """
    POST /api/v1/auth/password/reset/
    Demande de réinitialisation du mot de passe.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip()
        if not email:
            return api_error('ERR_EMAIL_REQUIS', 'Email requis.', 400)

        user = User.objects.filter(email=email).first()

        if not user:
            return Response({
                'status':  'success',
                'message': 'Si cet email existe, un lien de réinitialisation a été envoyé.',
            })

        # Générer le token
        token = default_token_generator.make_token(user)
        uid   = urlsafe_base64_encode(force_bytes(user.pk))

        # URL de réinitialisation (frontend)
        reset_url = f"{request.data.get('frontend_url', 'http://localhost:5173')}/mot-de-passe/confirmer?uid={uid}&token={token}"

        # Envoyer via API SendGrid
        try:
            status = envoyer_email_reset(
                destinataire = email,
                prenom       = user.first_name or user.username,
                reset_url    = reset_url,
                api_key      = django_settings.SENDGRID_API_KEY,
            )
            print(f"SendGrid status: {status}")
        except Exception as e:
            print(f"Erreur SendGrid: {e}")

        return Response({
            'status':  'success',
            'message': 'Si cet email existe, un lien de réinitialisation a été envoyé.',
        })


class ResetPasswordConfirmView(generics.GenericAPIView):
    """
    POST /api/v1/auth/password/confirm/
    Confirmation de la réinitialisation du mot de passe.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        uid              = request.data.get('uid', '')
        token            = request.data.get('token', '')
        password         = request.data.get('password', '')
        password_confirm = request.data.get('password_confirm', '')

        if not all([uid, token, password, password_confirm]):
            return api_error('ERR_PARAMS_MANQUANTS', 'Tous les champs sont requis.', 400)

        if password != password_confirm:
            return api_error('ERR_PASSWORDS_MISMATCH',
                             'Les mots de passe ne correspondent pas.', 400)

        if len(password) < 8:
            return api_error('ERR_PASSWORD_TROP_COURT',
                             'Le mot de passe doit contenir au moins 8 caractères.', 400)

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user    = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError):
            return api_error('ERR_LIEN_INVALIDE', 'Lien invalide ou expiré.', 400)

        if not default_token_generator.check_token(user, token):
            return api_error('ERR_TOKEN_INVALIDE', 'Lien invalide ou expiré.', 400)

        user.set_password(password)
        user.save()

        return Response({
            'status':  'success',
            'message': 'Mot de passe réinitialisé avec succès.',
        })