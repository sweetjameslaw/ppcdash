#!/usr/bin/env python3
"""
Sweet James Dashboard - Backend with Proper Campaign/Litify Integration and Forecasting
Updated: Refactored to use demo_data module for all demo/test data
TIMEZONE UPDATE: All queries now use Pacific Time (PT) for date ranges
"""

import os
import json
import logging
from datetime import datetime, timedelta, date, time
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import time as time_module
from collections import defaultdict
import calendar
import random
from urllib.parse import urlparse
import pytz  # Added for timezone support
import demo_data  # Import the demo data module
from performance_boost import optimize_app, global_cache, daily_cache, time_it, parallel_fetch

# Set Pacific Timezone
PACIFIC_TZ = pytz.timezone('America/Los_Angeles')

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

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'sweet-james-2025')
CORS(app)

# Helper function to get Pacific Time dates
def get_pacific_date_range(start_date_str=None, end_date_str=None):
    """
    Convert date strings to Pacific Time with proper start/end times
    Returns: (start_datetime_str, end_datetime_str) for API queries
    """
    if not start_date_str and not end_date_str:
        # Default to today in Pacific Time
        now_pt = datetime.now(PACIFIC_TZ)
        start_date_str = now_pt.strftime('%Y-%m-%d')
        end_date_str = start_date_str
    elif not end_date_str:
        end_date_str = datetime.now(PACIFIC_TZ).strftime('%Y-%m-%d')
    elif not start_date_str:
        start_date_str = end_date_str
    
    # Parse dates and set to Pacific Time
    # Start of day: 00:00:00 PT
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    start_dt_pt = PACIFIC_TZ.localize(datetime.combine(start_date.date(), time.min))
    
    # End of day: 23:59:59 PT
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    end_dt_pt = PACIFIC_TZ.localize(datetime.combine(end_date.date(), time.max))
    
    return start_dt_pt, end_dt_pt

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
CACHE_DURATION = 300  # 5 minutes in seconds

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
        logger.info("📋 Using default demo campaign mappings")

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
        logger.info("📋 Using default demo UTM mappings")

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
    
class GoogleAdsManager:
    """Enhanced Google Ads Manager with MCC and multi-account support"""
    
    def __init__(self):
        self.client = None
        self.connected = False
        self.error = None
        self.customer_ids = []  # Support multiple customer IDs
        self.is_mcc = False
        self.mcc_id = None
        self.child_accounts = {}  # Store child account info
        
    def initialize(self):
        """Initialize Google Ads connection with MCC support"""
        if not GOOGLE_ADS_AVAILABLE:
            self.error = "Google Ads library not installed"
            return False
            
        try:
            # Check for required credentials
            credentials_path = os.getenv('GOOGLE_ADS_CREDENTIALS_PATH', 'google-ads.yaml')
            
            # Check for MCC ID first
            mcc_id = os.getenv('GOOGLE_ADS_MCC_ID')
            
            # Support both single customer ID and comma-separated list
            customer_ids_env = os.getenv('GOOGLE_ADS_CUSTOMER_IDS', os.getenv('GOOGLE_ADS_CUSTOMER_ID', '2419159990'))
            
            # Parse customer IDs (support comma-separated list)
            if ',' in customer_ids_env:
                self.customer_ids = [cid.strip().replace('-', '') for cid in customer_ids_env.split(',')]
            else:
                self.customer_ids = [customer_ids_env.replace('-', '')]
            
            # If MCC ID is provided, use it
            if mcc_id:
                self.is_mcc = True
                self.mcc_id = mcc_id.replace('-', '')
                logger.info(f"🏢 Using MCC account: {self.mcc_id}")
            
            # Initialize Google Ads client
            if os.path.exists(credentials_path):
                # Load from file and potentially add login_customer_id
                self.client = GoogleAdsClient.load_from_storage(credentials_path)
                if self.is_mcc and hasattr(self.client, 'login_customer_id'):
                    self.client.login_customer_id = self.mcc_id
            else:
                # Try environment variables
                developer_token = os.getenv('GOOGLE_ADS_DEVELOPER_TOKEN')
                client_id = os.getenv('GOOGLE_ADS_CLIENT_ID')
                client_secret = os.getenv('GOOGLE_ADS_CLIENT_SECRET')
                refresh_token = os.getenv('GOOGLE_ADS_REFRESH_TOKEN')
                
                if not all([developer_token, client_id, client_secret, refresh_token]):
                    self.error = "Missing Google Ads credentials"
                    logger.warning(f"⚠️ {self.error}")
                    return False
                
                config = {
                    'developer_token': developer_token,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'refresh_token': refresh_token,
                    'use_proto_plus': True
                }
                
                # Add login_customer_id for MCC if available
                if self.is_mcc:
                    config['login_customer_id'] = self.mcc_id
                
                self.client = GoogleAdsClient.load_from_dict(config)
            
            # For backward compatibility, set customer_id to the first one
            self.customer_id = self.customer_ids[0] if self.customer_ids else None
            
            # If MCC, discover child accounts
            if self.is_mcc:
                self.discover_child_accounts()
            
            self.connected = True
            self.error = None
            logger.info(f"✅ Google Ads API initialized with {len(self.customer_ids)} account(s)")
            return True
            
        except Exception as e:
            self.error = str(e)
            self.connected = False
            logger.error(f"❌ Failed to initialize Google Ads API: {e}")
            return False
    
    def discover_child_accounts(self):
        """Discover all accessible child accounts under MCC"""
        if not self.client or not self.is_mcc:
            return
        
        try:
            ga_service = self.client.get_service("GoogleAdsService")
            
            # Query to get all accessible customers
            query = """
                SELECT
                    customer_client.id,
                    customer_client.descriptive_name,
                    customer_client.level,
                    customer_client.manager,
                    customer_client.status
                FROM customer_client
                WHERE customer_client.level <= 1
            """
            
            # Use MCC ID for the query
            response = ga_service.search_stream(customer_id=self.mcc_id, query=query)
            
            self.child_accounts = {}
            new_customer_ids = []
            
            for batch in response:
                for row in batch.results:
                    customer_id = str(row.customer_client.id)
                    # Only add non-manager, enabled accounts
                    if row.customer_client.status.name == 'ENABLED' and not row.customer_client.manager:
                        self.child_accounts[customer_id] = {
                            'name': row.customer_client.descriptive_name,
                            'level': row.customer_client.level
                        }
                        new_customer_ids.append(customer_id)
                        logger.info(f"  📂 Found child account: {row.customer_client.descriptive_name} ({customer_id})")
            
            # Add discovered accounts to our list
            for cid in new_customer_ids:
                if cid not in self.customer_ids:
                    self.customer_ids.append(cid)
            
            logger.info(f"✅ Discovered {len(self.child_accounts)} active child accounts")
            
        except Exception as e:
            logger.error(f"❌ Error discovering child accounts: {e}")
    
    def fetch_campaigns(self, start_date=None, end_date=None, active_only=True):
        """Fetch campaign performance data from Google Ads with Pacific Time support"""
        if not self.client or not self.connected:
            return None
        
        all_campaigns = []
        
        # Convert dates to Pacific Time
        if start_date or end_date:
            start_dt_pt, end_dt_pt = get_pacific_date_range(start_date, end_date)
            # Google Ads expects YYYY-MM-DD format
            start_date = start_dt_pt.strftime('%Y-%m-%d')
            end_date = end_dt_pt.strftime('%Y-%m-%d')
        else:
            # Default to today in Pacific Time
            now_pt = datetime.now(PACIFIC_TZ)
            start_date = end_date = now_pt.strftime('%Y-%m-%d')
        
        # Build date filter
        date_filter = f"AND segments.date BETWEEN '{start_date}' AND '{end_date}'"
        
        # Build status filter
        status_filter = "AND campaign.status = 'ENABLED'" if active_only else ""
        
        # Iterate through all customer IDs
        for customer_id in self.customer_ids:
            try:
                ga_service = self.client.get_service("GoogleAdsService")
                
                # Query for campaign performance including LSA
                query = f"""
                    SELECT
                        campaign.id,
                        campaign.name,
                        campaign.status,
                        campaign.advertising_channel_type,
                        customer.descriptive_name,
                        metrics.cost_micros,
                        metrics.clicks,
                        metrics.impressions,
                        metrics.conversions
                    FROM campaign
                    WHERE metrics.cost_micros >= 0
                    {status_filter}
                    {date_filter}
                    ORDER BY metrics.cost_micros DESC
                """
                
                response = ga_service.search_stream(customer_id=customer_id, query=query)
                
                account_campaigns = []
                for batch in response:
                    for row in batch.results:
                        campaign_data = {
                            'id': row.campaign.id,
                            'name': row.campaign.name,
                            'status': row.campaign.status.name,
                            'cost': row.metrics.cost_micros / 1_000_000,
                            'clicks': row.metrics.clicks,
                            'impressions': row.metrics.impressions,
                            'conversions': row.metrics.conversions,
                            'channel_type': row.campaign.advertising_channel_type.name if hasattr(row.campaign, 'advertising_channel_type') else 'UNKNOWN',
                            'customer_id': customer_id,
                            'customer_name': row.customer.descriptive_name if hasattr(row.customer, 'descriptive_name') else 'Unknown'
                        }
                        campaign_data['is_lsa'] = campaign_data['channel_type'] == 'LOCAL_SERVICES'
                        account_campaigns.append(campaign_data)
                        all_campaigns.append(campaign_data)
                
                if account_campaigns:
                    # Count LSA vs regular campaigns
                    lsa_count = sum(1 for c in account_campaigns if c.get('is_lsa'))
                    regular_count = len(account_campaigns) - lsa_count
                    
                    account_name = account_campaigns[0].get('customer_name', 'Unknown')
                    logger.info(f"  ✅ Account {customer_id} ({account_name}): {len(account_campaigns)} campaigns ({lsa_count} LSA, {regular_count} regular)")
                
            except Exception as e:
                logger.error(f"  ❌ Error fetching campaigns from {customer_id}: {e}")
                continue
        
        logger.info(f"✅ Total fetched: {len(all_campaigns)} campaigns from {len(self.customer_ids)} accounts")
        
        return all_campaigns
    
    def fetch_month_to_date_spend(self):
        """Fetch month-to-date spend by state with Pacific Time"""
        if not self.client or not self.connected:
            return None
            
        try:
            # Get current month date range in Pacific Time
            now_pt = datetime.now(PACIFIC_TZ)
            start_date = date(now_pt.year, now_pt.month, 1).strftime('%Y-%m-%d')
            end_date = now_pt.strftime('%Y-%m-%d')
            
            # Fetch campaigns for current month (including all accounts)
            campaigns = self.fetch_campaigns(start_date, end_date, active_only=False)
            
            if not campaigns:
                return None
            
            # Group spend by state
            state_spend = {
                "CA": 0,
                "AZ": 0,
                "GA": 0,
                "TX": 0
            }
            
            for campaign in campaigns:
                # Find bucket for this campaign
                campaign_name = campaign.get('name', '')
                bucket_name = None
                
                # Check CAMPAIGN_BUCKETS for this campaign
                for bucket, bucket_campaigns in CAMPAIGN_BUCKETS.items():
                    if campaign_name in bucket_campaigns:
                        bucket_name = bucket
                        break
                
                # Get state from bucket
                if bucket_name:
                    state = get_state_from_campaign_bucket(bucket_name)
                    if state and state in state_spend:
                        state_spend[state] += campaign.get('cost', 0)
            
            logger.info(f"✅ Fetched MTD spend by state: {state_spend}")
            return state_spend
            
        except Exception as e:
            self.error = str(e)
            logger.error(f"❌ Error fetching MTD spend: {e}")
            return None


class LitifyManager:
    """Manages Litify/Salesforce connections and data fetching"""
    
    def __init__(self):
        self.client = None
        self.connected = False
        self.error = None
        self.instance_url = None
        self.case_type_cache = set()
        
    def initialize(self):
        """Initialize Salesforce/Litify connection"""
        if not SALESFORCE_AVAILABLE:
            self.error = "Salesforce library not installed"
            return False
            
        try:
            # Check for required credentials
            username = os.getenv('LITIFY_USERNAME')
            password = os.getenv('LITIFY_PASSWORD')
            security_token = os.getenv('LITIFY_SECURITY_TOKEN')
            
            if not all([username, password, security_token]):
                self.error = "Missing Litify credentials"
                logger.warning(f"⚠️ {self.error}")
                return False
            
            # Initialize Salesforce client
            self.client = Salesforce(
                username=username,
                password=password,
                security_token=security_token,
                domain='login'  # Use 'test' for sandbox
            )
    
            self.instance_url = self.client.base_url.replace('/services/data/v61.0', '')
            
            self.connected = True
            self.error = None
            
            # Cache case types
            self._cache_case_types()
            
            logger.info(f"✅ Litify API initialized successfully")
            return True
            
        except Exception as e:
            self.error = str(e)
            self.connected = False
            logger.error(f"❌ Failed to initialize Litify API: {e}")
            return False
    
    def _cache_case_types(self):
        """Cache available case types from Litify"""
        if not self.client:
            return
            
        try:
            # Query for distinct case types
            query = """
                SELECT litify_pm__Case_Type__c 
                FROM litify_pm__Intake__c 
                WHERE litify_pm__Case_Type__c != null 
                GROUP BY litify_pm__Case_Type__c
            """
            
            result = self.client.query(query)
            
            for record in result['records']:
                case_type = record.get('litify_pm__Case_Type__c')
                if case_type:
                    self.case_type_cache.add(case_type)
            
            logger.info(f"✅ Cached {len(self.case_type_cache)} case types from Litify")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not cache case types: {e}")

    def fetch_detailed_leads(self, start_date=None, end_date=None, limit=10000, 
        include_spam=False, include_abandoned=False, include_duplicate=False,
        force_refresh=False, count_by_conversion_date=True):
        """Fetch detailed lead information from Litify with Pacific Time support"""
        if not self.client or not self.connected:
            return self.get_demo_litify_leads(include_spam, include_abandoned, include_duplicate)
            
        try:
            # Convert dates to Pacific Time
            start_dt_pt, end_dt_pt = get_pacific_date_range(start_date, end_date)
            
            # Convert Pacific Time to UTC for DATETIME fields
            start_dt_utc = start_dt_pt.astimezone(pytz.UTC)
            end_dt_utc = end_dt_pt.astimezone(pytz.UTC)
            
            # Format for queries
            date_format = start_dt_pt.strftime('%Y-%m-%d')  # For DATE fields
            end_date_format = end_dt_pt.strftime('%Y-%m-%d')  # For DATE fields
            datetime_start = start_dt_utc.strftime('%Y-%m-%dT%H:%M:%S.000Z')  # For DATETIME fields
            datetime_end = end_dt_utc.strftime('%Y-%m-%dT%H:%M:%S.999Z')  # For DATETIME fields
            
            # Query 1: Leads CREATED in date range (for lead counts)
            leads_query = f"""
                SELECT Id, Name, CreatedDate, 
                    litify_pm__Status__c,
                    litify_pm__Display_Name__c,
                    litify_pm__First_Name__c,
                    litify_pm__Last_Name__c,
                    Client_Name__c,
                    litify_pm__Case_Type__c,
                    litify_pm__Case_Type__r.Name,
                    Retainer_Signed_Date__c,
                    litify_pm__UTM_Campaign__c,
                    litify_pm__Matter__c,
                    litify_ext__Companion__c,
                    isDroppedatIntake__c
                FROM litify_pm__Intake__c
                WHERE litify_pm__UTM_Campaign__c != null
                AND CreatedDate >= {datetime_start}
                AND CreatedDate <= {datetime_end}
                ORDER BY CreatedDate DESC
                LIMIT {limit}
            """
            
            # Query 2: Leads CONVERTED in date range (for conversion metrics)
            conversions_query = f"""
                SELECT Id, Name, CreatedDate, 
                    litify_pm__Status__c,
                    litify_pm__Display_Name__c,
                    litify_pm__First_Name__c,
                    litify_pm__Last_Name__c,
                    Client_Name__c,
                    litify_pm__Case_Type__c,
                    litify_pm__Case_Type__r.Name,
                    Retainer_Signed_Date__c,
                    litify_pm__UTM_Campaign__c,
                    litify_pm__Matter__c,
                    litify_ext__Companion__c,
                    isDroppedatIntake__c
                FROM litify_pm__Intake__c
                WHERE litify_pm__UTM_Campaign__c != null
                AND Retainer_Signed_Date__c != null
                AND Retainer_Signed_Date__c >= {date_format}
                AND Retainer_Signed_Date__c <= {end_date_format}
                ORDER BY Retainer_Signed_Date__c DESC
                LIMIT {limit}
            """
            
            # Execute both queries with pagination
            created_leads = {}
            converted_leads = {}
            
            # Get leads created in period - USE query_all to handle pagination
            logger.info(f"Fetching leads CREATED between {start_dt_pt} and {end_dt_pt} PT...")
            created_records = self.client.query_all(leads_query)
            for record in created_records:
                created_leads[record['Id']] = record
            logger.info(f"   Found {len(created_leads)} leads created in period")
            
            # Get leads converted in period - USE query_all to handle pagination
            logger.info(f"Fetching leads CONVERTED between {date_format} and {end_date_format} PT...")
            converted_records = self.client.query_all(conversions_query)
            for record in converted_records:
                converted_leads[record['Id']] = record
            logger.info(f"   Found {len(converted_leads)} leads converted in period")
            
            # Merge the results intelligently
            all_records_dict = created_leads.copy()
            
            # Add conversions that weren't created in this period
            conversions_from_previous = 0
            for lead_id, lead_data in converted_leads.items():
                if lead_id not in all_records_dict:
                    # Mark this as a conversion from a previous period
                    lead_data['from_previous_period'] = True
                    all_records_dict[lead_id] = lead_data
                    conversions_from_previous += 1
            
            logger.info(f"   Including {conversions_from_previous} conversions from previous periods")
            
            all_records = list(all_records_dict.values())
            
            # Process leads
            leads = []
            utm_campaigns = set()
            excluded_count = 0
            
            for record in all_records:
                # Get UTM Campaign
                utm_campaign = record.get('litify_pm__UTM_Campaign__c', '')
                if utm_campaign:
                    utm_campaigns.add(utm_campaign)
                
                # Map UTM Campaign to bucket
                bucket = UTM_TO_BUCKET_MAPPING.get(utm_campaign, '')
                if not bucket and utm_campaign:
                    utm_lower = utm_campaign.lower()
                    for utm_key, bucket_name in UTM_TO_BUCKET_MAPPING.items():
                        if utm_key.lower() == utm_lower:
                            bucket = bucket_name
                            break
                
                # Get status
                status = record.get('litify_pm__Status__c', '')
                if not status:
                    status = 'Unknown'
                
                # Determine if converted
                is_converted = status in ['Signed', 'Retained', 'Retained - Converted']
                is_pending = status == 'Retainer Sent'
                
                # Get case type
                case_type = record.get('litify_pm__Case_Type__c', '')
                if not case_type:
                    case_type_obj = record.get('litify_pm__Case_Type__r')
                    if case_type_obj and isinstance(case_type_obj, dict):
                        case_type = case_type_obj.get('Name', '')
                
                # Check if this is an excluded case type
                is_excluded = case_type in ['Spam', 'Abandoned', 'Duplicate']
                
                # Apply exclusion filters
                if is_excluded:
                    excluded_count += 1
                    if case_type == 'Spam' and not include_spam:
                        continue
                    elif case_type == 'Abandoned' and not include_abandoned:
                        continue
                    elif case_type == 'Duplicate' and not include_duplicate:
                        continue
                
                # Determine in_practice
                in_practice = not is_excluded
                
                # Get companion info
                has_companion = bool(record.get('litify_ext__Companion__c'))
                is_dropped = record.get('isDroppedatIntake__c', False)
                
                # Get retainer signed date
                retainer_signed = record.get('Retainer_Signed_Date__c', '')
                
                # Get Salesforce URL
                instance_name = self.instance_url.split('//')[1].split('.')[0] if self.instance_url else 'sweetjames'
                salesforce_url = f"https://{instance_name}.lightning.force.com/lightning/r/litify_pm__Intake__c/{record.get('Id')}/view"
                
                # Format dates for display
                created_date_raw = record.get('CreatedDate', '')
                created_date_formatted = ''
                if created_date_raw:
                    try:
                        created_dt = datetime.fromisoformat(created_date_raw.replace('Z', '+00:00'))
                        created_dt_pt = created_dt.astimezone(PACIFIC_TZ)
                        created_date_formatted = created_dt_pt.strftime('%Y-%m-%d %I:%M %p PT')
                    except:
                        created_date_formatted = created_date_raw
                
                # Check if converted today
                converted_today = False
                if retainer_signed and retainer_signed == date_format:
                    converted_today = True
                
                # CRITICAL FIX: Determine if this lead should count for different metrics
                from_previous_period = record.get('from_previous_period', False)
                
                # A lead counts for leads metric if it was in the created_leads dictionary
                # (i.e., it was created in this period, not just converted in this period)
                was_created_in_period = record['Id'] in created_leads
                
                lead_data = {
                    'id': record.get('Id', ''),
                    'salesforce_url': salesforce_url,
                    'created_date': created_date_raw,
                    'created_date_formatted': created_date_formatted,
                    'conversion_date': retainer_signed or '',
                    'status': status,
                    'client_name': (
                        record.get('litify_pm__Display_Name__c', '') or
                        record.get('Client_Name__c', '') or
                        f"{record.get('litify_pm__First_Name__c', '')} {record.get('litify_pm__Last_Name__c', '')}".strip() or
                        record.get('Name', '') or
                        'Unknown'
                    ),
                    'is_converted': is_converted,
                    'converted_today': converted_today,
                    'is_pending': is_pending,
                    'case_type': case_type or 'Not Set',
                    'in_practice': in_practice,
                    'utm_campaign': utm_campaign or '-',
                    'bucket': bucket,
                    'is_excluded_type': is_excluded,
                    'has_companion': has_companion,
                    'matter_id': record.get('litify_pm__Matter__c', '') or '',
                    'companion_case_id': record.get('litify_ext__Companion__c', '') or '',
                    'is_dropped': is_dropped,
                    'retainer_signed_date': retainer_signed,
                    'from_previous_period': from_previous_period,
                    'count_for_leads': was_created_in_period,  # FIXED: Use was_created_in_period flag
                    'count_for_conversions': is_converted,
                    'is_new_today': was_created_in_period  # FIXED: Use was_created_in_period flag
                }
                
                leads.append(lead_data)
            
            logger.info(f"✅ Processed {len(leads)} total records")
            logger.info(f"   - {len([l for l in leads if l['count_for_leads']])} created in period")
            logger.info(f"   - {len([l for l in leads if l['from_previous_period']])} conversions from previous periods")
            logger.info(f"   - {excluded_count} excluded type leads")
            
            return leads
            
        except Exception as e:
            logger.error(f"❌ Litify query error: {e}")
            import traceback
            traceback.print_exc()
            return self.get_demo_litify_leads(include_spam, include_abandoned, include_duplicate)

    def fetch_month_to_date_metrics(self, include_spam=False, include_abandoned=False, include_duplicate=False):
        """Fetch month-to-date leads, cases, and retainers by state with Pacific Time"""
        if not self.client or not self.connected:
            return None
            
        try:
            # Get current month date range in Pacific Time
            now_pt = datetime.now(PACIFIC_TZ)
            start_date = date(now_pt.year, now_pt.month, 1)
            end_date = now_pt.date()
            
            # Fetch leads for current month
            leads = self.fetch_detailed_leads(
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d'),
                limit=5000,  # Higher limit for monthly data
                include_spam=include_spam,
                include_abandoned=include_abandoned,
                include_duplicate=include_duplicate
            )
            
            if not leads:
                return None
            
            # Initialize state metrics
            state_metrics = {
                "CA": {"leads": 0, "cases": 0, "retainers": 0},
                "AZ": {"leads": 0, "cases": 0, "retainers": 0},
                "GA": {"leads": 0, "cases": 0, "retainers": 0},
                "TX": {"leads": 0, "cases": 0, "retainers": 0}
            }
            
            # Use improved companion grouping for case counting
            case_assignments = build_companion_groups(leads)
            
            # Group cases by state
            cases_by_state = {
                "CA": set(),
                "AZ": set(),
                "GA": set(),
                "TX": set()
            }
            
            for lead in leads:
                # Determine state from bucket
                bucket = lead.get('bucket', '')
                state = get_state_from_campaign_bucket(bucket)
                
                if state and state in state_metrics:
                    # Count leads
                    state_metrics[state]["leads"] += 1
                    
                    # Count retainers (signed)
                    if lead.get('is_converted', False):
                        state_metrics[state]["retainers"] += 1
                        
                        # Track unique cases using improved grouping
                        lead_id = lead.get('id', '')
                        case_id = case_assignments.get(lead_id, f"unknown_{lead_id}")
                        cases_by_state[state].add(case_id)
            
            # Convert case sets to counts
            for state in state_metrics:
                state_metrics[state]["cases"] = len(cases_by_state[state])
            
            logger.info(f"✅ Fetched MTD metrics by state: {state_metrics}")
            return state_metrics
            
        except Exception as e:
            self.error = str(e)
            logger.error(f"❌ Error fetching MTD metrics: {e}")
            return None
    
    def get_demo_litify_leads(self, include_spam=False, include_abandoned=False, include_duplicate=False):
        """Return demo Litify leads data with bucket mapping and exclusion filters"""
        return demo_data.get_demo_litify_leads(
            UTM_TO_BUCKET_MAPPING, 
            include_spam, 
            include_abandoned, 
            include_duplicate
        )
    # Initialize managers
ads_manager = GoogleAdsManager()
litify_manager = LitifyManager()
optimize_app(app, ads_manager, litify_manager)

def get_demo_data(include_spam=False, include_abandoned=False, include_duplicate=False):
    """Wrapper function to maintain compatibility"""
    return demo_data.get_demo_bucket_data(include_spam, include_abandoned, include_duplicate)

def process_campaigns_to_buckets_with_litify(campaigns, litify_leads):
    """
    Process Google Ads campaigns and Litify leads to create bucketed data
    Uses CAMPAIGN_BUCKETS from campaign_mappings.json for ALL campaigns including LSA
    """
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
            cost = campaign.get('cost', 0)
            is_lsa = campaign.get('is_lsa', False) or 'LocalServicesCampaign' in campaign_name
            
            bucket_found = False
            
            # Check CAMPAIGN_BUCKETS for this campaign (works for both regular and LSA)
            for bucket_name, bucket_campaigns in CAMPAIGN_BUCKETS.items():
                if campaign_name in bucket_campaigns:
                    if bucket_name in bucketed_data:
                        bucketed_data[bucket_name]['campaigns'].append(campaign_name)
                        bucketed_data[bucket_name]['cost'] += cost
                        bucket_found = True
                        if is_lsa:
                            logger.info(f"✅ Mapped LSA campaign '{campaign_name}' to {bucket_name}")
                        break
            
            # If not found, add to unmapped
            if not bucket_found:
                unmapped_campaigns.append(campaign_name)
                if is_lsa:
                    logger.warning(f"⚠️ Unmapped LSA campaign: {campaign_name}")
                    logger.warning(f"   Consider adding to campaign_mappings.json")
    
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
    
    # Track unique cases per bucket
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
            # CRITICAL: Check if lead was created in this period
            # Don't use default True - be explicit
            count_for_leads = lead.get('count_for_leads', False)
            from_previous = lead.get('from_previous_period', False)
            
            # Only count in leads/in-practice if EXPLICITLY marked as created in period
            if count_for_leads and not from_previous:
                # Count as a lead
                bucketed_data[bucket_name]['leads'] += 1
                
                # Count in-practice if applicable
                if lead.get('in_practice', False):
                    bucketed_data[bucket_name]['inPractice'] += 1
                    
                    # Count unqualified (in-practice but not converted)
                    if not lead.get('is_converted', False):
                        bucketed_data[bucket_name]['unqualified'] += 1
            
            # SEPARATELY: Count ALL conversions regardless of creation date
            if lead.get('is_converted', False):
                bucketed_data[bucket_name]['retainers'] += 1
                
                # Track unique case
                lead_id = lead.get('id', '')
                case_id = case_assignments.get(lead_id, f"unknown_{lead_id}")
                cases_by_bucket[bucket_name].add(case_id)
            
            # Count pending retainers
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
        if data['leads'] > 0:
            data['inPracticePercent'] = round(data['inPractice'] / data['leads'], 3)
            data['costPerLead'] = round(data['cost'] / data['leads'], 2)
            data['conversionRate'] = round(data['cases'] / data['leads'], 3)
        else:
            data['inPracticePercent'] = 0
            data['costPerLead'] = 0
            data['conversionRate'] = 0
            
        if data['inPractice'] > 0:
            data['unqualifiedPercent'] = round(data['unqualified'] / data['inPractice'], 3)
        else:
            data['unqualifiedPercent'] = 0
        
        # Cost per case based on unique cases
        if data['cases'] > 0:
            data['cpa'] = round(data['cost'] / data['cases'], 2)
        else:
            data['cpa'] = 0
        
        # Cost per retainer based on signed retainers only
        if data['retainers'] > 0:
            data['costPerRetainer'] = round(data['cost'] / data['retainers'], 2)
        else:
            data['costPerRetainer'] = 0
    
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
                f"{total_unqualified} unqualified, {total_cases} cases, "
                f"{total_retainers} signed retainers, {total_pending} pending retainers")
    
    if lsa_count > 0:
        logger.info(f"🔍 LSA Campaigns: {lsa_count} campaigns, ${lsa_spend:,.2f} spend")
    
    logger.info(f"💰 Total Spend: ${total_cost:,.2f}")
    
    if excluded_counts['total'] > 0:
        logger.info(f"🚫 Excluded leads: {excluded_counts['total']} total "
                    f"(Spam: {excluded_counts['spam']}, Abandoned: {excluded_counts['abandoned']}, "
                    f"Duplicate: {excluded_counts['duplicate']})")
    
    if unmapped_campaigns:
        logger.warning(f"⚠️ Found {len(unmapped_campaigns)} unmapped campaigns")
        for camp in unmapped_campaigns[:5]:  # Show first 5
            logger.warning(f"   - {camp}")
    
    return list(bucketed_data.values()), unmapped_campaigns, unmapped_utm_campaigns, excluded_counts

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

@app.route('/current-month-performance')
def current_month_performance_page():
    """Serve the current month performance dashboard HTML"""
    return render_template('current-month-performance.html')

@app.route('/annual-analytics')
def annual_analytics_page():
    """Serve the annual analytics HTML"""
    return render_template('annual_analytics.html')

@app.route('/api/status')
def api_status():
    """Check API connection status"""
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
        'timestamp': datetime.now(PACIFIC_TZ).isoformat()
    })

@app.route('/api/dashboard-data')
def dashboard_data():
    """Get dashboard data with proper integration of Google Ads and Litify"""
    global CACHE_DATA, CACHE_TIME
    
    # Get parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', 10000, type=int)
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    # Get exclusion filter parameters
    include_spam = request.args.get('include_spam', 'false').lower() == 'true'
    include_abandoned = request.args.get('include_abandoned', 'false').lower() == 'true'
    include_duplicate = request.args.get('include_duplicate', 'false').lower() == 'true'
    
    # Create cache key based on filters
    cache_key = f"{start_date}_{end_date}_{limit}_{include_spam}_{include_abandoned}_{include_duplicate}"
    
    # Check cache validity - SKIP if force_refresh is true
    cache_valid = False
    if not force_refresh and CACHE_DATA and CACHE_TIME:
        cached_key = CACHE_DATA.get('cache_key')
        if cached_key == cache_key and (datetime.now() - CACHE_TIME).seconds < CACHE_DURATION:
            cache_valid = True
            logger.info(f"Returning cached data for key: {cache_key}")
    
    if cache_valid:
        return jsonify(CACHE_DATA)
    
    # If force_refresh, clear the performance caches too
    if force_refresh:
        logger.info("Force refresh requested - clearing all caches")
        CACHE_DATA = None
        CACHE_TIME = None
        # Clear performance caches if they exist
        if hasattr(global_cache, 'clear'):
            global_cache.clear()
        if hasattr(daily_cache, 'clear'):
            daily_cache.clear()
    
    logger.info(f"Fetching fresh data for filters: start={start_date}, end={end_date}, limit={limit}, "
                f"include_spam={include_spam}, include_abandoned={include_abandoned}, include_duplicate={include_duplicate}, "
                f"force_refresh={force_refresh}")
    
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
    
    # Fetch Litify leads (only those with UTM Campaign) - pass force_refresh parameter
    if litify_manager.connected:
        litify_leads = litify_manager.fetch_detailed_leads(
            start_date, end_date, limit=limit,
            include_spam=include_spam,
            include_abandoned=include_abandoned,
            include_duplicate=include_duplicate,
            force_refresh=force_refresh  # Add this parameter
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
    response_data = {
        'buckets': buckets,
        'unmapped_campaigns': unmapped_campaigns,
        'unmapped_utms': list(unmapped_utms) if isinstance(unmapped_utms, set) else unmapped_utms,
        'litify_leads': litify_leads,
        'available_buckets': list(BUCKET_PRIORITY),  # Include list of all available bucket names
        'data_source': data_source,
        'timestamp': datetime.now(PACIFIC_TZ).isoformat(),
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
        'cache_key': cache_key,
        'force_refresh': force_refresh  # Include this in response for debugging
    }
    
    # Cache the data only if not force_refresh
    if not force_refresh:
        CACHE_DATA = response_data
        CACHE_TIME = datetime.now()
        logger.info("Data cached for future requests")
    else:
        logger.info("Skipping cache due to force_refresh")
    
    return jsonify(response_data)

@app.route('/api/campaign-mapping', methods=['GET', 'POST'])
def api_campaign_mapping():
    """API for campaign bucket mapping"""
    global CAMPAIGN_BUCKETS, CACHE_DATA, CACHE_TIME
    
    if request.method == 'GET':
        return jsonify(CAMPAIGN_BUCKETS)
    
    elif request.method == 'POST':
        data = request.json
        action = data.get('action')
        
        if action == 'update_all':
            new_buckets = data.get('buckets', {})
            
            cleaned_buckets = {}
            for bucket_name, bucket_data in new_buckets.items():
                if isinstance(bucket_data, dict) and 'campaigns' in bucket_data:
                    cleaned_buckets[bucket_name] = bucket_data['campaigns']
                elif isinstance(bucket_data, list):
                    cleaned_buckets[bucket_name] = bucket_data
                else:
                    campaigns = []
                    for key, value in bucket_data.items():
                        if key.isdigit() and isinstance(value, str):
                            campaigns.append(value)
                    campaigns = [c for c in campaigns if c != bucket_name]
                    cleaned_buckets[bucket_name] = campaigns
            
            CAMPAIGN_BUCKETS = cleaned_buckets
            save_mappings()
            
            CACHE_DATA = None
            CACHE_TIME = None
            logger.info("Campaign buckets updated and cache cleared")
            
            return jsonify({'success': True, 'buckets': CAMPAIGN_BUCKETS})
        
        elif action == 'reset_to_defaults':
            CAMPAIGN_BUCKETS = demo_data.DEMO_CAMPAIGN_BUCKETS
            save_mappings()
            
            CACHE_DATA = None
            CACHE_TIME = None
            logger.info("Campaign buckets reset to defaults and cache cleared")
            
            return jsonify({'success': True, 'buckets': CAMPAIGN_BUCKETS})
        
        return jsonify({'success': False, 'error': 'Invalid action'}), 400

@app.route('/api/utm-mapping', methods=['GET', 'POST'])
def api_utm_mapping():
    """API for UTM to bucket mapping"""
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
                
                CACHE_DATA = None
                CACHE_TIME = None
                logger.info(f"UTM '{utm}' mapping deleted and cache cleared")
                
                return jsonify({'success': True, 'mappings': UTM_TO_BUCKET_MAPPING})
            
            return jsonify({'success': False, 'error': 'UTM not found'}), 404
        
        elif action == 'update_all':
            new_mappings = data.get('mappings', {})
            
            UTM_TO_BUCKET_MAPPING = new_mappings
            save_utm_mapping()
            
            CACHE_DATA = None
            CACHE_TIME = None
            logger.info("UTM mappings updated and cache cleared")
            
            return jsonify({'success': True, 'mappings': UTM_TO_BUCKET_MAPPING})
        
        elif action == 'reset_to_defaults':
            UTM_TO_BUCKET_MAPPING = demo_data.DEMO_UTM_TO_BUCKET_MAPPING
            save_utm_mapping()
            
            CACHE_DATA = None
            CACHE_TIME = None
            logger.info("UTM mapping reset to defaults and cache cleared")
            
            return jsonify({'success': True, 'mappings': UTM_TO_BUCKET_MAPPING})
        
        return jsonify({'success': False, 'error': 'Invalid action'}), 400

@app.route('/api/all-campaigns')
def api_all_campaigns():
    """Get list of all campaign names for mapping interface"""
    if not ads_manager.client:
        ads_manager.initialize()
    
    if ads_manager.connected:
        # Use Pacific Time for fetching
        now_pt = datetime.now(PACIFIC_TZ)
        today = now_pt.strftime('%Y-%m-%d')
        campaigns = ads_manager.fetch_campaigns(today, today)
        if campaigns:
            return jsonify([c['name'] for c in campaigns])
    
    # Return demo campaign names from module
    return jsonify(demo_data.DEMO_CAMPAIGNS)

@app.route('/api/forecast-settings', methods=['GET', 'POST'])
def api_forecast_settings():
    """API for forecast settings"""
    if request.method == 'GET':
        settings = load_forecast_settings()
        return jsonify(settings)
    
    elif request.method == 'POST':
        settings = request.json
        if save_forecast_settings(settings):
            return jsonify({'success': True, 'message': 'Settings saved successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to save settings'}), 500

@app.route('/api/forecast-pacing')
@time_it
def api_forecast_pacing():
    """
    Get current month pacing data with performance optimization and Pacific Time
    """
    # Get date parameters (default to current month)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    # Get exclusion filter parameters
    include_spam = request.args.get('include_spam', 'false').lower() == 'true'
    include_abandoned = request.args.get('include_abandoned', 'false').lower() == 'true'
    include_duplicate = request.args.get('include_duplicate', 'false').lower() == 'true'
    
    # Default to current month if not specified (Pacific Time)
    if not start_date or not end_date:
        now_pt = datetime.now(PACIFIC_TZ)
        start_date = datetime(now_pt.year, now_pt.month, 1).strftime('%Y-%m-%d')
        end_date = datetime(now_pt.year, now_pt.month, calendar.monthrange(now_pt.year, now_pt.month)[1]).strftime('%Y-%m-%d')
    
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
        'timestamp': datetime.now(PACIFIC_TZ).isoformat()
    }
    
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
    
    # Process Google Ads data
    if 'google_ads' in results and results['google_ads']:
        campaigns = results['google_ads']
        
        # Aggregate by state
        state_spend = {"CA": 0, "AZ": 0, "GA": 0, "TX": 0}
        
        for campaign in campaigns:
            # Map campaign to state based on bucket mapping
            state = determine_state_from_campaign(campaign.get('name', ''))
            if state in state_spend:
                state_spend[state] += campaign.get('cost', 0)
        
        # Update pacing data with spend
        for state, spend in state_spend.items():
            pacing_data['states'][state]['spend'] = spend
            pacing_data['totals']['spend'] += spend
    
    # Process Litify data
    if 'litify' in results and results['litify']:
        leads = results['litify']
        
        # Aggregate by state
        state_metrics = {"CA": {}, "AZ": {}, "GA": {}, "TX": {}}
        
        for state in state_metrics:
            state_metrics[state] = {
                'leads': 0,
                'cases': 0,
                'retainers': 0,
                'case_ids': set(),
                'retainer_ids': set()
            }
        
        for lead in leads:
            # Map UTM campaign to state
            utm_campaign = lead.get('litify_pm__UTM_Campaign__c', '')
            state = determine_state_from_utm(utm_campaign)
            
            if state in state_metrics:
                # Count leads
                state_metrics[state]['leads'] += 1
                
                # Check for retainer
                if lead.get('Retainer_Signed_Date__c'):
                    state_metrics[state]['retainer_ids'].add(lead.get('Id'))
                    state_metrics[state]['retainers'] += 1
                
                # Track unique cases
                matter_id = lead.get('litify_pm__Matter__c')
                if matter_id:
                    state_metrics[state]['case_ids'].add(matter_id)
        
        # Update pacing data with metrics
        for state, metrics in state_metrics.items():
            pacing_data['states'][state]['leads'] = metrics['leads']
            pacing_data['states'][state]['cases'] = len(metrics['case_ids'])
            pacing_data['states'][state]['retainers'] = metrics['retainers']
            
            # Calculate CPL and conversion rate
            if metrics['leads'] > 0:
                pacing_data['states'][state]['cpl'] = pacing_data['states'][state]['spend'] / metrics['leads']
                pacing_data['states'][state]['conversion_rate'] = (metrics['retainers'] / metrics['leads']) * 100
            
            # Update totals
            pacing_data['totals']['leads'] += metrics['leads']
            pacing_data['totals']['cases'] += len(metrics['case_ids'])
            pacing_data['totals']['retainers'] += metrics['retainers']
    
    # Fetch daily data for trend chart (if within current month)
    now_pt = datetime.now(PACIFIC_TZ)
    if start_date == datetime(now_pt.year, now_pt.month, 1).strftime('%Y-%m-%d'):
        daily_data = fetch_daily_pacing_data(start_date, end_date, include_spam, include_abandoned, include_duplicate)
        pacing_data['daily_data'] = daily_data
    
    # Cache the result
    global_cache.set(cache_key, pacing_data)
    
    logger.info(f"✅ Forecast pacing data generated: {pacing_data['totals']}")
    
    return jsonify(pacing_data)


@app.route('/api/forecast-projections')
@time_it
def api_forecast_projections():
    """
    Get forecast projections based on current pacing with advanced calculations
    """
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    # Cache key for projections
    cache_key = ['forecast_projections', datetime.now(PACIFIC_TZ).strftime('%Y-%m-%d')]
    
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
    
    # Calculate time factors (Pacific Time)
    now_pt = datetime.now(PACIFIC_TZ)
    days_in_month = calendar.monthrange(now_pt.year, now_pt.month)[1]
    days_elapsed = now_pt.day
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
        'timestamp': datetime.now(PACIFIC_TZ).isoformat()
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
        current_conversion = (current['cases'] / current['leads'] * 100) if current['leads'] > 0 else 0
        
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
    Get daily trend data for the current month with caching optimization and Pacific Time
    """
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    # Get filter parameters
    include_spam = request.args.get('include_spam', 'false').lower() == 'true'
    include_abandoned = request.args.get('include_abandoned', 'false').lower() == 'true'
    include_duplicate = request.args.get('include_duplicate', 'false').lower() == 'true'
    
    # Cache key
    cache_key = ['forecast_daily_trend', datetime.now(PACIFIC_TZ).strftime('%Y-%m'), 
                 include_spam, include_abandoned, include_duplicate]
    
    if not force_refresh:
        cached = global_cache.get(cache_key)
        if cached:
            logger.info("✅ Returning cached daily trend data")
            return jsonify(cached)
    
    # Get current month date range (Pacific Time)
    now_pt = datetime.now(PACIFIC_TZ)
    month_start = datetime(now_pt.year, now_pt.month, 1, tzinfo=PACIFIC_TZ)
    month_end = datetime(now_pt.year, now_pt.month, calendar.monthrange(now_pt.year, now_pt.month)[1], tzinfo=PACIFIC_TZ)
    today = min(now_pt, month_end)
    
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
        'month': now_pt.strftime('%Y-%m'),
        'timestamp': datetime.now(PACIFIC_TZ).isoformat()
    }
    
    # Cache the result
    global_cache.set(cache_key, result)
    
    logger.info(f"✅ Daily trend data generated: {len(daily_data)} days")
    
    return jsonify(result)

# Helper functions continue...

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
    Fetch metrics for a single day with Pacific Time support
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
    """Calculate date ranges for comparison periods with Pacific Time"""
    today_pt = datetime.now(PACIFIC_TZ).date()
    
    if period == 'today':
        start = end = today_pt
        compare_start = compare_end = today_pt - timedelta(days=1)
    elif period == 'yesterday':
        start = end = today_pt - timedelta(days=1)
        compare_start = compare_end = today_pt - timedelta(days=2)
    elif period == 'week':
        start = today_pt - timedelta(days=today_pt.weekday())
        end = today_pt
        compare_start = start - timedelta(days=7)
        compare_end = end - timedelta(days=7)
    elif period == 'month':
        start = date(today_pt.year, today_pt.month, 1)
        end = today_pt
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
        start = date(today_pt.year, today_pt.month, 1)
        end = today_pt
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
    
    if summary['total_leads'] > 0:
       summary['conversion_rate'] = summary['total_cases'] / summary['total_leads']
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
    
    # Calculate date ranges with Pacific Time
    if period == 'custom' and custom_start and custom_end:
        current_start = custom_start
        current_end = custom_end
    else:
        today_pt = datetime.now(PACIFIC_TZ).date()
        if period == 'today':
            current_start = current_end = today_pt.strftime('%Y-%m-%d')
        elif period == 'yesterday':
            yesterday = today_pt - timedelta(days=1)
            current_start = current_end = yesterday.strftime('%Y-%m-%d')
        elif period == 'week':
            week_start = today_pt - timedelta(days=today_pt.weekday())
            current_start = week_start.strftime('%Y-%m-%d')
            current_end = today_pt.strftime('%Y-%m-%d')
        elif period == 'month':
            current_start = date(today_pt.year, today_pt.month, 1).strftime('%Y-%m-%d')
            current_end = today_pt.strftime('%Y-%m-%d')
        else:  # mtd
            current_start = date(today_pt.year, today_pt.month, 1).strftime('%Y-%m-%d')
            current_end = today_pt.strftime('%Y-%m-%d')
    
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
        'timestamp': datetime.now(PACIFIC_TZ).isoformat()
    })

@app.route('/api/annual-data')
def api_annual_data():
    """Get annual data with monthly breakdown and Pacific Time support"""
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
        year = request.args.get('year', datetime.now(PACIFIC_TZ).year, type=int)
        current_date_pt = datetime.now(PACIFIC_TZ)
        current_month = current_date_pt.month if year == current_date_pt.year else 12
        
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
            month_date = datetime(year, month_num, 1, tzinfo=PACIFIC_TZ)
            month_name = month_date.strftime('%B')
            is_current = (month_num == current_month and year == current_date_pt.year)
            
            # Skip future months
            if month_date > current_date_pt:
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
                next_month_date = datetime(year + 1, 1, 1, tzinfo=PACIFIC_TZ)
            else:
                next_month_date = datetime(year, month_num + 1, 1, tzinfo=PACIFIC_TZ)
            
            start_date = month_date.strftime('%Y-%m-%d')
            end_date = (next_month_date - timedelta(days=1)).strftime('%Y-%m-%d')
            
            # For current month, end at today
            if is_current:
                end_date = current_date_pt.strftime('%Y-%m-%d')
            
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
            if month_summary['leads'] > 0:
                month_summary['conversion_rate'] = round(month_summary['cases'] / month_summary['leads'], 3)
            
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
        if annual_summary['total_leads'] > 0:
            annual_summary['avg_conversion_rate'] = round(annual_summary['total_cases'] / annual_summary['total_leads'], 3)
        
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
        'timestamp': datetime.now(PACIFIC_TZ).isoformat()
    })

@app.route('/api/current-month-daily')
def api_current_month_daily():
    """
    Get daily performance data for the current month with day-over-day deltas
    Including bucket-level breakdown for each day - Pacific Time support
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
        
        # Get current month date range in Pacific Time
        now_pt = datetime.now(PACIFIC_TZ)
        month_start = date(now_pt.year, now_pt.month, 1)
        month_end = date(now_pt.year, now_pt.month, calendar.monthrange(now_pt.year, now_pt.month)[1])
        today = now_pt.date()
        
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
            current_date = date(now_pt.year, now_pt.month, day_num)
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
            
            if day_data['leads'] > 0:
                day_data['convRate'] = round(day_data['cases'] / day_data['leads'], 3)
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
            'convRate': round(month_totals['total_cases'] / month_totals['total_leads'], 3) if month_totals['total_leads'] > 0 else 0,
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
            'timestamp': datetime.now(PACIFIC_TZ).isoformat()
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
    Shows exactly which date is being processed - Pacific Time support
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
        
        # Get current month date range in Pacific Time
        now_pt = datetime.now(PACIFIC_TZ)
        month_start = date(now_pt.year, now_pt.month, 1)
        month_end = date(now_pt.year, now_pt.month, calendar.monthrange(now_pt.year, now_pt.month)[1])
        today = now_pt.date()
        
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
            current_date = date(now_pt.year, now_pt.month, day_num)
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
                    logger.info(f"  ✔️ Fetched {len(campaigns)} campaigns for {date_str}")
            
            # Fetch Litify leads for this day
            if litify_manager.connected:
                litify_leads = litify_manager.fetch_detailed_leads(
                    date_str, date_str, limit=500,
                    include_spam=include_spam,
                    include_abandoned=include_abandoned,
                    include_duplicate=include_duplicate
                )
                if litify_leads:
                    logger.info(f"  ✔️ Fetched {len(litify_leads)} Litify leads for {date_str}")
            
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
            'convRate': round(month_totals['total_cases'] / month_totals['total_leads'], 3) if month_totals['total_leads'] > 0 else 0,
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
            'timestamp': datetime.now(PACIFIC_TZ).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in accurate current month daily API: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/lsa-discovery')
def debug_lsa_discovery():
    """
    Debug route to discover all LSA campaigns across all accounts - Pacific Time
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
        
        # Get date range for last 30 days in Pacific Time
        end_date_pt = datetime.now(PACIFIC_TZ)
        start_date_pt = end_date_pt - timedelta(days=30)
        end_date = end_date_pt.strftime('%Y-%m-%d')
        start_date = start_date_pt.strftime('%Y-%m-%d')
        
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
            state = get_state_from_campaign_bucket(name)
            
            if state and state in lsa_by_region:
                lsa_by_region[state].append(campaign)
            else:
                lsa_by_region['Unknown'].append(campaign)
        
        # Prepare output
        output = {
            'success': True,
            'timestamp': datetime.now(PACIFIC_TZ).isoformat(),
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
                'region': get_state_from_campaign_bucket(c.get('name', ''))
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
        filename = f"lsa_discovery_{datetime.now(PACIFIC_TZ).strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(os.getcwd(), filename)
        
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"✅ LSA discovery complete. Found {len(lsa_campaigns)} LSA campaigns")
        logger.info(f"📂 Report saved to {filename}")
        
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
    Debug route to check if LSA campaigns are being fetched and processed correctly - Pacific Time
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
        
        # Get today's date for testing in Pacific Time
        today_pt = datetime.now(PACIFIC_TZ)
        today = today_pt.strftime('%Y-%m-%d')
        
        # Fetch campaigns for today (or last 7 days for more data)
        end_date = today
        start_date = (today_pt - timedelta(days=7)).strftime('%Y-%m-%d')
        
        logger.info(f"🔍 Checking LSA spend from {start_date} to {end_date} PT")
        
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
            'timestamp': datetime.now(PACIFIC_TZ).isoformat(),
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
            today_pt = datetime.now(PACIFIC_TZ)
            today = today_pt.strftime('%Y-%m-%d')
            week_ago = (today_pt - timedelta(days=7)).strftime('%Y-%m-%d')
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
            'timestamp': datetime.now(PACIFIC_TZ).isoformat(),
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

@app.route('/api/debug/timezone-check')
def debug_timezone_check():
    """
    Debug route to verify timezone settings and date conversions
    """
    try:
        # Get various time representations
        now_utc = datetime.now(pytz.UTC)
        now_pt = datetime.now(PACIFIC_TZ)
        now_naive = datetime.now()
        
        # Test date range conversion
        test_date = "2025-01-15"
        start_dt_pt, end_dt_pt = get_pacific_date_range(test_date, test_date)
        
        # Convert to UTC for Salesforce DATETIME fields
        start_dt_utc = start_dt_pt.astimezone(pytz.UTC)
        end_dt_utc = end_dt_pt.astimezone(pytz.UTC)
        
        return jsonify({
            'success': True,
            'current_times': {
                'utc': now_utc.isoformat(),
                'pacific': now_pt.isoformat(),
                'naive': now_naive.isoformat(),
                'pacific_date': now_pt.strftime('%Y-%m-%d'),
                'pacific_time': now_pt.strftime('%H:%M:%S %Z')
            },
            'test_conversion': {
                'input_date': test_date,
                'pacific_start': start_dt_pt.isoformat(),
                'pacific_end': end_dt_pt.isoformat(),
                'utc_start': start_dt_utc.isoformat(),
                'utc_end': end_dt_utc.isoformat(),
                'salesforce_datetime_format': start_dt_utc.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                'salesforce_date_format': start_dt_pt.strftime('%Y-%m-%d')
            },
            'time_differences': {
                'utc_to_pt_hours': (now_pt.hour - now_utc.hour) % 24,
                'is_dst': bool(now_pt.dst()),
                'dst_offset': str(now_pt.dst()) if now_pt.dst() else 'No DST'
            }
        })
        
    except Exception as e:
        logger.error(f"Error in timezone check: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/debug/clear-cache', methods=['POST'])
def debug_clear_cache():
    """
    Debug route to clear all caches
    """
    try:
        global CACHE_DATA, CACHE_TIME
        
        # Clear main cache
        CACHE_DATA = None
        CACHE_TIME = None
        
        # Clear global cache
        if hasattr(global_cache, 'clear'):
            global_cache.clear()
        
        # Clear daily cache
        if hasattr(daily_cache, 'clear'):
            daily_cache.clear()
        
        logger.info("🧹 All caches cleared")
        
        return jsonify({
            'success': True,
            'message': 'All caches cleared successfully',
            'timestamp': datetime.now(PACIFIC_TZ).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/debug/test-apis')
def debug_test_apis():
    """
    Debug route to test API connections and basic functionality
    """
    results = {
        'timestamp': datetime.now(PACIFIC_TZ).isoformat(),
        'timezone': 'Pacific Time (America/Los_Angeles)',
        'google_ads': {
            'available': GOOGLE_ADS_AVAILABLE,
            'connected': False,
            'error': None,
            'test_result': None
        },
        'litify': {
            'available': SALESFORCE_AVAILABLE,
            'connected': False,
            'error': None,
            'test_result': None
        }
    }
    
    # Test Google Ads
    if GOOGLE_ADS_AVAILABLE:
        if not ads_manager.client:
            ads_manager.initialize()
        
        results['google_ads']['connected'] = ads_manager.connected
        results['google_ads']['error'] = ads_manager.error
        
        if ads_manager.connected:
            try:
                # Try to fetch today's campaigns
                today = datetime.now(PACIFIC_TZ).strftime('%Y-%m-%d')
                campaigns = ads_manager.fetch_campaigns(today, today, active_only=True)
                results['google_ads']['test_result'] = {
                    'campaigns_found': len(campaigns) if campaigns else 0,
                    'customer_ids': ads_manager.customer_ids,
                    'is_mcc': ads_manager.is_mcc
                }
            except Exception as e:
                results['google_ads']['test_result'] = f"Error: {str(e)}"
    
    # Test Litify
    if SALESFORCE_AVAILABLE:
        if not litify_manager.client:
            litify_manager.initialize()
        
        results['litify']['connected'] = litify_manager.connected
        results['litify']['error'] = litify_manager.error
        
        if litify_manager.connected:
            try:
                # Try to fetch today's leads
                today = datetime.now(PACIFIC_TZ).strftime('%Y-%m-%d')
                leads = litify_manager.fetch_detailed_leads(today, today, limit=10)
                results['litify']['test_result'] = {
                    'leads_found': len(leads) if leads else 0,
                    'instance_url': litify_manager.instance_url,
                    'case_types_cached': len(litify_manager.case_type_cache)
                }
            except Exception as e:
                results['litify']['test_result'] = f"Error: {str(e)}"
    
    return jsonify(results)

# ========== MAIN EXECUTION ==========

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("🚀 Starting Sweet James Dashboard with Exclusion Filters")
    logger.info("🕐 Timezone: Pacific Time (America/Los_Angeles)")
    logger.info("=" * 60)
    
    logger.info("Initializing API connections...")
    
    if ads_manager.initialize():
        logger.info("✅ Google Ads API connected")
        if ads_manager.is_mcc:
            logger.info(f"   Using MCC account: {ads_manager.mcc_id}")
            logger.info(f"   Child accounts: {len(ads_manager.child_accounts)}")
        logger.info(f"   Customer IDs: {ads_manager.customer_ids}")
    else:
        logger.warning(f"⚠️ Google Ads API not connected: {ads_manager.error}")
    
    if litify_manager.initialize():
        logger.info("✅ Litify API connected")
        logger.info(f"   Cached {len(litify_manager.case_type_cache)} case types")
        logger.info(f"   Salesforce instance: {litify_manager.instance_url}")
    else:
        logger.warning(f"⚠️ Litify API not connected: {litify_manager.error}")
    
    port = int(os.getenv('PORT', 8080))
    logger.info("=" * 60)
    logger.info("📍 ENDPOINTS:")
    logger.info(f"Dashboard: http://localhost:{port}")
    logger.info(f"Campaign Mapping: http://localhost:{port}/campaign-mapping")
    logger.info(f"Forecasting: http://localhost:{port}/forecasting")
    logger.info(f"Comparison Dashboard: http://localhost:{port}/comparison-dashboard")
    logger.info(f"Current Month Performance: http://localhost:{port}/current-month-performance")
    logger.info(f"Annual Analytics: http://localhost:{port}/annual-analytics")
    logger.info(f"API Status: http://localhost:{port}/api/status")
    logger.info("=" * 60)
    logger.info("🕐 TIMEZONE INFO:")
    logger.info("All date ranges are now in Pacific Time (PT)")
    logger.info("Query times: 12:00 AM PT to 11:59:59 PM PT")
    logger.info("Current PT time: " + datetime.now(PACIFIC_TZ).strftime('%Y-%m-%d %H:%M:%S %Z'))
    logger.info("=" * 60)
    logger.info("📊 FIELD NAME CORRECTIONS:")
    logger.info("Custom fields (NO litify_pm__ prefix):")
    logger.info("    - Retainer_Signed_Date__c (DATE field)")
    logger.info("    - Client_Name__c")
    logger.info("    - isDroppedatIntake__c")
    logger.info("Standard Litify fields (WITH litify_pm__ prefix):")
    logger.info("    - litify_pm__Status__c")
    logger.info("    - litify_pm__Display_Name__c")
    logger.info("    - litify_pm__UTM_Campaign__c")
    logger.info("    - litify_pm__Case_Type__c")
    logger.info("    - litify_pm__Matter__c")
    logger.info("DATETIME fields (use UTC conversion):")
    logger.info("    - CreatedDate")
    logger.info("=" * 60)
    logger.info("✅ CONVERSION CRITERIA:")
    logger.info("A retainer/conversion is counted when:")
    logger.info("    - Retainer Signed Date is not empty")
    logger.info("    - Status NOT 'Converted DAI' or 'Referred Out'")   
    logger.info("    - isDroppedatIntake = False")
    logger.info("    - Display Name != 'test'")
    logger.info("Unqualified = In practice but NOT converted")
    logger.info("Cases = Grouped by Matter ID (or companion ID, or solo)")
    logger.info("Retainers = Total converted intakes")
    logger.info("=" * 60)
    logger.info("🔧 DEBUG ENDPOINTS:")
    logger.info(f"Test APIs: http://localhost:{port}/api/debug/test-apis")
    logger.info(f"Timezone Check: http://localhost:{port}/api/debug/timezone-check")
    logger.info(f"Campaign Dump: http://localhost:{port}/api/debug/campaigns-dump")
    logger.info(f"LSA Discovery: http://localhost:{port}/api/debug/lsa-discovery")
    logger.info(f"LSA Spend Check: http://localhost:{port}/api/debug/lsa-spend-check")
    logger.info(f"Bucket Check: http://localhost:{port}/api/debug/bucket-check")
    logger.info(f"Clear Cache: POST http://localhost:{port}/api/debug/clear-cache")
    logger.info(f"Fix LSA Mapping: POST http://localhost:{port}/api/fix-lsa-mapping")
    logger.info("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=port)