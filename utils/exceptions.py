from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_error(code: str, message: str, http_status: int = 400,
              details: dict = None) -> Response:
    """Retourne une réponse d'erreur au format standard."""
    return Response({
        'status':  'error',
        'code':    code,
        'message': message,
        'details': details or {},
    }, status=http_status)


def custom_exception_handler(exc, context):
    """Handler global qui reformate toutes les erreurs DRF."""
    response = exception_handler(exc, context)

    if response is not None:
        code = 'ERR_VALIDATION' if response.status_code == 400 else 'ERR_SERVER'
        response.data = {
            'status':  'error',
            'code':    code,
            'message': 'Une erreur est survenue.',
            'details': response.data,
        }

    return response