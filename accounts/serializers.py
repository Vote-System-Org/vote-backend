import csv
import io
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import ListeBlancheReference, Electeur


class InscriptionSerializer(serializers.Serializer):
    matricule        = serializers.CharField(max_length=20)
    email            = serializers.EmailField()
    password         = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError(
                {'password_confirm': 'Les mots de passe ne correspondent pas.'})

        validate_password(data['password'])

        try:
            ref = ListeBlancheReference.objects.get(matricule=data['matricule'])
        except ListeBlancheReference.DoesNotExist:
            raise serializers.ValidationError(
                {'matricule': 'Matricule non reconnu. Contactez l\'administration.'})

        if ref.a_cree_son_compte:
            raise serializers.ValidationError(
                {'matricule': 'Un compte existe déjà pour ce matricule.'})

        if ref.email.lower() != data['email'].lower():
            raise serializers.ValidationError(
                {'email': 'Cet email ne correspond pas à votre matricule.'})

        data['_ref'] = ref
        return data

    def create(self, validated_data):
        ref = validated_data['_ref']

        user = User.objects.create_user(
            username   = validated_data['matricule'],
            email      = validated_data['email'],
            password   = validated_data['password'],
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

        return electeur


class ElecteurSerializer(serializers.ModelSerializer):
    nom    = serializers.CharField(source='user.last_name',  read_only=True)
    prenom = serializers.CharField(source='user.first_name', read_only=True)
    email  = serializers.EmailField(source='user.email')

    class Meta:
        model  = Electeur
        fields = ['id', 'matricule', 'nom', 'prenom', 'email',
                  'filiere', 'niveau', 'statut', 'a_vote', 'date_vote', 'created_at']
        read_only_fields = ['matricule', 'filiere', 'niveau',
                            'a_vote', 'date_vote', 'created_at']

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        if 'email' in user_data:
            instance.user.email = user_data['email']
            instance.user.save()
        return super().update(instance, validated_data)


class ElecteurStatutSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Electeur
        fields = ['statut']

    def validate_statut(self, value):
        allowed = ['ELIGIBLE', 'SUSPENDU']
        if value not in allowed:
            raise serializers.ValidationError(
                f'Statut invalide. Valeurs autorisées : {allowed}')
        return value


class ListeBlancheSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ListeBlancheReference
        fields = ['id', 'matricule', 'nom', 'prenom', 'email',
                  'filiere', 'niveau', 'a_cree_son_compte', 'created_at']
        # matricule, filiere et niveau non modifiables — intégrité du référentiel officiel
        read_only_fields = ['matricule', 'filiere', 'niveau',
                            'a_cree_son_compte', 'created_at']


class ImportCSVSerializer(serializers.Serializer):
    fichier = serializers.FileField()

    def validate_fichier(self, fichier):
        if not fichier.name.endswith('.csv'):
            raise serializers.ValidationError('Le fichier doit être au format CSV.')
        return fichier

    def process(self):
        """Import standard — ignore les doublons existants."""
        fichier = self.validated_data['fichier']
        contenu = fichier.read().decode('utf-8-sig')
        reader  = csv.DictReader(io.StringIO(contenu))

        stats  = {'importes': 0, 'doublons': 0, 'erreurs': 0, 'details_erreurs': []}
        champs = ['matricule', 'nom', 'prenom', 'email', 'filiere', 'niveau']

        for i, row in enumerate(reader, start=2):
            if not all(row.get(c, '').strip() for c in champs):
                stats['erreurs'] += 1
                stats['details_erreurs'].append(f'Ligne {i}: champs manquants')
                continue

            try:
                _, created = ListeBlancheReference.objects.get_or_create(
                    matricule=row['matricule'].strip(),
                    defaults={
                        'nom':     row['nom'].strip(),
                        'prenom':  row['prenom'].strip(),
                        'email':   row['email'].strip().lower(),
                        'filiere': row['filiere'].strip().upper(),
                        'niveau':  row['niveau'].strip().upper(),
                    }
                )
                if created:
                    stats['importes'] += 1
                else:
                    stats['doublons'] += 1
            except Exception as e:
                stats['erreurs'] += 1
                stats['details_erreurs'].append(f'Ligne {i}: {str(e)}')

        return stats

    def process_upsert(self):
        """Import avec mise à jour des entrées existantes non encore inscrites."""
        fichier = self.validated_data['fichier']
        contenu = fichier.read().decode('utf-8-sig')
        reader  = csv.DictReader(io.StringIO(contenu))

        stats  = {
            'importes':       0,
            'mis_a_jour':     0,
            'doublons':       0,
            'erreurs':        0,
            'details_erreurs': [],
        }
        champs = ['matricule', 'nom', 'prenom', 'email', 'filiere', 'niveau']

        for i, row in enumerate(reader, start=2):
            if not all(row.get(c, '').strip() for c in champs):
                stats['erreurs'] += 1
                stats['details_erreurs'].append(f'Ligne {i}: champs manquants')
                continue

            try:
                obj, created = ListeBlancheReference.objects.get_or_create(
                    matricule=row['matricule'].strip(),
                    defaults={
                        'nom':     row['nom'].strip(),
                        'prenom':  row['prenom'].strip(),
                        'email':   row['email'].strip().lower(),
                        'filiere': row['filiere'].strip().upper(),
                        'niveau':  row['niveau'].strip().upper(),
                    }
                )
                if created:
                    stats['importes'] += 1
                elif not obj.a_cree_son_compte:
                    # Mise à jour uniquement si l'étudiant n'a pas encore créé son compte
                    obj.nom     = row['nom'].strip()
                    obj.prenom  = row['prenom'].strip()
                    obj.email   = row['email'].strip().lower()
                    obj.filiere = row['filiere'].strip().upper()
                    obj.niveau  = row['niveau'].strip().upper()
                    obj.save()
                    stats['mis_a_jour'] += 1
                else:
                    # Compte déjà créé — on ne modifie rien
                    stats['doublons'] += 1
            except Exception as e:
                stats['erreurs'] += 1
                stats['details_erreurs'].append(f'Ligne {i}: {str(e)}')

        return stats