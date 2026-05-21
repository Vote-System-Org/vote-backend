from rest_framework import serializers
from .models import LogAudit


class LogAuditSerializer(serializers.ModelSerializer):
    acteur_nom = serializers.CharField(
        source='acteur.username', read_only=True, allow_null=True)

    class Meta:
        model  = LogAudit
        fields = ['id', 'action', 'acteur', 'acteur_nom', 'details',
                  'hash_precedent', 'hash_courant', 'created_at']
        read_only_fields = fields