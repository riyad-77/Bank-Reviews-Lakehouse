"""
Scraper Google Maps - Extraction de TOUS les avis bancaires
============================================================
Selecteurs CSS actuels de Google Maps (avril 2026):
- Conteneur d'avis: div.jftiEf
- Nom auteur: .d4r55 ou button.al6Kxe
- Etoiles: span.kvMY9c avec aria-label='X etoiles'
- Texte: span.wiI79c
- Date: span.rskqf
- Bouton Plus: button.w8Bnu
"""

import json
import os
import re
import time as time_module
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)

# --- Configuration ---
BRONZE_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_AGENCIES = 5
MAX_SCROLL_ATTEMPTS = 30
SCROLL_PAUSE = 1.5


def parse_relative_time_fr(text):
    """Convertit un temps relatif français en timestamp Unix approximatif."""
    now = int(time_module.time())
    if not text:
        return now
    text = text.lower().strip()

    match = re.search(r'il y a (\d+)\s*(jour|semaine|mois|an)', text)
    if match:
        n = int(match.group(1))
        unit = match.group(2)
        if 'jour' in unit:
            return now - n * 86400
        elif 'semaine' in unit:
            return now - n * 604800
        elif 'mois' in unit:
            return now - n * 2592000
        elif 'an' in unit:
            return now - n * 31536000

    if 'un an' in text:
        return now - 31536000
    elif 'un mois' in text:
        return now - 2592000
    elif 'une semaine' in text:
        return now - 604800
    elif 'un jour' in text or 'hier' in text:
        return now - 86400

    return now


def parse_star_rating(aria_label):
    """Extrait la note depuis l'aria-label: '1 étoiles' -> 1, '5 étoiles' -> 5."""
    if not aria_label:
        return 0
    match = re.search(r'(\d)', aria_label)
    return int(match.group(1)) if match else 0


def accept_cookies(driver):
    """Accepte la popup de consentement Google si elle apparaît."""
    try:
        cookie_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR,
                'button[aria-label*="Accepter"], button[aria-label*="Accept"], form:nth-child(2) button'))
        )
        cookie_btn.click()
        time_module.sleep(1)
        print("   ✅ Popup de cookies acceptée")
    except TimeoutException:
        pass


def scroll_reviews_panel(driver):
    """Scrolle le panneau pour charger TOUS les avis."""
    scrollable = None

    # Strategie 1: Chercher par role="feed" et remonter au parent scrollable
    try:
        feed = driver.find_element(By.CSS_SELECTOR, 'div[role="feed"]')
        if feed:
            scrollable = driver.execute_script("""
                var el = arguments[0];
                while (el && el.parentElement) {
                    el = el.parentElement;
                    if (el.scrollHeight > el.clientHeight && el.clientHeight > 100) {
                        return el;
                    }
                }
                return arguments[0];
            """, feed)
    except:
        pass

    # Strategie 2: Chercher div.m6QErb scrollable via JavaScript
    if not scrollable:
        try:
            scrollable = driver.execute_script("""
                var divs = document.querySelectorAll('div.m6QErb');
                for (var i = 0; i < divs.length; i++) {
                    if (divs[i].scrollHeight > divs[i].clientHeight && divs[i].clientHeight > 200) {
                        return divs[i];
                    }
                }
                return null;
            """)
        except:
            pass

    # Strategie 3: N'importe quel conteneur avec overflow scroll contenant des avis
    if not scrollable:
        try:
            scrollable = driver.execute_script("""
                var all = document.querySelectorAll('div');
                for (var i = 0; i < all.length; i++) {
                    var el = all[i];
                    var style = window.getComputedStyle(el);
                    if ((style.overflowY === 'auto' || style.overflowY === 'scroll') 
                        && el.scrollHeight > el.clientHeight 
                        && el.clientHeight > 200
                        && el.querySelector('.jftiEf')) {
                        return el;
                    }
                }
                return null;
            """)
        except:
            pass

    if not scrollable:
        print("   ⚠️ Conteneur scrollable non trouvé")
        try:
            scrollable = driver.find_element(By.CSS_SELECTOR, 'div.m6QErb')
        except:
            return

    last_height = 0
    no_change = 0
    for i in range(MAX_SCROLL_ATTEMPTS):
        driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable)
        time_module.sleep(SCROLL_PAUSE)
        new_height = driver.execute_script('return arguments[0].scrollHeight', scrollable)
        if new_height == last_height:
            no_change += 1
            if no_change >= 3:
                break
        else:
            no_change = 0
        last_height = new_height
    print(f"   📜 Scroll terminé ({i + 1} scrolls effectués)")


def expand_all_reviews(driver):
    """Clique sur 'Plus' pour voir les textes complets."""
    try:
        btns = driver.find_elements(By.CSS_SELECTOR, 'button.w8Bnu, button.w8nwRe, button.M77dve')
        for btn in btns:
            try:
                driver.execute_script("arguments[0].click();", btn)
                time_module.sleep(0.2)
            except:
                pass
        if btns:
            print(f"   📖 {len(btns)} avis dépliés")
    except:
        pass


def extract_reviews_from_page(driver):
    """Extrait TOUS les avis visibles sur la page."""
    reviews = []

    review_elements = driver.find_elements(By.CSS_SELECTOR, 'div.jftiEf')
    if not review_elements:
        review_elements = driver.find_elements(By.CSS_SELECTOR, 'div[data-review-id]')

    if not review_elements:
        print("   ⚠️ Aucun élément d'avis trouvé dans le DOM")
        return reviews

    print(f"   📋 {len(review_elements)} éléments d'avis trouvés dans le DOM")

    for elem in review_elements:
        try:
            # Auteur
            author = "Anonyme"
            for sel in ['.d4r55', 'button.al6Kxe', '.TSUbDb a']:
                try:
                    a = elem.find_element(By.CSS_SELECTOR, sel)
                    txt = a.text.strip() if a.text else a.get_attribute('aria-label')
                    if txt and txt.strip():
                        author = txt.strip()
                        break
                except NoSuchElementException:
                    continue

            # Note (étoiles) - span.kvMY9c avec aria-label="X étoiles"
            rating = 0
            for sel in ['span.kvMY9c', 'span.kvMYJc', '.DU9Pgb span[role="img"]', 'span[aria-label*="toile"]']:
                try:
                    r = elem.find_element(By.CSS_SELECTOR, sel)
                    aria = r.get_attribute('aria-label') or ''
                    rating = parse_star_rating(aria)
                    if rating > 0:
                        break
                except NoSuchElementException:
                    continue

            # Texte - span.wiI79c
            text = ""
            for sel in ['span.wiI79c', 'span.wiI7pd', '.MyEned span', '.review-full-text']:
                try:
                    t = elem.find_element(By.CSS_SELECTOR, sel)
                    text = t.text.strip()
                    if text:
                        break
                except NoSuchElementException:
                    continue

            # Date - span.rskqf
            time_text = ""
            for sel in ['span.rskqf', 'span.rsqaWe', 'span.xRkPPb']:
                try:
                    tt = elem.find_element(By.CSS_SELECTOR, sel)
                    time_text = tt.text.strip()
                    if time_text:
                        break
                except NoSuchElementException:
                    continue

            timestamp = parse_relative_time_fr(time_text)

            if rating > 0:
                reviews.append({
                    'author_name': author,
                    'rating': rating,
                    'text': text,
                    'time': timestamp,
                })

        except StaleElementReferenceException:
            continue
        except Exception:
            continue

    return reviews


def scrape_google_maps_reviews(query, max_agencies=MAX_AGENCIES):
    """Scrape les VRAIS avis Google Maps."""
    print(f"🚀 Lancement du navigateur pour chercher : '{query}'...")

    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--lang=fr')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])

    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(5)

    all_raw_data = []

    try:
        url_query = query.replace(' ', '+')
        url = f"https://www.google.com/maps/search/{url_query}"
        driver.get(url)

        accept_cookies(driver)

        print("⏳ Attente du chargement des résultats...")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'a.hfpxzc'))
        )
        time_module.sleep(3)

        agences = driver.find_elements(By.CSS_SELECTOR, 'a.hfpxzc')
        agency_info = []
        for a in agences[:max_agencies]:
            try:
                name = a.get_attribute('aria-label') or "Nom inconnu"
                href = a.get_attribute('href') or ""
                agency_info.append((name, href))
            except:
                pass

        print(f"✅ {len(agency_info)} agences trouvées. Extraction de TOUS les avis...\n")

        for idx, (nom, href) in enumerate(agency_info, 1):
            print(f"{'═' * 50}")
            print(f"📍 [{idx}/{len(agency_info)}] {nom}")

            try:
                driver.get(href)
                time_module.sleep(4)

                # Cliquer sur l'onglet Avis
                tab_clicked = False
                
                try:
                    tab = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, 'button[aria-label*="Avis"]')
                        )
                    )
                    tab.click()
                    time_module.sleep(3)
                    tab_clicked = True
                except:
                    pass

                if not tab_clicked:
                    try:
                        tab = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable(
                                (By.CSS_SELECTOR, 'button[data-tab-index="1"]')
                            )
                        )
                        tab.click()
                        time_module.sleep(3)
                        tab_clicked = True
                    except:
                        pass

                if not tab_clicked:
                    try:
                        tabs = driver.find_elements(By.CSS_SELECTOR, 'button[role="tab"]')
                        for t in tabs:
                            label = (t.text + ' ' + (t.get_attribute('aria-label') or '')).lower()
                            if 'avis' in label or 'review' in label:
                                t.click()
                                time_module.sleep(3)
                                tab_clicked = True
                                break
                    except:
                        pass

                scroll_reviews_panel(driver)
                expand_all_reviews(driver)
                time_module.sleep(1)

                reviews = extract_reviews_from_page(driver)

                print(f"   ✅ {len(reviews)} avis extraits")

                all_raw_data.append({
                    "result": {
                        "name": nom,
                        "url": href,
                        "reviews": reviews,
                    }
                })

            except Exception as e:
                print(f"   ❌ Erreur : {e}")
                all_raw_data.append({
                    "result": {"name": nom, "url": href, "reviews": []}
                })

    except Exception as e:
        print(f"❌ Erreur générale : {e}")
    finally:
        driver.quit()
        total = sum(len(d['result']['reviews']) for d in all_raw_data)
        print(f"\n{'═' * 50}")
        print(f"🏁 Scraping terminé ! {len(all_raw_data)} agences, {total} avis au total.")

    return all_raw_data


def save_to_bronze(data):
    """Sauvegarde les données au format JSON brut dans la couche Bronze."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scraped_reviews_raw_{timestamp}.json"
    filepath = os.path.join(BRONZE_DIR, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    total = sum(len(d['result']['reviews']) for d in data)
    print(f"\n📁 Fichier JSON sauvegardé : {filename}")
    print(f"   → {len(data)} agences, {total} avis au total")

    return filepath


if __name__ == "__main__":
    query = "Agences bancaires Rabat"
    raw_data = scrape_google_maps_reviews(query)

    if raw_data:
        save_to_bronze(raw_data)
    else:
        print("❌ Aucune donnée récupérée.")
