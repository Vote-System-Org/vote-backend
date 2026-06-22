import httpx
import time

URLS = [
    'https://vote-backend-api.onrender.com/api/v1/public/scrutins/clotures/',
    'https://vote-backend-api.onrender.com/api/docs/',
    'https://vote-frontend-phi.vercel.app/',
]

print("=== TEST DE DISPONIBILITE ===\n")

for url in URLS:
    try:
        debut = time.time()
        response = httpx.get(url, timeout=10)
        duree = round((time.time() - debut) * 1000)

        statut = "OK" if response.status_code < 400 else "ERREUR"
        print(f"[{statut}] {url}")
        print(f"      Status : {response.status_code}")
        print(f"      Temps  : {duree} ms\n")

    except httpx.TimeoutException:
        print(f"[TIMEOUT] {url} — pas de reponse apres 10s\n")
    except httpx.ConnectError:
        print(f"[HORS LIGNE] {url} — connexion impossible\n")
