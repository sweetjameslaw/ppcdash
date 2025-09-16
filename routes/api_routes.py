from datetime import datetime, timedelta, date
from flask import Flask, render_template, jsonify, request, send_from_directory, Blueprint
import logging
import calendar
import random 

import demo_data
from performance_boost import time_it

from services import state

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

@api_bp.route('/api/dashboard-data')
def dashboard_data():
    """Get dashboard data with proper integration of Google Ads and Litify"""
    # TODO: Import these globals from a shared module or pass as dependencies
    from app import (CACHE_DATA, CACHE_TIME, CACHE_DURATION, ads_manager, 
                     litify_manager, process_campaigns_to_buckets_with_litify,
                     get_demo_data)
    
    # Get parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', 1000, type=int)
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    # Get exclusion filter parameters
    include_spam = request.args.get('include_spam', 'false').lower() == 'true'
    include_abandoned = request.args.get('include_abandoned', 'false').lower() == 'true'
    include_duplicate = request.args.get('include_duplicate', 'false').lower() == 'true'
    
    # Create cache key based on filters
    cache_key = f"{start_date}_{end_date}_{limit}_{include_spam}_{include_abandoned}_{include_duplicate}"
    
    # Check cache validity
    cache_valid = False
    if not force_refresh and CACHE_DATA and CACHE_TIME:
        cached_key = CACHE_DATA.get('cache_key')
        if cached_key == cache_key and (datetime.now() - CACHE_TIME).seconds < CACHE_DURATION:
            cache_valid = True
            logger.info(f"Returning cached data for key: {cache_key}")
    
    if cache_valid:
        return jsonify(CACHE_DATA)
    
    logger.info(f"Fetching fresh data for filters: start={start_date}, end={end_date}, limit={limit}, "
                f"include_spam={include_spam}, include_abandoned={include_abandoned}, include_duplicate={include_duplicate}")
    
    # Initialize managers if needed
    if not ads_manager.client:
        ads_manager.initialize()
    if not litify_manager.client:
        litify_manager.initialize()
    
    # Fetch data from both sources
    campaigns = None
    litify_leads = []
    data_source = 'Demo Data'
    
    # Fetch Google Ads campaigns - ONLY ACTIVE (default behavior)
    if ads_manager.connected:
        campaigns = ads_manager.fetch_campaigns(start_date, end_date)  # Uses default active_only=True
        if campaigns:
            data_source = 'Google Ads API'
            logger.info(f"Fetched {len(campaigns)} campaigns from Google Ads")
    
    # Fetch Litify leads (only those with UTM Campaign)
    if litify_manager.connected:
        litify_leads = litify_manager.fetch_detailed_leads(
            start_date, end_date, limit=limit,
            include_spam=include_spam,
            include_abandoned=include_abandoned,
            include_duplicate=include_duplicate
        )
        if litify_leads:
            if data_source == 'Google Ads API':
                data_source = 'Google Ads + Litify'
            else:
                data_source = 'Litify'
            logger.info(f"Fetched {len(litify_leads)} detailed leads from Litify")
    else:
        litify_leads = litify_manager.get_demo_litify_leads(include_spam, include_abandoned, include_duplicate)
        logger.info("Using demo Litify leads data")
    
    # Process and integrate data
    excluded_counts = {'spam': 0, 'abandoned': 0, 'duplicate': 0, 'total': 0}
    if campaigns or litify_leads:
        # Use actual campaigns if available, otherwise create empty list
        campaigns_to_process = campaigns if campaigns else []
        buckets, unmapped_campaigns, unmapped_utms, excluded_counts = process_campaigns_to_buckets_with_litify(campaigns_to_process, litify_leads)
    else:
        demo = get_demo_data(include_spam, include_abandoned, include_duplicate)
        buckets = demo['buckets']
        unmapped_campaigns = demo.get('unmapped_campaigns', [])
        unmapped_utms = demo.get('unmapped_utms', [])
        litify_leads = demo.get('litify_leads', [])
        excluded_counts = demo.get('excluded_lead_counts', {'spam': 0, 'abandoned': 0, 'duplicate': 0, 'total': 0})
    
    # Prepare response with available buckets
    from app import BUCKET_PRIORITY
    response_data = {
        'buckets': buckets,
        'unmapped_campaigns': unmapped_campaigns,
        'unmapped_utms': list(unmapped_utms) if isinstance(unmapped_utms, set) else unmapped_utms,
        'litify_leads': litify_leads,
        'available_buckets': list(BUCKET_PRIORITY),  # Include list of all available bucket names
        'data_source': data_source,
        'timestamp': datetime.now().isoformat(),
        'date_range': {
            'start': start_date or 'today',
            'end': end_date or 'today'
        },
        'filters': {
            'include_spam': include_spam,
            'include_abandoned': include_abandoned,
            'include_duplicate': include_duplicate
        },
        'excluded_lead_counts': excluded_counts,
        'cache_key': cache_key
    }
    
    # Cache the data
    CACHE_DATA = response_data
    CACHE_TIME = datetime.now()
    
    return jsonify(response_data)

@api_bp.route('/api/utm-mapping', methods=['GET', 'POST'])
def api_utm_mapping():
    """API for UTM to bucket mapping"""
    from app import UTM_TO_BUCKET_MAPPING, CACHE_DATA, CACHE_TIME, save_utm_mapping
    global UTM_TO_BUCKET_MAPPING, CACHE_DATA, CACHE_TIME
    
    if request.method == 'GET':
        return jsonify(UTM_TO_BUCKET_MAPPING)
    
    elif request.method == 'POST':
        data = request.json
        action = data.get('action')
        
        if action == 'update':
            utm = data.get('utm')
            bucket = data.get('bucket')
            
            if utm and bucket:
                UTM_TO_BUCKET_MAPPING[utm] = bucket
                save_utm_mapping()
                
                # Clear cache
                CACHE_DATA = None
                CACHE_TIME = None
                logger.info(f"UTM '{utm}' mapped to bucket '{bucket}' and cache cleared")
                
                return jsonify({'success': True, 'mappings': UTM_TO_BUCKET_MAPPING})
            
            return jsonify({'success': False, 'error': 'Missing UTM or bucket'}), 400
        
        elif action == 'delete':
            utm = data.get('utm')
            
            if utm and utm in UTM_TO_BUCKET_MAPPING:
                del UTM_TO_BUCKET_MAPPING[utm]
                save_utm_mapping()
                
                # Clear cache
                CACHE_DATA = None
                CACHE_TIME = None
                logger.info(f"UTM '{utm}' mapping deleted and cache cleared")
                
                return jsonify({'success': True, 'mappings': UTM_TO_BUCKET_MAPPING})
            
            return jsonify({'success': False, 'error': 'UTM not found'}), 404
        
        elif action == 'update_all':
            new_mappings = data.get('mappings', {})
            
            UTM_TO_BUCKET_MAPPING = new_mappings
            save_utm_mapping()
            
            # Clear cache
            CACHE_DATA = None
            CACHE_TIME = None
            logger.info("UTM mappings updated and cache cleared")
            
            return jsonify({'success': True, 'mappings': UTM_TO_BUCKET_MAPPING})
        
        elif action == 'reset_to_defaults':
            UTM_TO_BUCKET_MAPPING = demo_data.DEMO_UTM_TO_BUCKET_MAPPING
            save_utm_mapping()
            
            # Clear cache
            CACHE_DATA = None
            CACHE_TIME = None
            logger.info("UTM mapping reset to defaults and cache cleared")
            
            return jsonify({'success': True, 'mappings': UTM_TO_BUCKET_MAPPING})
        
        return jsonify({'success': False, 'error': 'Invalid action'}), 400

@api_bp.route('/api/all-campaigns')
def api_all_campaigns():
    """Get list of all campaign names for mapping interface"""
    from app import ads_manager
    
    if not ads_manager.client:
        ads_manager.initialize()
    
    if ads_manager.connected:
        campaigns = ads_manager.fetch_campaigns()
        if campaigns:
            return jsonify([c['name'] for c in campaigns])
    
    # Return demo campaign names from module
    return jsonify(demo_data.DEMO_CAMPAIGNS)

@api_bp.route('/api/forecast-settings', methods=['GET', 'POST'])
def api_forecast_settings():
    """API for forecast settings"""
    from app import load_forecast_settings, save_forecast_settings
    
    if request.method == 'GET':
        settings = load_forecast_settings()
        return jsonify(settings)
    
    elif request.method == 'POST':
        settings = request.json
        if save_forecast_settings(settings):
            return jsonify({'success': True, 'message': 'Settings saved successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to save settings'}), 500

@api_bp.route('/api/forecast-pacing')
@time_it
def api_forecast_pacing():
    """
    Get current month pacing data with performance optimization
    Leverages daily_cache for better performance
    """
    from app import ads_manager, litify_manager
    from performance_boost import global_cache, parallel_fetch
    
    # Get date parameters (default to current month)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    # Get exclusion filter parameters
    include_spam = request.args.get('include_spam', 'false').lower() == 'true'
    include_abandoned = request.args.get('include_abandoned', 'false').lower() == 'true'
    include_duplicate = request.args.get('include_duplicate', 'false').lower() == 'true'
    
    # Default to current month if not specified
    if not start_date or not end_date:
        now = datetime.now()
        start_date = datetime(now.year, now.month, 1).strftime('%Y-%m-%d')
        end_date = datetime(now.year, now.month, calendar.monthrange(now.year, now.month)[1]).strftime('%Y-%m-%d')
    
    # Create cache key for pacing data
    cache_key = ['forecast_pacing', start_date, end_date, include_spam, include_abandoned, include_duplicate]
    
    # Check cache first
    if not force_refresh:
        cached = global_cache.get(cache_key)
        if cached:
            logger.info("✅ Returning cached forecast pacing data")
            return jsonify(cached)
    
    # Initialize managers if needed
    if not ads_manager.client:
        ads_manager.initialize()
    if not litify_manager.client:
        litify_manager.initialize()
    
    # Initialize response structure
    pacing_data = {
        'states': {
            "CA": {"spend": 0, "leads": 0, "cases": 0, "retainers": 0, "cpl": 0, "conversion_rate": 0},
            "AZ": {"spend": 0, "leads": 0, "cases": 0, "retainers": 0, "cpl": 0, "conversion_rate": 0},
            "GA": {"spend": 0, "leads": 0, "cases": 0, "retainers": 0, "cpl": 0, "conversion_rate": 0},
            "TX": {"spend": 0, "leads": 0, "cases": 0, "retainers": 0, "cpl": 0, "conversion_rate": 0}
        },
        'daily_data': [],
        'totals': {
            'spend': 0,
            'leads': 0,
            'cases': 0,
            'retainers': 0
        },
        'date_range': {
            'start': start_date,
            'end': end_date
        },
        'timestamp': datetime.now().isoformat()
    }
    
    # TODO: Implement the full pacing logic here
    # This is a simplified version - the full logic is quite complex
    # and would need the helper functions from the main app
    
    # Use parallel fetch for Google Ads and Litify data
    fetch_functions = {}
    
    # Google Ads fetch function
    def fetch_ads_data():
        if ads_manager.connected:
            return ads_manager.fetch_campaigns(start_date, end_date, active_only=False)
        else:
            return demo_data.get_demo_google_ads_data()
    
    # Litify fetch function
    def fetch_litify_data():
        if litify_manager.connected:
            return litify_manager.fetch_detailed_leads(
                start_date, end_date, 
                limit=1000,
                include_spam=include_spam,
                include_abandoned=include_abandoned,
                include_duplicate=include_duplicate
            )
        else:
            return demo_data.get_demo_litify_leads(include_spam, include_abandoned, include_duplicate)
    
    fetch_functions['google_ads'] = fetch_ads_data
    fetch_functions['litify'] = fetch_litify_data
    
    # Execute parallel fetch
    results = parallel_fetch(fetch_functions, timeout=30)
    
    # Process results and build pacing data
    # (This would contain the complex logic from the original function)
    
    # Cache the results
    global_cache.set(cache_key, pacing_data, ttl=1800)  # 30 minutes
    
    return jsonify(pacing_data)
