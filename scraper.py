import requests
from bs4 import BeautifulSoup
import json
import base64
import os
from datetime import datetime
import hashlib

GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN")
GITHUB_USER   = "profzammataro"
GITHUB_REPO   = "orariodoc"
GITHUB_FILE   = "comunicazioni.json"
SCUOLA_URL    = "https://www.liceolabriola.edu.it/comunicazioni/"
FIREBASE_SA   = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
PROJECT_ID    = "orariodoc"


def scrape_comunicazioni():
    try:
        resp = requests.get(SCUOLA_URL, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"Errore fetch: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    tables = soup.find_all("table")
    ingressi_uscite, sostituzioni, cambi_aula = [], [], []

    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2: continue
        header_cells = rows[0].find_all(["th", "td"])
        headers = [c.get_text(strip=True).upper() for c in header_cells]
        header_str = " ".join(headers)

        if "INGRESSO" in header_str:
            for row in rows[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                if len(cells) >= 2 and any(cells):
                    ingressi_uscite.append({"classe": cells[0] if len(cells)>0 else "", "ingresso": cells[1] if len(cells)>1 else "", "uscita": cells[2] if len(cells)>2 else "", "sostituzione": cells[3] if len(cells)>3 else "", "aula": cells[4] if len(cells)>4 else ""})
        elif "ORA" in header_str and "CLASSE" in header_str and "AULA" in header_str and headers[0] == "ORA":
            for row in rows[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                if len(cells) >= 2 and any(cells):
                    cambi_aula.append({"ora": cells[0] if len(cells)>0 else "", "classe": cells[1] if len(cells)>1 else "", "aula": cells[2] if len(cells)>2 else "", "docente": cells[3] if len(cells)>3 else ""})
        elif "CLASSE" in header_str and "ORA" in header_str and "DOCENTE" in header_str and headers[0] == "CLASSE":
            for row in rows[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                if len(cells) >= 2 and any(cells):
                    sostituzioni.append({"classe": cells[0] if len(cells)>0 else "", "ora": cells[1] if len(cells)>1 else "", "aula": cells[2] if len(cells)>2 else "", "docente": cells[3] if len(cells)>3 else ""})

    data_str, giorno_settimana = "", -1
    GIORNI_IT = {"LUNEDÌ":0,"LUNEDI":0,"MARTEDÌ":1,"MARTEDI":1,"MERCOLEDÌ":2,"MERCOLEDI":2,"GIOVEDÌ":3,"GIOVEDI":3,"VENERDÌ":4,"VENERDI":4}
    MESI_IT = {"GENNAIO":1,"FEBBRAIO":2,"MARZO":3,"APRILE":4,"MAGGIO":5,"GIUGNO":6,"LUGLIO":7,"AGOSTO":8,"SETTEMBRE":9,"OTTOBRE":10,"NOVEMBRE":11,"DICEMBRE":12}
    for h2 in soup.find_all("h2"):
        testo = h2.get_text(strip=True).upper()
        for nome_giorno, idx in GIORNI_IT.items():
            if nome_giorno in testo:
                giorno_settimana = idx
                try:
                    parole = testo.replace("*","").split()
                    mese_num = MESI_IT.get(parole[2], 0)
                    if mese_num:
                        data_str = f"{int(parole[1]):02d}/{mese_num:02d}/{parole[3]}"
                except: pass
                break
    if not data_str:
        data_str = datetime.now().strftime("%d/%m/%Y")

    return {"data": data_str, "giorno_settimana": giorno_settimana, "ingressi_uscite": ingressi_uscite, "sostituzioni": sostituzioni, "cambi_aula": cambi_aula}


def aggiorna_github(dati):
    api_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    r = requests.get(api_url, headers=headers)
    sha = r.json().get("sha", "") if r.status_code == 200 else ""
    contenuto_b64 = base64.b64encode(json.dumps(dati, ensure_ascii=False, indent=2).encode()).decode()
    payload = {"message": f"Comunicazioni aggiornate: {dati['data']}", "content": contenuto_b64}
    if sha: payload["sha"] = sha
    resp = requests.put(api_url, headers=headers, json=payload)
    print(f"{'✅' if resp.status_code in (200,201) else '❌'} GitHub update: {resp.status_code}")


def get_access_token():
    if not FIREBASE_SA: return None
    import time
    try:
        sa = json.loads(FIREBASE_SA)
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        now = int(time.time())
        header = base64.urlsafe_b64encode(json.dumps({"alg":"RS256","typ":"JWT"}).encode()).rstrip(b'=').decode()
        payload_data = {"iss":sa["client_email"],"scope":"https://www.googleapis.com/auth/firebase.messaging https://www.googleapis.com/auth/datastore","aud":"https://oauth2.googleapis.com/token","iat":now,"exp":now+3600}
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b'=').decode()
        private_key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
        msg = f"{header}.{payload_b64}".encode()
        sig_b64 = base64.urlsafe_b64encode(private_key.sign(msg, padding.PKCS1v15(), hashes.SHA256())).rstrip(b'=').decode()
        jwt_token = f"{header}.{payload_b64}.{sig_b64}"
        resp = requests.post("https://oauth2.googleapis.com/token", data={"grant_type":"urn:ietf:params:oauth:grant-type:jwt-bearer","assertion":jwt_token})
        if resp.status_code == 200:
            print("✅ Access token ottenuto")
            return resp.json().get("access_token")
        print(f"❌ Token error: {resp.text}")
    except Exception as e:
        print(f"❌ Errore JWT: {e}")
    return None


def get_firestore_tokens(access_token):
    url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/notifiche_orario"
    resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"})
    if resp.status_code != 200:
        print(f"⚠️ Firestore: {resp.status_code}")
        return []
    docs = resp.json().get("documents", [])
    tokens = []
    for doc in docs:
        f = doc.get("fields", {})
        t = f.get("token",{}).get("stringValue","")
        if t:
            tokens.append({"token":t, "nome":f.get("nome",{}).get("stringValue","").upper(), "tipo":f.get("tipo",{}).get("stringValue","")})
    print(f"📱 {len(tokens)} iscritti")
    return tokens


def invia_notifica(access_token, fcm_token, title, body):
    url = f"https://fcm.googleapis.com/v1/projects/{PROJECT_ID}/messages:send"
    payload = {"message":{"token":fcm_token,"notification":{"title":title,"body":body},"webpush":{"notification":{"icon":"https://profzammataro.github.io/orariodoc/icon-192.png","tag":"orariodoc","vibrate":[200,100,200]}}}}
    resp = requests.post(url, headers={"Authorization":f"Bearer {access_token}","Content-Type":"application/json"}, json=payload)
    return resp.status_code in (200, 201)




def get_hash_firestore(access_token):
    """Legge l'hash delle comunicazioni salvato in Firestore."""
    url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/config/comunicazioni_hash"
    resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"})
    if resp.status_code == 200:
        fields = resp.json().get("fields", {})
        return fields.get("hash", {}).get("stringValue", "")
    return ""


def set_hash_firestore(access_token, new_hash):
    """Salva il nuovo hash delle comunicazioni in Firestore."""
    url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/config/comunicazioni_hash"
    payload = {"fields": {"hash": {"stringValue": new_hash}}}
    resp = requests.patch(url, headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }, json=payload)
    return resp.status_code in (200, 201)

def invia_notifiche(dati, access_token=None):
    if not FIREBASE_SA:
        print("⚠️ Notifiche skip: secret non configurato")
        return
    token = access_token or get_access_token()
    if not token: return
    iscritti = get_firestore_tokens(token)
    if not iscritti:
        print("ℹ️ Nessun iscritto")
        return

    inviati = 0
    # Log debug nomi
    print(f"  📋 Sostituzioni trovate: {[s.get('docente','') for s in dati.get('sostituzioni',[])]}")
    for i in iscritti:
        nome, tipo, fcm = i["nome"], i["tipo"], i["token"]
        title = body = None
        if tipo == "docente":
            subs = [s for s in dati.get("sostituzioni",[])
                    if s.get("docente","").strip() not in ("", "—", "-", "--")
                    and (nome in s.get("docente","").upper().strip()
                    or s.get("docente","").upper().strip() in nome)]

            # Cerca anche cambi aula per le classi del docente
            cambi = [c for c in dati.get("cambi_aula",[])
                     if c.get("docente","").strip() not in ("", "—", "-", "--")
                     and (nome in c.get("docente","").upper().strip()
                     or c.get("docente","").upper().strip() in nome)]

            messaggi = []
            if subs:
                messaggi += [f"{s['ora']}ª ora – {s['classe']} – aula {s['aula']}" for s in subs]
            if cambi:
                messaggi += [f"{c['ora']}ª ora – {c['classe']} – cambio aula {c['aula']}" for c in cambi]

            if messaggi:
                title = "📋 Comunicazione docente"
                body = " | ".join(messaggi)
        elif tipo == "classe":
            iu = [r for r in dati.get("ingressi_uscite",[]) if nome in r.get("classe","").upper()]
            if iu:
                r = iu[0]
                parti = []
                if r.get("ingresso") and r["ingresso"] not in ("—",""):
                    parti.append(f"Ingresso posticipato: {r['ingresso']}")
                if r.get("uscita") and r["uscita"] not in ("—",""):
                    parti.append(f"Uscita anticipata: {r['uscita']}")
                if parti:
                    title = f"📅 Comunicazione per la {nome}"
                    body = " | ".join(parti)
        if title and body:
            ok = invia_notifica(token, fcm, title, body)
            print(f"  {'✅' if ok else '⚠️'} Push → {nome} ({tipo})")
            if ok: inviati += 1

    print(f"📤 Inviate: {inviati}/{len(iscritti)}")


if __name__ == "__main__":
    print("🔄 Avvio scraping...")
    dati = scrape_comunicazioni()
    if dati:
        print(f"📋 {len(dati['sostituzioni'])} sostituzioni, {len(dati['ingressi_uscite'])} ingressi/uscite")
        aggiorna_github(dati)

        if FIREBASE_SA:
            access_token = get_access_token()
            if access_token:
                # Calcola hash delle comunicazioni attuali
                contenuto = json.dumps(dati, ensure_ascii=False, sort_keys=True)
                new_hash = hashlib.md5(contenuto.encode()).hexdigest()
                old_hash = get_hash_firestore(access_token)
                print(f"🔍 Hash nuovo: {new_hash[:8]}... | Hash vecchio: {old_hash[:8] if old_hash else 'nessuno'}...")

                if new_hash != old_hash:
                    print("✅ Comunicazioni cambiate → invio notifiche")
                    set_hash_firestore(access_token, new_hash)
                    invia_notifiche(dati, access_token)
                else:
                    print("⏭️ Comunicazioni invariate → notifiche skip")
        else:
            print("⚠️ Notifiche skip: secret non configurato")
    else:
        print("⚠️ Nessun dato.")
