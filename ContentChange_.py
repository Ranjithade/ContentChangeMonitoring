import requests
import hashlib
import logging
from bs4 import BeautifulSoup
import os
import csv
from datetime import datetime
import sys
import re
from dateutil import parser
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep

# ------------------ Configuration ------------------ #
SLACK_WEBHOOK_URL = "https://Yourwebhock.cat.com/services/xxx/yyy/zzz"  # Replace with your actual Slack webhook URL
URLS = [
    'https://www.canada.ca/en/immigration-refugees-citizenship/corporate/mandate/policies-operational-instructions-agreements/ministerial-instructions/express-entry-rounds.html',
    'https://www.ontario.ca/page/oinp-express-entry-notifications-interest',
    'https://www.ontario.ca/page/ontario-immigrant-nominee-program-oinp-invitations-apply',
    'https://www.welcomebc.ca/immigrate-to-b-c/invitations-to-apply',
    'https://www.quebec.ca/en/immigration/permanent/skilled-workers/regular-skilled-worker-program/invitation',
    'https://www.alberta.ca/aaip-processing-times-and-inventory',
    'https://www.princeedwardisland.ca/en/information/office-of-immigration/expression-of-interest-draws',
    'https://www.saskatchewan.ca/residents/moving-to-saskatchewan/live-in-saskatchewan/by-immigrating/saskatchewan-immigrant-nominee-program/browse-sinp-programs/applicants-international-skilled-workers/international-skilled-worker-eoi-system',
    'https://immigratemanitoba.com/news/',
    'https://publications.saskatchewan.ca/api/v1/products/102708/formats/113850/download'
]
URLS_FILE = 'urls_tracked.txt'

# ------------------ Logging ------------------ #
sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("content_change.log", encoding='utf-8'), logging.StreamHandler(sys.stdout)]
)

# ------------------ Utilities ------------------ #
def load_previous_urls():
    if not os.path.exists(URLS_FILE):
        return set()
    with open(URLS_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def save_current_urls(urls):
    with open(URLS_FILE, 'w', encoding='utf-8') as f:
        for url in urls:
            f.write(url + '\n')

def send_slack_notification(message: str):
    payload = {"text": message}
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        logging.info(f"Slack webhook HTTP {response.status_code}")
        logging.debug(f"Slack response: {response.text}")
        response.raise_for_status()
        logging.info("Slack notification sent successfully.")
        return True
    except Exception as e:
        logging.error(f"Failed to send Slack notification: {e}")
        # fallback: save message so you can retry manually
        try:
            with open("pending_slack_message.txt", "w", encoding="utf-8") as f:
                f.write(message)
            logging.info("Saved pending_slack_message.txt for manual retry.")
        except Exception as e2:
            logging.error(f"Failed to save fallback message: {e2}")
        return False

def check_url_list_changes(current_urls):
    previous_urls = load_previous_urls()
    current_urls_set = set(current_urls)
    added_urls = current_urls_set - previous_urls
    removed_urls = previous_urls - current_urls_set
    if added_urls or removed_urls:
        message = "URL list changed:\n"
        if added_urls:
            message += f"Added URLs:\n" + "\n".join(added_urls) + "\n"
        if removed_urls:
            message += f"Removed URLs:\n" + "\n".join(removed_urls) + "\n"
        #send_slack_notification(message)
        #save_current_urls(current_urls)

def get_content_hash(content):
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def get_previous_content_hash(url):
    file_name = f"hash_{url.split('//')[1].replace('/', '_')}.txt"
    if os.path.exists(file_name):
        with open(file_name, 'r', encoding='utf-8') as file:
            return file.read().strip()
    return None

def save_content_hash(url, content):
    file_name = f"hash_{url.split('//')[1].replace('/', '_')}.txt"
    with open(file_name, 'w', encoding='utf-8') as file:
        file.write(get_content_hash(content))

def compare_content(url, content):
    return get_content_hash(content) != get_previous_content_hash(url)

# ------------------ Fetch Page ------------------ #
def fetch_page_content(url, use_selenium=False):
    if url.endswith("/download"):
        # Just return raw bytes for download links
        response = requests.get(url)
        return response.text
    if use_selenium:
        return fetch_with_undetected_chrome(url)
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.text

def fetch_with_undetected_chrome(url, retries=2):
    for attempt in range(1, retries + 1):
        driver = None
        try:
            logging.info(f"Selenium fetching {url}, attempt {attempt}")
            options = uc.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            driver = uc.Chrome(options=options, enable_cdp_events=False)
            driver.get(url)
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
            sleep(2)
            page_source = driver.page_source
            driver.quit()  # Explicitly quit here
            driver = None  # Prevent __del__ from trying again
            return page_source
        except Exception as e:
            logging.warning(f"Selenium attempt {attempt} failed for {url}: {e}")
            sleep(3)
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
                driver = None
    raise RuntimeError(f"All Selenium attempts failed for {url}")

# ------------------ Draw Extraction ------------------ #
def extract_recent_draws_canada_express_entry(content):
    """Return last 3 draws as list of dicts with 2026 filter"""
    soup = BeautifulSoup(content, 'html.parser')
    table = soup.find("table")
    if not table:
        return []
    rows = table.find_all("tr")
    draws = []
    for row in rows:
        if row.find_all("th"):
            continue
        cells = row.find_all("td")
        if len(cells) >= 3:
            try:
                draw_date = parser.parse(cells[1].get_text(strip=True))
                if draw_date.year < 2024:
                    continue
                draws.append({
                    "Program": cells[0].get_text(strip=True),
                    "Draw Date": draw_date.strftime("%B %d, %Y"),
                    "Invitations": cells[2].get_text(strip=True),
                    "CRS Cutoff": cells[3].get_text(strip=True) if len(cells) > 3 else "N/A"
                })
            except:
                continue
    return draws[:3]

def extract_draw_date_bc(content):
    soup = BeautifulSoup(content, 'html.parser')
    dates = soup.find_all(string=re.compile(r"\b\w+ \d{1,2}, \d{4}\b"))
    for date_str in dates:
        try:
            parsed = parser.parse(date_str, fuzzy=True)
            return parsed.strftime('%B %d, %Y')
        except:
            continue
    return "No draw date found"

#def extract_draw_date_manitoba(content):
#    soup = BeautifulSoup(content, 'html.parser')
#    articles = soup.find_all('article')
#    for article in articles:
#        match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}', article.text)
#       if match:
#            try:
#                parsed = parser.parse(match.group(0), fuzzy=True)
#                return parsed.strftime('%B %d, %Y')
#            except:
#                continue
#    return "No draw date found"

def extract_draws_ontario(content):
    soup = BeautifulSoup(content, 'html.parser')
    draws = []
    for heading in soup.find_all(['h2', 'h3']):
        stream_name = heading.get_text(strip=True)
        for sibling in heading.find_next_siblings():
            if sibling.name and sibling.name.startswith('h'):
                break
            text = sibling.get_text(separator=' ', strip=True)
            date_match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+(202[4-9]|203\d)", text)
            if date_match:
                draws.append({
                    "Stream": stream_name,
                    "Draw Date": date_match.group(0),
                    "Details": text[:300]
                })
                break
    return draws

def extract_draw_date_pei(content):
    text = BeautifulSoup(content, 'html.parser').get_text()
    match = re.search(r"Last updated:.*?(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+(202[4-9]|203\d)", text)
    return match.group(1) + " 2026" if match else "No draw date found"

def extract_draw_date_manitoba(content):
    soup = BeautifulSoup(content, 'html.parser')
    articles = soup.find_all('article')
    for article in articles:
        match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+2026", article.text)
        if match:
            return match.group(0)
    return "No draw date found"

def extract_page_title(content):
    soup = BeautifulSoup(content, 'html.parser')
    return soup.title.get_text(strip=True) if soup.title else "No title found"

def extract_content_summary(content):
    soup = BeautifulSoup(content, 'html.parser')
    first_p = soup.find('p')
    return first_p.get_text(strip=True) if first_p else "Content changed, no details found."

# ------------------ Main Processing ------------------ #
def process_url(url):
    logging.info(f"Processing: {url}")
    try:
        use_selenium = any(k in url for k in ["canada.ca/en/immigration-refugees-citizenship", "princeedwardisland.ca", "immigratemanitoba.com"])
        content = fetch_page_content(url, use_selenium=use_selenium)
        content_changed = compare_content(url, content)

        messages = []

        if "canada.ca/en/immigration-refugees-citizenship" in url:
            draws = extract_recent_draws_canada_express_entry(content)
            for draw in draws:
                messages.append(f"{draw['Program']}\n{url}\nDraw Date: {draw['Draw Date']}\nInvitations: {draw['Invitations']}\nInvitations Issued: {draw['CRS Cutoff']}")

        elif "ontario.ca/page/ontario-immigrant-nominee-program-oinp-invitations-apply" in url:
            draws = extract_draws_ontario(content)
            for draw in draws:
                messages.append(f"{draw['Stream']}\n{url}\nDraw Date: {draw['Draw Date']}\nDetails: {draw['Details']}")

        elif "princeedwardisland.ca" in url:
            draw_date = extract_draw_date_pei(content)
            messages.append(f"PEI EOI Draw\n{url}\nDraw Date: {draw_date}")

        elif "immigratemanitoba.com" in url:
            draw_date = extract_draw_date_manitoba(content)
            messages.append(f"Manitoba EOI Draw\n{url}\nDraw Date: {draw_date}")
        
        elif "welcomebc.ca" in url:
            draw_date = extract_draw_date_bc(content)
            messages.append(f"BC PNP Draw\n{url}\nUpdated Date: {draw_date}")

        else:
            if content_changed:
                messages.append(f"Change detected at {url}\nSummary: {extract_content_summary(content)}")

        # Send alerts if there is any message
        if messages:
            save_content_hash(url, content)

        return messages


    except Exception as e:
        logging.error(f"Error processing {url}: {e}")
        return[]

# ------------------ Run All URLs ------------------ #
if __name__ == "__main__":
    check_url_list_changes(URLS)
    all_messages = []
    for url in URLS:
        msgs = process_url(url)
        if msgs:
            all_messages.extend(msgs)

    logging.info(f"Total update messages collected: {len(all_messages)}")
    if all_messages:
        combined_message = "*Updates detected during run:*\n\n• " + "\n\n• ".join(all_messages)
        logging.info("Prepared Slack message:")
        logging.info(combined_message)
        sent = send_slack_notification(combined_message)
        if not sent:
            logging.error("Slack notification failed; see pending_slack_message.txt")
    else:
        logging.info("No updates detected during run.")