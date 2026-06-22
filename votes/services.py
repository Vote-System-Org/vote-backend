import base64
import json
import hmac
import hashlib
from django.conf import settings as django_settings


def verifier_signature_bulletin(bulletin_chiffre: str, signature: str) -> bool:
    """
    Vérifie que la signature HMAC-SHA256 d'un bulletin est valide.
    Retourne True si intact, False si altéré.
    """
    secret = django_settings.SECRET_KEY.encode('utf-8')
    signature_attendue = hmac.new(
        secret,
        bulletin_chiffre.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    # compare_digest évite les attaques par timing
    return hmac.compare_digest(signature_attendue, signature)


def dechiffrer_bulletin(bulletin_chiffre_b64: str) -> dict:
    """
    Déchiffre un bulletin RSA 2048 OAEP.
    Retourne : {'candidat_id': int, 'scrutin_id': int}
    """
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_OAEP

    with open(django_settings.RSA_PRIVATE_KEY_PATH, 'rb') as f:
        cle_privee = RSA.import_key(f.read())

    cipher         = PKCS1_OAEP.new(cle_privee)
    bulletin_bytes = base64.b64decode(bulletin_chiffre_b64)
    contenu        = cipher.decrypt(bulletin_bytes)
    return json.loads(contenu.decode('utf-8'))