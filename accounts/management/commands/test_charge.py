import httpx
import asyncio
import time

URL = 'https://vote-backend-api.onrender.com/api/v1/public/scrutins/clotures/'
NB_REQUETES = 50

resultats = {'ok': 0, 'erreur': 0, 'temps': []}

async def une_requete(client, numero):
    debut = time.time()
    try:
        response = await client.get(URL, timeout=15)
        duree = round((time.time() - debut) * 1000)
        resultats['temps'].append(duree)
        if response.status_code < 400:
            resultats['ok'] += 1
            print(f"Requete {numero:02d} : {response.status_code} OK — {duree} ms")
        else:
            resultats['erreur'] += 1
            print(f"Requete {numero:02d} : {response.status_code} ERREUR — {duree} ms")
    except Exception as e:
        resultats['erreur'] += 1
        print(f"Requete {numero:02d} : TIMEOUT/ERREUR — {e}")

async def main():
    print(f"Lancement de {NB_REQUETES} requetes simultanees...\n")
    debut_total = time.time()

    async with httpx.AsyncClient() as client:
        taches = [une_requete(client, i+1) for i in range(NB_REQUETES)]
        await asyncio.gather(*taches)

    duree_totale = round(time.time() - debut_total, 2)

    # Statistiques
    temps = resultats['temps']
    if temps:
        print(f"\n{'='*40}")
        print(f"RESULTATS — {NB_REQUETES} requetes simultanees")
        print(f"{'='*40}")
        print(f"  Succes   : {resultats['ok']}/{NB_REQUETES}")
        print(f"  Erreurs  : {resultats['erreur']}/{NB_REQUETES}")
        print(f"  Temps min    : {min(temps)} ms")
        print(f"  Temps max    : {max(temps)} ms")
        print(f"  Temps moyen  : {round(sum(temps)/len(temps))} ms")
        print(f"  Duree totale : {duree_totale}s")
        print(f"{'='*40}")

        # Verdict disponibilite
        taux = resultats['ok'] / NB_REQUETES * 100
        print(f"\nDISPONIBILITE : {taux:.0f}%")
        if taux == 100:
            print("=> EXCELLENT : aucune requete echouee sur 50 simultanees")
        elif taux >= 95:
            print("=> BON : disponibilite acceptable")
        else:
            print("=> PROBLEME : trop d'erreurs detectees")

asyncio.run(main())