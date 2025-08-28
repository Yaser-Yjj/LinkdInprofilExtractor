import json
import random

from flask import Flask, jsonify, send_file
import os
import sys
import logging
from dotenv import load_dotenv
import threading
import time

from linkedin_scraper import Person

from MoroccoLinkedInProfileExtractor import MoroccoLinkedInProfileExtractor
from MoroccoLinkedInProfileExtractor import driver

# Add the 'scripts' directory to Python path
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), 'scripts')
sys.path.append(SCRIPTS_DIR)

import config

app = Flask(__name__)
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

# Global variables for tracking extraction status
extraction_status = {
    'running': False,
    'progress': 0,
    'total': 0,
    'current_phase': 'idle',
    'message': 'Ready to start',
    'profiles_found': 0,
    'latest_file': None,
    'error': None
}

HTML_DIR = "linkedin_pages"
OUTPUT_DIR = "parsed_profiles"
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.route('/')
def home():
    """Home endpoint with API documentation"""
    return jsonify({
        'message': 'Morocco LinkedIn Profile Extractor API',
        'endpoints': {
            '/': 'This documentation',
            '/extract': 'Start profile extraction (GET)',
            '/status': 'Check extraction status',
            '/profiles': 'Get extracted profiles',
            '/config': 'Get current configuration',
            '/health': 'Health check'
        },
        'version': '1.0.0'
    })


@app.route('/status')
def get_status():
    """Get current extraction status"""
    return jsonify(extraction_status)


@app.route('/extract')
def start_extraction():
    """Start the LinkedIn profile extraction process"""
    global extraction_status
    
    # Check if extraction is already running
    if extraction_status['running']:
        return jsonify({
            'error': 'Extraction already in progress',
            'status': extraction_status
        }), 400
    
    # Check LinkedIn credentials
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")
    
    if not email or not password:
        return jsonify({
            'error': 'LinkedIn credentials not found in .env file',
            'message': 'Please set LINKEDIN_EMAIL and LINKEDIN_PASSWORD'
        }), 400
    
    # Reset status
    extraction_status.update({
        'running': True,
        'progress': 0,
        'total': config.MAX_PROFILES,
        'current_phase': 'starting',
        'message': 'Initializing extraction...',
        'profiles_found': 0,
        'latest_file': None,
        'error': None
    })
    
    # Start extraction in a separate thread
    thread = threading.Thread(target=run_extraction_process)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'message': 'Extraction started successfully',
        'status': extraction_status,
        'check_status_url': '/status'
    })


def run_extraction_process():
    """Run the full extraction process in background"""
    global extraction_status
    
    try:
        # Phase 1: Extract Profiles
        extraction_status.update({
            'current_phase': 'extraction',
            'message': 'Extracting LinkedIn profiles...'
        })
        
        extractor = MoroccoLinkedInProfileExtractor()
        success = extractor.run()
        
        if not success:
            extraction_status.update({
                'running': False,
                'error': 'Profile extraction failed',
                'current_phase': 'error'
            })
            return
        
        json_file = extractor.save_to_json()
        if not json_file:
            extraction_status.update({
                'running': False,
                'error': 'Failed to save extracted profiles',
                'current_phase': 'error'
            })
            return

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


        extraction_status.update({
            'profiles_found': len(extractor.profiles),
            'latest_file': json_file,
            'progress': 33
        })
            
    except Exception as e:
        logging.error(f"Extraction process error: {e}")
        extraction_status.update({
            'running': False,
            'error': str(e),
            'current_phase': 'error'
        })


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Endpoint not found',
        'message': 'Please check the URL and try again',
        'available_endpoints': [
            '/', '/extract', '/status', '/profiles', '/config', '/health'
        ]
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal server error',
        'message': 'Something went wrong on the server'
    }), 500


if __name__ == '__main__':
    print("🇲🇦" + "=" * 60)
    print("   MOROCCO LINKEDIN PROFILE EXTRACTOR - FLASK API")
    print("=" * 63)
    print(f"📋 Project: {config.PROJECT_DESCRIPTION}")
    print(f"🎯 Target: {config.MAX_PROFILES} profiles from Morocco")
    print(f"🌍 Geographic Focus: {', '.join(config.TARGET_LOCATIONS)}")
    print("=" * 63)
    print("🚀 Starting Flask server...")
    print("📡 API Endpoints:")
    print("   GET  /           - API documentation")
    print("   GET  /extract    - Start extraction process")
    print("   GET  /status     - Check extraction status")
    print("   GET  /profiles   - Get extracted profiles")
    print("   GET  /config     - Get configuration")
    print("   GET  /health     - Health check")
    print("=" * 63)
    
    # Run the Flask app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )