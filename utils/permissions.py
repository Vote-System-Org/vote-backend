from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """L'utilisateur doit être staff (administrateur)."""
    message = 'Accès réservé aux administrateurs.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class IsElecteur(BasePermission):
    """L'utilisateur doit être un électeur avec statut ELIGIBLE."""
    message = 'Votre compte n\'est pas éligible.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        try:
            return request.user.electeur.statut == 'ELIGIBLE'
        except Exception:
            return False