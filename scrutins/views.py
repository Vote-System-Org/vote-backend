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
    """Envoie les résultats par email au candidat via SendGrid."""
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
                'from': {'email': 'kenmatiov@gmail.com', 'name': 'VoteSystem'},
                'content': [{
                    'type':  'text/plain',
                    'value': f"""Bonjour {nom_candidat},

Le scrutin "{scrutin_titre}" vient d'être clôturé.

═══════════════════════════════════════
  VOS RÉSULTATS
═══════════════════════════════════════

  Voix obtenues   : {nb_voix}
  Pourcentage     : {pourcentage}%
  Total votants   : {nb_votants}
  Participation   : {taux_participation}%

  Élu(e)          : {gagnant}

═══════════════════════════════════════

Consultez les résultats complets :
{resultats_url}

— L'équipe VoteSystem""",
                }],
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
        scrutin = self.get_object()
        return Response({'status': 'success', 'data': scrutin.get_resultats()})

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