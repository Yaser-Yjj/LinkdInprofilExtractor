#!/usr/bin/env bash
export FLASK_APP=flask_linkedin_extractor.py
export FLASK_ENV=production
flask run --host=0.0.0.0 --port=$PORT
