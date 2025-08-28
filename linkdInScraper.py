from linkedin_scraper import Person, actions
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import json
import time
import random
from MoroccoLinkedInProfileExtractor import MoroccoLinkedInProfileExtractor

chrome_options = Options()
# chrome_options.add_argument("--headless")  # uncomment = run without UI
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

email = "benbaringenierieetconseil@gmail.com"
password = "zEwja6-xebhav-jyxfef"

try:
    actions.login(driver, email, password)
except Exception as e:
    print(f"[Login] Failed: {e}")
    driver.quit()
    exit()

extractor = MoroccoLinkedInProfileExtractor()
extractor.run()
json_file = extractor.save_to_json()

with open(json_file, 'r', encoding='utf-8') as f:
    linkedin_urls = json.load(f)

def safe_get(obj, attr, default="N/A"):
    try:
        return getattr(obj, attr) if getattr(obj, attr, None) else default
    except Exception:
        return default

profiles_data = []

for url in linkedin_urls:
    print(f"[Scraping] {url}")
    try:
        person = Person(url, driver=driver, scrape=True, close_on_complete=False)
    except Exception as e:
        print(f"[Scrape] Failed for {url}: {e}")
        continue

    data = {
        "url": url,
        "profile": {
            "name": safe_get(person, "name"),
            "location": safe_get(person, "location"),
            "about": safe_get(person, "about"),
            "open_to_work": safe_get(person, "open_to_work")
        },
        "experiences": [],
        "educations": [],
        "interests": [],
        "accomplishments": [],
        "contacts": []
    }

    for exp in person.experiences:
        data["experiences"].append({
            "title": safe_get(exp, "position_title"),
            "company": safe_get(exp, "institution_name"),
            "from": safe_get(exp, "from_date"),
            "to": safe_get(exp, "to_date"),
            "description": safe_get(exp, "description")
        })

    for edu in person.educations:
        data["educations"].append({
            "institution": safe_get(edu, "institution_name"),
            "degree": safe_get(edu, "degree"),
            "from": safe_get(edu, "from_date"),
            "to": safe_get(edu, "to_date"),
            "description": safe_get(edu, "description")
        })

    for interest in person.interests:
        data["interests"].append(safe_get(interest, "name"))

    for acc in person.accomplishments:
        data["accomplishments"].append({
            "category": safe_get(acc, "category"),
            "title": safe_get(acc, "title")
        })

    for contact in person.contacts:
        data["contacts"].append({
            "name": safe_get(contact, "name"),
            "occupation": safe_get(contact, "occupation"),
            "url": safe_get(contact, "url")
        })

    profiles_data.append(data)
    time.sleep(random.randint(5, 10))

with open("linkedin_profiles.json", "w", encoding="utf-8") as f:
    json.dump(profiles_data, f, ensure_ascii=False, indent=4)

print(f"✅ {len(profiles_data)} profiles saved to linkedin_profiles.json")

driver.quit()
