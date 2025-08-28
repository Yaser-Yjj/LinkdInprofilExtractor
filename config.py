"""
Simple Configuration for LinkedIn Profile Extractor
"""

# Extraction Settings
import os

MAX_PROFILES = 4
OUTPUT_FILE = "linkedin_profiles.json"

# Browser Settings
HEADLESS_MODE = False  # Set to True to hide browser window

"""
Simple Configuration for LinkedIn Profile Extractor
"""

# Project Configuration
PROJECT_DESCRIPTION = "Full stack developer with experience in React, Node.js, Python, and database management for e-commerce platform development"

# Location Filtering - Morocco only
TARGET_LOCATIONS = [
    "Morocco",
    "Maroc"
]

# Search Configuration
SEARCH_LOCATION_FILTER = "Morocco"  # Add location filter to LinkedIn search
REQUIRE_MOROCCO_LOCATION = True     # Only keep profiles with Morocco locations

# Input JSON file path
INPUT_JSON_FILE = "profiles.json"

# Output directory for saving HTML files
OUTPUT_DIR = os.path.join(os.getcwd(), "linkedin_pages")

# Chrome options (set to True for stealth, False for debugging)
HEADLESS = False

# Delay between profile downloads (to be respectful)
DELAY_BETWEEN_PROFILES = 3  # seconds
