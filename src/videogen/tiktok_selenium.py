"""TikTok auto-uploader vía Selenium (cuenta desechable, riesgo ban).

Alternativa a la Content Posting API que quedó en Sandbox (drafts only).
Usa browser automation con cookies pre-autenticadas.

IMPORTANTE:
- Usar SIEMPRE con cuenta TT DESECHABLE, nunca la principal (@interest_stuff).
- TikTok puede detectar automatización → risk de shadow-ban o ban duro.
- Ejecutar máx 3-5 uploads/día para minimizar señales de bot.
- Rotar user-agents + delays humanos aleatorios.

Setup one-time (user):
1. Crear cuenta TT NUEVA (ej. @waitwhy_es_bot) — NO usar principal.
2. Login en Chrome desktop con esa cuenta.
3. Instalar extension 'Get cookies.txt' (EditThisCookie).
4. Exportar cookies de tiktok.com como JSON.
5. Guardar en GitHub Secret TIKTOK_COOKIES_JSON (json array de cookies).

Uso:
    from videogen.tiktok_selenium import upload_via_selenium
    result = upload_via_selenium(video_path, caption)
"""
from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import Any, Optional


def _prepare_driver():
    """Chrome headless con anti-detection + cookies TT cargadas.
    Requiere selenium + webdriver-manager (chromedriver auto-install)."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
    except ImportError:
        print("  tt-selenium: selenium no instalado — pip install selenium")
        return None

    opts = Options()
    # Headless moderno (no --headless=old que TT detecta)
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--window-size=1920,1080")
    # User-agent común desktop (no webdriver default)
    ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
          "AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/128.0.0.0 Safari/537.36")
    opts.add_argument(f"--user-agent={ua}")
    # Excluye señales automation
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    try:
        # Auto-install chromedriver si no existe (webdriver-manager)
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=opts)
        except ImportError:
            # Fallback: chromedriver en PATH del sistema
            driver = webdriver.Chrome(options=opts)
    except Exception as e:
        print(f"  tt-selenium: driver init fail {type(e).__name__}: {e}")
        return None

    # Anti-detection: sobreescribe navigator.webdriver
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


def _load_cookies(driver, cookies_json: str) -> bool:
    """Carga cookies exportadas al driver. Formato: JSON array de dicts."""
    try:
        cookies = json.loads(cookies_json)
    except Exception as e:
        print(f"  tt-selenium: cookies JSON inválido: {e}")
        return False

    # Debe visitar el dominio antes de setear cookies
    driver.get("https://www.tiktok.com/")
    time.sleep(2)

    added = 0
    for c in cookies:
        # Sanitiza formato (algunas exports tienen campos extras)
        cookie = {k: v for k, v in c.items()
                  if k in ("name", "value", "domain", "path", "expires",
                            "secure", "httpOnly", "sameSite")}
        # Fix sameSite si viene como "unspecified"
        if cookie.get("sameSite", "").lower() in ("unspecified", "no_restriction"):
            cookie["sameSite"] = "None"
        elif cookie.get("sameSite", "").lower() == "lax":
            cookie["sameSite"] = "Lax"
        elif cookie.get("sameSite", "").lower() == "strict":
            cookie["sameSite"] = "Strict"
        # Domain debe empezar por . o coincidir exacto
        if "domain" in cookie and not cookie["domain"].startswith("."):
            if "tiktok" not in cookie["domain"]:
                continue
        try:
            driver.add_cookie(cookie)
            added += 1
        except Exception as ce:
            print(f"  tt-selenium: skip cookie {cookie.get('name','?')}: {ce}")
    print(f"  tt-selenium: {added}/{len(cookies)} cookies cargadas")
    return added > 0


def upload_via_selenium(video_path: Path, caption: str,
                          dry_run: bool = False) -> dict[str, Any] | None:
    """Sube video a TikTok via browser automation. Requiere TIKTOK_COOKIES_JSON."""
    if dry_run:
        print(f"  tt-selenium DRY-RUN — {video_path.name} · caption {len(caption)}c")
        return {"dry_run": True}

    cookies_env = os.environ.get("TIKTOK_COOKIES_JSON", "").strip()
    if not cookies_env:
        print("  tt-selenium: falta TIKTOK_COOKIES_JSON secret")
        return None

    if not video_path.exists():
        print(f"  tt-selenium: video no existe {video_path}")
        return None

    driver = _prepare_driver()
    if not driver:
        return None

    try:
        if not _load_cookies(driver, cookies_env):
            return None

        # Delay humano
        time.sleep(random.uniform(2, 4))

        # Navega a upload page
        driver.get("https://www.tiktok.com/creator-center/upload?lang=es")
        time.sleep(random.uniform(4, 6))

        # Verifica que estamos logueados (no en login page)
        if "login" in driver.current_url.lower():
            print(f"  tt-selenium: cookies inválidas → redirect login")
            return None

        # Encuentra input file (invisible normalmente)
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        wait = WebDriverWait(driver, 30)
        file_input = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
        )
        file_input.send_keys(str(video_path.resolve()))
        print(f"  tt-selenium: archivo subido · esperando procesamiento…")

        # Espera hasta que aparezca el textarea de caption
        caption_input = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR,
                                          "[contenteditable='true']"))
        )
        # Delay humano antes de escribir
        time.sleep(random.uniform(3, 5))

        # Limpia y escribe caption
        caption_input.click()
        time.sleep(1)
        # Selenium send_keys puede ser lento pero natural
        for chunk in [caption[i:i+50] for i in range(0, len(caption), 50)]:
            caption_input.send_keys(chunk)
            time.sleep(random.uniform(0.1, 0.3))

        time.sleep(random.uniform(5, 10))

        # Click "Publicar" — texto puede variar por idioma
        publish_btn = None
        for text in ("Publicar", "Post", "Publish"):
            try:
                publish_btn = driver.find_element(
                    By.XPATH, f"//button[.//text()[contains(., '{text}')]]"
                )
                break
            except Exception:
                continue

        if not publish_btn:
            print(f"  tt-selenium: no encuentra botón publish")
            return None

        publish_btn.click()
        time.sleep(random.uniform(8, 12))

        # Verifica éxito (URL cambia, aparece confirm)
        success = "creator-center" in driver.current_url or "posts" in driver.current_url
        if success:
            print(f"  tt-selenium: ✅ upload OK")
            return {"posted": True, "url": driver.current_url}
        print(f"  tt-selenium: upload posiblemente OK · current_url={driver.current_url}")
        return {"posted": True, "url": driver.current_url, "unverified": True}

    except Exception as e:
        print(f"  tt-selenium: {type(e).__name__}: {str(e)[:200]}")
        return None
    finally:
        try:
            driver.quit()
        except Exception:
            pass
