import csv
from django.http import HttpResponse
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend

from utils.permissions import IsAdmin, IsElecteur
from utils.exceptions import api_error
from audit.services import AuditService
from .models import Scrutin, Candidat
from .serializers import ScrutinSerializer, CandidatSerializer


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
            AuditService.log(
                action  = 'CLOTURE_SCRUTIN',
                acteur  = request.user,
                details = {'scrutin_id': scrutin.id, 'declencheur': 'manuel'},
                request = request,
            )
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
        response.write('\ufeff')  # BOM UTF-8 pour Excel

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
        scrutin_pk = self.kwargs.get('scrutin_pk')
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
    """GET /api/v1/electeur/scrutins/"""
    serializer_class   = ScrutinSerializer
    permission_classes = [IsElecteur]

    def get_queryset(self):
        electeur = self.request.user.electeur
        from django.db.models import Q
        from votes.models import ElecteurScrutinVote

        deja_votes = ElecteurScrutinVote.objects.filter(
            electeur=electeur).values_list('scrutin_id', flat=True)

        return Scrutin.objects.filter(statut='OUVERT').filter(
            Q(filiere_cible__isnull=True) | Q(filiere_cible=electeur.filiere)
        ).filter(
            Q(niveau_cible__isnull=True) | Q(niveau_cible=electeur.niveau)
        ).exclude(id__in=deja_votes)


class CandidatsScrutinView(generics.ListAPIView):
    """GET /api/v1/electeur/scrutins/{id}/candidats/"""
    serializer_class   = CandidatSerializer
    permission_classes = [IsElecteur]

    def get_queryset(self):
        scrutin_id = self.kwargs['pk']
        electeur   = self.request.user.electeur
        try:
            scrutin = Scrutin.objects.get(id=scrutin_id, statut='OUVERT')
        except Scrutin.DoesNotExist:
            return Candidat.objects.none()
        eligible, _ = electeur.est_eligible_scrutin(scrutin)
        if not eligible:
            return Candidat.objects.none()
        return Candidat.objects.filter(scrutin=scrutin)


class ResultatsElecteurView(generics.RetrieveAPIView):
    """GET /api/v1/electeur/scrutins/{id}/resultats/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            scrutin = Scrutin.objects.get(id=pk)
        except Scrutin.DoesNotExist:
            return api_error('ERR_SCRUTIN_INEXISTANT', 'Scrutin introuvable.', 404)
        if scrutin.statut != 'CLOTURE':
            return api_error('ERR_RESULTATS_PROTEGES',
                             'Résultats disponibles uniquement après clôture (RG07).', 403)
        return Response({'status': 'success', 'data': scrutin.get_resultats()})


class ResultatsPublicView(generics.RetrieveAPIView):
    """GET /api/v1/public/scrutins/{id}/resultats/"""
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            scrutin = Scrutin.objects.get(id=pk, statut='CLOTURE')
        except Scrutin.DoesNotExist:
            return api_error('ERR_RESULTATS_INDISPONIBLES',
                             'Résultats non disponibles.', 404)
        return Response({'status': 'success', 'data': scrutin.get_resultats()})