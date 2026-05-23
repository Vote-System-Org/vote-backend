from rest_framework import serializers
from .models import Scrutin, Candidat


class CandidatSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Candidat
        fields = ['id', 'scrutin', 'nom', 'prenom','email', 'photo',
                  'programme', 'est_vote_blanc', 'created_at']
        read_only_fields = ['est_vote_blanc', 'created_at']

    def validate(self, data):
        scrutin = data.get('scrutin') or (self.instance.scrutin if self.instance else None)
        if scrutin and scrutin.statut in ['OUVERT', 'CLOTURE']:
            raise serializers.ValidationError(
                'Impossible de modifier les candidats d\'un scrutin ouvert ou clôturé (RG11).')
        return data


class ScrutinSerializer(serializers.ModelSerializer):
    nb_eligibles   = serializers.SerializerMethodField()
    nb_candidats   = serializers.SerializerMethodField()
    created_by_nom = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model  = Scrutin
        fields = ['id', 'titre', 'description', 'date_debut', 'date_fin',
                  'statut', 'filiere_cible', 'niveau_cible', 'nb_eligibles',
                  'nb_candidats', 'created_by', 'created_by_nom', 'created_at']
        read_only_fields = ['statut', 'created_by', 'created_at']

    def get_nb_eligibles(self, obj):
        return obj.get_nb_eligibles()

    def get_nb_candidats(self, obj):
        return obj.candidats.filter(est_vote_blanc=False).count()

    def validate(self, data):
        debut = data.get('date_debut')
        fin   = data.get('date_fin')
        if debut and fin and fin <= debut:
            raise serializers.ValidationError(
                {'date_fin': 'La date de fin doit être postérieure à la date de début.'})
        return data

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        scrutin = super().create(validated_data)
        # Créer automatiquement le vote blanc (RG03)
        Candidat.objects.create(
            scrutin        = scrutin,
            nom            = 'Vote Blanc',
            est_vote_blanc = True,
        )
        return scrutin


class ScrutinPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Scrutin
        fields = ['id', 'titre', 'description', 'date_debut',
                  'date_fin', 'statut', 'filiere_cible', 'niveau_cible']