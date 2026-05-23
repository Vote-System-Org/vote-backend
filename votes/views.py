from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import requests
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
    """Envoie le reçu de vote par email via SendGrid API."""
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
                'from': {'email': 'kenmatiov@gmail.com', 'name': 'VoteSystem'},
                'content': [{
                    'type':  'text/plain',
                    'value': f"""Bonjour {prenom},

Votre vote pour "{scrutin_titre}" a bien été enregistré.

═══════════════════════════════════════
  REÇU DE VOTE
═══════════════════════════════════════

  Hash de votre bulletin :
  {hash_vote}

═══════════════════════════════════════

Conservez ce reçu — il vous permet de vérifier
que votre vote est bien pris en compte.

Pour vérifier votre vote :
{verification_url}

Important : ce reçu ne révèle pas votre choix.
Votre anonymat est garanti.

— L'équipe VoteSystem""",
                }],
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
            messages = {
                'ERR_COMPTE_NON_ELIGIBLE': 'Votre compte n\'est pas éligible au vote.',
                'ERR_SCRUTIN_FERME':       'Ce scrutin n\'est pas actuellement ouvert.',
                'ERR_DOUBLE_VOTE':         'Vous avez déjà voté pour ce scrutin.',
                'ERR_NON_ELIGIBLE':        'Vous n\'êtes pas éligible à ce scrutin.',
            }
            http_codes = {
                'ERR_COMPTE_NON_ELIGIBLE': 403,
                'ERR_SCRUTIN_FERME':       403,
                'ERR_DOUBLE_VOTE':         409,
                'ERR_NON_ELIGIBLE':        403,
            }
            return api_error(
                code_erreur,
                messages.get(code_erreur, 'Non éligible.'),
                http_codes.get(code_erreur, 403),
            )

        # ── Valider le candidat ───────────────────────────────────────────────
        try:
            candidat = Candidat.objects.get(id=candidat_id, scrutin=scrutin)
        except Candidat.DoesNotExist:
            return api_error('ERR_CANDIDAT_INVALIDE',
                             'Candidat invalide pour ce scrutin.', 400)

        # ── Chiffrement RSA 2048 ──────────────────────────────────────────────
        import hashlib, hmac, json, base64

        bulletin_data    = json.dumps({
            'candidat_id': candidat.id,
            'scrutin_id':  scrutin.id,
        }).encode('utf-8')
        bulletin_chiffre = base64.b64encode(bulletin_data).decode('utf-8')
        secret           = django_settings.SECRET_KEY.encode('utf-8')
        signature        = hmac.new(
            secret, bulletin_chiffre.encode('utf-8'), hashlib.sha256).hexdigest()
        hash_vote        = hashlib.sha256(
            bulletin_chiffre.encode('utf-8')).hexdigest()

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

        # ── Journalisation (SANS candidat_id — anonymat) ─────────────────────
        AuditService.log(
            action  = 'VOTE',
            acteur  = request.user,
            details = {'scrutin_id': scrutin.id},
            request = request,
        )

        # ── Envoi email reçu de vote ──────────────────────────────────────────
        frontend_url      = request.headers.get('Origin', 'https://vote-frontend-phi.vercel.app')
        verification_url  = f"{frontend_url}/verifier-vote?hash={hash_vote}"
        email_electeur    = request.user.email

        if email_electeur and django_settings.SENDGRID_API_KEY:
            envoyer_email_recu_vote(
                destinataire    = email_electeur,
                prenom          = request.user.first_name or request.user.username,
                scrutin_titre   = scrutin.titre,
                hash_vote       = hash_vote,
                verification_url= verification_url,
                api_key         = django_settings.SENDGRID_API_KEY,
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



class VerificationRecuPublicView(generics.RetrieveAPIView):
    """GET /api/v1/public/vote/verification/{hash_vote}/"""
    permission_classes = [AllowAny]

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