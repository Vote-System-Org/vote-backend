from django.contrib.auth.models import User
# from django.utils import timezone
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

from .models import OTPInscription

class InscriptionView(generics.CreateAPIView):
    """
    POST /api/v1/auth/inscription/
    Étape 1 : valide le matricule + email, génère et envoie l'OTP.
    Ne crée PAS encore le compte.
    """
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

        # Les données sont valides — on génère l'OTP mais on ne crée pas encore le compte
        ref = serializer.validated_data['_ref']

        otp = OTPInscription.generer(
            matricule = ref.matricule,
            email     = ref.email,
        )

        # Stocker les données d'inscription en session temporaire (dans le cache Redis)
        from django.core.cache import cache
        import json

        cache_key = f"inscription_pending_{ref.matricule}"
        cache.set(cache_key, json.dumps({
            'matricule':        ref.matricule,
            'email':            serializer.validated_data['email'],
            'password':         serializer.validated_data['password'],
        }), timeout=600)  # 10 minutes

        # Envoyer l'OTP par email
        api_key = getattr(settings, 'SENDGRID_API_KEY', '')
        if api_key:
            envoyer_otp_inscription(
                destinataire = ref.email,
                prenom       = ref.prenom,
                code         = otp.code,
                api_key      = api_key,
            )
        else:
            # En dev sans SendGrid : afficher le code dans les logs
            print(f"\n{'='*40}")
            print(f"OTP INSCRIPTION [{ref.matricule}] : {otp.code}")
            print(f"{'='*40}\n")

        return Response({
            'status':  'otp_envoye',
            'message': f'Un code de vérification a été envoyé à votre adresse email institutionnelle.',
            'data': {
                'matricule': ref.matricule,
                'email_masque': _masquer_email(ref.email),
            },
        }, status=status.HTTP_200_OK)


def _masquer_email(email: str) -> str:
    """Masque partiellement l'email pour l'affichage. ex: ke***@univ.cm"""
    parts = email.split('@')
    if len(parts) != 2:
        return email
    local = parts[0]
    visible = local[:2] if len(local) >= 2 else local
    return f"{visible}***@{parts[1]}"


class VerificationOTPView(generics.GenericAPIView):
    """
    POST /api/v1/auth/inscription/verification-otp/
    Étape 2 : vérifie le code OTP et crée le compte si valide.
    Corps : { "matricule": "21GL1234", "code": "482931" }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        matricule = request.data.get('matricule', '').strip()
        code      = request.data.get('code', '').strip()

        if not matricule or not code:
            return api_error('ERR_PARAMS_MANQUANTS',
                             'matricule et code sont requis.', 400)

        # Récupérer l'OTP en base
        try:
            otp = OTPInscription.objects.filter(
                matricule = matricule,
                utilise   = False,
            ).latest('created_at')
        except OTPInscription.DoesNotExist:
            return api_error('ERR_OTP_INTROUVABLE',
                             'Aucun code en attente pour ce matricule.', 400)

        # Vérifier validité (expiration + tentatives)
        if not otp.est_valide():
            return api_error('ERR_OTP_EXPIRE',
                             'Code expiré ou nombre de tentatives dépassé. '
                             'Recommencez l\'inscription.', 400)

        # Vérifier le code
        if otp.code != code:
            otp.tentatives += 1
            otp.save()
            restantes = 3 - otp.tentatives
            if restantes <= 0:
                return api_error('ERR_OTP_BLOQUE',
                                 'Trop de tentatives. Recommencez l\'inscription.', 400)
            return api_error('ERR_OTP_INVALIDE',
                             f'Code incorrect. {restantes} tentative(s) restante(s).', 400)

        # Code correct — récupérer les données en cache
        from django.core.cache import cache
        import json

        cache_key = f"inscription_pending_{matricule}"
        donnees   = cache.get(cache_key)

        if not donnees:
            return api_error('ERR_SESSION_EXPIREE',
                             'Session expirée. Recommencez l\'inscription.', 400)

        donnees = json.loads(donnees)

        # Créer le compte
        try:
            ref = ListeBlancheReference.objects.get(matricule=matricule)

            if ref.a_cree_son_compte:
                return api_error('ERR_COMPTE_EXISTANT',
                                 'Un compte existe déjà pour ce matricule.', 400)

            user = User.objects.create_user(
                username   = matricule,
                email      = donnees['email'],
                password   = donnees['password'],
                first_name = ref.prenom,
                last_name  = ref.nom,
            )

            electeur = Electeur.objects.create(
                user      = user,
                matricule = ref.matricule,
                filiere   = ref.filiere,
                niveau    = ref.niveau,
                statut    = 'ELIGIBLE',
            )

            ref.a_cree_son_compte = True
            ref.save()

            # Marquer l'OTP comme utilisé
            otp.utilise = True
            otp.save()

            # Nettoyer le cache
            cache.delete(cache_key)

            AuditService.log(
                action  = 'INSCRIPTION',
                acteur  = user,
                details = {'matricule': electeur.matricule, 'mfa': 'OTP_EMAIL'},
                request = request,
            )

            return Response({
                'status':  'success',
                'message': 'Compte créé avec succès. Vous pouvez maintenant vous connecter.',
                'data': {
                    'matricule': electeur.matricule,
                    'statut':   electeur.statut,
                },
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return api_error('ERR_CREATION_COMPTE',
                             f'Erreur lors de la création du compte : {str(e)}', 500)


class RenvoyerOTPView(generics.GenericAPIView):
    """
    POST /api/v1/auth/inscription/renvoyer-otp/
    Renvoie un nouveau code si l'ancien est expiré.
    Corps : { "matricule": "21GL1234" }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        matricule = request.data.get('matricule', '').strip()

        if not matricule:
            return api_error('ERR_PARAMS_MANQUANTS', 'matricule requis.', 400)

        # Vérifier que le matricule est en cours d'inscription
        from django.core.cache import cache
        cache_key = f"inscription_pending_{matricule}"
        if not cache.get(cache_key):
            return api_error('ERR_SESSION_EXPIREE',
                             'Session expirée. Recommencez l\'inscription.', 400)

        try:
            ref = ListeBlancheReference.objects.get(matricule=matricule)
        except ListeBlancheReference.DoesNotExist:
            return api_error('ERR_MATRICULE_INCONNU', 'Matricule inconnu.', 400)

        otp = OTPInscription.generer(
            matricule = matricule,
            email     = ref.email,
        )

        api_key = getattr(settings, 'SENDGRID_API_KEY', '')
        if api_key:
            envoyer_otp_inscription(
                destinataire = ref.email,
                prenom       = ref.prenom,
                code         = otp.code,
                api_key      = api_key,
            )
        else:
            print(f"\nOTP RENVOI [{matricule}] : {otp.code}\n")

        return Response({
            'status':  'success',
            'message': 'Nouveau code envoyé.',
            'data':    {'email_masque': _masquer_email(ref.email)},
        })

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


# class CaptchaRefreshView(generics.GenericAPIView):
#     """GET /api/auth/captcha/"""
#     permission_classes = [AllowAny]

#     def get(self, request):
#         new_key = CaptchaStore.generate_key()
#         return Response({
#             'captcha_key':       new_key,
#             # 'captcha_image_url': captcha_image_url(new_key)
#              'captcha_image_url': request.build_absolute_uri(
#                 captcha_image_url(new_key)),
            
#         })
        
        
class CaptchaRefreshView(generics.GenericAPIView):
    """GET /api/auth/captcha/"""
    permission_classes = [AllowAny]

    def get(self, request):
        new_key = CaptchaStore.generate_key()
        image_url = captcha_image_url(new_key)

        if not getattr(settings, 'CAPTCHA_USE_RELATIVE_URL', False):
            # Force l'URL vers le backend Django directement
            backend_url = getattr(settings, 'BACKEND_URL', 'http://127.0.0.1:8000')
            image_url = f"{backend_url}{image_url}"

        return Response({
            'captcha_key':       new_key,
            'captcha_image_url': image_url,
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
    """Envoie le lien de réinitialisation de mot de passe via SendGrid avec template HTML professionnel."""

    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Réinitialisation de mot de passe — VoteSystem</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f6f9;font-family:'Segoe UI',Arial,sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f9;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

          <!-- EN-TÊTE -->
          <tr>
            <td style="background:linear-gradient(135deg,#1e3a5f 0%,#2563a8 100%);border-radius:12px 12px 0 0;padding:40px 48px;text-align:center;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td align="center" style="padding-bottom:16px;">
                    <div style="display:inline-block;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.25);border-radius:12px;padding:14px 20px;">
                      <span style="font-size:28px;color:#ffffff;font-weight:700;letter-spacing:1px;">VoteSystem</span>
                    </div>
                  </td>
                </tr>
                <tr>
                  <td align="center">
                    <p style="margin:0;color:rgba(255,255,255,0.85);font-size:14px;letter-spacing:0.5px;">
                      Système de Vote Électronique Sécurisé
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- CORPS -->
          <tr>
            <td style="background:#ffffff;padding:48px;border-left:1px solid #e5e9f0;border-right:1px solid #e5e9f0;">

              <!-- Icône cadenas -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
                <tr>
                  <td align="center">
                    <div style="width:64px;height:64px;background:#f0f4ff;border:2px solid #2563a8;border-radius:16px;display:inline-flex;align-items:center;justify-content:center;font-size:28px;line-height:64px;text-align:center;">
                      🔐
                    </div>
                  </td>
                </tr>
              </table>

              <!-- Salutation -->
              <p style="margin:0 0 8px;font-size:22px;font-weight:600;color:#1a2844;">
                Bonjour {prenom},
              </p>
              <p style="margin:0 0 32px;font-size:15px;color:#64748b;line-height:1.6;">
                Nous avons reçu une demande de réinitialisation du mot de passe associé à votre compte VoteSystem.
                Cliquez sur le bouton ci-dessous pour définir un nouveau mot de passe.
              </p>

              <!-- Séparateur -->
              <hr style="border:none;border-top:1px solid #e5e9f0;margin:0 0 32px;">

              <!-- Bouton CTA -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
                <tr>
                  <td align="center">
                    <a href="{reset_url}"
                       style="display:inline-block;background:linear-gradient(135deg,#1e3a5f 0%,#2563a8 100%);color:#ffffff;text-decoration:none;font-size:15px;font-weight:600;padding:16px 40px;border-radius:10px;letter-spacing:0.5px;">
                      Réinitialiser mon mot de passe
                    </a>
                  </td>
                </tr>
              </table>

              <!-- Lien texte de secours -->
              <p style="margin:0 0 32px;font-size:12px;color:#94a3b8;text-align:center;line-height:1.6;">
                Si le bouton ne fonctionne pas, copiez et collez ce lien dans votre navigateur :<br>
                <a href="{reset_url}" style="color:#2563a8;word-break:break-all;font-size:12px;">{reset_url}</a>
              </p>

              <!-- Séparateur -->
              <hr style="border:none;border-top:1px solid #e5e9f0;margin:0 0 32px;">

              <!-- Avertissement expiration -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
                <tr>
                  <td style="background:#fff8ed;border:1px solid #fcd34d;border-radius:8px;padding:14px 20px;">
                    <p style="margin:0;font-size:13px;color:#92400e;line-height:1.5;">
                      <strong>Ce lien expire dans 24 heures.</strong>
                      Passé ce délai, vous devrez effectuer une nouvelle demande de réinitialisation.
                    </p>
                  </td>
                </tr>
              </table>

              <!-- Avertissement sécurité -->
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background:#fff1f2;border:1px solid #fecdd3;border-radius:8px;padding:14px 20px;">
                    <p style="margin:0;font-size:13px;color:#9f1239;line-height:1.5;">
                      <strong>Vous n'avez pas fait cette demande ?</strong><br>
                      Ignorez cet email. Votre mot de passe actuel restera inchangé.
                      Si vous pensez que votre compte a été compromis, contactez immédiatement l'administration.
                    </p>
                  </td>
                </tr>
              </table>

            </td>
          </tr>

          <!-- PIED DE PAGE -->
          <tr>
            <td style="background:#f8faff;border:1px solid #e5e9f0;border-top:none;border-radius:0 0 12px 12px;padding:28px 48px;text-align:center;">
              <p style="margin:0 0 8px;font-size:13px;color:#94a3b8;">
                Ce message a été envoyé automatiquement par la plateforme VoteSystem.
              </p>
              <p style="margin:0 0 16px;font-size:12px;color:#cbd5e1;">
                Université &nbsp;|&nbsp; Filière Génie Logiciel &nbsp;|&nbsp; Licence 2025-2026
              </p>
              <p style="margin:0;font-size:11px;color:#e2e8f0;">
                Cet email est confidentiel et destiné uniquement à son destinataire.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""

    text_content = f"""Bonjour {prenom},

Nous avons reçu une demande de réinitialisation de votre mot de passe VoteSystem.

Cliquez sur ce lien pour définir un nouveau mot de passe :
{reset_url}

Ce lien expire dans 24 heures.

Si vous n'avez pas fait cette demande, ignorez cet email.
Votre mot de passe actuel restera inchangé.

— VoteSystem | Université | Génie Logiciel 2025-2026"""

    try:
        response = requests.post(
            'https://api.sendgrid.com/v3/mail/send',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type':  'application/json',
            },
            json={
                'personalizations': [{
                    'to':      [{'email': destinataire}],
                    'subject': 'Réinitialisation de votre mot de passe — VoteSystem',
                }],
                'from':    {'email': 'kenmatiov@gmail.com', 'name': 'VoteSystem'},
                'content': [
                    {'type': 'text/plain', 'value': text_content},
                    {'type': 'text/html',  'value': html_content},
                ],
            },
            timeout=10,
        )
        print(f"Reset password SendGrid status: {response.status_code}")
        return response.status_code
    except Exception as e:
        print(f"Erreur envoi email reset: {e}")
        return None


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
        



def envoyer_otp_inscription(destinataire: str, prenom: str, code: str, api_key: str):
    """Envoie le code OTP par email via SendGrid avec template HTML professionnel."""
    
    chiffres = list(code)  # ["4", "8", "2", "9", "3", "1"]
    
    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Code de vérification — VoteSystem</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f6f9;font-family:'Segoe UI',Arial,sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f9;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

          <!-- EN-TÊTE -->
          <tr>
            <td style="background:linear-gradient(135deg,#1e3a5f 0%,#2563a8 100%);border-radius:12px 12px 0 0;padding:40px 48px;text-align:center;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td align="center" style="padding-bottom:16px;">
                    <div style="display:inline-block;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.25);border-radius:12px;padding:14px 20px;">
                      <span style="font-size:28px;color:#ffffff;font-weight:700;letter-spacing:1px;">VoteSystem</span>
                    </div>
                  </td>
                </tr>
                <tr>
                  <td align="center">
                    <p style="margin:0;color:rgba(255,255,255,0.85);font-size:14px;letter-spacing:0.5px;">
                      Système de Vote Électronique Sécurisé
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- CORPS -->
          <tr>
            <td style="background:#ffffff;padding:48px;border-left:1px solid #e5e9f0;border-right:1px solid #e5e9f0;">

              <!-- Salutation -->
              <p style="margin:0 0 8px;font-size:22px;font-weight:600;color:#1a2844;">
                Bonjour {prenom},
              </p>
              <p style="margin:0 0 32px;font-size:15px;color:#64748b;line-height:1.6;">
                Vous avez initié une inscription sur la plateforme de vote électronique de votre université.
                Veuillez utiliser le code ci-dessous pour confirmer votre identité et finaliser la création de votre compte.
              </p>

              <!-- Séparateur -->
              <hr style="border:none;border-top:1px solid #e5e9f0;margin:0 0 32px;">

              <!-- Titre code -->
              <p style="margin:0 0 20px;font-size:13px;font-weight:600;color:#94a3b8;text-align:center;letter-spacing:2px;text-transform:uppercase;">
                Votre code de vérification
              </p>

              <!-- Code OTP — chiffres individuels -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
                <tr>
                  <td align="center">
                    <table cellpadding="0" cellspacing="0">
                      <tr>
                        {''.join([f'''
                        <td style="padding:0 4px;">
                          <div style="
                            width:52px;
                            height:64px;
                            background:#f0f4ff;
                            border:2px solid #2563a8;
                            border-radius:10px;
                            display:inline-block;
                            text-align:center;
                            line-height:64px;
                            font-size:32px;
                            font-weight:700;
                            color:#1e3a5f;
                            font-family:'Courier New',monospace;
                          ">{c}</div>
                        </td>''' for c in chiffres])}
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Durée de validité -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
                <tr>
                  <td style="background:#fff8ed;border:1px solid #fcd34d;border-radius:8px;padding:14px 20px;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="font-size:13px;color:#92400e;line-height:1.5;">
                          <strong>Ce code expire dans 10 minutes.</strong>
                          Si vous n'avez pas demandé ce code, ignorez cet email. Votre compte ne sera pas créé.
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Séparateur -->
              <hr style="border:none;border-top:1px solid #e5e9f0;margin:0 0 32px;">

              <!-- Informations sécurité -->
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background:#f8faff;border-radius:8px;padding:20px 24px;">
                    <p style="margin:0 0 12px;font-size:13px;font-weight:600;color:#1e3a5f;">
                      Pourquoi ce code ?
                    </p>
                    <p style="margin:0 0 8px;font-size:13px;color:#64748b;line-height:1.6;">
                      Pour garantir la sécurité des élections universitaires, notre système vérifie
                      que vous êtes bien le titulaire du matricule utilisé lors de l'inscription.
                      Ce code confirme que vous avez accès à l'adresse email institutionnelle associée.
                    </p>
                    <p style="margin:0;font-size:12px;color:#94a3b8;line-height:1.5;">
                      Ne partagez jamais ce code avec quelqu'un d'autre, même s'il prétend faire partie de l'administration.
                    </p>
                  </td>
                </tr>
              </table>

            </td>
          </tr>

          <!-- PIED DE PAGE -->
          <tr>
            <td style="background:#f8faff;border:1px solid #e5e9f0;border-top:none;border-radius:0 0 12px 12px;padding:28px 48px;text-align:center;">
              <p style="margin:0 0 8px;font-size:13px;color:#94a3b8;">
                Ce message a été envoyé automatiquement par la plateforme VoteSystem.
              </p>
              <p style="margin:0 0 16px;font-size:12px;color:#cbd5e1;">
                Université &nbsp;|&nbsp; Filière Génie Logiciel &nbsp;|&nbsp; Licence 2025-2026
              </p>
              <p style="margin:0;font-size:11px;color:#e2e8f0;">
                Cet email est confidentiel et destiné uniquement à son destinataire.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""

    text_content = f"""Bonjour {prenom},

Votre code de vérification VoteSystem : {code}

Ce code expire dans 10 minutes.
Ne le partagez avec personne.

Si vous n'avez pas demandé ce code, ignorez cet email.

— VoteSystem | Université | Génie Logiciel 2025-2026"""

    try:
        response = requests.post(
            'https://api.sendgrid.com/v3/mail/send',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type':  'application/json',
            },
            json={
                'personalizations': [{
                    'to':      [{'email': destinataire}],
                    'subject': 'Votre code de vérification — VoteSystem',
                }],
                'from':    {'email': 'kenmatiov@gmail.com', 'name': 'VoteSystem'},
                'content': [
                    {'type': 'text/plain', 'value': text_content},
                    {'type': 'text/html',  'value': html_content},
                ],
            },
            timeout=10,
        )
        print(f"OTP SendGrid status: {response.status_code}")
        return response.status_code
    except Exception as e:
        print(f"Erreur envoi OTP: {e}")
        return None