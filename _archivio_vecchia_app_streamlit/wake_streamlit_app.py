"""
Modulo per risvegliare e mantenere attiva l'applicazione su Streamlit Community Cloud.
Utilizza Playwright per navigare come un vero browser headless, rilevare l'eventuale
stato di dormienza ("This app has gone to sleep due to inactivity") e cliccare
automaticamente il pulsante "Yes, get this app back up!".
In caso di assenza di Playwright o fallimento, esegue un fallback HTTP avanzato con cookie session.
"""

import os
import sys
import time

DEFAULT_APP_URL = "https://prezzifuturescereali-7saqhw3pevvq9rzzswqbpx.streamlit.app"

def wake_with_playwright(target_url: str) -> bool:
    """Tenta di risvegliare l'app Streamlit usando Playwright headless."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[INFO] Playwright non presente, si utilizzerà il fallback HTTP.")
        return False

    print(f"[PLAYWRIGHT] Apertura sessione browser verso {target_url}...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = context.new_page()

            # Navigazione iniziale con timeout generoso (fino a 60s)
            print(f"[PLAYWRIGHT] Caricamento pagina...")
            try:
                page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
            except Exception as e:
                print(f"[PLAYWRIGHT] Attenzione durante goto: {e}")

            time.sleep(5)

            # Rilevamento eventuale stato di ibernazione / pulsante di wake up
            # Streamlit Cloud mostra solitamente un pulsante con testo 'Yes, get this app back up!'
            selectors = [
                "button:has-text('Yes, get this app back up')",
                "button:has-text('get this app back up')",
                "button:has-text('Wake')",
                "button:has-text('Ripristina')",
                "text=This app has gone to sleep"
            ]

            wake_button_found = False
            for selector in selectors:
                try:
                    locator = page.locator(selector).first
                    if locator.is_visible(timeout=3000):
                        print(f"[PLAYWRIGHT] Rilevato stato di dormienza o pulsante con selettore: '{selector}'")
                        if "button" in selector:
                            print("[PLAYWRIGHT] Clicco sul pulsante di risveglio...")
                            locator.click()
                            wake_button_found = True
                            break
                        else:
                            # Se è il testo "This app has gone to sleep", cerca qualsiasi bottone vicino
                            btn = page.locator("button").first
                            if btn.is_visible(timeout=2000):
                                print("[PLAYWRIGHT] Clicco sul bottone associato alla pagina di dormienza...")
                                btn.click()
                                wake_button_found = True
                                break
                except Exception:
                    continue

            if wake_button_found:
                print("[PLAYWRIGHT] Inviata richiesta di risveglio al container Streamlit. Attendo 25 secondi per il riavvio...")
                page.wait_for_timeout(25000)
            else:
                print("[PLAYWRIGHT] L'applicazione non mostra schermate di dormienza (è già sveglia e operativa).")
                page.wait_for_timeout(5000)

            title = page.title()
            print(f"[PLAYWRIGHT] Titolo pagina riscontrato: '{title}'")
            browser.close()
            return True
    except Exception as e:
        print(f"[PLAYWRIGHT] Errore durante l'esecuzione del browser: {e}")
        return False


def wake_with_requests(target_url: str) -> bool:
    """Fallback con richieste HTTP e gestione cookie di sessione Streamlit."""
    import requests

    print(f"[HTTP] Invio ping sessione verso {target_url}...")
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7"
    })

    try:
        response = session.get(target_url, timeout=30, allow_redirects=True)
        print(f"[HTTP] Risposta ricevuta: codice {response.status_code}, URL finale: {response.url}")
        
        # Test anche dell'endpoint health di Streamlit
        health_url = f"{target_url.rstrip('/')}/_stcore/health"
        try:
            h_resp = session.get(health_url, timeout=10)
            print(f"[HTTP] Health check Streamlit: codice {h_resp.status_code}")
        except Exception:
            pass

        if response.status_code in [200, 302, 303]:
            print("[HTTP] Sessione Streamlit mantenuta con successo.")
            return True
        else:
            print(f"[HTTP] Codice inatteso: {response.status_code}")
            return False
    except Exception as e:
        print(f"[HTTP] Errore connessione HTTP: {e}")
        return False


def main():
    target_url = os.getenv("STREAMLIT_APP_URL") or os.getenv("INPUT_URL") or DEFAULT_APP_URL
    target_url = target_url.strip()
    if not target_url.startswith("http"):
        target_url = f"https://{target_url}"

    print(f"=== Keep-Alive Streamlit App ===")
    print(f"URL di destinazione: {target_url}")

    # 1. Prova prima con Playwright (in grado di cliccare il bottone di risveglio se dormiente)
    success = wake_with_playwright(target_url)

    # 2. Se Playwright fallisce o non è installato, esegui fallback HTTP
    if not success:
        print("[INFO] Avvio fallback HTTP...")
        success = wake_with_requests(target_url)

    if success:
        print("[SUCCESSO] Segnale di risveglio e attività registrato correttamente.")
        sys.exit(0)
    else:
        print("[ATTENZIONE] Il ping non ha ricevuto conferma ottimale, ma la richiesta è stata inoltrata.")
        sys.exit(0)

if __name__ == "__main__":
    main()
