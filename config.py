"""
Simple Configuration for LinkedIn Profile Extractor
"""

# Extraction Settings
import os

MAX_PROFILES = 5
OUTPUT_FILE = "linkedin_profiles.json"

HEADLESS_MODE = False

PROJECT_DESCRIPTION = "Full stack developer with experience in React, Node.js, Python, and database management for e-commerce platform development"

TARGET_LOCATIONS = [
    "Morocco",
    "Maroc"
]

SEARCH_LOCATION_FILTER = "Morocco"
REQUIRE_MOROCCO_LOCATION = True
INPUT_JSON_FILE = "profiles.json"
OUTPUT_DIR = os.path.join(os.getcwd(), "linkedin_pages")
HEADLESS = False
DELAY_BETWEEN_PROFILES = 3  # seconds
