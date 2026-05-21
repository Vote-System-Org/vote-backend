from rest_framework import generics, filters
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from utils.permissions import IsAdmin
from .models import LogAudit
from .serializers import LogAuditSerializer


class LogAuditListView(generics.ListAPIView):
    """GET /api/v1/admin/audit/logs/"""
    queryset           = LogAudit.objects.select_related('acteur').all()
    serializer_class   = LogAuditSerializer
    permission_classes = [IsAdmin]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter,
                          filters.OrderingFilter]
    filterset_fields   = ['action']
    search_fields      = ['action', 'acteur__username']
    ordering_fields    = ['created_at']
    ordering           = ['-created_at']


class VerifierIntegriteView(generics.GenericAPIView):
    """GET /api/v1/admin/audit/integrite/"""
    permission_classes = [IsAdmin]

    def get(self, request):
        integre, message = LogAudit.verifier_integrite()
        return Response({
            'status':  'success' if integre else 'error',
            'integre': integre,
            'message': message,
        })