#!/usr/bin/env python3
"""
Sweet James Dashboard - Backend with Proper Campaign/Litify Integration and Forecasting
Updated: Refactored to use demo_data module for all demo/test data
"""

import os
import json
import logging
from datetime import datetime, timedelta, date
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import time
from collections import defaultdict
import calendar
import random
from urllib.parse import urlparse
import demo_data  # Import the demo data module
from performance_boost import optimize_app, global_cache, daily_cache, time_it, parallel_fetch
from services import state

from routes.api_routes import api_bp

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)






# Try importing optional libraries
try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
    GOOGLE_ADS_AVAILABLE = True
    logger.info("✅ Google Ads API loaded successfully")
except ImportError as e:
    GOOGLE_ADS_AVAILABLE = False
    logger.warning(f"⚠️ Google Ads API not available: {e}")

try:
    from simple_salesforce import Salesforce
    SALESFORCE_AVAILABLE = True
    logger.info("✅ Salesforce API loaded successfully")
except ImportError:
    SALESFORCE_AVAILABLE = False
    logger.warning("⚠️ Salesforce API not available")


from services.google_ads_services import GoogleAdsManager
from services.litify_services import LitifyManager



# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'sweet-james-2025')
CORS(app)







app.register_blueprint(api_bp)

# In-Practice Case Types
IN_PRACTICE_CASE_TYPES = [
    'Pedestrian',
    'Automobile Accident',
    'Wrongful Death',
    'Premise Liability',
    'Public Entity',
    'Personal injury',
    'Habitability',
    'Automobile Accident - Commercial',
    'Bicycle',
    'Animal Incident',
    'Wildfire 2025',
    'Motorcycle',
    'Slip and Fall',
    'Electric Scooter',
    'Mold',
    'Product Liability'
]

# Case types to exclude by default (can be included via checkbox)
EXCLUDED_CASE_TYPES = [
    'Spam',
    'Abandoned',
    'Duplicate'
]

# Campaign Bucket Mapping Configuration (for Google Ads campaign names)
CAMPAIGN_BUCKETS = {}

# UTM Campaign to Bucket Mapping (for Litify leads)
UTM_TO_BUCKET_MAPPING = {}

# Bucket Priority Order (defines the order buckets appear in UI)
BUCKET_PRIORITY = [
    "California Brand",
    "California Prospecting", 
    "California LSA",
    "Arizona Brand",
    "Arizona Prospecting",
    "Arizona LSA",
    "Georgia Brand",
    "Georgia Prospecting",
    "Georgia LSA",
    "Texas Brand",
    "Texas Prospecting",
    "Texas LSA", 
    "Crisp/Youtube"
]

# Simple cache for dashboard data
CACHE_DATA = None
CACHE_TIME = None
CACHE_DURATION = 301  # 5 minutes in seconds

def load_campaign_mappings():
    """Load campaign bucket mappings from JSON file or use demo defaults"""
    global CAMPAIGN_BUCKETS
    mappings_file = 'campaign_mappings.json'
    
    if os.path.exists(mappings_file):
        try:
            with open(mappings_file, 'r') as f:
                CAMPAIGN_BUCKETS = json.load(f)
            logger.info(f"✅ Loaded campaign mappings from {mappings_file}")
            logger.info(f"   Found {len(CAMPAIGN_BUCKETS)} bucket mappings")
        except Exception as e:
            logger.error(f"❌ Error loading campaign mappings: {e}")
            # Fall back to demo mappings
            CAMPAIGN_BUCKETS = demo_data.DEMO_CAMPAIGN_BUCKETS
    else:
        # Use demo mappings as defaults
        CAMPAIGN_BUCKETS = demo_data.DEMO_CAMPAIGN_BUCKETS
        logger.info("📊 Using default demo campaign mappings")

def save_mappings():
    """Save campaign bucket mappings to JSON file"""
    mappings_file = 'campaign_mappings.json'
    try:
        with open(mappings_file, 'w') as f:
            json.dump(CAMPAIGN_BUCKETS, f, indent=2)
        logger.info(f"✅ Saved campaign mappings to {mappings_file}")
        return True
    except Exception as e:
        logger.error(f"❌ Error saving campaign mappings: {e}")
        return False

def load_utm_mapping():
    """Load UTM to bucket mapping from JSON file or use demo defaults"""
    global UTM_TO_BUCKET_MAPPING
    utm_file = 'utm_mappings.json'
    
    if os.path.exists(utm_file):
        try:
            with open(utm_file, 'r') as f:
                UTM_TO_BUCKET_MAPPING = json.load(f)
            logger.info(f"✅ Loaded UTM mappings from {utm_file}")
        except Exception as e:
            logger.error(f"❌ Error loading UTM mappings: {e}")
            # Fall back to demo mappings
            UTM_TO_BUCKET_MAPPING = demo_data.DEMO_UTM_TO_BUCKET_MAPPING
    else:
        # Use demo mappings as defaults
        UTM_TO_BUCKET_MAPPING = demo_data.DEMO_UTM_TO_BUCKET_MAPPING
        logger.info("📊 Using default demo UTM mappings")

def save_utm_mapping():
    """Save UTM to bucket mapping to JSON file"""
    utm_file = 'utm_mappings.json'
    try:
        with open(utm_file, 'w') as f:
            json.dump(UTM_TO_BUCKET_MAPPING, f, indent=2)
        logger.info(f"✅ Saved UTM mappings to {utm_file}")
        return True
    except Exception as e:
        logger.error(f"❌ Error saving UTM mappings: {e}")
        return False

# Load mappings on startup
load_campaign_mappings()
load_utm_mapping()

def load_forecast_settings():
    """Load forecast settings from JSON file"""
    settings_file = 'forecast_settings.json'
    
    # Default settings
    default_settings = {
        'targets': {
            'CA': {'spend': 1500000, 'leads': 1200, 'retainers': 300, 'cases': 240},
            'AZ': {'spend': 500000, 'leads': 400, 'retainers': 100, 'cases': 80},
            'GA': {'spend': 300000, 'leads': 240, 'retainers': 60, 'cases': 48},
            'TX': {'spend': 200000, 'leads': 160, 'retainers': 40, 'cases': 32}
        },
        'conversion_rates': {
            'CA': {'lead_to_retainer': 0.25, 'lead_to_case': 0.20},
            'AZ': {'lead_to_retainer': 0.25, 'lead_to_case': 0.20},
            'GA': {'lead_to_retainer': 0.25, 'lead_to_case': 0.20},
            'TX': {'lead_to_retainer': 0.25, 'lead_to_case': 0.20}
        },
        'cpl_targets': {
            'CA': 1250,
            'AZ': 1250,
            'GA': 1250,
            'TX': 1250
        }
    }
    
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                # Merge with defaults to ensure all fields exist
                for key in default_settings:
                    if key not in settings:
                        settings[key] = default_settings[key]
                return settings
        except Exception as e:
            logger.error(f"Error loading forecast settings: {e}")
    
    return default_settings

def save_forecast_settings(settings):
    """Save forecast settings to JSON file"""
    settings_file = 'forecast_settings.json'
    try:
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2)
        logger.info(f"✅ Saved forecast settings to {settings_file}")
        return True
    except Exception as e:
        logger.error(f"❌ Error saving forecast settings: {e}")
        return False

def get_state_from_campaign_bucket(bucket_name):
    """Determine state from campaign bucket name"""
    bucket_lower = bucket_name.lower()
    
    if 'california' in bucket_lower:
        return 'CA'
    elif 'arizona' in bucket_lower:
        return 'AZ'
    elif 'georgia' in bucket_lower:
        return 'GA'
    elif 'texas' in bucket_lower:
        return 'TX'
    
    return None

def build_companion_groups(leads):
    """
    Build case groups using improved companion relationship detection.
    Returns a mapping of lead_id to case_id for tracking.
    """
    companion_map = {}
    case_assignments = {}
    case_counter = 1
    
    # Build companion relationships (bidirectional)
    for lead in leads:
        lead_id = lead.get('id', '')
        companion_id = lead.get('companion_case_id', '')
        matter_id = lead.get('matter_id', '')
        
        if companion_id:
            # Create bidirectional mapping
            if lead_id not in companion_map:
                companion_map[lead_id] = set()
            if companion_id not in companion_map:
                companion_map[companion_id] = set()
            
            companion_map[lead_id].add(companion_id)
            companion_map[companion_id].add(lead_id)
        
        # Also link through matter_id
        if matter_id:
            for other_lead in leads:
                other_id = other_lead.get('id', '')
                other_matter = other_lead.get('matter_id', '')
                
                if other_id != lead_id and other_matter == matter_id:
                    if lead_id not in companion_map:
                        companion_map[lead_id] = set()
                    if other_id not in companion_map:
                        companion_map[other_id] = set()
                    
                    companion_map[lead_id].add(other_id)
                    companion_map[other_id].add(lead_id)
    
    # Traverse companion groups
    visited = set()
    
    for lead in leads:
        lead_id = lead.get('id', '')
        
        if lead_id not in visited:
            # Start a new case group
            case_id = f"CASE_{case_counter:04d}"
            case_counter += 1
            
            # Use BFS to find all related companions
            queue = [lead_id]
            group_members = set()
            
            while queue:
                current = queue.pop(0)
                if current not in visited:
                    visited.add(current)
                    group_members.add(current)
                    
                    # Add all companions to queue
                    if current in companion_map:
                        for companion in companion_map[current]:
                            if companion not in visited:
                                queue.append(companion)
            
            # Assign the same case_id to all group members
            for member in group_members:
                case_assignments[member] = case_id
    
    return case_assignments

# Initialize managers
ads_manager = GoogleAdsManager()
litify_manager = LitifyManager()

state.set_managers(ads_manager, litify_manager)


optimize_app(app, ads_manager, litify_manager)

def get_demo_data(include_spam=False, include_abandoned=False, include_duplicate=False):
    """Wrapper function to maintain compatibility"""
    return demo_data.get_demo_bucket_data(include_spam, include_abandoned, include_duplicate)

def process_campaigns_to_buckets_with_litify(campaigns, litify_leads):
    """
    Process Google Ads campaigns and Litify leads to create bucketed data with improved companion case grouping
    Enhanced with LSA campaign detection using customer IDs
    """
    # LSA Account to State Mapping (based on discovery)
    LSA_ACCOUNT_STATE_MAP = {
        '2419159990': 'Arizona LSA',      # Google - Sweet James (Arizona)
        '8734393866': 'Georgia LSA',      # LSA - Atlanta
        '2065821782': 'California LSA',   # LSA - Los Angeles
        '1130290121': 'California LSA',   # LSA - Newport
        '9598631966': 'Georgia LSA',      # LSA - Roswell
        '1867060368': 'California LSA',   # Sweet James Accident Attorneys
    }
    
    # Initialize buckets
    bucketed_data = {bucket: {
        'name': bucket,
        'state': get_state_from_campaign_bucket(bucket) or 'Unknown',
        'campaigns': [],
        'cost': 0,
        'leads': 0,
        'inPractice': 0,
        'unqualified': 0,
        'cases': 0,
        'retainers': 0,
        'pendingRetainers': 0,
        'totalRetainers': 0
    } for bucket in BUCKET_PRIORITY}
    
    unmapped_campaigns = []
    unmapped_utm_campaigns = set()
    excluded_counts = {'spam': 0, 'abandoned': 0, 'duplicate': 0, 'total': 0}
    
    # Process Google Ads campaigns
    if campaigns:
        for campaign in campaigns:
            campaign_name = campaign.get('name', 'Unknown')
            customer_id = campaign.get('customer_id', '')
            cost = campaign.get('cost', 0)
            is_lsa = campaign.get('is_lsa', False) or 'LocalServicesCampaign' in campaign_name
            
            bucket_found = False
            
            # Special handling for LSA campaigns
            if is_lsa:
                # Try to map LSA campaign using customer ID
                if customer_id in LSA_ACCOUNT_STATE_MAP:
                    bucket_name = LSA_ACCOUNT_STATE_MAP[customer_id]
                    if bucket_name in bucketed_data:
                        bucketed_data[bucket_name]['campaigns'].append(campaign_name)
                        bucketed_data[bucket_name]['cost'] += cost
                        bucket_found = True
                        logger.info(f"✅ Mapped LSA campaign from account {customer_id} to {bucket_name}")
                else:
                    # Try to determine state from campaign or customer name
                    customer_name = campaign.get('customer_name', '')
                    
                    # Check customer name for location hints
                    if any(x in customer_name.lower() for x in ['los angeles', 'la ', 'newport', 'california']):
                        bucket_name = 'California LSA'
                    elif any(x in customer_name.lower() for x in ['atlanta', 'roswell', 'georgia']):
                        bucket_name = 'Georgia LSA'
                    elif any(x in customer_name.lower() for x in ['phoenix', 'arizona']):
                        bucket_name = 'Arizona LSA'
                    elif any(x in customer_name.lower() for x in ['houston', 'dallas', 'texas']):
                        bucket_name = 'Texas LSA'
                    else:
                        bucket_name = None
                    
                    if bucket_name and bucket_name in bucketed_data:
                        bucketed_data[bucket_name]['campaigns'].append(campaign_name)
                        bucketed_data[bucket_name]['cost'] += cost
                        bucket_found = True
                        logger.info(f"✅ Mapped LSA campaign '{campaign_name}' to {bucket_name} based on customer name")
            
            # If not LSA or LSA not mapped, try regular campaign bucket mapping
            if not bucket_found:
                for bucket_name, bucket_campaigns in CAMPAIGN_BUCKETS.items():
                    if campaign_name in bucket_campaigns:
                        if bucket_name in bucketed_data:
                            bucketed_data[bucket_name]['campaigns'].append(campaign_name)
                            bucketed_data[bucket_name]['cost'] += cost
                            bucket_found = True
                            break
            
            # If still not found, add to unmapped
            if not bucket_found:
                unmapped_campaigns.append(campaign_name)
                if is_lsa:
                    logger.warning(f"⚠️ Unmapped LSA campaign: {campaign_name} (Customer ID: {customer_id})")
                else:
                    logger.warning(f"⚠️ Unmapped campaign: {campaign_name}")
    
    # Track excluded lead counts by type
    for lead in litify_leads:
        case_type = lead.get('case_type', '')
        if case_type == 'Spam':
            excluded_counts['spam'] += 1
            excluded_counts['total'] += 1
        elif case_type == 'Abandoned':
            excluded_counts['abandoned'] += 1
            excluded_counts['total'] += 1
        elif case_type == 'Duplicate':
            excluded_counts['duplicate'] += 1
            excluded_counts['total'] += 1
    
    # Build companion groups for case counting
    case_assignments = build_companion_groups(litify_leads)
    
    # Track unique cases per bucket (using case_id from grouping)
    cases_by_bucket = defaultdict(set)
    
    # Process Litify leads
    for lead in litify_leads:
        bucket_name = lead.get('bucket', '')
        
        # If no bucket mapping, try to map based on UTM campaign
        if not bucket_name:
            utm = lead.get('utm_campaign', '')
            if utm and utm not in ['-', '']:
                unmapped_utm_campaigns.add(utm)
                continue
        
        if bucket_name in bucketed_data:
            # Count leads
            bucketed_data[bucket_name]['leads'] += 1
            
            # Count in-practice leads
            if lead.get('in_practice', False):
                bucketed_data[bucket_name]['inPractice'] += 1
                
                # Count converted retainers
                if lead.get('is_converted', False):
                    bucketed_data[bucket_name]['retainers'] += 1
                    
                    # Track unique case using the case_id from grouping
                    lead_id = lead.get('id', '')
                    case_id = case_assignments.get(lead_id, f"unknown_{lead_id}")
                    cases_by_bucket[bucket_name].add(case_id)
                else:
                    # In practice but not converted = unqualified
                    bucketed_data[bucket_name]['unqualified'] += 1
            
            # Count pending retainers separately
            if lead.get('is_pending', False):
                bucketed_data[bucket_name]['pendingRetainers'] += 1
    
    # Convert case sets to counts
    for bucket_name in bucketed_data:
        bucketed_data[bucket_name]['cases'] = len(cases_by_bucket[bucket_name])
    
    # Calculate total retainers (signed + pending) and percentages
    for bucket_name, data in bucketed_data.items():
        # Total retainers includes both signed and pending
        data['totalRetainers'] = data['retainers'] + data['pendingRetainers']
        
        # Calculate percentages
        if data['inPractice'] > 0:
            data['inPracticePercent'] = round(data['inPractice'] / data['leads'], 3) if data['leads'] > 0 else 0
            data['unqualifiedPercent'] = round(data['unqualified'] / data['inPractice'], 3)
            data['conversionRate'] = round(data['retainers'] / data['inPractice'], 3)
        else:
            data['inPracticePercent'] = 0
            data['unqualifiedPercent'] = 0
            data['conversionRate'] = 0
        
        # Calculate cost metrics
        if data['leads'] > 0:
            data['costPerLead'] = round(data['cost'] / data['leads'], 2)
        
        # Cost per case based on unique cases
        if data['cases'] > 0:
            data['cpa'] = round(data['cost'] / data['cases'], 2)
        
        # Cost per retainer based on signed retainers only (for now)
        if data['retainers'] > 0:
            data['costPerRetainer'] = round(data['cost'] / data['retainers'], 2)
    
    # Log summary for debugging
    total_leads = sum(b['leads'] for b in bucketed_data.values())
    total_cases = sum(b['cases'] for b in bucketed_data.values())
    total_retainers = sum(b['retainers'] for b in bucketed_data.values())
    total_pending = sum(b.get('pendingRetainers', 0) for b in bucketed_data.values())
    total_in_practice = sum(b['inPractice'] for b in bucketed_data.values())
    total_unqualified = sum(b['unqualified'] for b in bucketed_data.values())
    total_cost = sum(b['cost'] for b in bucketed_data.values())
    
    # Count LSA campaigns
    lsa_buckets = ['California LSA', 'Arizona LSA', 'Georgia LSA', 'Texas LSA']
    lsa_count = sum(len(bucketed_data[b]['campaigns']) for b in lsa_buckets if b in bucketed_data)
    lsa_spend = sum(bucketed_data[b]['cost'] for b in lsa_buckets if b in bucketed_data)
    
    logger.info(f"📊 Summary: {total_leads} leads, {total_in_practice} in practice, "
                f"{total_unqualified} unqualified (in practice but not converted), "
                f"{total_cases} cases, {total_retainers} signed retainers, "
                f"{total_pending} pending retainers")
    
    if lsa_count > 0:
        logger.info(f"📍 LSA Campaigns: {lsa_count} campaigns, ${lsa_spend:,.2f} spend")
    
    logger.info(f"💰 Total Spend: ${total_cost:,.2f}")
    
    if excluded_counts['total'] > 0:
        logger.info(f"🚫 Excluded leads: {excluded_counts['total']} total "
                    f"(Spam: {excluded_counts['spam']}, Abandoned: {excluded_counts['abandoned']}, "
                    f"Duplicate: {excluded_counts['duplicate']})")
    
    return list(bucketed_data.values()), unmapped_campaigns, unmapped_utm_campaigns, excluded_counts

# ========== API ROUTES ==========

@app.route('/')
def index():
    """Serve the dashboard HTML"""
    return render_template('dashboard.html')

@app.route('/campaign-mapping')
@app.route('/campaign-mapping/')
def campaign_mapping_page():
    """Serve the campaign mapping HTML"""
    return render_template('campaign-mapping.html')

@app.route('/forecasting')
def forecasting_page():
    """Serve the forecasting dashboard HTML"""
    return render_template('forecasting.html')

@app.route('/comparison-dashboard')
def comparison_dashboard_page():
    """Serve the comparison dashboard HTML"""
    return render_template('comparison-dashboard.html')


@app.route('/api/forecast-projections')
@time_it
def api_forecast_projections():
    """
    Get forecast projections based on current pacing with advanced calculations
    """
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    # Cache key for projections
    cache_key = ['forecast_projections', datetime.now().strftime('%Y-%m-%d')]
    
    if not force_refresh:
        cached = global_cache.get(cache_key)
        if cached:
            logger.info("✅ Returning cached forecast projections")
            return jsonify(cached)
    
    # Get current month pacing data
    pacing_response = api_forecast_pacing()
    pacing_data = pacing_response.get_json()
    
    # Load forecast settings
    settings = load_forecast_settings()
    
    # Calculate time factors
    now = datetime.now()
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    days_elapsed = now.day
    days_remaining = days_in_month - days_elapsed
    percent_complete = (days_elapsed / days_in_month) * 100
    
    # Initialize projections
    projections = {
        'states': {},
        'totals': {
            'current': {'spend': 0, 'leads': 0, 'cases': 0, 'retainers': 0},
            'projected': {'spend': 0, 'leads': 0, 'cases': 0, 'retainers': 0},
            'target': {'spend': 0, 'leads': 0, 'cases': 0, 'retainers': 0},
            'variance': {'spend': 0, 'leads': 0, 'cases': 0, 'retainers': 0},
            'variance_percent': {'spend': 0, 'leads': 0, 'cases': 0, 'retainers': 0}
        },
        'time_metrics': {
            'days_elapsed': days_elapsed,
            'days_remaining': days_remaining,
            'days_in_month': days_in_month,
            'percent_complete': percent_complete
        },
        'recommendations': [],
        'timestamp': datetime.now().isoformat()
    }
    
    # Calculate projections by state
    for state in ['CA', 'AZ', 'GA', 'TX']:
        current = pacing_data['states'][state]
        targets = settings['targets'][state]
        conversion_rates = settings['conversion_rates'][state]
        cpl_target = settings['cpl_targets'][state]
        
        # Calculate daily run rates
        daily_rates = {
            'spend': current['spend'] / days_elapsed if days_elapsed > 0 else 0,
            'leads': current['leads'] / days_elapsed if days_elapsed > 0 else 0,
            'retainers': current['retainers'] / days_elapsed if days_elapsed > 0 else 0,
            'cases': current['cases'] / days_elapsed if days_elapsed > 0 else 0
        }
        
        # Project full month based on current pace
        projected = {
            'spend': daily_rates['spend'] * days_in_month,
            'leads': daily_rates['leads'] * days_in_month,
            'retainers': daily_rates['retainers'] * days_in_month,
            'cases': daily_rates['cases'] * days_in_month
        }
        
        # Calculate required daily rates to hit targets
        required_daily = {
            'spend': (targets['spend'] - current['spend']) / days_remaining if days_remaining > 0 else 0,
            'leads': (targets['leads'] - current['leads']) / days_remaining if days_remaining > 0 else 0,
            'retainers': (targets['retainers'] - current['retainers']) / days_remaining if days_remaining > 0 else 0,
            'cases': (targets['cases'] - current['cases']) / days_remaining if days_remaining > 0 else 0
        }
        
        # Calculate variances
        variance = {
            'spend': projected['spend'] - targets['spend'],
            'leads': projected['leads'] - targets['leads'],
            'retainers': projected['retainers'] - targets['retainers'],
            'cases': projected['cases'] - targets['cases']
        }
        
        variance_percent = {
            'spend': (variance['spend'] / targets['spend'] * 100) if targets['spend'] > 0 else 0,
            'leads': (variance['leads'] / targets['leads'] * 100) if targets['leads'] > 0 else 0,
            'retainers': (variance['retainers'] / targets['retainers'] * 100) if targets['retainers'] > 0 else 0,
            'cases': (variance['cases'] / targets['cases'] * 100) if targets['cases'] > 0 else 0
        }
        
        # Calculate performance metrics
        current_cpl = current['spend'] / current['leads'] if current['leads'] > 0 else 0
        projected_cpl = projected['spend'] / projected['leads'] if projected['leads'] > 0 else 0
        current_conversion = (current['retainers'] / current['leads'] * 100) if current['leads'] > 0 else 0
        
        # Store state projections
        projections['states'][state] = {
            'current': current,
            'projected': projected,
            'target': targets,
            'variance': variance,
            'variance_percent': variance_percent,
            'daily_rates': daily_rates,
            'required_daily': required_daily,
            'metrics': {
                'current_cpl': current_cpl,
                'projected_cpl': projected_cpl,
                'target_cpl': cpl_target,
                'current_conversion': current_conversion,
                'target_conversion': conversion_rates['lead_to_retainer'] * 100
            },
            'status': determine_pacing_status(variance_percent['spend'], percent_complete)
        }
        
        # Update totals
        for metric in ['spend', 'leads', 'cases', 'retainers']:
            projections['totals']['current'][metric] += current[metric]
            projections['totals']['projected'][metric] += projected[metric]
            projections['totals']['target'][metric] += targets[metric]
            projections['totals']['variance'][metric] += variance[metric]
    
    # Calculate total variance percentages
    for metric in ['spend', 'leads', 'cases', 'retainers']:
        if projections['totals']['target'][metric] > 0:
            projections['totals']['variance_percent'][metric] = (
                projections['totals']['variance'][metric] / projections['totals']['target'][metric] * 100
            )
    
    # Generate recommendations
    projections['recommendations'] = generate_forecast_recommendations(projections)
    
    # Cache the result
    global_cache.set(cache_key, projections)
    
    logger.info(f"✅ Forecast projections generated")
    
    return jsonify(projections)

@app.route('/api/forecast-daily-trend')
@time_it
def api_forecast_daily_trend():
    """
    Get daily trend data for the current month with caching optimization
    """
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    # Get filter parameters
    include_spam = request.args.get('include_spam', 'false').lower() == 'true'
    include_abandoned = request.args.get('include_abandoned', 'false').lower() == 'true'
    include_duplicate = request.args.get('include_duplicate', 'false').lower() == 'true'
    
    # Cache key
    cache_key = ['forecast_daily_trend', datetime.now().strftime('%Y-%m'), 
                 include_spam, include_abandoned, include_duplicate]
    
    if not force_refresh:
        cached = global_cache.get(cache_key)
        if cached:
            logger.info("✅ Returning cached daily trend data")
            return jsonify(cached)
    
    # Get current month date range
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)
    month_end = datetime(now.year, now.month, calendar.monthrange(now.year, now.month)[1])
    today = min(now, month_end)
    
    daily_data = []
    cumulative = {'spend': 0, 'leads': 0, 'cases': 0, 'retainers': 0}
    
    # Fetch data day by day (leveraging daily_cache)
    current_date = month_start
    while current_date <= today:
        date_str = current_date.strftime('%Y-%m-%d')
        
        # Fetch data for this day (will use daily_cache if available)
        day_metrics = fetch_single_day_metrics(
            date_str, 
            include_spam, 
            include_abandoned, 
            include_duplicate
        )
        
        # Update cumulative totals
        for metric in ['spend', 'leads', 'cases', 'retainers']:
            cumulative[metric] += day_metrics.get(metric, 0)
        
        daily_data.append({
            'date': date_str,
            'daily': day_metrics,
            'cumulative': dict(cumulative)  # Copy current cumulative state
        })
        
        current_date += timedelta(days=1)
    
    result = {
        'daily_data': daily_data,
        'month': now.strftime('%Y-%m'),
        'timestamp': datetime.now().isoformat()
    }
    
    # Cache the result
    global_cache.set(cache_key, result)
    
    logger.info(f"✅ Daily trend data generated: {len(daily_data)} days")
    
    return jsonify(result)

# ==================== HELPER FUNCTIONS ====================

def determine_state_from_campaign(campaign_name):
    """Map campaign name to state using bucket mappings"""
    # Check campaign bucket mapping
    for bucket, campaigns in CAMPAIGN_BUCKETS.items():
        if campaign_name in campaigns:
            # Extract state from bucket name
            if 'California' in bucket or 'CA' in bucket:
                return 'CA'
            elif 'Arizona' in bucket or 'AZ' in bucket:
                return 'AZ'
            elif 'Georgia' in bucket or 'GA' in bucket:
                return 'GA'
            elif 'Texas' in bucket or 'TX' in bucket:
                return 'TX'
    
    # Fallback: check campaign name directly
    campaign_lower = campaign_name.lower()
    if any(x in campaign_lower for x in ['california', ' ca ', 'los angeles', 'san diego', 'san francisco']):
        return 'CA'
    elif any(x in campaign_lower for x in ['arizona', ' az ', 'phoenix', 'tucson']):
        return 'AZ'
    elif any(x in campaign_lower for x in ['georgia', ' ga ', 'atlanta']):
        return 'GA'
    elif any(x in campaign_lower for x in ['texas', ' tx ', 'houston', 'dallas', 'austin']):
        return 'TX'
    
    return 'CA'  # Default to CA if unable to determine


def determine_state_from_utm(utm_campaign):
    """Map UTM campaign to state using UTM mappings"""
    # Check UTM to bucket mapping
    bucket = UTM_TO_BUCKET_MAPPING.get(utm_campaign)
    
    if bucket:
        if 'California' in bucket or 'CA' in bucket:
            return 'CA'
        elif 'Arizona' in bucket or 'AZ' in bucket:
            return 'AZ'
        elif 'Georgia' in bucket or 'GA' in bucket:
            return 'GA'
        elif 'Texas' in bucket or 'TX' in bucket:
            return 'TX'
    
    # Fallback: check UTM campaign directly
    utm_lower = utm_campaign.lower()
    if any(x in utm_lower for x in ['california', '_ca_', 'losangeles', 'sandiego']):
        return 'CA'
    elif any(x in utm_lower for x in ['arizona', '_az_', 'phoenix']):
        return 'AZ'
    elif any(x in utm_lower for x in ['georgia', '_ga_', 'atlanta']):
        return 'GA'
    elif any(x in utm_lower for x in ['texas', '_tx_', 'houston', 'dallas']):
        return 'TX'
    
    return 'CA'  # Default to CA


def fetch_single_day_metrics(date_str, include_spam=False, include_abandoned=False, include_duplicate=False):
    """
    Fetch metrics for a single day, leveraging daily_cache
    """
    # Check daily cache first
    cache_type = f'metrics_{include_spam}_{include_abandoned}_{include_duplicate}'
    cached = daily_cache.get_day(date_str, cache_type)
    if cached:
        return cached
    
    # Initialize metrics
    metrics = {'spend': 0, 'leads': 0, 'cases': 0, 'retainers': 0}
    
    # Fetch Google Ads data for the day
    if ads_manager.connected:
        campaigns = ads_manager.fetch_campaigns(date_str, date_str, active_only=False)
        if campaigns:
            for campaign in campaigns:
                metrics['spend'] += campaign.get('cost', 0)
    
    # Fetch Litify data for the day
    if litify_manager.connected:
        leads = litify_manager.fetch_detailed_leads(
            date_str, date_str,
            limit=500,
            include_spam=include_spam,
            include_abandoned=include_abandoned,
            include_duplicate=include_duplicate
        )
        if leads:
            metrics['leads'] = len(leads)
            case_ids = set()
            retainer_count = 0
            
            for lead in leads:
                if lead.get('Retainer_Signed_Date__c'):
                    retainer_count += 1
                
                matter_id = lead.get('litify_pm__Matter__c')
                if matter_id:
                    case_ids.add(matter_id)
            
            metrics['cases'] = len(case_ids)
            metrics['retainers'] = retainer_count
    
    # Cache the result
    daily_cache.set_day(date_str, metrics, cache_type)
    
    return metrics


def fetch_daily_pacing_data(start_date, end_date, include_spam=False, include_abandoned=False, include_duplicate=False):
    """
    Fetch daily pacing data for trend charts
    """
    daily_data = []
    
    # Parse dates
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    # Use parallel fetching for multiple days
    fetch_functions = {}
    current = start
    
    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        fetch_functions[date_str] = lambda d=date_str: fetch_single_day_metrics(
            d, include_spam, include_abandoned, include_duplicate
        )
        current += timedelta(days=1)
    
    # Execute parallel fetch
    if len(fetch_functions) > 1:
        results = parallel_fetch(fetch_functions, timeout=30)
    else:
        results = {date_str: fetch_functions[date_str]() for date_str in fetch_functions}
    
    # Build daily data array
    for date_str in sorted(results.keys()):
        daily_data.append({
            'date': date_str,
            'metrics': results[date_str]
        })
    
    return daily_data


def determine_pacing_status(variance_percent, time_percent):
    """
    Determine pacing status based on variance and time elapsed
    """
    # Calculate pacing efficiency
    pacing_efficiency = variance_percent - (time_percent - 100)
    
    if abs(pacing_efficiency) <= 5:
        return 'on_track'
    elif pacing_efficiency > 5:
        return 'ahead'
    else:
        return 'behind'


def generate_forecast_recommendations(projections):
    """
    Generate actionable recommendations based on projections
    """
    recommendations = []
    time_percent = projections['time_metrics']['percent_complete']
    
    for state, data in projections['states'].items():
        variance = data['variance_percent']
        
        # Check spend pacing
        if variance['spend'] < -10:
            recommendations.append({
                'state': state,
                'type': 'spend',
                'severity': 'high',
                'message': f"{state} is {abs(variance['spend']):.1f}% under spend target. Consider increasing daily budget by ${data['required_daily']['spend']:,.0f}/day."
            })
        elif variance['spend'] > 10:
            recommendations.append({
                'state': state,
                'type': 'spend',
                'severity': 'medium',
                'message': f"{state} is {variance['spend']:.1f}% over spend target. Consider reducing daily budget."
            })
        
        # Check lead pacing
        if variance['leads'] < -10:
            recommendations.append({
                'state': state,
                'type': 'leads',
                'severity': 'high',
                'message': f"{state} needs {data['required_daily']['leads']:.0f} leads/day to hit target (current: {data['daily_rates']['leads']:.1f}/day)."
            })
        
        # Check CPL efficiency
        if data['metrics']['current_cpl'] > data['metrics']['target_cpl'] * 1.2:
            recommendations.append({
                'state': state,
                'type': 'efficiency',
                'severity': 'medium',
                'message': f"{state} CPL is ${data['metrics']['current_cpl']:.0f} (target: ${data['metrics']['target_cpl']:.0f}). Review campaign targeting and quality."
            })
        
        # Check conversion rate
        if data['metrics']['current_conversion'] < data['metrics']['target_conversion'] * 0.8:
            recommendations.append({
                'state': state,
                'type': 'conversion',
                'severity': 'medium',
                'message': f"{state} conversion rate is {data['metrics']['current_conversion']:.1f}% (target: {data['metrics']['target_conversion']:.1f}%). Review lead quality and intake process."
            })
    
    # Sort by severity
    severity_order = {'high': 0, 'medium': 1, 'low': 2}
    recommendations.sort(key=lambda x: severity_order.get(x['severity'], 3))
    
    return recommendations[:10]  # Return top 10 recommendations

def calculate_comparison_dates(period, custom_start=None, custom_end=None):
    """Calculate date ranges for comparison periods"""
    today = datetime.now().date()
    
    if period == 'today':
        start = end = today
        compare_start = compare_end = today - timedelta(days=1)
    elif period == 'yesterday':
        start = end = today - timedelta(days=1)
        compare_start = compare_end = today - timedelta(days=2)
    elif period == 'week':
        start = today - timedelta(days=today.weekday())
        end = today
        compare_start = start - timedelta(days=7)
        compare_end = end - timedelta(days=7)
    elif period == 'month':
        start = date(today.year, today.month, 1)
        end = today
        # Previous month
        if start.month == 1:
            compare_start = date(start.year-1, 12, 1)
        else:
            compare_start = date(start.year, start.month-1, 1)
        compare_end = start - timedelta(days=1)
    elif period == 'custom' and custom_start and custom_end:
        start = datetime.strptime(custom_start, '%Y-%m-%d').date()
        end = datetime.strptime(custom_end, '%Y-%m-%d').date()
        period_days = (end - start).days + 1
        compare_start = start - timedelta(days=period_days)
        compare_end = end - timedelta(days=period_days)
    else:  # mtd
        start = date(today.year, today.month, 1)
        end = today
        # Same period last month
        if start.month == 1:
            compare_start = date(start.year-1, 12, 1)
            compare_end = date(start.year-1, 12, min(end.day, 31))
        else:
            # Handle month length differences
            compare_start = start.replace(month=start.month-1)
            compare_end = end.replace(month=end.month-1)
            # Adjust for different month lengths
            last_day_prev_month = calendar.monthrange(compare_start.year, compare_start.month)[1]
            if compare_end.day > last_day_prev_month:
                compare_end = compare_end.replace(day=last_day_prev_month)
    
    return compare_start.strftime('%Y-%m-%d'), compare_end.strftime('%Y-%m-%d')

def fetch_period_data(start_date, end_date, include_spam, include_abandoned, include_duplicate):
    """Fetch data for a specific period (reuse existing logic)"""
    campaigns = None
    litify_leads = []
    
    # Fetch Google Ads campaigns - ONLY ACTIVE (default behavior)
    if ads_manager.connected:
        campaigns = ads_manager.fetch_campaigns(start_date, end_date)  # Uses default active_only=True
    
    # Fetch Litify leads
    if litify_manager.connected:
        litify_leads = litify_manager.fetch_detailed_leads(
            start_date, end_date, limit=1000,
            include_spam=include_spam,
            include_abandoned=include_abandoned,
            include_duplicate=include_duplicate
        )
    else:
        litify_leads = litify_manager.get_demo_litify_leads(
            include_spam, include_abandoned, include_duplicate
        )
    
    # Process data (reuse existing logic)
    if campaigns or litify_leads:
        campaigns_to_process = campaigns if campaigns else []
        buckets, _, _, excluded_counts = process_campaigns_to_buckets_with_litify(
            campaigns_to_process, litify_leads
        )
    else:
        demo = get_demo_data(include_spam, include_abandoned, include_duplicate)
        buckets = demo['buckets']
        excluded_counts = demo.get('excluded_lead_counts', {})
    
    # Calculate summary metrics
    summary = {
        'total_spend': sum(b['cost'] for b in buckets),
        'total_leads': sum(b['leads'] for b in buckets),
        'total_cases': sum(b['cases'] for b in buckets),
        'total_retainers': sum(b['retainers'] for b in buckets),
        'total_in_practice': sum(b['inPractice'] for b in buckets),
        'total_unqualified': sum(b['unqualified'] for b in buckets),
        'buckets': buckets,
        'excluded_counts': excluded_counts
    }
    
    # Calculate derived metrics
    if summary['total_leads'] > 0:
        summary['avg_cpl'] = summary['total_spend'] / summary['total_leads']
    else:
        summary['avg_cpl'] = 0
    
    if summary['total_cases'] > 0:
        summary['avg_cpa'] = summary['total_spend'] / summary['total_cases']
    else:
        summary['avg_cpa'] = 0
    
    if summary['total_retainers'] > 0:
        summary['avg_cpr'] = summary['total_spend'] / summary['total_retainers']
    else:
        summary['avg_cpr'] = 0
    
    if summary['total_in_practice'] > 0:
        summary['conversion_rate'] = summary['total_retainers'] / summary['total_in_practice']
    else:
        summary['conversion_rate'] = 0
    
    return summary

@app.route('/api/comparison-data')
def api_comparison_data():
    """Get comparison data between two periods"""
    # Initialize managers if needed
    if not ads_manager.client:
        ads_manager.initialize()
    if not litify_manager.client:
        litify_manager.initialize()
    
    # Get parameters
    period = request.args.get('period', 'mtd')
    custom_start = request.args.get('custom_start')
    custom_end = request.args.get('custom_end')
    
    # Get exclusion filter parameters
    include_spam = request.args.get('include_spam', 'false').lower() == 'true'
    include_abandoned = request.args.get('include_abandoned', 'false').lower() == 'true'
    include_duplicate = request.args.get('include_duplicate', 'false').lower() == 'true'
    
    # Calculate date ranges
    if period == 'custom' and custom_start and custom_end:
        current_start = custom_start
        current_end = custom_end
    else:
        today = datetime.now().date()
        if period == 'today':
            current_start = current_end = today.strftime('%Y-%m-%d')
        elif period == 'yesterday':
            yesterday = today - timedelta(days=1)
            current_start = current_end = yesterday.strftime('%Y-%m-%d')
        elif period == 'week':
            week_start = today - timedelta(days=today.weekday())
            current_start = week_start.strftime('%Y-%m-%d')
            current_end = today.strftime('%Y-%m-%d')
        elif period == 'month':
            current_start = date(today.year, today.month, 1).strftime('%Y-%m-%d')
            current_end = today.strftime('%Y-%m-%d')
        else:  # mtd
            current_start = date(today.year, today.month, 1).strftime('%Y-%m-%d')
            current_end = today.strftime('%Y-%m-%d')
    
    compare_start, compare_end = calculate_comparison_dates(
        period, custom_start, custom_end
    )
    
    # Fetch data for both periods
    current_data = fetch_period_data(current_start, current_end, include_spam, include_abandoned, include_duplicate)
    compare_data = fetch_period_data(compare_start, compare_end, include_spam, include_abandoned, include_duplicate)
    
    # Calculate changes
    changes = {}
    metrics = ['total_spend', 'total_leads', 'total_cases', 'total_retainers', 'avg_cpl', 'avg_cpa', 'avg_cpr', 'conversion_rate']
    
    for metric in metrics:
        current_val = current_data.get(metric, 0)
        compare_val = compare_data.get(metric, 0)
        
        if compare_val > 0:
            change_pct = ((current_val - compare_val) / compare_val) * 100
        else:
            change_pct = 100 if current_val > 0 else 0
        
        changes[metric] = {
            'current': current_val,
            'previous': compare_val,
            'change': current_val - compare_val,
            'change_percent': round(change_pct, 1)
        }
    
    return jsonify({
        'current_period': {
            'start': current_start,
            'end': current_end,
            'data': current_data
        },
        'comparison_period': {
            'start': compare_start,
            'end': compare_end,
            'data': compare_data
        },
        'changes': changes,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/annual-data')
def api_annual_data():
    """Get annual data with monthly breakdown"""
    try:
        # Initialize managers if needed
        if not ads_manager.client:
            ads_manager.initialize()
        if not litify_manager.client:
            litify_manager.initialize()
        
        # Get exclusion filter parameters
        include_spam = request.args.get('include_spam', 'false').lower() == 'true'
        include_abandoned = request.args.get('include_abandoned', 'false').lower() == 'true'
        include_duplicate = request.args.get('include_duplicate', 'false').lower() == 'true'
        
        # Get current year or specified year
        year = request.args.get('year', datetime.now().year, type=int)
        current_date = datetime.now()
        current_month = current_date.month if year == current_date.year else 12
        
        monthly_data = []
        annual_summary = {
            'total_spend': 0,
            'total_leads': 0,
            'total_retainers': 0,
            'total_cases': 0,
            'total_in_practice': 0,
            'total_unqualified': 0,
            'avg_cpl': 0,
            'avg_cpa': 0,
            'avg_cpr': 0,
            'avg_conversion_rate': 0
        }
        
        # Process each month
        for month_num in range(1, current_month + 1):
            month_date = datetime(year, month_num, 1)
            month_name = month_date.strftime('%B')
            is_current = (month_num == current_month and year == current_date.year)
            
            # Skip future months
            if month_date > current_date:
                monthly_data.append({
                    'month': month_name,
                    'month_num': month_num,
                    'is_current': False,
                    'is_future': True,
                    'summary': {
                        'spend': 0,
                        'leads': 0,
                        'retainers': 0,
                        'cases': 0,
                        'in_practice': 0,
                        'unqualified': 0,
                        'cpl': 0,
                        'cpa': 0,
                        'cpr': 0,
                        'conversion_rate': 0
                    }
                })
                continue
            
            # Calculate date range for the month
            if month_num == 12:
                next_month_date = datetime(year + 1, 1, 1)
            else:
                next_month_date = datetime(year, month_num + 1, 1)
            
            start_date = month_date.strftime('%Y-%m-%d')
            end_date = (next_month_date - timedelta(days=1)).strftime('%Y-%m-%d')
            
            # For current month, end at today
            if is_current:
                end_date = current_date.strftime('%Y-%m-%d')
            
            # Fetch data for this month
            campaigns = None
            litify_leads = []
            
            # Fetch Google Ads campaigns - INCLUDING ALL CAMPAIGNS (not just active)
            if ads_manager.connected:
                campaigns = ads_manager.fetch_campaigns(start_date, end_date, active_only=False)
                if campaigns:
                    logger.info(f"Fetched {len(campaigns)} campaigns for {month_name} {year} (ALL statuses)")
            
            # Fetch Litify leads
            if litify_manager.connected:
                litify_leads = litify_manager.fetch_detailed_leads(
                    start_date, end_date, limit=2000,
                    include_spam=include_spam,
                    include_abandoned=include_abandoned,
                    include_duplicate=include_duplicate
                )
                if litify_leads:
                    logger.info(f"Fetched {len(litify_leads)} Litify leads for {month_name} {year}")
            
            # Process data for this month
            if campaigns or litify_leads:
                campaigns_to_process = campaigns if campaigns else []
                buckets, _, _, excluded_counts = process_campaigns_to_buckets_with_litify(
                    campaigns_to_process, litify_leads
                )
                
                # Calculate month summary
                month_summary = {
                    'spend': sum(b['cost'] for b in buckets),
                    'leads': sum(b['leads'] for b in buckets),
                    'cases': sum(b['cases'] for b in buckets),
                    'retainers': sum(b['retainers'] for b in buckets),
                    'in_practice': sum(b['inPractice'] for b in buckets),
                    'unqualified': sum(b['unqualified'] for b in buckets),
                    'cpl': 0,
                    'cpa': 0,
                    'cpr': 0,
                    'conversion_rate': 0
                }
            else:
                # Use demo data from module if no real data available
                month_summary = demo_data.get_demo_monthly_summary()
            
            # Calculate metrics
            if month_summary['leads'] > 0:
                month_summary['cpl'] = round(month_summary['spend'] / month_summary['leads'], 2)
            if month_summary['cases'] > 0:
                month_summary['cpa'] = round(month_summary['spend'] / month_summary['cases'], 2)
            if month_summary['retainers'] > 0:
                month_summary['cpr'] = round(month_summary['spend'] / month_summary['retainers'], 2)
            if month_summary['in_practice'] > 0:
                month_summary['conversion_rate'] = round(month_summary['retainers'] / month_summary['in_practice'], 3)
            
            # Add to annual totals
            annual_summary['total_spend'] += month_summary['spend']
            annual_summary['total_leads'] += month_summary['leads']
            annual_summary['total_retainers'] += month_summary['retainers']
            annual_summary['total_cases'] += month_summary['cases']
            annual_summary['total_in_practice'] += month_summary['in_practice']
            annual_summary['total_unqualified'] += month_summary['unqualified']
            
            monthly_data.append({
                'month': month_name,
                'month_num': month_num,
                'is_current': is_current,
                'is_future': False,
                'summary': month_summary,
                'buckets': buckets if campaigns or litify_leads else []
            })
        
        # Calculate annual averages
        if annual_summary['total_leads'] > 0:
            annual_summary['avg_cpl'] = round(annual_summary['total_spend'] / annual_summary['total_leads'], 2)
        if annual_summary['total_cases'] > 0:
            annual_summary['avg_cpa'] = round(annual_summary['total_spend'] / annual_summary['total_cases'], 2)
        if annual_summary['total_retainers'] > 0:
            annual_summary['avg_cpr'] = round(annual_summary['total_spend'] / annual_summary['total_retainers'], 2)
        if annual_summary['total_in_practice'] > 0:
            annual_summary['avg_conversion_rate'] = round(annual_summary['total_retainers'] / annual_summary['total_in_practice'], 3)
        
        # Filter for past months only (excluding current month)
        past_months = [m for m in monthly_data if not m['is_current'] and not m['is_future']]
        
        # Add performance analysis
        performance_analysis = {}
        
        if past_months:
            # Best CPL month
            best_cpl = min(past_months, key=lambda x: x['summary']['cpl'] if x['summary']['cpl'] > 0 else float('inf'))
            performance_analysis['best_cpl_month'] = best_cpl
            
            # Best conversion month
            best_conv = max(past_months, key=lambda x: x['summary']['conversion_rate'])
            performance_analysis['best_conversion_month'] = best_conv
            
            # Highest volume month
            highest_vol = max(past_months, key=lambda x: x['summary']['leads'])
            performance_analysis['highest_volume_month'] = highest_vol
            
            # Worst conversion month (needs attention)
            worst_conv = min(past_months, key=lambda x: x['summary']['conversion_rate'])
            performance_analysis['worst_conversion_month'] = worst_conv
            
            # Add monthly averages
            num_valid_months = max(1, len(past_months))
            performance_analysis['avg_monthly_spend'] = annual_summary['total_spend'] / num_valid_months
            performance_analysis['avg_monthly_leads'] = annual_summary['total_leads'] / num_valid_months
            performance_analysis['avg_monthly_retainers'] = annual_summary['total_retainers'] / num_valid_months
        
        # Check if we're connected to real APIs
        data_source = 'Demo Data'
        if ads_manager.connected and litify_manager.connected:
            data_source = 'Live Data (All Campaigns)'
        elif ads_manager.connected:
            data_source = 'Partial Data (Google Ads - All Campaigns)'
        elif litify_manager.connected:
            data_source = 'Partial Data (Litify)'
        
        return jsonify({
            'monthly_data': monthly_data,
            'annual_summary': annual_summary,
            'performance_analysis': performance_analysis,
            'data_source': data_source
        })
        
    except Exception as e:
        app.logger.error(f"Error in annual data API: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/debug/campaigns-dump')
def debug_campaigns_dump():
    """
    Debug route to dump ALL Google Ads campaigns (enabled and disabled) 
    with their CIDs to a JSON file for easier LSA mapping
    """
    try:
        # Initialize manager if needed
        if not ads_manager.client:
            ads_manager.initialize()
        
        if not ads_manager.connected:
            return jsonify({
                'success': False,
                'error': 'Google Ads API not connected',
                'details': ads_manager.error
            }), 503
        
        # Fetch ALL campaigns (both enabled and disabled)
        logger.info("🔍 Starting debug campaign dump - fetching ALL campaigns...")
        
        # Get customer ID
        customer_id = os.getenv('GOOGLE_ADS_CUSTOMER_ID', '2419159990').replace('-', '')
        ga_service = ads_manager.client.get_service("GoogleAdsService")
        
        # Query to get detailed campaign information including CID
        query = """
            SELECT
                campaign.id,
                campaign.name,
                campaign.status,
                campaign.advertising_channel_type,
                campaign.advertising_channel_sub_type,
                customer.id,
                customer.descriptive_name,
                metrics.cost_micros,
                metrics.clicks,
                metrics.impressions,
                metrics.conversions
            FROM campaign
            WHERE segments.date DURING LAST_30_DAYS
            ORDER BY campaign.id
        """
        
        response = ga_service.search_stream(customer_id=customer_id, query=query)
        
        # Process campaigns with detailed information
        campaigns_data = {}
        lsa_campaigns = []
        total_count = 0
        
        for batch in response:
            for row in batch.results:
                campaign_id = str(row.campaign.id)
                campaign_name = row.campaign.name
                
                # Check if it's an LSA campaign
                is_lsa = ("LocalServicesCampaign" in campaign_name or 
                         "LSA" in campaign_name.upper() or
                         row.campaign.advertising_channel_type.name == "LOCAL_SERVICES")
                
                campaign_info = {
                    'campaign_id': campaign_id,
                    'campaign_name': campaign_name,
                    'status': row.campaign.status.name,
                    'channel_type': row.campaign.advertising_channel_type.name if hasattr(row.campaign, 'advertising_channel_type') else 'UNKNOWN',
                    'channel_sub_type': row.campaign.advertising_channel_sub_type.name if hasattr(row.campaign, 'advertising_channel_sub_type') else 'UNKNOWN',
                    'customer_id': str(row.customer.id) if hasattr(row.customer, 'id') else customer_id,
                    'is_lsa': is_lsa,
                    'metrics_30_days': {
                        'cost': float(row.metrics.cost_micros / 1_000_000) if row.metrics.cost_micros else 0,
                        'clicks': int(row.metrics.clicks),
                        'impressions': int(row.metrics.impressions),
                        'conversions': float(row.metrics.conversions or 0)
                    }
                }
                
                # Add to appropriate collections
                if campaign_id not in campaigns_data:
                    campaigns_data[campaign_id] = campaign_info
                    total_count += 1
                    
                    if is_lsa:
                        lsa_campaigns.append(campaign_info)
                else:
                    # Update metrics if we've seen this campaign before (aggregating daily data)
                    campaigns_data[campaign_id]['metrics_30_days']['cost'] += campaign_info['metrics_30_days']['cost']
                    campaigns_data[campaign_id]['metrics_30_days']['clicks'] += campaign_info['metrics_30_days']['clicks']
                    campaigns_data[campaign_id]['metrics_30_days']['impressions'] += campaign_info['metrics_30_days']['impressions']
                    campaigns_data[campaign_id]['metrics_30_days']['conversions'] += campaign_info['metrics_30_days']['conversions']
        
        # Organize data by state/region for LSAs
        lsa_by_region = {
            'CA': [],
            'AZ': [],
            'GA': [],
            'TX': [],
            'Unknown': []
        }
        
        for lsa in lsa_campaigns:
            name = lsa['campaign_name']
            matched = False
            
            # Try to identify state from campaign name
            for state in ['CA', 'AZ', 'GA', 'TX']:
                if f":{state}" in name or f"-{state}-" in name or f" {state} " in name:
                    lsa_by_region[state].append(lsa)
                    matched = True
                    break
            
            # Additional pattern matching
            if not matched:
                if any(x in name.upper() for x in ['CALIFORNIA', 'CALIF', 'LOS ANGELES', 'SAN FRANCISCO', 'NEWPORT']):
                    lsa_by_region['CA'].append(lsa)
                elif any(x in name.upper() for x in ['ARIZONA', 'PHOENIX']):
                    lsa_by_region['AZ'].append(lsa)
                elif any(x in name.upper() for x in ['GEORGIA', 'ATLANTA', 'ROSWELL']):
                    lsa_by_region['GA'].append(lsa)
                elif any(x in name.upper() for x in ['TEXAS', 'HOUSTON', 'DALLAS']):
                    lsa_by_region['TX'].append(lsa)
                else:
                    lsa_by_region['Unknown'].append(lsa)
        
        # Create organized output
        output_data = {
            'generated_at': datetime.now().isoformat(),
            'customer_id': customer_id,
            'total_campaigns': total_count,
            'total_lsa_campaigns': len(lsa_campaigns),
            'summary': {
                'enabled_campaigns': sum(1 for c in campaigns_data.values() if c['status'] == 'ENABLED'),
                'paused_campaigns': sum(1 for c in campaigns_data.values() if c['status'] == 'PAUSED'),
                'removed_campaigns': sum(1 for c in campaigns_data.values() if c['status'] == 'REMOVED'),
                'total_30_day_spend': sum(c['metrics_30_days']['cost'] for c in campaigns_data.values())
            },
            'lsa_campaigns_by_region': lsa_by_region,
            'all_campaigns': list(campaigns_data.values()),
            'campaign_name_to_id_mapping': {
                c['campaign_name']: c['campaign_id'] 
                for c in campaigns_data.values()
            }
        }
        
        # Save to JSON file
        filename = f"campaign_dump_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(os.getcwd(), filename)
        
        with open(filepath, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        logger.info(f"✅ Campaign dump saved to {filepath}")
        logger.info(f"📊 Found {total_count} total campaigns, {len(lsa_campaigns)} LSA campaigns")
        
        # Also save a simplified LSA mapping file for easier reference
        lsa_mapping_file = f"lsa_mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        lsa_mapping_path = os.path.join(os.getcwd(), lsa_mapping_file)
        
        lsa_mapping_data = {
            'generated_at': datetime.now().isoformat(),
            'lsa_campaigns': [
                {
                    'name': c['campaign_name'],
                    'id': c['campaign_id'],
                    'status': c['status'],
                    'region': next((k for k, v in lsa_by_region.items() if c in v), 'Unknown')
                }
                for c in lsa_campaigns
            ],
            'suggested_mapping': {
                'California LSA': [c['campaign_name'] for c in lsa_by_region['CA']],
                'Arizona LSA': [c['campaign_name'] for c in lsa_by_region['AZ']],
                'Georgia LSA': [c['campaign_name'] for c in lsa_by_region['GA']],
                'Texas LSA': [c['campaign_name'] for c in lsa_by_region['TX']],
                'Unmapped LSA': [c['campaign_name'] for c in lsa_by_region['Unknown']]
            }
        }
        
        with open(lsa_mapping_path, 'w') as f:
            json.dump(lsa_mapping_data, f, indent=2)
        
        logger.info(f"✅ LSA mapping saved to {lsa_mapping_path}")
        
        return jsonify({
            'success': True,
            'message': f'Campaign dump successful! Found {total_count} campaigns total, {len(lsa_campaigns)} LSA campaigns',
            'files_created': [filename, lsa_mapping_file],
            'summary': {
                'total_campaigns': total_count,
                'lsa_campaigns': len(lsa_campaigns),
                'enabled': output_data['summary']['enabled_campaigns'],
                'paused': output_data['summary']['paused_campaigns'],
                'removed': output_data['summary']['removed_campaigns']
            },
            'lsa_by_region': {k: len(v) for k, v in lsa_by_region.items()},
            'preview': {
                'sample_lsa': lsa_campaigns[:3] if lsa_campaigns else [],
                'sample_regular': [c for c in list(campaigns_data.values())[:3] if not c['is_lsa']]
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Error in debug campaign dump: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

# Add these routes to your app.py file after the other routes

@app.route('/current-month-performance')
def current_month_performance_page():
    """Serve the current month performance dashboard HTML"""
    return render_template('current-month-performance.html')

@app.route('/api/current-month-daily')
def api_current_month_daily():
    """
    Get daily performance data for the current month with day-over-day deltas
    Including bucket-level breakdown for each day
    """
    try:
        # Initialize managers if needed
        if not ads_manager.client:
            ads_manager.initialize()
        if not litify_manager.client:
            litify_manager.initialize()
        
        # Get exclusion filter parameters
        include_spam = request.args.get('include_spam', 'false').lower() == 'true'
        include_abandoned = request.args.get('include_abandoned', 'false').lower() == 'true'
        include_duplicate = request.args.get('include_duplicate', 'false').lower() == 'true'
        
        # Get current month date range
        now = datetime.now()
        month_start = date(now.year, now.month, 1)
        month_end = date(now.year, now.month, calendar.monthrange(now.year, now.month)[1])
        today = now.date()
        
        # Initialize daily data structure
        daily_data = []
        previous_day_data = None
        previous_buckets_data = {}  # Store previous day bucket data for deltas
        
        # Month totals for summary
        month_totals = {
            'total_spend': 0,
            'total_leads': 0,
            'total_cases': 0,
            'total_retainers': 0,
            'total_in_practice': 0,
            'total_unqualified': 0
        }
        
        # Best/worst tracking
        best_days = {
            'highest_leads': None,
            'best_conversion': None,
            'lowest_cpl': None
        }
        worst_days = {
            'highest_cpl': None,
            'lowest_conversion': None,
            'inefficient': None
        }
        
        # Get list of available buckets from the campaign mapping
        available_buckets = list(BUCKET_PRIORITY)
        
        # Process each day of the month
        for day_num in range(1, month_end.day + 1):
            current_date = date(now.year, now.month, day_num)
            date_str = current_date.strftime('%Y-%m-%d')
            
            # Skip future dates
            if current_date > today:
                daily_data.append({
                    'date': date_str,
                    'dayNum': day_num,
                    'dayName': current_date.strftime('%a'),
                    'isToday': False,
                    'isFuture': True,
                    'isWeekend': current_date.weekday() >= 5,
                    'spend': 0,
                    'leads': 0,
                    'inPractice': 0,
                    'unqualified': 0,
                    'cases': 0,
                    'retainers': 0,
                    'cpl': 0,
                    'cpa': 0,
                    'cpr': 0,
                    'convRate': 0,
                    'buckets': [],  # Empty buckets for future dates
                    # All deltas are null for future dates
                    'spendDelta': None,
                    'leadsDelta': None,
                    'inPracticeDelta': None,
                    'unqualifiedDelta': None,
                    'casesDelta': None,
                    'retainersDelta': None,
                    'cplDelta': None,
                    'cpaDelta': None,
                    'cprDelta': None,
                    'convDelta': None
                })
                continue
            
            # Fetch data for this specific day
            campaigns = None
            litify_leads = []
            
            # Fetch Google Ads campaigns for this day
            if ads_manager.connected:
                campaigns = ads_manager.fetch_campaigns(date_str, date_str, active_only=False)
                if campaigns:
                    logger.info(f"Fetched {len(campaigns)} campaigns for {date_str}")
            
            # Fetch Litify leads for this day
            if litify_manager.connected:
                litify_leads = litify_manager.fetch_detailed_leads(
                    date_str, date_str, limit=500,
                    include_spam=include_spam,
                    include_abandoned=include_abandoned,
                    include_duplicate=include_duplicate
                )
                if litify_leads:
                    logger.info(f"Fetched {len(litify_leads)} Litify leads for {date_str}")
            
            # Process data for this day and get bucket breakdown
            if campaigns or litify_leads:
                campaigns_to_process = campaigns if campaigns else []
                buckets, _, _, _ = process_campaigns_to_buckets_with_litify(
                    campaigns_to_process, litify_leads
                )
                
                # Calculate day totals
                day_data = {
                    'spend': sum(b['cost'] for b in buckets),
                    'leads': sum(b['leads'] for b in buckets),
                    'inPractice': sum(b['inPractice'] for b in buckets),
                    'unqualified': sum(b['unqualified'] for b in buckets),
                    'cases': sum(b['cases'] for b in buckets),
                    'retainers': sum(b['retainers'] for b in buckets)
                }
                
                # Process each bucket for this day
                day_buckets = []
                for bucket in buckets:
                    bucket_name = bucket['name']
                    
                    # Calculate bucket metrics
                    bucket_metrics = {
                        'name': bucket_name,
                        'spend': bucket['cost'],
                        'leads': bucket['leads'],
                        'inPractice': bucket['inPractice'],
                        'unqualified': bucket['unqualified'],
                        'cases': bucket['cases'],
                        'retainers': bucket['retainers'],
                        'cpl': bucket['costPerLead'] if bucket.get('costPerLead') else 0,
                        'cpa': bucket['cpa'] if bucket.get('cpa') else 0,
                        'cpr': bucket['costPerRetainer'] if bucket.get('costPerRetainer') else 0,
                        'convRate': bucket['conversionRate'] if bucket.get('conversionRate') else 0
                    }
                    
                    # Calculate bucket deltas if we have previous day data
                    if bucket_name in previous_buckets_data:
                        prev_bucket = previous_buckets_data[bucket_name]
                        
                        # Spend delta (absolute dollar amount)
                        bucket_metrics['spendDelta'] = bucket_metrics['spend'] - prev_bucket['spend']
                        
                        # Other deltas
                        bucket_metrics['leadsDelta'] = bucket_metrics['leads'] - prev_bucket['leads']
                        bucket_metrics['inPracticeDelta'] = bucket_metrics['inPractice'] - prev_bucket['inPractice']
                        bucket_metrics['casesDelta'] = bucket_metrics['cases'] - prev_bucket['cases']
                        bucket_metrics['retainersDelta'] = bucket_metrics['retainers'] - prev_bucket['retainers']
                        
                        # CPL delta
                        if prev_bucket['cpl'] > 0:
                            bucket_metrics['cplDelta'] = round(((bucket_metrics['cpl'] - prev_bucket['cpl']) / prev_bucket['cpl']) * 100, 1)
                        else:
                            bucket_metrics['cplDelta'] = 0
                        
                        # Conversion rate delta
                        bucket_metrics['convDelta'] = round((bucket_metrics['convRate'] - prev_bucket['convRate']) * 100, 1)
                    else:
                        # First day of month - no deltas
                        bucket_metrics['spendDelta'] = 0
                        bucket_metrics['leadsDelta'] = 0
                        bucket_metrics['inPracticeDelta'] = 0
                        bucket_metrics['casesDelta'] = 0
                        bucket_metrics['retainersDelta'] = 0
                        bucket_metrics['cplDelta'] = 0
                        bucket_metrics['convDelta'] = 0
                    
                    day_buckets.append(bucket_metrics)
                    
                    # Update previous buckets data for next iteration
                    previous_buckets_data[bucket_name] = bucket_metrics
                
                day_data['buckets'] = day_buckets
            else:
                # Use demo data or zeros
                day_data = {
                    'spend': random.randint(20000, 50000) if not ads_manager.connected else 0,
                    'leads': random.randint(15, 40) if not litify_manager.connected else 0,
                    'inPractice': random.randint(12, 35) if not litify_manager.connected else 0,
                    'unqualified': random.randint(2, 8) if not litify_manager.connected else 0,
                    'cases': random.randint(3, 10) if not litify_manager.connected else 0,
                    'retainers': random.randint(4, 12) if not litify_manager.connected else 0,
                    'buckets': []  # No bucket data for demo
                }
            
            # Calculate metrics
            if day_data['leads'] > 0:
                day_data['cpl'] = round(day_data['spend'] / day_data['leads'], 2)
            else:
                day_data['cpl'] = 0
            
            if day_data['cases'] > 0:
                day_data['cpa'] = round(day_data['spend'] / day_data['cases'], 2)
            else:
                day_data['cpa'] = 0
            
            if day_data['retainers'] > 0:
                day_data['cpr'] = round(day_data['spend'] / day_data['retainers'], 2)
            else:
                day_data['cpr'] = 0
            
            if day_data['inPractice'] > 0:
                day_data['convRate'] = round(day_data['retainers'] / day_data['inPractice'], 3)
            else:
                day_data['convRate'] = 0
            
            # Calculate deltas (day-over-day changes)
            if previous_day_data:
                # Spend delta 
                day_data['spendDelta'] = day_data['spend'] - previous_day_data['spend']
                
                # Leads delta (absolute)
                day_data['leadsDelta'] = day_data['leads'] - previous_day_data['leads']
                
                # In Practice delta (absolute)
                day_data['inPracticeDelta'] = day_data['inPractice'] - previous_day_data['inPractice']
                
                # Unqualified delta (absolute)
                day_data['unqualifiedDelta'] = day_data['unqualified'] - previous_day_data['unqualified']
                
                # Cases delta (absolute)
                day_data['casesDelta'] = day_data['cases'] - previous_day_data['cases']
                
                # Retainers delta (absolute)
                day_data['retainersDelta'] = day_data['retainers'] - previous_day_data['retainers']
                
                # CPL delta (percentage)
                if previous_day_data['cpl'] > 0:
                    day_data['cplDelta'] = round(((day_data['cpl'] - previous_day_data['cpl']) / previous_day_data['cpl']) * 100, 1)
                else:
                    day_data['cplDelta'] = 0
                
                # CPA delta (percentage)
                if previous_day_data['cpa'] > 0:
                    day_data['cpaDelta'] = round(((day_data['cpa'] - previous_day_data['cpa']) / previous_day_data['cpa']) * 100, 1)
                else:
                    day_data['cpaDelta'] = 0
                
                # CPR delta (percentage)
                if previous_day_data['cpr'] > 0:
                    day_data['cprDelta'] = round(((day_data['cpr'] - previous_day_data['cpr']) / previous_day_data['cpr']) * 100, 1)
                else:
                    day_data['cprDelta'] = 0
                
                # Conversion rate delta (percentage points)
                day_data['convDelta'] = round((day_data['convRate'] - previous_day_data['convRate']) * 100, 1)
            else:
                # First day of month - no previous day to compare
                day_data['spendDelta'] = 0
                day_data['leadsDelta'] = 0
                day_data['inPracticeDelta'] = 0
                day_data['unqualifiedDelta'] = 0
                day_data['casesDelta'] = 0
                day_data['retainersDelta'] = 0
                day_data['cplDelta'] = 0
                day_data['cpaDelta'] = 0
                day_data['cprDelta'] = 0
                day_data['convDelta'] = 0
            
            # Add metadata
            day_data['date'] = date_str
            day_data['dayNum'] = day_num
            day_data['dayName'] = current_date.strftime('%a')
            day_data['isToday'] = current_date == today
            day_data['isFuture'] = False
            day_data['isWeekend'] = current_date.weekday() >= 5
            
            # Update month totals
            month_totals['total_spend'] += day_data['spend']
            month_totals['total_leads'] += day_data['leads']
            month_totals['total_cases'] += day_data['cases']
            month_totals['total_retainers'] += day_data['retainers']
            month_totals['total_in_practice'] += day_data['inPractice']
            month_totals['total_unqualified'] += day_data['unqualified']
            
            # Track best/worst days (only for past days with data)
            if day_data['leads'] > 0:
                # Best days
                if not best_days['highest_leads'] or day_data['leads'] > best_days['highest_leads']['leads']:
                    best_days['highest_leads'] = {
                        'date': current_date.strftime('%b %d'),
                        'leads': day_data['leads']
                    }
                
                if not best_days['best_conversion'] or day_data['convRate'] > best_days['best_conversion']['convRate']:
                    best_days['best_conversion'] = {
                        'date': current_date.strftime('%b %d'),
                        'convRate': day_data['convRate']
                    }
                
                if day_data['cpl'] > 0 and (not best_days['lowest_cpl'] or day_data['cpl'] < best_days['lowest_cpl']['cpl']):
                    best_days['lowest_cpl'] = {
                        'date': current_date.strftime('%b %d'),
                        'cpl': day_data['cpl']
                    }
                
                # Worst days
                if day_data['cpl'] > 0 and (not worst_days['highest_cpl'] or day_data['cpl'] > worst_days['highest_cpl']['cpl']):
                    worst_days['highest_cpl'] = {
                        'date': current_date.strftime('%b %d'),
                        'cpl': day_data['cpl']
                    }
                
                if not worst_days['lowest_conversion'] or day_data['convRate'] < worst_days['lowest_conversion']['convRate']:
                    worst_days['lowest_conversion'] = {
                        'date': current_date.strftime('%b %d'),
                        'convRate': day_data['convRate']
                    }
                
                # Inefficient day (high spend, low retainers)
                efficiency_score = day_data['retainers'] / (day_data['spend'] / 10000) if day_data['spend'] > 0 else 0
                if not worst_days['inefficient'] or efficiency_score < worst_days['inefficient'].get('efficiency', float('inf')):
                    worst_days['inefficient'] = {
                        'date': current_date.strftime('%b %d'),
                        'spend': day_data['spend'],
                        'retainers': day_data['retainers'],
                        'efficiency': efficiency_score
                    }
            
            # Add to daily data list
            daily_data.append(day_data)
            
            # Store for next iteration's delta calculation
            previous_day_data = day_data
        
        # Calculate month summary with today's deltas
        days_elapsed = min(today.day, month_end.day)
        today_data = daily_data[today.day - 1] if today.day <= len(daily_data) else None
        yesterday_data = daily_data[today.day - 2] if today.day > 1 and today.day - 2 < len(daily_data) else None
        
        month_summary = {
            'totalSpend': month_totals['total_spend'],
            'totalLeads': month_totals['total_leads'],
            'totalCases': month_totals['total_cases'],
            'totalRetainers': month_totals['total_retainers'],
            'avgCPL': round(month_totals['total_spend'] / month_totals['total_leads'], 2) if month_totals['total_leads'] > 0 else 0,
            'avgCPA': round(month_totals['total_spend'] / month_totals['total_cases'], 2) if month_totals['total_cases'] > 0 else 0,
            'avgCPR': round(month_totals['total_spend'] / month_totals['total_retainers'], 2) if month_totals['total_retainers'] > 0 else 0,
            'convRate': round(month_totals['total_retainers'] / month_totals['total_in_practice'], 3) if month_totals['total_in_practice'] > 0 else 0,
            'dailyAvgSpend': round(month_totals['total_spend'] / days_elapsed, 2) if days_elapsed > 0 else 0,
            'dailyAvgLeads': round(month_totals['total_leads'] / days_elapsed, 1) if days_elapsed > 0 else 0,
            # Today's deltas
            'spendDelta': today_data['spendDelta'] if today_data else 0,
            'leadsDelta': today_data['leadsDelta'] if today_data else 0,
            'casesDelta': today_data['casesDelta'] if today_data else 0,
            'retainersDelta': today_data['retainersDelta'] if today_data else 0,
            'cplDelta': today_data['cplDelta'] if today_data else 0,
            'cpaDelta': today_data['cpaDelta'] if today_data else 0,
            'convDelta': today_data['convDelta'] if today_data else 0
        }
        
        # Check data source
        data_source = 'Demo Data'
        if ads_manager.connected and litify_manager.connected:
            data_source = 'Live Data'
        elif ads_manager.connected:
            data_source = 'Partial Data (Google Ads)'
        elif litify_manager.connected:
            data_source = 'Partial Data (Litify)'
        
        return jsonify({
            'daily_data': daily_data,
            'month_summary': month_summary,
            'best_days': best_days,
            'worst_days': worst_days,
            'available_buckets': available_buckets,  # Include available buckets for filtering
            'data_source': data_source,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in current month daily API: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Add this endpoint to your app.py - it fetches day by day with progress updates
@app.route('/api/current-month-daily-optimized')
def api_current_month_daily_optimized():
    """
    Accurate day-by-day fetching with real-time progress updates
    Shows exactly which date is being processed
    """
    try:
        import calendar
        from datetime import datetime, date, timedelta
        
        # Initialize managers if needed
        if not ads_manager.client:
            ads_manager.initialize()
        if not litify_manager.client:
            litify_manager.initialize()
        
        # Get exclusion filter parameters
        include_spam = request.args.get('include_spam', 'false').lower() == 'true'
        include_abandoned = request.args.get('include_abandoned', 'false').lower() == 'true'
        include_duplicate = request.args.get('include_duplicate', 'false').lower() == 'true'
        
        # Get current month date range
        now = datetime.now()
        month_start = date(now.year, now.month, 1)
        month_end = date(now.year, now.month, calendar.monthrange(now.year, now.month)[1])
        today = now.date()
        
        logger.info(f"🚀 Starting ACCURATE day-by-day fetch for {month_start} to {today}")
        
        # Initialize daily data structure
        daily_data = []
        previous_day_data = None
        previous_buckets_data = {}
        
        # Month totals for summary
        month_totals = {
            'total_spend': 0,
            'total_leads': 0,
            'total_cases': 0,
            'total_retainers': 0,
            'total_in_practice': 0,
            'total_unqualified': 0
        }
        
        # Best/worst tracking
        best_days = {
            'highest_leads': None,
            'best_conversion': None,
            'lowest_cpl': None
        }
        worst_days = {
            'highest_cpl': None,
            'lowest_conversion': None,
            'inefficient': None
        }
        
        # Get available buckets
        available_buckets = list(BUCKET_PRIORITY)
        
        # ====================
        # FETCH DATA DAY BY DAY WITH PROGRESS
        # ====================
        total_days = today.day
        
        for day_num in range(1, month_end.day + 1):
            current_date = date(now.year, now.month, day_num)
            date_str = current_date.strftime('%Y-%m-%d')
            
            # Skip future dates
            if current_date > today:
                daily_data.append({
                    'date': date_str,
                    'dayNum': day_num,
                    'dayName': current_date.strftime('%a'),
                    'isToday': False,
                    'isFuture': True,
                    'isWeekend': current_date.weekday() >= 5,
                    'spend': 0,
                    'leads': 0,
                    'inPractice': 0,
                    'unqualified': 0,
                    'cases': 0,
                    'retainers': 0,
                    'cpl': 0,
                    'cpa': 0,
                    'cpr': 0,
                    'convRate': 0,
                    'buckets': [],
                    'spendDelta': None,
                    'leadsDelta': None,
                    'casesDelta': None,
                    'retainersDelta': None,
                    'cplDelta': None,
                    'cpaDelta': None,
                    'cprDelta': None,
                    'convDelta': None
                })
                continue
            
            # Log progress for this day
            progress_pct = round((day_num / total_days) * 100)
            logger.info(f"📅 Processing {date_str} ({day_num}/{total_days} - {progress_pct}%)")
            
            # Fetch data for this specific day
            campaigns = None
            litify_leads = []
            
            # Fetch Google Ads campaigns for this day
            if ads_manager.connected:
                campaigns = ads_manager.fetch_campaigns(date_str, date_str, active_only=False)
                if campaigns:
                    logger.info(f"  ✓ Fetched {len(campaigns)} campaigns for {date_str}")
            
            # Fetch Litify leads for this day
            if litify_manager.connected:
                litify_leads = litify_manager.fetch_detailed_leads(
                    date_str, date_str, limit=500,
                    include_spam=include_spam,
                    include_abandoned=include_abandoned,
                    include_duplicate=include_duplicate
                )
                if litify_leads:
                    logger.info(f"  ✓ Fetched {len(litify_leads)} Litify leads for {date_str}")
            
            # Process data for this day and get bucket breakdown
            if campaigns or litify_leads:
                campaigns_to_process = campaigns if campaigns else []
                buckets, _, _, _ = process_campaigns_to_buckets_with_litify(
                    campaigns_to_process, litify_leads
                )
                
                # Calculate day totals
                day_data = {
                    'date': date_str,
                    'dayNum': day_num,
                    'dayName': current_date.strftime('%a'),
                    'isToday': current_date == today,
                    'isFuture': False,
                    'isWeekend': current_date.weekday() >= 5,
                    'spend': sum(b['cost'] for b in buckets),
                    'leads': sum(b['leads'] for b in buckets),
                    'inPractice': sum(b['inPractice'] for b in buckets),
                    'unqualified': sum(b['unqualified'] for b in buckets),
                    'cases': sum(b['cases'] for b in buckets),
                    'retainers': sum(b['retainers'] for b in buckets),
                    'buckets': []
                }
                
                # Calculate metrics
                if day_data['leads'] > 0:
                    day_data['cpl'] = round(day_data['spend'] / day_data['leads'], 2)
                else:
                    day_data['cpl'] = 0
                
                if day_data['cases'] > 0:
                    day_data['cpa'] = round(day_data['spend'] / day_data['cases'], 2)
                else:
                    day_data['cpa'] = 0
                
                if day_data['retainers'] > 0:
                    day_data['cpr'] = round(day_data['spend'] / day_data['retainers'], 2)
                else:
                    day_data['cpr'] = 0
                
                if day_data['inPractice'] > 0:
                    day_data['convRate'] = round(
                        (day_data['retainers'] / day_data['inPractice']) * 100, 1
                    )
                else:
                    day_data['convRate'] = 0
                
                # Process each bucket for this day
                for bucket in buckets:
                    bucket_name = bucket['name']
                    
                    # Calculate bucket metrics
                    bucket_metrics = {
                        'name': bucket_name,
                        'spend': bucket['cost'],
                        'leads': bucket['leads'],
                        'inPractice': bucket['inPractice'],
                        'unqualified': bucket['unqualified'],
                        'cases': bucket['cases'],
                        'retainers': bucket['retainers'],
                        'cpl': bucket.get('costPerLead', 0),
                        'cpa': bucket.get('cpa', 0),
                        'cpr': bucket.get('costPerRetainer', 0),
                        'convRate': round(
                            (bucket['retainers'] / bucket['inPractice'] * 100) 
                            if bucket['inPractice'] > 0 else 0, 1
                        )
                    }
                    
                    # Calculate bucket deltas
                    prev_bucket = previous_buckets_data.get(bucket_name)
                    if prev_bucket:
                        if prev_bucket['spend'] > 0:
                            bucket_metrics['spendDelta'] = round(
                                ((bucket_metrics['spend'] - prev_bucket['spend']) / 
                                 prev_bucket['spend'] * 100), 1
                            )
                        else:
                            bucket_metrics['spendDelta'] = 0
                        bucket_metrics['leadsDelta'] = bucket_metrics['leads'] - prev_bucket['leads']
                    else:
                        bucket_metrics['spendDelta'] = None
                        bucket_metrics['leadsDelta'] = None
                    
                    day_data['buckets'].append(bucket_metrics)
                    previous_buckets_data[bucket_name] = bucket_metrics
                
                # Calculate deltas vs previous day
                if previous_day_data:
                    if previous_day_data['spend'] > 0:
                        day_data['spendDelta'] = round(
                            ((day_data['spend'] - previous_day_data['spend']) / 
                             previous_day_data['spend'] * 100), 1
                        )
                    else:
                        day_data['spendDelta'] = 0
                    
                    day_data['leadsDelta'] = day_data['leads'] - previous_day_data['leads']
                    day_data['casesDelta'] = day_data['cases'] - previous_day_data['cases']
                    day_data['retainersDelta'] = day_data['retainers'] - previous_day_data['retainers']
                    
                    if previous_day_data['cpl'] > 0:
                        day_data['cplDelta'] = round(
                            ((day_data['cpl'] - previous_day_data['cpl']) / 
                             previous_day_data['cpl'] * 100), 1
                        )
                    else:
                        day_data['cplDelta'] = 0
                    
                    if previous_day_data['cpa'] > 0:
                        day_data['cpaDelta'] = round(
                            ((day_data['cpa'] - previous_day_data['cpa']) / 
                             previous_day_data['cpa'] * 100), 1
                        )
                    else:
                        day_data['cpaDelta'] = 0
                    
                    if previous_day_data['cpr'] > 0:
                        day_data['cprDelta'] = round(
                            ((day_data['cpr'] - previous_day_data['cpr']) / 
                             previous_day_data['cpr'] * 100), 1
                        )
                    else:
                        day_data['cprDelta'] = 0
                    
                    day_data['convDelta'] = round(
                        day_data['convRate'] - previous_day_data['convRate'], 1
                    )
                else:
                    # First day - no deltas
                    day_data['spendDelta'] = None
                    day_data['leadsDelta'] = None
                    day_data['casesDelta'] = None
                    day_data['retainersDelta'] = None
                    day_data['cplDelta'] = None
                    day_data['cpaDelta'] = None
                    day_data['cprDelta'] = None
                    day_data['convDelta'] = None
                
                # Update month totals
                month_totals['total_spend'] += day_data['spend']
                month_totals['total_leads'] += day_data['leads']
                month_totals['total_cases'] += day_data['cases']
                month_totals['total_retainers'] += day_data['retainers']
                month_totals['total_in_practice'] += day_data['inPractice']
                month_totals['total_unqualified'] += day_data['unqualified']
                
                # Track best/worst days
                if day_data['leads'] > 0:
                    if not best_days['highest_leads'] or day_data['leads'] > best_days['highest_leads']['leads']:
                        best_days['highest_leads'] = {
                            'date': date_str,
                            'leads': day_data['leads'],
                            'spend': day_data['spend']
                        }
                    
                    if day_data['cpl'] > 0:
                        if not best_days['lowest_cpl'] or day_data['cpl'] < best_days['lowest_cpl']['cpl']:
                            best_days['lowest_cpl'] = {
                                'date': date_str,
                                'cpl': day_data['cpl'],
                                'leads': day_data['leads']
                            }
                        
                        if not worst_days['highest_cpl'] or day_data['cpl'] > worst_days['highest_cpl']['cpl']:
                            worst_days['highest_cpl'] = {
                                'date': date_str,
                                'cpl': day_data['cpl'],
                                'leads': day_data['leads']
                            }
                
                if day_data['convRate'] > 0:
                    if not best_days['best_conversion'] or day_data['convRate'] > best_days['best_conversion']['convRate']:
                        best_days['best_conversion'] = {
                            'date': date_str,
                            'convRate': day_data['convRate'],
                            'retainers': day_data['retainers']
                        }
                
                if day_data['inPractice'] > 0:  # Only count days with in-practice leads
                    if not worst_days['lowest_conversion'] or day_data['convRate'] < worst_days['lowest_conversion']['convRate']:
                        worst_days['lowest_conversion'] = {
                            'date': date_str,
                            'convRate': day_data['convRate'],
                            'retainers': day_data['retainers']
                        }
                
                # Track inefficient days (high spend, low retainers)
                if day_data['spend'] > 0:
                    efficiency = day_data['retainers'] / (day_data['spend'] / 10000)
                    if not worst_days['inefficient'] or efficiency < worst_days['inefficient']['efficiency']:
                        worst_days['inefficient'] = {
                            'date': date_str,
                            'spend': day_data['spend'],
                            'retainers': day_data['retainers'],
                            'efficiency': efficiency
                        }
            else:
                # No data for this day
                day_data = {
                    'date': date_str,
                    'dayNum': day_num,
                    'dayName': current_date.strftime('%a'),
                    'isToday': current_date == today,
                    'isFuture': False,
                    'isWeekend': current_date.weekday() >= 5,
                    'spend': 0,
                    'leads': 0,
                    'inPractice': 0,
                    'unqualified': 0,
                    'cases': 0,
                    'retainers': 0,
                    'cpl': 0,
                    'cpa': 0,
                    'cpr': 0,
                    'convRate': 0,
                    'buckets': [],
                    'spendDelta': None,
                    'leadsDelta': None,
                    'casesDelta': None,
                    'retainersDelta': None,
                    'cplDelta': None,
                    'cpaDelta': None,
                    'cprDelta': None,
                    'convDelta': None
                }
            
            # Add to daily data list
            daily_data.append(day_data)
            
            # Store for next iteration's delta calculation
            previous_day_data = day_data
            
            logger.info(f"  💰 Day total: ${day_data['spend']:,.2f} spend, {day_data['leads']} leads")
        
        # Calculate month summary with today's deltas
        days_elapsed = min(today.day, month_end.day)
        today_data = daily_data[today.day - 1] if today.day <= len(daily_data) else None
        
        month_summary = {
            'totalSpend': month_totals['total_spend'],
            'totalLeads': month_totals['total_leads'],
            'totalCases': month_totals['total_cases'],
            'totalRetainers': month_totals['total_retainers'],
            'avgCPL': round(month_totals['total_spend'] / month_totals['total_leads'], 2) if month_totals['total_leads'] > 0 else 0,
            'avgCPA': round(month_totals['total_spend'] / month_totals['total_cases'], 2) if month_totals['total_cases'] > 0 else 0,
            'avgCPR': round(month_totals['total_spend'] / month_totals['total_retainers'], 2) if month_totals['total_retainers'] > 0 else 0,
            'convRate': round(month_totals['total_retainers'] / month_totals['total_in_practice'], 3) if month_totals['total_in_practice'] > 0 else 0,
            'dailyAvgSpend': round(month_totals['total_spend'] / days_elapsed, 2) if days_elapsed > 0 else 0,
            'dailyAvgLeads': round(month_totals['total_leads'] / days_elapsed, 1) if days_elapsed > 0 else 0,
            # Today's deltas
            'spendDelta': today_data['spendDelta'] if today_data else 0,
            'leadsDelta': today_data['leadsDelta'] if today_data else 0,
            'casesDelta': today_data['casesDelta'] if today_data else 0,
            'retainersDelta': today_data['retainersDelta'] if today_data else 0,
            'cplDelta': today_data['cplDelta'] if today_data else 0,
            'cpaDelta': today_data['cpaDelta'] if today_data else 0,
            'convDelta': today_data['convDelta'] if today_data else 0
        }
        
        # Check data source
        data_source = 'Demo Data'
        if ads_manager.connected and litify_manager.connected:
            data_source = 'Live Data (Accurate)'
        elif ads_manager.connected:
            data_source = 'Partial Data (Google Ads)'
        elif litify_manager.connected:
            data_source = 'Partial Data (Litify)'
        
        logger.info(f"✅ ACCURATE day-by-day fetch complete!")
        logger.info(f"   Total days processed: {today.day}")
        logger.info(f"   Month totals: ${month_totals['total_spend']:,.2f} spend, {month_totals['total_leads']} leads")
        
        return jsonify({
            'daily_data': daily_data,
            'month_summary': month_summary,
            'best_days': best_days,
            'worst_days': worst_days,
            'available_buckets': available_buckets,
            'data_source': data_source,
            'accuracy': 'HIGH',  # This is accurate day-by-day data
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in accurate current month daily API: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/lsa-discovery')
def debug_lsa_discovery():
    """
    Debug route to discover all LSA campaigns across all accounts
    """
    try:
        # Initialize manager if needed
        if not ads_manager.client:
            ads_manager.initialize()
        
        if not ads_manager.connected:
            return jsonify({
                'success': False,
                'error': 'Google Ads API not connected',
                'details': ads_manager.error
            }), 503
        
        logger.info("🔍 Starting LSA discovery across all accounts...")
        
        # Get date range for last 30 days
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # Fetch all campaigns including LSA
        campaigns = ads_manager.fetch_campaigns(start_date, end_date, active_only=False)
        
        if not campaigns:
            return jsonify({
                'success': False,
                'error': 'No campaigns found',
                'customer_ids_checked': ads_manager.customer_ids
            }), 404
        
        # Filter for LSA campaigns
        lsa_campaigns = [c for c in campaigns if c.get('channel_type') == 'LOCAL_SERVICES' or 
                         'LocalServicesCampaign' in c.get('name', '')]
        
        # Organize LSA by region
        lsa_by_region = {
            'CA': [],
            'AZ': [],
            'GA': [],
            'TX': [],
            'Unknown': []
        }
        
        # State name mapping
        state_names = {
            'CA': 'California',
            'AZ': 'Arizona', 
            'GA': 'Georgia',
            'TX': 'Texas'
        }
        
        for campaign in lsa_campaigns:
            name = campaign.get('name', '')
            state = ads_manager.get_state_from_campaign_name(name)
            
            if state and state in lsa_by_region:
                lsa_by_region[state].append(campaign)
            else:
                lsa_by_region['Unknown'].append(campaign)
        
        # Prepare output
        output = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'accounts_checked': ads_manager.customer_ids,
            'is_mcc': ads_manager.is_mcc,
            'summary': {
                'total_campaigns': len(campaigns),
                'total_lsa_campaigns': len(lsa_campaigns),
                'total_lsa_cost': sum(c.get('cost', 0) for c in lsa_campaigns),
                'regular_campaigns': len(campaigns) - len(lsa_campaigns)
            },
            'lsa_by_region': {},
            'all_lsa_campaigns': [],
            'recommendations': []
        }
        
        # Add regional summaries
        for region, region_campaigns in lsa_by_region.items():
            if region_campaigns:
                output['lsa_by_region'][region] = {
                    'name': state_names.get(region, region),
                    'count': len(region_campaigns),
                    'total_spend': sum(c.get('cost', 0) for c in region_campaigns),
                    'campaigns': [
                        {
                            'name': c.get('name', ''),
                            'customer_id': c.get('customer_id', ''),
                            'spend': c.get('cost', 0),
                            'conversions': c.get('conversions', 0),
                            'status': c.get('status', '')
                        }
                        for c in region_campaigns
                    ]
                }
        
        # Add all LSA campaigns list
        output['all_lsa_campaigns'] = [
            {
                'name': c.get('name', ''),
                'customer_id': c.get('customer_id', ''),
                'customer_name': c.get('customer_name', 'Unknown'),
                'spend': c.get('cost', 0),
                'conversions': c.get('conversions', 0),
                'status': c.get('status', ''),
                'region': ads_manager.get_state_from_campaign_name(c.get('name', ''))
            }
            for c in lsa_campaigns
        ]
        
        # Add recommendations
        if not lsa_campaigns:
            output['recommendations'].append(
                "No LSA campaigns found. Check if you have access to all necessary Google Ads accounts."
            )
        
        if not ads_manager.is_mcc and len(ads_manager.customer_ids) == 1:
            output['recommendations'].append(
                "Currently using single account. Consider adding more account IDs or using an MCC for complete coverage."
            )
        
        # Check for missing regions
        missing_regions = []
        for region in ['CA', 'AZ', 'GA', 'TX']:
            if not lsa_by_region[region]:
                missing_regions.append(state_names[region])
        
        if missing_regions:
            output['recommendations'].append(
                f"No LSA campaigns found for: {', '.join(missing_regions)}. Check if separate accounts exist for these regions."
            )
        
        if lsa_by_region['Unknown']:
            output['recommendations'].append(
                f"Found {len(lsa_by_region['Unknown'])} LSA campaigns that couldn't be mapped to a region. "
                "Consider updating campaign names to include state codes."
            )
        
        # Create suggested campaign mapping
        suggested_mapping = {}
        for region, region_campaigns in lsa_by_region.items():
            if region != 'Unknown' and region_campaigns:
                bucket_name = state_names.get(region, region) + " LSA"
                suggested_mapping[bucket_name] = list(set([c.get('name', '') for c in region_campaigns]))
        
        output['suggested_campaign_mapping'] = suggested_mapping
        
        # Save to file
        filename = f"lsa_discovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(os.getcwd(), filename)
        
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"✅ LSA discovery complete. Found {len(lsa_campaigns)} LSA campaigns")
        logger.info(f"📁 Report saved to {filename}")
        
        output['file_saved'] = filename
        
        return jsonify(output)
        
    except Exception as e:
        logger.error(f"Error in LSA discovery: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/debug/lsa-spend-check')
def debug_lsa_spend_check():
    """
    Debug route to check if LSA campaigns are being fetched and processed correctly
    """
    try:
        # Force refresh cache first
        global CACHE_DATA, CACHE_TIME
        CACHE_DATA = None
        CACHE_TIME = None
        
        # Initialize if needed
        if not ads_manager.client:
            ads_manager.initialize()
        
        if not ads_manager.connected:
            return jsonify({
                'success': False,
                'error': 'Google Ads API not connected'
            }), 503
        
        # Get today's date for testing
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Fetch campaigns for today (or last 7 days for more data)
        end_date = today
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        logger.info(f"🔍 Checking LSA spend from {start_date} to {end_date}")
        
        # Fetch ALL campaigns including LSA
        campaigns = ads_manager.fetch_campaigns(start_date, end_date, active_only=False)
        
        if not campaigns:
            return jsonify({
                'success': False,
                'error': 'No campaigns found',
                'date_range': {'start': start_date, 'end': end_date}
            }), 404
        
        # Separate LSA and regular campaigns
        lsa_campaigns = []
        regular_campaigns = []
        
        for campaign in campaigns:
            if campaign.get('is_lsa') or 'LocalServicesCampaign' in campaign.get('name', ''):
                lsa_campaigns.append(campaign)
            else:
                regular_campaigns.append(campaign)
        
        # Group LSA campaigns by customer_id
        lsa_by_account = {}
        for campaign in lsa_campaigns:
            customer_id = campaign.get('customer_id', 'unknown')
            if customer_id not in lsa_by_account:
                lsa_by_account[customer_id] = {
                    'campaigns': [],
                    'total_spend': 0,
                    'customer_name': campaign.get('customer_name', 'Unknown')
                }
            lsa_by_account[customer_id]['campaigns'].append({
                'name': campaign.get('name', ''),
                'spend': campaign.get('cost', 0),
                'status': campaign.get('status', '')
            })
            lsa_by_account[customer_id]['total_spend'] += campaign.get('cost', 0)
        
        # Map LSA campaigns to buckets using the processing function
        test_leads = []  # Empty leads for this test
        buckets, unmapped, _, _ = process_campaigns_to_buckets_with_litify(campaigns, test_leads)
        
        # Extract LSA bucket data
        lsa_buckets_data = {}
        for bucket in buckets:
            if 'LSA' in bucket.get('name', ''):
                lsa_buckets_data[bucket['name']] = {
                    'campaigns': bucket.get('campaigns', []),
                    'spend': bucket.get('cost', 0),
                    'campaign_count': len(bucket.get('campaigns', []))
                }
        
        # Create diagnostic output
        output = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'date_range': {
                'start': start_date,
                'end': end_date
            },
            'summary': {
                'total_campaigns': len(campaigns),
                'lsa_campaigns': len(lsa_campaigns),
                'regular_campaigns': len(regular_campaigns),
                'total_lsa_spend': sum(c.get('cost', 0) for c in lsa_campaigns),
                'total_regular_spend': sum(c.get('cost', 0) for c in regular_campaigns),
                'accounts_checked': ads_manager.customer_ids
            },
            'lsa_by_account': lsa_by_account,
            'lsa_buckets': lsa_buckets_data,
            'unmapped_lsa': [c.get('name', '') for c in unmapped if 'LocalServicesCampaign' in c],
            'sample_lsa_campaigns': [
                {
                    'name': c.get('name', ''),
                    'customer_id': c.get('customer_id', ''),
                    'customer_name': c.get('customer_name', ''),
                    'spend': c.get('cost', 0),
                    'status': c.get('status', '')
                }
                for c in lsa_campaigns[:5]  # First 5 LSA campaigns
            ]
        }
        
        # Log the findings
        logger.info(f"✅ LSA Spend Check Complete:")
        logger.info(f"   - Found {len(lsa_campaigns)} LSA campaigns")
        logger.info(f"   - Total LSA spend: ${output['summary']['total_lsa_spend']:,.2f}")
        logger.info(f"   - LSA accounts: {len(lsa_by_account)}")
        
        for bucket_name, data in lsa_buckets_data.items():
            logger.info(f"   - {bucket_name}: ${data['spend']:,.2f} ({data['campaign_count']} campaigns)")
        
        return jsonify(output)
        
    except Exception as e:
        logger.error(f"Error in LSA spend check: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/debug/bucket-check')
def debug_bucket_check():
    """
    Check what's actually in CAMPAIGN_BUCKETS and how LSA campaigns are being processed
    """
    try:
        # Force reload campaign mappings from file
        load_campaign_mappings()
        
        # Check what's in CAMPAIGN_BUCKETS
        lsa_buckets = {}
        for bucket_name, campaigns in CAMPAIGN_BUCKETS.items():
            if 'LSA' in bucket_name:
                lsa_buckets[bucket_name] = campaigns
        
        # Fetch current campaigns to test processing
        if ads_manager.connected:
            today = datetime.now().strftime('%Y-%m-%d')
            week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            campaigns = ads_manager.fetch_campaigns(week_ago, today, active_only=False)
        else:
            campaigns = []
        
        # Find LSA campaigns in fetched data
        fetched_lsa = []
        for campaign in campaigns:
            if campaign.get('is_lsa') or 'LocalServicesCampaign' in campaign.get('name', ''):
                fetched_lsa.append({
                    'name': campaign.get('name', ''),
                    'customer_id': campaign.get('customer_id', ''),
                    'customer_name': campaign.get('customer_name', ''),
                    'cost': campaign.get('cost', 0)
                })
        
        # Test the processing function with empty leads
        test_buckets, unmapped, _, _ = process_campaigns_to_buckets_with_litify(campaigns, [])
        
        # Extract processed LSA bucket data
        processed_lsa_buckets = {}
        for bucket in test_buckets:
            if 'LSA' in bucket.get('name', ''):
                processed_lsa_buckets[bucket['name']] = {
                    'campaigns': bucket.get('campaigns', []),
                    'cost': bucket.get('cost', 0),
                    'count': len(bucket.get('campaigns', []))
                }
        
        return jsonify({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'diagnostics': {
                'campaign_buckets_file': 'campaign_mappings.json exists' if os.path.exists('campaign_mappings.json') else 'NOT FOUND',
                'lsa_buckets_in_memory': lsa_buckets,
                'lsa_campaigns_fetched': fetched_lsa,
                'lsa_buckets_after_processing': processed_lsa_buckets,
                'bucket_priority_includes_lsa': [b for b in BUCKET_PRIORITY if 'LSA' in b],
                'unmapped_lsa': [c for c in unmapped if 'LocalServicesCampaign' in c]
            },
            'recommendations': []
        })
        
    except Exception as e:
        logger.error(f"Error in bucket check: {str(e)}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/fix-lsa-mapping', methods=['POST'])
def fix_lsa_mapping():
    """
    Fix LSA mapping by ensuring all LSA campaigns are in CAMPAIGN_BUCKETS
    """
    try:
        global CAMPAIGN_BUCKETS, CACHE_DATA, CACHE_TIME
        
        # Clear cache
        CACHE_DATA = None
        CACHE_TIME = None
        
        # Load current mappings
        if os.path.exists('campaign_mappings.json'):
            with open('campaign_mappings.json', 'r') as f:
                CAMPAIGN_BUCKETS = json.load(f)
        
        # Ensure LSA buckets exist and have the correct campaigns
        lsa_campaign_names = {
            "California LSA": [
                "LocalServicesCampaign:SystemGenerated:0005d4f7245ee23e",  # LA
                "LocalServicesCampaign:SystemGenerated:0006052bb31f123b",  # Newport
                "LocalServicesCampaign:SystemGenerated:00063a39a1a7c234"   # Generic
            ],
            "Arizona LSA": [
                "LocalServicesCampaign:SystemGenerated:0005d4ed423a5b7b"
            ],
            "Georgia LSA": [
                "LocalServicesCampaign:SystemGenerated:0005d4ef00ed9a77",  # Atlanta
                "LocalServicesCampaign:SystemGenerated:0005d4fe17585d4f"   # Roswell
            ],
            "Texas LSA": []  # No Texas LSA campaigns found yet
        }
        
        # Update CAMPAIGN_BUCKETS with LSA campaigns
        updated = False
        for bucket_name, campaign_list in lsa_campaign_names.items():
            if bucket_name not in CAMPAIGN_BUCKETS:
                CAMPAIGN_BUCKETS[bucket_name] = campaign_list
                updated = True
                logger.info(f"Added new bucket: {bucket_name}")
            else:
                # Merge campaigns, avoiding duplicates
                existing = set(CAMPAIGN_BUCKETS[bucket_name])
                for campaign in campaign_list:
                    if campaign not in existing:
                        CAMPAIGN_BUCKETS[bucket_name].append(campaign)
                        updated = True
                        logger.info(f"Added {campaign} to {bucket_name}")
        
        # Ensure all LSA buckets are in BUCKET_PRIORITY
        for bucket in ["California LSA", "Arizona LSA", "Georgia LSA", "Texas LSA"]:
            if bucket not in BUCKET_PRIORITY:
                # Add after the corresponding Prospecting bucket
                state = bucket.replace(" LSA", "")
                prospecting_bucket = f"{state} Prospecting"
                if prospecting_bucket in BUCKET_PRIORITY:
                    idx = BUCKET_PRIORITY.index(prospecting_bucket)
                    BUCKET_PRIORITY.insert(idx + 1, bucket)
                else:
                    BUCKET_PRIORITY.append(bucket)
                logger.info(f"Added {bucket} to BUCKET_PRIORITY")
        
        # Save updated mappings
        if updated:
            with open('campaign_mappings.json', 'w') as f:
                json.dump(CAMPAIGN_BUCKETS, f, indent=2)
            logger.info("✅ Updated campaign_mappings.json with LSA campaigns")
        
        return jsonify({
            'success': True,
            'message': 'LSA mapping fixed and saved',
            'lsa_buckets': {k: v for k, v in CAMPAIGN_BUCKETS.items() if 'LSA' in k},
            'bucket_priority': BUCKET_PRIORITY,
            'cache_cleared': True
        })
        
    except Exception as e:
        logger.error(f"Error fixing LSA mapping: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/annual-analytics')
def annual_analytics_page():
    """Serve the annual analytics HTML"""
    return render_template('annual_analytics.html')

# ========== MAIN EXECUTION ==========

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("🚀 Starting Sweet James Dashboard with Exclusion Filters")
    logger.info("=" * 60)
    
    logger.info("Initializing API connections...")
    
    if ads_manager.initialize():
        logger.info("✅ Google Ads API connected")
    else:
        logger.warning(f"⚠️ Google Ads API not connected: {ads_manager.error}")
    
    if litify_manager.initialize():
        logger.info("✅ Litify API connected")
        logger.info(f"   Cached {len(litify_manager.case_type_cache)} case types")
        logger.info(f"   Salesforce instance: {litify_manager.instance_url}")
    else:
        logger.warning(f"⚠️ Litify API not connected: {litify_manager.error}")
    
    port = int(os.getenv('PORT', 9000))
    is_production = os.getenv('ENVIRONMENT', 'development').lower() == 'production'
    
    logger.info(f"📊 Dashboard: http://localhost:{port}")
    logger.info(f"🗺️ Campaign Mapping: http://localhost:{port}/campaign-mapping")
    logger.info(f"📈 Forecasting: http://localhost:{port}/forecasting")
    logger.info(f"📡 API Status: http://localhost:{port}/api/status")
    logger.info("=" * 60)
    logger.info("✅ FIELD NAME CORRECTIONS:")
    logger.info("  • Custom fields (NO litify_pm__ prefix):")
    logger.info("    - Retainer_Signed_Date__c")
    logger.info("    - UTM_Campaign__c")
    logger.info("    - Client_Name__c")
    logger.info("    - isDroppedatIntake__c")
    logger.info("  • Standard Litify fields (WITH litify_pm__ prefix):")
    logger.info("    - litify_pm__Status__c")
    logger.info("    - litify_pm__Display_Name__c")
    logger.info("    - litify_pm__Case_Type__c")
    logger.info("    - litify_pm__Matter__c")
    logger.info("=" * 60)
    logger.info("✅ CONVERSION CRITERIA:")
    logger.info("  • A retainer/conversion is counted when:")
    logger.info("    - Retainer Signed Date is not empty")
    logger.info("    - Status NOT 'Converted DAI' or 'Referred Out'")   
    logger.info("    - isDroppedatIntake = False")
    logger.info("    - Display Name != 'test'")
    logger.info("  • Unqualified = In practice but NOT converted")
    logger.info("  • Cases = Grouped by Matter ID (or companion ID, or solo)")
    logger.info("  • Retainers = Total converted intakes")
    logger.info("=" * 60)
    
    if is_production:
        # In production, use a proper WSGI server (gunicorn)
        logger.info("🚀 Production mode - use gunicorn or another WSGI server")
        logger.info("   Example: gunicorn --bind 0.0.0.0:$PORT app:app")
    else:
        # Development mode
        app.run(debug=True, host='0.0.0.0', port=port)