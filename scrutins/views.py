import csv
import requests as http_requests
from django.http import HttpResponse
from django.conf import settings as django_settings
from rest_framework import viewsets, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from utils.permissions import IsAdmin, IsElecteur
from utils.exceptions import api_error
from audit.services import AuditService
from .models import Scrutin, Candidat
from .serializers import ScrutinSerializer, CandidatSerializer, ScrutinPublicSerializer

from django.core.cache import cache
from django.conf import settings as django_settings


def envoyer_email_resultats_candidat(destinataire: str, nom_candidat: str,
                                      scrutin_titre: str, nb_voix: int,
                                      pourcentage: float, nb_votants: int,
                                      taux_participation: float,
                                      gagnant: str, resultats_url: str,
                                      api_key: str):
    """Envoie les résultats par email au candidat via SendGrid avec template HTML professionnel."""

    est_gagnant = nom_candidat.strip().lower() in gagnant.strip().lower()

    if est_gagnant:
        bandeau_bg    = '#16a34a'
        bandeau_texte = 'Félicitations — Vous avez été élu(e) !'
        carte_bg      = '#f0fdf4'
        carte_border  = '#bbf7d0'
        carte_couleur = '#166534'
    else:
        bandeau_bg    = '#2563a8'
        bandeau_texte = 'Résultats du scrutin disponibles'
        carte_bg      = '#f8faff'
        carte_border  = '#dbeafe'
        carte_couleur = '#1e3a5f'

    # Barre de progression pourcentage
    barre_largeur = min(int(pourcentage), 100)

    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Résultats — {scrutin_titre}</title>
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

          <!-- BANDEAU STATUT -->
          <tr>
            <td style="background:{bandeau_bg};padding:16px 48px;text-align:center;">
              <p style="margin:0;color:#ffffff;font-size:14px;font-weight:600;letter-spacing:0.5px;">
                {bandeau_texte}
              </p>
            </td>
          </tr>

          <!-- CORPS -->
          <tr>
            <td style="background:#ffffff;padding:48px;border-left:1px solid #e5e9f0;border-right:1px solid #e5e9f0;">

              <!-- Salutation -->
              <p style="margin:0 0 8px;font-size:22px;font-weight:600;color:#1a2844;">
                Bonjour {nom_candidat},
              </p>
              <p style="margin:0 0 32px;font-size:15px;color:#64748b;line-height:1.6;">
                Le scrutin <strong style="color:#1a2844;">«&nbsp;{scrutin_titre}&nbsp;»</strong>
                vient d'être clôturé. Voici le détail de vos résultats officiels.
              </p>

              <!-- Séparateur -->
              <hr style="border:none;border-top:1px solid #e5e9f0;margin:0 0 32px;">

              <!-- Carte résultats personnels -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
                <tr>
                  <td style="background:{carte_bg};border:1px solid {carte_border};border-radius:12px;padding:28px 32px;">

                    <p style="margin:0 0 20px;font-size:11px;font-weight:700;color:#94a3b8;letter-spacing:2px;text-transform:uppercase;text-align:center;">
                      Vos résultats
                    </p>

                    <!-- Grille stats -->
                    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
                      <tr>
                        <td width="50%" style="padding:0 8px 0 0;">
                          <table width="100%" cellpadding="0" cellspacing="0">
                            <tr>
                              <td style="background:#ffffff;border:1px solid #e5e9f0;border-radius:8px;padding:16px;text-align:center;">
                                <p style="margin:0 0 4px;font-size:28px;font-weight:700;color:{carte_couleur};">{nb_voix}</p>
                                <p style="margin:0;font-size:12px;color:#94a3b8;">Voix obtenues</p>
                              </td>
                            </tr>
                          </table>
                        </td>
                        <td width="50%" style="padding:0 0 0 8px;">
                          <table width="100%" cellpadding="0" cellspacing="0">
                            <tr>
                              <td style="background:#ffffff;border:1px solid #e5e9f0;border-radius:8px;padding:16px;text-align:center;">
                                <p style="margin:0 0 4px;font-size:28px;font-weight:700;color:{carte_couleur};">{pourcentage}%</p>
                                <p style="margin:0;font-size:12px;color:#94a3b8;">Des suffrages</p>
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                    </table>

                    <!-- Barre de progression -->
                    <p style="margin:0 0 8px;font-size:12px;color:#64748b;">
                      Part des voix obtenues
                    </p>
                    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:4px;">
                      <tr>
                        <td style="background:#e5e9f0;border-radius:999px;height:10px;overflow:hidden;">
                          <div style="background:linear-gradient(90deg,#1e3a5f,#2563a8);height:10px;width:{barre_largeur}%;border-radius:999px;"></div>
                        </td>
                      </tr>
                    </table>
                    <p style="margin:0;font-size:11px;color:#94a3b8;text-align:right;">{pourcentage}%</p>

                  </td>
                </tr>
              </table>

              <!-- Carte participation globale -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
                <tr>
                  <td style="background:#f8faff;border:1px solid #e5e9f0;border-radius:12px;padding:20px 32px;">
                    <p style="margin:0 0 16px;font-size:11px;font-weight:700;color:#94a3b8;letter-spacing:2px;text-transform:uppercase;">
                      Données globales du scrutin
                    </p>
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="font-size:13px;color:#64748b;padding:6px 0;border-bottom:1px solid #e5e9f0;">
                          Total des votants
                        </td>
                        <td style="font-size:13px;font-weight:600;color:#1a2844;text-align:right;padding:6px 0;border-bottom:1px solid #e5e9f0;">
                          {nb_votants} électeurs
                        </td>
                      </tr>
                      <tr>
                        <td style="font-size:13px;color:#64748b;padding:6px 0;border-bottom:1px solid #e5e9f0;">
                          Taux de participation
                        </td>
                        <td style="font-size:13px;font-weight:600;color:#1a2844;text-align:right;padding:6px 0;border-bottom:1px solid #e5e9f0;">
                          {taux_participation}%
                        </td>
                      </tr>
                      <tr>
                        <td style="font-size:13px;color:#64748b;padding:6px 0;">
                          Candidat élu
                        </td>
                        <td style="font-size:13px;font-weight:600;color:#16a34a;text-align:right;padding:6px 0;">
                          {gagnant}
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Bouton résultats complets -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
                <tr>
                  <td align="center">
                    <a href="{resultats_url}"
                       style="display:inline-block;background:linear-gradient(135deg,#1e3a5f 0%,#2563a8 100%);color:#ffffff;text-decoration:none;font-size:14px;font-weight:600;padding:14px 36px;border-radius:10px;letter-spacing:0.5px;">
                      Consulter les résultats complets
                    </a>
                  </td>
                </tr>
              </table>

              <!-- Séparateur -->
              <hr style="border:none;border-top:1px solid #e5e9f0;margin:0 0 24px;">

              <!-- Note intégrité -->
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background:#f8faff;border-radius:8px;padding:18px 20px;">
                    <p style="margin:0 0 6px;font-size:13px;font-weight:600;color:#1e3a5f;">
                      Intégrité des résultats garantie
                    </p>
                    <p style="margin:0;font-size:13px;color:#64748b;line-height:1.6;">
                      Ces résultats ont été calculés automatiquement à partir des bulletins
                      chiffrés en RSA 2048 et signés par HMAC-SHA256. Toute altération
                      est détectable grâce à la chaîne d'audit immuable du système.
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

    text_content = f"""Bonjour {nom_candidat},

Le scrutin "{scrutin_titre}" vient d'être clôturé.

VOS RÉSULTATS
-------------
Voix obtenues    : {nb_voix}
Part des suffrages : {pourcentage}%
Total votants    : {nb_votants}
Taux participation : {taux_participation}%
Candidat élu     : {gagnant}

Consultez les résultats complets :
{resultats_url}

— VoteSystem | Université | Génie Logiciel 2025-2026"""

    try:
        response = http_requests.post(
            'https://api.sendgrid.com/v3/mail/send',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type':  'application/json',
            },
            json={
                'personalizations': [{
                    'to':      [{'email': destinataire}],
                    'subject': f'Résultats — {scrutin_titre}',
                }],
                'from':    {'email': 'kenmatiov@gmail.com', 'name': 'VoteSystem'},
                'content': [
                    {'type': 'text/plain', 'value': text_content},
                    {'type': 'text/html',  'value': html_content},
                ],
            },
            timeout=10,
        )
        print(f"Email résultats candidat {destinataire}: {response.status_code}")
    except Exception as e:
        print(f"Erreur email résultats: {e}")


class ScrutinAdminViewSet(viewsets.ModelViewSet):
    """CRUD scrutins — admin uniquement"""
    queryset           = Scrutin.objects.all()
    serializer_class   = ScrutinSerializer
    permission_classes = [IsAdmin]

    def update(self, request, *args, **kwargs):
        scrutin = self.get_object()
        if scrutin.statut != 'BROUILLON':
            return api_error('ERR_SCRUTIN_MODIF_IMPOSSIBLE',
                             'Seul un scrutin en BROUILLON peut être modifié.', 403)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        scrutin = self.get_object()
        if scrutin.statut != 'BROUILLON':
            return api_error('ERR_SCRUTIN_MODIF_IMPOSSIBLE',
                             'Seul un scrutin en BROUILLON peut être supprimé.', 403)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def ouvrir(self, request, pk=None):
        """POST /api/v1/admin/scrutins/{id}/ouvrir/"""
        scrutin = self.get_object()
        try:
            scrutin.ouvrir()
            AuditService.log(
                action  = 'OUVERTURE_SCRUTIN',
                acteur  = request.user,
                details = {'scrutin_id': scrutin.id, 'declencheur': 'manuel'},
                request = request,
            )
            return Response({
                'status':  'success',
                'message': 'Scrutin ouvert.',
                'data':    ScrutinSerializer(scrutin, context={'request': request}).data,
            })
        except ValueError as e:
            return api_error('ERR_OUVERTURE_IMPOSSIBLE', str(e), 400)

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        """POST /api/v1/admin/scrutins/{id}/cloturer/"""
        scrutin = self.get_object()
        try:
            scrutin.cloturer()
            # Invalider tous les caches liés à ce scrutin
            cache.delete(f"candidats_scrutin_{scrutin.id}")
            cache.delete(f"resultats_public_{scrutin.id}")
            cache.delete(f"resultats_electeur_{scrutin.id}")
            cache.delete("scrutins_clotures_public")
            cache.delete_pattern("scrutins_eligibles_*")
            AuditService.log(
                action  = 'CLOTURE_SCRUTIN',
                acteur  = request.user,
                details = {'scrutin_id': scrutin.id, 'declencheur': 'manuel'},
                request = request,
            )

            # ── Envoi emails aux candidats ────────────────────────────
            api_key = getattr(django_settings, 'SENDGRID_API_KEY', '')
            if api_key:
                try:
                    from votes.models import Vote
                    from accounts.models import Electeur

                    candidats  = scrutin.candidats.filter(est_vote_blanc=False)
                    nb_votants = Vote.objects.filter(scrutin=scrutin).count()

                    # Calculer nb_eligibles
                    qs = Electeur.objects.filter(statut='ELIGIBLE')
                    if scrutin.filiere_cible:
                        qs = qs.filter(filiere=scrutin.filiere_cible)
                    if scrutin.niveau_cible:
                        qs = qs.filter(niveau=scrutin.niveau_cible)
                    nb_eligibles = qs.count()

                    taux = round((nb_votants / nb_eligibles * 100), 1) \
                           if nb_eligibles > 0 else 0

                    # Calculer le gagnant
                    resultats_list = []
                    for c in scrutin.candidats.all():
                        nb = Vote.objects.filter(scrutin=scrutin, candidat=c).count()
                        resultats_list.append((c, nb))

                    gagnant_obj = max(
                        [r for r in resultats_list if not r[0].est_vote_blanc],
                        key=lambda x: x[1],
                        default=(None, 0)
                    )
                    gagnant_nom = f"{gagnant_obj[0].nom} {gagnant_obj[0].prenom or ''}".strip() \
                        if gagnant_obj[0] else 'Aucun'

                    frontend_url  = request.headers.get(
                        'Origin', 'https://vote-frontend-phi.vercel.app')
                    resultats_url = f"{frontend_url}/resultats/{scrutin.id}"

                    for candidat in candidats:
                        if candidat.email:
                            nb_voix_candidat = next(
                                (nb for c, nb in resultats_list if c.id == candidat.id), 0
                            )
                            pourcentage = round((nb_voix_candidat / nb_votants * 100), 1) \
                                if nb_votants > 0 else 0
                            envoyer_email_resultats_candidat(
                                destinataire       = candidat.email,
                                nom_candidat       = f"{candidat.nom} {candidat.prenom or ''}".strip(),
                                scrutin_titre      = scrutin.titre,
                                nb_voix            = nb_voix_candidat,
                                pourcentage        = pourcentage,
                                nb_votants         = nb_votants,
                                taux_participation = taux,
                                gagnant            = gagnant_nom,
                                resultats_url      = resultats_url,
                                api_key            = api_key,
                            )
                except Exception as e:
                    print(f"Erreur envoi emails clôture: {e}")

            return Response({
                'status':  'success',
                'message': 'Scrutin clôturé.',
                'data':    ScrutinSerializer(scrutin, context={'request': request}).data,
            })
        except ValueError as e:
            return api_error('ERR_CLOTURE_IMPOSSIBLE', str(e), 400)

    @action(detail=True, methods=['get'])
    def resultats(self, request, pk=None):
        """GET /api/v1/admin/scrutins/{id}/resultats/"""
        from votes.models import Vote
        from votes.services import verifier_signature_bulletin
        from audit.services import AuditService

        scrutin = self.get_object()

        # ── Vérification d'intégrité de tous les bulletins ────────────────
        bulletins_alteres = []
        votes = Vote.objects.filter(scrutin=scrutin)

        for vote in votes:
            if not verifier_signature_bulletin(vote.bulletin_chiffre, vote.signature):
                bulletins_alteres.append(vote.id)
                # Journalise l'alerte sans révéler le candidat
                AuditService.log(
                    action  = 'ALERTE_FRAUDE',
                    acteur  = request.user,
                    details = {'scrutin_id': scrutin.id, 'vote_id': vote.id},
                    request = request,
                )

        resultats = scrutin.get_resultats()

        # Ajoute l'info d'intégrité dans la réponse admin
        resultats['integrite'] = {
            'bulletins_total'   : votes.count(),
            'bulletins_valides' : votes.count() - len(bulletins_alteres),
            'bulletins_alteres' : len(bulletins_alteres),
            'alerte'            : len(bulletins_alteres) > 0,
        }

        return Response({'status': 'success', 'data': resultats})

    @action(detail=True, methods=['get'], url_path='resultats/export')
    def export_csv(self, request, pk=None):
        """GET /api/v1/admin/scrutins/{id}/resultats/export/"""
        scrutin   = self.get_object()
        resultats = scrutin.get_resultats()

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = \
            f'attachment; filename="resultats_{scrutin.id}.csv"'
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow(['Scrutin', 'Date début', 'Date fin',
                         'Nb éligibles', 'Nb votants', 'Taux participation'])
        writer.writerow([
            resultats['titre'], scrutin.date_debut, scrutin.date_fin,
            resultats['nb_eligibles'], resultats['nb_votants'],
            f"{resultats['taux_participation']}%",
        ])
        writer.writerow([])
        writer.writerow(['Candidat', 'Prénom', 'Type', 'Nb voix', 'Pourcentage'])
        for r in resultats['resultats']:
            writer.writerow([
                r['nom'], r.get('prenom', ''),
                'Vote Blanc' if r['est_vote_blanc'] else 'Candidat réel',
                r['nb_voix'], f"{r['pourcentage']}%",
            ])
        writer.writerow(['Abstentions', '', '', resultats['nb_abstentions'], ''])

        return response


class CandidatAdminViewSet(viewsets.ModelViewSet):
    """CRUD candidats — admin uniquement"""
    serializer_class   = CandidatSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        scrutin_pk = self.request.query_params.get('scrutin_id')
        if scrutin_pk:
            return Candidat.objects.filter(scrutin_id=scrutin_pk)
        return Candidat.objects.all()

    def destroy(self, request, *args, **kwargs):
        candidat = self.get_object()
        if candidat.est_vote_blanc:
            return api_error('ERR_CANDIDAT_VOTE_BLANC',
                             'Le candidat vote blanc ne peut pas être supprimé (RG03).', 403)
        if candidat.scrutin.statut in ['OUVERT', 'CLOTURE']:
            return api_error('ERR_SCRUTIN_MODIF_IMPOSSIBLE',
                             'Impossible de supprimer un candidat sur scrutin ouvert/clôturé.', 403)
        return super().destroy(request, *args, **kwargs)


class ScrutinsEligiblesView(generics.ListAPIView):
    """GET /api/v1/electeur/scrutins/ — avec cache Redis 30s"""
    serializer_class   = ScrutinSerializer
    permission_classes = [IsElecteur]

    def get_queryset(self):
        electeur   = self.request.user.electeur
        cache_key  = f"scrutins_eligibles_{electeur.filiere}_{electeur.niveau}_{electeur.id}"
        cached     = cache.get(cache_key)
        if cached is not None:
            return cached

        from django.db.models import Q
        from votes.models import ElecteurScrutinVote

        deja_votes = ElecteurScrutinVote.objects.filter(
            electeur=electeur).values_list('scrutin_id', flat=True)

        queryset = Scrutin.objects.filter(statut='OUVERT').filter(
            Q(filiere_cible__isnull=True) | Q(filiere_cible=electeur.filiere)
        ).filter(
            Q(niveau_cible__isnull=True) | Q(niveau_cible=electeur.niveau)
        ).exclude(id__in=deja_votes)

        timeout = getattr(django_settings, 'CACHE_SCRUTINS_ELIGIBLES', 30)
        cache.set(cache_key, queryset, timeout=timeout)
        return queryset

class CandidatsScrutinView(generics.ListAPIView):
    """GET /api/v1/electeur/scrutins/{id}/candidats/ — avec cache Redis 2min"""
    serializer_class   = CandidatSerializer
    permission_classes = [IsElecteur]

    def get_queryset(self):
        scrutin_id = self.kwargs['pk']
        electeur   = self.request.user.electeur
        cache_key  = f"candidats_scrutin_{scrutin_id}"
        cached     = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            scrutin = Scrutin.objects.get(id=scrutin_id, statut='OUVERT')
        except Scrutin.DoesNotExist:
            return Candidat.objects.none()

        eligible, _ = electeur.est_eligible_scrutin(scrutin)
        if not eligible:
            return Candidat.objects.none()

        queryset = Candidat.objects.filter(scrutin=scrutin)
        timeout  = getattr(django_settings, 'CACHE_LISTE_CANDIDATS', 120)
        cache.set(cache_key, queryset, timeout=timeout)
        return queryset

class ResultatsElecteurView(generics.RetrieveAPIView):
    """GET /api/v1/electeur/scrutins/{id}/resultats/ — avec cache Redis 60s"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        cache_key = f"resultats_electeur_{pk}"
        cached    = cache.get(cache_key)
        if cached is not None:
            return Response({'status': 'success', 'data': cached})

        try:
            scrutin = Scrutin.objects.get(id=pk)
        except Scrutin.DoesNotExist:
            return api_error('ERR_SCRUTIN_INEXISTANT', 'Scrutin introuvable.', 404)

        if scrutin.statut != 'CLOTURE':
            return api_error('ERR_RESULTATS_PROTEGES',
                             'Résultats disponibles uniquement après clôture (RG07).', 403)

        resultats = scrutin.get_resultats()
        timeout   = getattr(django_settings, 'CACHE_RESULTATS_PUBLICS', 60)
        cache.set(cache_key, resultats, timeout=timeout)
        return Response({'status': 'success', 'data': resultats})

class ResultatsPublicView(generics.RetrieveAPIView):
    """GET /api/v1/public/scrutins/{id}/resultats/ — avec cache Redis 60s"""
    permission_classes = [AllowAny]

    def get(self, request, pk):
        cache_key = f"resultats_public_{pk}"
        cached    = cache.get(cache_key)
        if cached is not None:
            return Response({'status': 'success', 'data': cached})

        try:
            scrutin = Scrutin.objects.get(id=pk, statut='CLOTURE')
        except Scrutin.DoesNotExist:
            return api_error('ERR_RESULTATS_INDISPONIBLES',
                             'Résultats non disponibles.', 404)

        resultats = scrutin.get_resultats()
        timeout   = getattr(django_settings, 'CACHE_RESULTATS_PUBLICS', 60)
        cache.set(cache_key, resultats, timeout=timeout)
        return Response({'status': 'success', 'data': resultats})

class ScrutinsClotures(generics.ListAPIView):
    """GET /api/v1/electeur/scrutins/clotures/"""
    serializer_class   = ScrutinSerializer
    permission_classes = [IsElecteur]

    def get_queryset(self):
        electeur = self.request.user.electeur
        from django.db.models import Q
        return Scrutin.objects.filter(statut='CLOTURE').filter(
            Q(filiere_cible__isnull=True) | Q(filiere_cible=electeur.filiere)
        ).filter(
            Q(niveau_cible__isnull=True) | Q(niveau_cible=electeur.niveau)
        )


class ScrutinsCloturesPublicView(generics.ListAPIView):
    """GET /api/v1/public/scrutins/clotures/ — avec cache Redis 60s"""
    serializer_class   = ScrutinPublicSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        cache_key = "scrutins_clotures_public"
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached

        queryset = Scrutin.objects.filter(
            statut='CLOTURE').order_by('-date_fin')
        cache.set(cache_key, queryset, timeout=60)
        return queryset



# Commande de management pour clôturer automatiquement les scrutins expirés (RG06)
# Cron Render : `0 * * * *` (toutes les heures à 0 min)



from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clôture automatiquement les scrutins dont date_fin est dépassée (RG06)'

    def handle(self, *args, **options):
        from scrutins.models import Scrutin
        from audit.services import AuditService

        scrutins_expires = Scrutin.objects.filter(
            statut='OUVERT',
            date_fin__lte=timezone.now()
        )

        count = scrutins_expires.count()

        if count == 0:
            self.stdout.write("Aucun scrutin à clôturer.")
            return

        for scrutin in scrutins_expires:
            try:
                scrutin.statut = 'CLOTURE'
                scrutin.save(update_fields=['statut'])

                # Invalider le cache
                cache.delete(f"candidats_scrutin_{scrutin.id}")
                cache.delete(f"resultats_public_{scrutin.id}")
                cache.delete(f"resultats_electeur_{scrutin.id}")
                cache.delete("scrutins_clotures_public")
                cache.delete_pattern("scrutins_eligibles_*")

                # Log audit
                AuditService.log(
                    action='CLOTURE_SCRUTIN',
                    acteur=None,
                    details={
                        'scrutin_id':  scrutin.id,
                        'titre':       scrutin.titre,
                        'declencheur': 'CRON_RENDER',
                    }
                )

                # Envoyer emails résultats
                self._envoyer_emails(scrutin)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Scrutin {scrutin.id} '{scrutin.titre}' clôturé."
                    )
                )
                logger.info(f"Scrutin {scrutin.id} clôturé via cron Render.")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Erreur scrutin {scrutin.id} : {e}")
                )
                logger.error(f"Erreur clôture scrutin {scrutin.id} : {e}")

        self.stdout.write(f"{count} scrutin(s) clôturé(s).")

    def _envoyer_emails(self, scrutin):
        """Envoie les résultats par email à chaque candidat."""
        try:
            from votes.models import Vote
            from django.core.mail import send_mail
            from django.conf import settings

            candidats  = scrutin.candidats.filter(
                est_vote_blanc=False
            ).exclude(email='').exclude(email__isnull=True)

            total_votes = Vote.objects.filter(scrutin=scrutin).count()

            for candidat in candidats:
                nb_voix     = Vote.objects.filter(
                    scrutin=scrutin, candidat=candidat
                ).count()
                pourcentage = round(
                    (nb_voix / total_votes * 100), 1
                ) if total_votes > 0 else 0

                send_mail(
                    subject=f"Résultats — {scrutin.titre}",
                    message=(
                        f"Bonjour {candidat.prenom} {candidat.nom},\n\n"
                        f"Le scrutin '{scrutin.titre}' est clôturé.\n\n"
                        f"Vos résultats :\n"
                        f"  Voix : {nb_voix} / {total_votes} "
                        f"({pourcentage}%)\n\n"
                        f"Cordialement,\nL'équipe VoteSystem"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[candidat.email],
                    fail_silently=True,
                )
        except Exception as e:
            logger.error(f"Erreur emails scrutin {scrutin.id} : {e}")



# Commande de management pour clôturer automatiquement les scrutins expirés (RG06) via GitHub Actions
# Cron GitHub Actions : `0 * * * *` (toutes les heures à 0 min)



from rest_framework.decorators import api_view, permission_classes as drf_permission_classes


@api_view(['POST'])
@drf_permission_classes([AllowAny])
def cron_cloture(request):
    """
    POST /api/v1/public/cron/cloture/
    Endpoint appelé par le cron GitHub Actions — sécurisé par token secret.
    """
    token = request.headers.get('X-Cron-Token', '')
    from django.conf import settings as conf
    if not token or token != getattr(conf, 'CRON_SECRET_TOKEN', ''):
        return Response({'error': 'Non autorisé'}, status=403)

    from django.utils import timezone
    from audit.services import AuditService

    scrutins_expires = Scrutin.objects.filter(
        statut='OUVERT',
        date_fin__lte=timezone.now()
    )

    count    = scrutins_expires.count()
    clotures = []

    for scrutin in scrutins_expires:
        try:
            scrutin.statut = 'CLOTURE'
            scrutin.save(update_fields=['statut'])

            # Invalider le cache
            cache.delete(f"candidats_scrutin_{scrutin.id}")
            cache.delete(f"resultats_public_{scrutin.id}")
            cache.delete(f"resultats_electeur_{scrutin.id}")
            cache.delete("scrutins_clotures_public")
            try:
                cache.delete_pattern("scrutins_eligibles_*")
            except Exception:
                pass

            AuditService.log(
                action='CLOTURE_SCRUTIN',
                acteur=None,
                details={
                    'scrutin_id':  scrutin.id,
                    'titre':       scrutin.titre,
                    'declencheur': 'CRON_GITHUB_ACTIONS',
                }
            )

            clotures.append({'id': scrutin.id, 'titre': scrutin.titre})

        except Exception as e:
            logger.error(f"Erreur clôture scrutin {scrutin.id} : {e}")

    return Response({
        'status':   'success',
        'clotures': count,
        'scrutins': clotures,
    })
