from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from linkedin_scraper import actions
from dotenv import load_dotenv
import nltk
import time
import json
import os
import re
import config

load_dotenv()

class MoroccoLinkedInProfileExtractor:
    def __init__(self):
        self.driver = None
        self.profiles = []
        self.target_locations = [loc.lower().strip() for loc in config.TARGET_LOCATIONS]
        self.email = os.getenv('LINKEDIN_EMAIL')
        self.password = os.getenv('LINKEDIN_PASSWORD')
        if not self.email or not self.password:
            raise ValueError("Please set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env file")
        self.setup_nltk()

    def setup_nltk(self):
        required_packages = ['punkt', 'stopwords', 'wordnet']
        for package in required_packages:
            try:
                nltk.data.find(f'tokenizers/{package}')
            except LookupError:
                nltk.download(package, quiet=True)

    def setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless=new") # run on background
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    def login_to_linkedin(self):
        try:
            actions.login(self.driver, self.email, self.password)
            return True
        except Exception as e:
            print("⚠️ Captcha or login issue detected:", e)
            print("👉 Please solve the captcha manually in the opened browser...")
            input("Press ENTER after solving the captcha...")
            return True

    def extract_keywords(self, description):
        stop_words = set(stopwords.words('english'))
        lemmatizer = WordNetLemmatizer()
        text = re.sub(r'[^a-zA-Z\s]', '', description.lower())
        tokens = word_tokenize(text)
        keywords = [lemmatizer.lemmatize(t) for t in tokens if t not in stop_words and len(t) > 2]
        return list(set(keywords))[:10]

    def search_morocco_profiles(self, keywords):
        search_query = " ".join(keywords)
        search_strategies = [
            f"https://www.linkedin.com/search/results/people/?keywords={search_query}&geoUrn=%5B%22102787409%22%5D",
            f"https://www.linkedin.com/search/results/people/?keywords={search_query}%20Morocco&geoUrn=%5B%22102787409%22%5D",
            f"https://www.linkedin.com/search/results/people/?keywords={search_query}%20Maroc&geoUrn=%5B%22102787409%22%5D",
            f"https://www.linkedin.com/search/results/people/?keywords={search_query}%20Casablanca&geoUrn=%5B%22102787409%22%5D",
            f"https://www.linkedin.com/search/results/people/?keywords={search_query}%20Rabat&geoUrn=%5B%22102787409%22%5D",
            f"https://www.linkedin.com/search/results/people/?keywords={search_query}%20Marrakech&geoUrn=%5B%22102787409%22%5D",
        ]
        profiles_found = 0
        for search_url in search_strategies:
            if profiles_found >= config.MAX_PROFILES:
                break
            profiles_found += self._search_with_url(search_url, profiles_found)

    def _search_with_url(self, search_url, current_count):
        self.driver.get(search_url)
        time.sleep(3)
        profiles_found = 0
        page = 1
        max_pages = 5
        while profiles_found + current_count < config.MAX_PROFILES and page <= max_pages:
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".search-results-container, .search-results__list"))
                )
                profile_cards = self.driver.find_elements(By.CSS_SELECTOR,
                                                          ".reusable-search__result-container, .entity-result__item, [data-chameleon-result-urn]")
                for card in profile_cards:
                    if profiles_found + current_count >= config.MAX_PROFILES:
                        break
                    profile_data = self.extract_profile_data(card)
                    if profile_data:
                        if not self._is_duplicate_profile(profile_data):
                            self.profiles.append(profile_data)
                            profiles_found += 1
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label='Next']")
                    if next_button.is_enabled():
                        next_button.click()
                        time.sleep(3)
                        page += 1
                    else:
                        break
                except NoSuchElementException:
                    break
            except TimeoutException:
                break
        return profiles_found

    def extract_profile_data(self, card):
        try:
            profile_links = card.find_elements(By.XPATH, ".//a[contains(@href, '/in/')]")
            profile_url = ""
            for link in profile_links:
                href = link.get_attribute('href')
                if href and '/in/' in href:
                    profile_url = href.split('?')[0]
                    break
            if not profile_url:
                return None
            return {"profile_url": profile_url}
        except:
            return None

    def _is_duplicate_profile(self, new_profile):
        new_url = new_profile.get('profile_url', '').strip().lower()
        for existing_profile in self.profiles:
            existing_url = existing_profile.get('profile_url', '').strip().lower()
            if new_url and existing_url and new_url == existing_url:
                return True
        return False

    def save_to_json(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        folder_name = "urlsExtractor"
        folder_path = os.path.join(script_dir, folder_name)

        os.makedirs(folder_path, exist_ok=True)

        base_name = "linkedin_urls_"
        i = 1
        while True:
            filename = f"{base_name}{i}.json"
            filepath = os.path.join(folder_path, filename)
            if not os.path.exists(filepath):
                break
            i += 1

        urls = [p['profile_url'] for p in self.profiles]
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(urls, f, ensure_ascii=False, indent=4)
            return filepath
        except:
            return None

    def run(self, project_description):
        keywords = self.extract_keywords(project_description)
        self.setup_driver()
        if not self.login_to_linkedin():
            return False
        self.search_morocco_profiles(keywords)
        return True
