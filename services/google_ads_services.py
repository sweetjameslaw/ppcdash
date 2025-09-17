"""
Google Ads Service for Sweet James Dashboard
Manages all Google Ads API connections and data fetching
"""

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
    
    GOOGLE_ADS_AVAILABLE = True
    logger.info("✅ Google Ads API loaded successfully")
except ImportError as e:
    GOOGLE_ADS_AVAILABLE = False
    logger.warning(f"⚠️ Google Ads API not available: {e}")
    # Create dummy classes to prevent import errors
    class GoogleAdsClient:
        pass
    class GoogleAdsException:
        pass


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
                        logger.info(f"  📁 Found child account: {row.customer_client.descriptive_name} ({customer_id})")
            
            # Add discovered accounts to our list
            for cid in new_customer_ids:
                if cid not in self.customer_ids:
                    self.customer_ids.append(cid)
            
            logger.info(f"✅ Discovered {len(self.child_accounts)} active child accounts")
            
        except Exception as e:
            logger.error(f"❌ Error discovering child accounts: {e}")
    
    def fetch_campaigns(self, start_date=None, end_date=None, active_only=True):
        """Fetch campaign performance data from Google Ads - Enhanced with multi-account support"""
        if not self.client or not self.connected:
            return None
        
        all_campaigns = []
        
        # Build date filter
        date_filter = ""
        if start_date and end_date:
            date_filter = f"AND segments.date BETWEEN '{start_date}' AND '{end_date}'"
        elif start_date:
            date_filter = f"AND segments.date >= '{start_date}'"
        elif end_date:
            date_filter = f"AND segments.date <= '{end_date}'"
        else:
            today = datetime.now().strftime('%Y-%m-%d')
            date_filter = f"AND segments.date = '{today}'"
        
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
        """Fetch month-to-date spend by state"""
        if not self.client or not self.connected:
            return None
            
        try:
            # Get current month date range
            now = datetime.now()
            from datetime import date
            start_date = date(now.year, now.month, 1).strftime('%Y-%m-%d')
            end_date = now.strftime('%Y-%m-%d')
            
            # Fetch campaigns for current month (including all accounts)
            campaigns = self.fetch_campaigns(start_date, end_date, active_only=False)
            
            if not campaigns:
                return None
            
            # Group spend by state (this will need to be imported from the main app)
            # For now, return the campaigns and let the caller handle state mapping
            return campaigns
            
        except Exception as e:
            self.error = str(e)
            logger.error(f"❌ Error fetching MTD spend: {e}")
            return None

    def get_state_from_campaign_name(self, campaign_name):
        """Helper method to determine state from campaign name"""
        campaign_lower = campaign_name.lower()
        
        if any(x in campaign_lower for x in ['california', ' ca ', 'los angeles', 'san diego', 'san francisco']):
            return 'CA'
        elif any(x in campaign_lower for x in ['arizona', ' az ', 'phoenix', 'tucson']):
            return 'AZ'
        elif any(x in campaign_lower for x in ['georgia', ' ga ', 'atlanta']):
            return 'GA'
        elif any(x in campaign_lower for x in ['texas', ' tx ', 'houston', 'dallas', 'austin']):
            return 'TX'
        
        return None