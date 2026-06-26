from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import requests
import hashlib
import hmac
import json
import base64
from django.conf import settings as django_settings

from utils.permissions import IsElecteur
from utils.exceptions import api_error
from audit.services import AuditService
from scrutins.models import Scrutin, Candidat
from .models import Vote, ElecteurScrutinVote


from rest_framework.permissions import AllowAny


def envoyer_email_recu_vote(destinataire: str, prenom: str,
                             scrutin_titre: str, hash_vote: str,
                             verification_url: str, api_key: str):
    """Envoie le reçu de vote par email via SendGrid avec template HTML professionnel."""

    # Découpe le hash en blocs de 8 pour la lisibilité
    hash_blocs = ' '.join([hash_vote[i:i+8] for i in range(0, len(hash_vote), 8)])

    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reçu de vote — {scrutin_titre}</title>
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

          <!-- BANDEAU CONFIRMATION -->
          <tr>
            <td style="background:#16a34a;padding:16px 48px;text-align:center;">
              <p style="margin:0;color:#ffffff;font-size:14px;font-weight:600;letter-spacing:0.5px;">
                Vote enregistré avec succès
              </p>
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
                Votre vote pour le scrutin <strong style="color:#1a2844;">«&nbsp;{scrutin_titre}&nbsp;»</strong>
                a bien été enregistré dans notre système. Conservez ce reçu — il vous permet
                de vérifier à tout moment que votre bulletin est bien pris en compte.
              </p>

              <!-- Séparateur -->
              <hr style="border:none;border-top:1px solid #e5e9f0;margin:0 0 32px;">

              <!-- Carte reçu -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
                <tr>
                  <td style="background:#f8faff;border:1px solid #dbeafe;border-radius:12px;padding:28px 32px;">

                    <!-- Titre reçu -->
                    <p style="margin:0 0 20px;font-size:11px;font-weight:700;color:#94a3b8;letter-spacing:2px;text-transform:uppercase;text-align:center;">
                      Reçu de vote officiel
                    </p>

                    <!-- Scrutin -->
                    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">
                      <tr>
                        <td style="font-size:13px;color:#64748b;padding-bottom:4px;">Scrutin</td>
                      </tr>
                      <tr>
                        <td style="font-size:15px;font-weight:600;color:#1a2844;">{scrutin_titre}</td>
                      </tr>
                    </table>

                    <hr style="border:none;border-top:1px solid #dbeafe;margin:0 0 16px;">

                    <!-- Hash -->
                    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px;">
                      <tr>
                        <td style="font-size:13px;color:#64748b;padding-bottom:8px;">
                          Empreinte cryptographique de votre bulletin (SHA-256)
                        </td>
                      </tr>
                      <tr>
                        <td style="background:#1e3a5f;border-radius:8px;padding:14px 16px;">
                          <p style="margin:0;font-family:'Courier New',monospace;font-size:12px;color:#93c5fd;letter-spacing:1px;word-break:break-all;line-height:1.8;">
                            {hash_blocs}
                          </p>
                        </td>
                      </tr>
                    </table>
                    <p style="margin:0;font-size:11px;color:#94a3b8;line-height:1.5;">
                      Cette empreinte est unique et identifie votre bulletin de manière irréversible,
                      sans révéler votre choix.
                    </p>

                  </td>
                </tr>
              </table>

              <!-- Bouton vérification -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
                <tr>
                  <td align="center">
                    <a href="{verification_url}"
                       style="display:inline-block;background:linear-gradient(135deg,#1e3a5f 0%,#2563a8 100%);color:#ffffff;text-decoration:none;font-size:14px;font-weight:600;padding:14px 36px;border-radius:10px;letter-spacing:0.5px;">
                      Vérifier mon vote en ligne
                    </a>
                  </td>
                </tr>
              </table>

              <!-- Séparateur -->
              <hr style="border:none;border-top:1px solid #e5e9f0;margin:0 0 32px;">

              <!-- Garantie anonymat -->
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:18px 20px;">
                    <p style="margin:0 0 6px;font-size:13px;font-weight:600;color:#166534;">
                      Votre anonymat est garanti
                    </p>
                    <p style="margin:0;font-size:13px;color:#15803d;line-height:1.6;">
                      Ce reçu confirme uniquement que votre vote a été enregistré.
                      Il ne révèle en aucun cas le candidat pour lequel vous avez voté.
                      Aucun lien n'existe entre votre identité et votre bulletin dans notre base de données.
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

Votre vote pour "{scrutin_titre}" a bien été enregistré.

RECU DE VOTE OFFICIEL
---------------------
Scrutin : {scrutin_titre}

Empreinte de votre bulletin (SHA-256) :
{hash_blocs}

Cette empreinte confirme que votre vote est bien pris en compte,
sans révéler votre choix. Votre anonymat est garanti.

Vérifier votre vote en ligne :
{verification_url}

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
                    'subject': f'Reçu de vote — {scrutin_titre}',
                }],
                'from':    {'email': 'kenmatiov@gmail.com', 'name': 'VoteSystem'},
                'content': [
                    {'type': 'text/plain', 'value': text_content},
                    {'type': 'text/html',  'value': html_content},
                ],
            },
            timeout=10,
        )
        print(f"SendGrid reçu vote status: {response.status_code}")
    except Exception as e:
        print(f"Erreur envoi email reçu vote: {e}")

class VoteView(generics.CreateAPIView):
    """
    POST /api/v1/electeur/vote/
    Corps : { "scrutin_id": int, "candidat_id": int }
    """
    permission_classes = [IsElecteur]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        import os
        from Crypto.PublicKey import RSA
        from Crypto.Cipher   import PKCS1_OAEP

        electeur    = request.user.electeur
        scrutin_id  = request.data.get('scrutin_id')
        candidat_id = request.data.get('candidat_id')

        # ── Validation paramètres ─────────────────────────────────────────────
        if not scrutin_id or not candidat_id:
            return api_error('ERR_PARAMS_MANQUANTS',
                             'scrutin_id et candidat_id sont requis.', 400)

        # ── Récupérer le scrutin ──────────────────────────────────────────────
        try:
            scrutin = Scrutin.objects.get(id=scrutin_id)
        except Scrutin.DoesNotExist:
            return api_error('ERR_SCRUTIN_INEXISTANT', 'Scrutin introuvable.', 404)

        # ── Moteur d'éligibilité (RG10) ───────────────────────────────────────
        eligible, code_erreur = electeur.est_eligible_scrutin(scrutin)
        if not eligible:
            messages_erreur = {
                'ERR_COMPTE_NON_ELIGIBLE': "Votre compte n'est pas éligible au vote.",
                'ERR_SCRUTIN_FERME':       "Ce scrutin n'est pas actuellement ouvert.",
                'ERR_DOUBLE_VOTE':         'Vous avez déjà voté pour ce scrutin.',
                'ERR_NON_ELIGIBLE':        "Vous n'êtes pas éligible à ce scrutin.",
            }
            http_codes = {
                'ERR_COMPTE_NON_ELIGIBLE': 403,
                'ERR_SCRUTIN_FERME':       403,
                'ERR_DOUBLE_VOTE':         409,
                'ERR_NON_ELIGIBLE':        403,
            }
            return api_error(
                code_erreur,
                messages_erreur.get(code_erreur, 'Non éligible.'),
                http_codes.get(code_erreur, 403),
            )

        # ── Valider le candidat ───────────────────────────────────────────────
        try:
            candidat = Candidat.objects.get(id=candidat_id, scrutin=scrutin)
        except Candidat.DoesNotExist:
            return api_error('ERR_CANDIDAT_INVALIDE',
                             'Candidat invalide pour ce scrutin.', 400)

        # ── Chiffrement RSA 2048 OAEP ─────────────────────────────────────────
        bulletin_data = json.dumps({
            'candidat_id': candidat.id,
            'scrutin_id':  scrutin.id,
        }).encode('utf-8')

        try:
            # Priorité 1 : variable d'environnement (Render production)
            cle_pem = os.environ.get('RSA_PUBLIC_KEY', '').strip()
            if cle_pem:
                cle_publique = RSA.import_key(cle_pem)
            else:
                # Priorité 2 : fichier local (développement)
                with open(django_settings.RSA_PUBLIC_KEY_PATH, 'rb') as f:
                    cle_publique = RSA.import_key(f.read())

            cipher           = PKCS1_OAEP.new(cle_publique)
            bulletin_chiffre = base64.b64encode(
                cipher.encrypt(bulletin_data)
            ).decode('utf-8')

        except Exception as e:
            print(f"Erreur chiffrement RSA : {e}")
            return api_error('ERR_CHIFFREMENT',
                             'Erreur lors du chiffrement du bulletin.', 500)

        # ── Signature HMAC-SHA256 ─────────────────────────────────────────────
        secret    = django_settings.SECRET_KEY.encode('utf-8')
        signature = hmac.new(
            secret, bulletin_chiffre.encode('utf-8'), hashlib.sha256
        ).hexdigest()

        # ── Hash SHA-256 (reçu remis à l'électeur) ────────────────────────────
        hash_vote = hashlib.sha256(
            bulletin_chiffre.encode('utf-8')
        ).hexdigest()

        # ── Stockage anonyme (SANS electeur_id — RG04) ────────────────────────
        vote = Vote.objects.create(
            scrutin          = scrutin,
            candidat         = candidat,
            bulletin_chiffre = bulletin_chiffre,
            signature        = signature,
            hash_vote        = hash_vote,
        )

        # ── Anti-doublon (RG01) ───────────────────────────────────────────────
        ElecteurScrutinVote.objects.create(
            electeur = electeur,
            scrutin  = scrutin,
        )

        # ── Mise à jour flag a_vote ───────────────────────────────────────────
        electeur.a_vote    = True
        electeur.date_vote = timezone.now()
        electeur.save(update_fields=['a_vote', 'date_vote'])

        # ── Journalisation (SANS candidat_id — anonymat préservé) ────────────
        AuditService.log(
            action  = 'VOTE',
            acteur  = request.user,
            details = {'scrutin_id': scrutin.id},
            request = request,
        )

        # ── Envoi email reçu de vote ──────────────────────────────────────────
        frontend_url     = request.headers.get(
            'Origin', 'https://vote-frontend-phi.vercel.app')
        verification_url = f"{frontend_url}/verifier-vote?hash={hash_vote}"
        email_electeur   = request.user.email

        if email_electeur and django_settings.SENDGRID_API_KEY:
            envoyer_email_recu_vote(
                destinataire     = email_electeur,
                prenom           = request.user.first_name or request.user.username,
                scrutin_titre    = scrutin.titre,
                hash_vote        = hash_vote,
                verification_url = verification_url,
                api_key          = django_settings.SENDGRID_API_KEY,
            )

        return Response({
            'status':  'success',
            'message': 'Votre vote a bien été enregistré.',
            'data': {
                'recu':       vote.hash_vote,
                'scrutin_id': scrutin.id,
            },
        }, status=status.HTTP_200_OK)

class VerificationRecuView(generics.RetrieveAPIView):
    """GET /api/v1/electeur/vote/confirmation/{hash_vote}/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, hash_vote):
        existe = Vote.objects.filter(hash_vote=hash_vote).exists()
        if existe:
            return Response({
                'status':  'success',
                'message': 'Ce reçu correspond à un vote valide.',
                'data':    {'hash': hash_vote, 'valide': True},
            })
        return api_error('ERR_RECU_INVALIDE',
                         'Ce reçu ne correspond à aucun vote.', 404)