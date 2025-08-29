from flask_cors import CORS
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
import config

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), 'scripts')
sys.path.append(SCRIPTS_DIR)

app = Flask(__name__)
CORS(app)
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

def run_extraction_process(description_project):
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

        url_file = extractor.save_to_json()
        if not url_file:
            extraction_status.update({
                'running': False,
                'error': 'Failed to save extracted URLs',
                'current_phase': 'error'
            })
            return

        with open(url_file, 'r', encoding='utf-8') as f:
            linkedin_urls = json.load(f)

        profiles_data = []

        def safe_get(obj, attr, default="N/A"):
            try:
                return getattr(obj, attr) if getattr(obj, attr, None) else default
            except Exception:
                return default

        for url in linkedin_urls:
            try:
                person = Person(url, driver=extractor.driver, scrape=True, close_on_complete=False)
            except Exception:
                continue

            unique_educations = []
            seen_edu = set()
            for edu in person.educations:
                edu_tuple = (
                    safe_get(edu, "institution_name"),
                    safe_get(edu, "degree"),
                    safe_get(edu, "from_date"),
                    safe_get(edu, "to_date"),
                    safe_get(edu, "description")
                )
                if edu_tuple not in seen_edu:
                    seen_edu.add(edu_tuple)
                    unique_educations.append({
                        "institution": edu_tuple[0],
                        "degree": edu_tuple[1],
                        "from": edu_tuple[2],
                        "to": edu_tuple[3],
                        "description": edu_tuple[4]
                    })

            data = {
                "url": url,
                "profile": {
                    "name": safe_get(person, "name"),
                    "location": safe_get(person, "location"),
                    "about": safe_get(person, "about"),
                    "open_to_work": safe_get(person, "open_to_work")
                },
                "experiences": [{
                    "title": safe_get(exp, "position_title"),
                    "company": safe_get(exp, "institution_name"),
                    "from": safe_get(exp, "from_date"),
                    "to": safe_get(exp, "to_date"),
                    "description": safe_get(exp, "description")
                } for exp in person.experiences],
                "educations": unique_educations,
                "interests": [safe_get(interest, "name") for interest in person.interests],
                "accomplishments": [{
                    "category": safe_get(acc, "category"),
                    "title": safe_get(acc, "title")
                } for acc in person.accomplishments],
                "contacts": [{
                    "name": safe_get(contact, "name"),
                    "occupation": safe_get(contact, "occupation"),
                    "url": safe_get(contact, "url")
                } for contact in person.contacts]
            }

            profiles_data.append(data)
            time.sleep(random.randint(5, 10))

        # Save full profiles JSON
        output_dir = "profilsExtractor"
        os.makedirs(output_dir, exist_ok=True)
        i = 1
        while True:
            filename = os.path.join(output_dir, f"linkedin_profiles_{i}.json")
            if not os.path.exists(filename):
                break
            i += 1

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(profiles_data, f, ensure_ascii=False, indent=4)

        extractor.driver.quit()

        extraction_status.update({
            'running': False,
            'profiles_found': len(profiles_data),
            'latest_file': filename,
            'progress': 100
        })

    except Exception as e:
        extraction_status.update({
            'running': False,
            'error': str(e),
            'current_phase': 'error'
        })


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
        return jsonify({"error": "Missing description_project in request body"}), 400

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

    thread = threading.Thread(target=run_extraction_process, args=(description_project,))
    thread.start()
    thread.join()

    latest_file = extraction_status.get('latest_file')
    if latest_file and os.path.exists(latest_file):
        with open(latest_file, "r", encoding="utf-8") as f:
            raw_json = f.read()
        return Response(raw_json, mimetype='application/json')
    else:
        return jsonify({
            'error': 'Scraping finished but no JSON file was created',
            'status': extraction_status
        })

@app.route('/profiles', methods=['GET'])
def get_last_profiles():
    """Return the last saved profiles JSON file"""
    latest_file = extraction_status.get('latest_file')

    if not latest_file or not os.path.exists(latest_file):
        folder = "profilsExtractor"
        if not os.path.exists(folder):
            return jsonify({"error": "No profiles folder found"}), 404

        files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".json")]
        if not files:
            return jsonify({"error": "No profiles JSON file found"}), 404

        latest_file = max(files, key=os.path.getmtime)

    with open(latest_file, "r", encoding="utf-8") as f:
        raw_json = f.read()

    return Response(raw_json, mimetype="application/json")

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
    print("   GET  /profiles   - display last extracted profiles")
    print("=" * 63)
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )