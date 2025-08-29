from concurrent.futures import thread
from linkedin_scraper import Person
from MoroccoLinkedInProfileExtractor import MoroccoLinkedInProfileExtractor
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
import os
import sys
import logging
import threading
import time
import json
import random

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), 'scripts')
sys.path.append(SCRIPTS_DIR)

import config

app = Flask(__name__)
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

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


@app.route('/')
def home():
    """Home endpoint with API documentation"""
    return jsonify({
        'message': 'Morocco LinkedIn Profile Extractor API',
        'endpoints': {
            '/': 'This documentation',
            '/extract': 'Start profile extraction (POST)',
            '/status': 'Check extraction status'
        },
        'version': '1.0.0'
    })

@app.route('/status')
def get_status():
    """Get current extraction status"""
    return jsonify(extraction_status)


@app.route('/extract', methods=['POST'])
def start_extraction():
    global extraction_status

    if extraction_status['running']:
        return jsonify({
            'error': 'Extraction already in progress',
            'status': extraction_status
        }), 400

    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")

    if not email or not password:
        return jsonify({
            'error': 'LinkedIn credentials not found in .env file',
            'message': 'Please set LINKEDIN_EMAIL and LINKEDIN_PASSWORD'
        }), 400

    data = request.get_json()
    if not data or "description_project" not in data:
        return jsonify({
            "error": "Missing description_project in request body"
        }), 400

    description_project = data["description_project"]

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
    
    thread = threading.Thread(
        target=run_extraction_process,
        args=(description_project,)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        'message': 'Extraction started successfully',
        'status': extraction_status,
        'check_status_url': '/status'
    })

@app.route('/profil', methods=['GET'])
def last_json():
    folder = "profilsExtractor"
    files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".json")]
    
    if not files:
        return Response(json.dumps({"error": "No JSON files found"}), status=404, mimetype='application/json')

    latest_file = max(files, key=os.path.getmtime)
    
    with open(latest_file, "r") as f:
        raw_json = f.read()
    
    return Response(raw_json, mimetype='application/json')

def run_extraction_process(description_project):
    """Run the full extraction process in background"""
    global extraction_status
    
    try:
        extraction_status.update({
            'current_phase': 'extraction',
            'message': 'Extracting LinkedIn profiles...'
        })
        
        extractor = MoroccoLinkedInProfileExtractor()
        success = extractor.run(description_project)
        
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
                person = Person(url, driver=extractor.driver, scrape=True, close_on_complete=False)
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

        base_name = "linkedin_profiles_"
        output_dir = "profilsExtractor"

        os.makedirs(output_dir, exist_ok=True)

        i = 1
        while True:
            filename = os.path.join(output_dir, f"{base_name}{i}.json")
            if not os.path.exists(filename):
                break
            i += 1

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(profiles_data, f, ensure_ascii=False, indent=4)

        print(f"✅ {len(profiles_data)} profiles saved to linkedin_profiles.json")

        extractor.driver.quit()
        
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
def not_found():
    return jsonify({
        'error': 'Endpoint not found',
        'message': 'Please check the URL and try again',
        'available_endpoints': [
            '/', '/extract', '/status', '/profiles', '/config', '/health'
        ]
    }), 404


@app.errorhandler(500)
def internal_error():
    return jsonify({
        'error': 'Internal server error',
        'message': 'Something went wrong on the server'
    }), 500

if __name__ == '__main__':
    print("🇲🇦" + "=" * 60)
    print("   MOROCCO LINKEDIN PROFILE EXTRACTOR - FLASK API")
    print("=" * 63)
    print(f"🎯 Target: {config.MAX_PROFILES} profiles from Morocco")
    print(f"🌍 Geographic Focus: {', '.join(config.TARGET_LOCATIONS)}")
    print("=" * 63)
    print("🚀 Starting Flask server...")
    print("📡 API Endpoints:")
    print("   GET  /           - API documentation")
    print("   POST /extract    - Start extraction process")
    print("   GET  /status     - Check extraction status")
    print("=" * 63)
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )