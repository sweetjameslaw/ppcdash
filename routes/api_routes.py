from datetime import datetime, timedelta, date
from flask import Flask, render_template, jsonify, request, send_from_directory, Blueprint
import logging
import calendar
import random 

import demo_data
from performance_boost import time_it

logger = logging.getLogger(__name__)

# Create a blueprint for API routes 
api_bp = Blueprint('api', __name__)

@api_bp.route('/api/status')
def api_status():
    """Check API connection status"""
    # TODO: Import these from services layer
    from app import ads_manager, litify_manager, GOOGLE_ADS_AVAILABLE, SALESFORCE_AVAILABLE
    
    if not ads_manager.client:
        ads_manager.initialize()
    if not litify_manager.client:
        litify_manager.initialize()
    
    return jsonify({
        'status': 'online',
        'google_ads_available': GOOGLE_ADS_AVAILABLE,
        'google_ads_connected': ads_manager.connected,
        'google_ads_error': ads_manager.error,
        'litify_available': SALESFORCE_AVAILABLE,
        'litify_connected': litify_manager.connected,
        'litify_error': litify_manager.error,
        'timestamp': datetime.now().isoformat()
    })


