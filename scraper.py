import requests
from bs4 import BeautifulSoup
import json
import base64
import os
from datetime import datetime

# ─── CONFIGURAZIONE ───────────────────────────────────────────────
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN")   # Personal Access Token
GITHUB_USER   = "profzammataro"
GITHUB_REPO   = "orariodoc"
GITHUB_FILE   = "comunicazioni.json"
SCUOLA_URL    = "https://www.liceolabriola.edu.it/comunicazioni/"
# ──────────────────────────────────────────────────────────────────

def scrape_comunicazioni():
    """Legge le tabelle dalla pagina scolastica e restituisce i dati strutturati."""
    try:
        resp = requests.get(SCUOLA_URL, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"Errore nel fetch della pagina: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    tables = soup.find_all("table")

    ingressi_uscite = []
    sostituzioni    = []
    cambi_aula      = []

    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        # Leggi intestazione per capire che tabella è
        header_cells = rows[0].find_all(["th", "td"])
        headers = [c.get_text(strip=True).upper() for c in header_cells]
        header_str = " ".join(headers)

        # ─── Tabella INGRESSI / USCITE ───────────────────────────
        if "CLASSI" in header_str and "INGRESSO" in header_str:
            for row in rows[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                if len(cells) >= 2 and any(cells):
                    ingressi_uscite.append({
                        "classe":       cells[0] if len(cells) > 0 else "",
                        "ingresso":     cells[1] if len(cells) > 1 else "",
                        "uscita":       cells[2] if len(cells) > 2 else "",
                        "sostituzione": cells[3] if len(cells) > 3 else "",
                        "aula":         cells[4] if len(cells) > 4 else ""
                    })

        # ─── Tabella SOSTITUZIONI ────────────────────────────────
        elif "CLASSE" in header_str and "ORA" in header_str and "DOCENTE" in header_str:
            for row in rows[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                if len(cells) >= 2 and any(cells):
                    sostituzioni.append({
                        "classe":  cells[0] if len(cells) > 0 else "",
                        "ora":     cells[1] if len(cells) > 1 else "",
                        "aula":    cells[2] if len(cells) > 2 else "",
                        "docente": cells[3] if len(cells) > 3 else ""
                    })

        # ─── Tabella CAMBI AULA ──────────────────────────────────
        elif "ORA" in header_str and "CLASSE" in header_str and "AULA" in header_str:
            for row in rows[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                if len(cells) >= 2 and any(cells):
                    cambi_aula.append({
                        "ora":     cells[0] if len(cells) > 0 else "",
                        "classe":  cells[1] if len(cells) > 1 else "",
                        "aula":    cells[2] if len(cells) > 2 else "",
                        "docente": cells[3] if len(cells) > 3 else ""
                    })

    oggi = datetime.now().strftime("%d/%m/%Y")
    return {
        "data":             oggi,
        "ingressi_uscite":  ingressi_uscite,
        "sostituzioni":     sostituzioni,
        "cambi_aula":       cambi_aula
    }


def aggiorna_github(dati):
    """Carica il JSON aggiornato su GitHub tramite API."""
    api_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    # Recupera SHA del file attuale (necessario per l'update)
    r = requests.get(api_url, headers=headers)
    sha = r.json().get("sha", "") if r.status_code == 200 else ""

    # Codifica il JSON in base64
    contenuto = json.dumps(dati, ensure_ascii=False, indent=2)
    contenuto_b64 = base64.b64encode(contenuto.encode("utf-8")).decode("utf-8")

    payload = {
        "message": f"Comunicazioni aggiornate: {dati['data']}",
        "content": contenuto_b64,
    }
    if sha:
        payload["sha"] = sha

    resp = requests.put(api_url, headers=headers, json=payload)
    if resp.status_code in (200, 201):
        print(f"✅ comunicazioni.json aggiornato con successo ({dati['data']})")
    else:
        print(f"❌ Errore GitHub API: {resp.status_code} – {resp.text}")


if __name__ == "__main__":
    print("🔄 Avvio scraping comunicazioni scolastiche...")
    dati = scrape_comunicazioni()
    if dati:
        print(f"📋 Trovate: {len(dati['ingressi_uscite'])} ingressi/uscite, "
              f"{len(dati['sostituzioni'])} sostituzioni, "
              f"{len(dati['cambi_aula'])} cambi aula")
        aggiorna_github(dati)
    else:
        print("⚠️ Nessun dato recuperato, GitHub non aggiornato.")
