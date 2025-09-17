"""
Litify Service for Sweet James Dashboard
Manages all Litify/Salesforce API connections and data fetching
"""

import os
import logging
from datetime import datetime, timedelta
import requests
import json
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

class LitifyManager:
    """Litify/Salesforce API Manager for lead and case data"""
    
    def __init__(self):
        self.client = None
        self.connected = False
        self.error = None
        self.access_token = None
        self.instance_url = None
        self.case_type_cache = {}
        
    def initialize(self):
        """Initialize Litify/Salesforce connection"""
        try:
            # Check for Salesforce credentials
            client_id = os.getenv('SALESFORCE_CLIENT_ID')
            client_secret = os.getenv('SALESFORCE_CLIENT_SECRET')
            username = os.getenv('SALESFORCE_USERNAME')
            password = os.getenv('SALESFORCE_PASSWORD')
            security_token = os.getenv('SALESFORCE_SECURITY_TOKEN')
            sandbox = os.getenv('SALESFORCE_SANDBOX', 'false').lower() == 'true'
            
            if not all([client_id, client_secret, username, password]):
                self.error = "Missing Salesforce credentials"
                logger.warning(f"⚠️ {self.error}")
                return False
            
            # Authenticate with Salesforce
            login_url = 'https://test.salesforce.com' if sandbox else 'https://login.salesforce.com'
            auth_url = f"{login_url}/services/oauth2/token"
            
            auth_data = {
                'grant_type': 'password',
                'client_id': client_id,
                'client_secret': client_secret,
                'username': username,
                'password': password + (security_token or '')
            }
            
            response = requests.post(auth_url, data=auth_data)
            
            if response.status_code == 200:
                auth_info = response.json()
                self.access_token = auth_info['access_token']
                self.instance_url = auth_info['instance_url']
                self.connected = True
                self.error = None
                logger.info(f"✅ Litify API initialized: {self.instance_url}")
                
                # Cache case types
                self._load_case_types()
                return True
            else:
                self.error = f"Authentication failed: {response.text}"
                logger.error(f"❌ Litify authentication failed: {self.error}")
                return False
                
        except Exception as e:
            self.error = str(e)
            self.connected = False
            logger.error(f"❌ Failed to initialize Litify API: {e}")
            return False
    
    def _load_case_types(self):
        """Load case types from Litify"""
        try:
            if not self.connected:
                return
            
            # Query case types
            query = "SELECT Id, Name FROM litify_pm__Case_Type__c"
            result = self._execute_soql(query)
            
            if result and 'records' in result:
                for record in result['records']:
                    self.case_type_cache[record['Id']] = record['Name']
                logger.info(f"✅ Cached {len(self.case_type_cache)} case types")
                
        except Exception as e:
            logger.error(f"❌ Error loading case types: {e}")
    
    def _execute_soql(self, query):
        """Execute SOQL query against Salesforce"""
        if not self.connected:
            return None
        
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.instance_url}/services/data/v58.0/query"
            params = {'q': query}
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"SOQL query failed: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error executing SOQL: {e}")
            return None
    
    def fetch_detailed_leads(self, start_date, end_date, limit=1000, 
                           include_spam=False, include_abandoned=False, include_duplicate=False):
        """Fetch detailed lead data from Litify"""
        if not self.connected:
            return self.get_demo_litify_leads(include_spam, include_abandoned, include_duplicate)
        
        try:
            # Build exclusion filters
            exclusion_filters = []
            if not include_spam:
                exclusion_filters.append("litify_pm__Case_Type__r.Name != 'Spam'")
            if not include_abandoned:
                exclusion_filters.append("litify_pm__Case_Type__r.Name != 'Abandoned'")
            if not include_duplicate:
                exclusion_filters.append("litify_pm__Case_Type__r.Name != 'Duplicate'")
            
            exclusion_clause = ""
            if exclusion_filters:
                exclusion_clause = " AND " + " AND ".join(exclusion_filters)
            
            # SOQL query for leads/intakes
            query = f"""
                SELECT 
                    Id,
                    Name,
                    litify_pm__Display_Name__c,
                    litify_pm__Status__c,
                    litify_pm__Case_Type__r.Name,
                    litify_pm__Matter__c,
                    Retainer_Signed_Date__c,
                    UTM_Campaign__c,
                    Client_Name__c,
                    isDroppedatIntake__c,
                    CreatedDate,
                    LastModifiedDate
                FROM litify_pm__Intake__c 
                WHERE CreatedDate >= {start_date}T00:00:00Z 
                AND CreatedDate <= {end_date}T23:59:59Z
                {exclusion_clause}
                ORDER BY CreatedDate DESC
                LIMIT {limit}
            """
            
            result = self._execute_soql(query)
            
            if result and 'records' in result:
                leads = []
                for record in result['records']:
                    lead_data = self._process_lead_record(record)
                    leads.append(lead_data)
                
                logger.info(f"✅ Fetched {len(leads)} Litify leads from {start_date} to {end_date}")
                return leads
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Error fetching Litify leads: {e}")
            return self.get_demo_litify_leads(include_spam, include_abandoned, include_duplicate)
    
    def _process_lead_record(self, record):
        """Process a single lead record from Salesforce"""
        # Extract case type name
        case_type = 'Unknown'
        if record.get('litify_pm__Case_Type__r') and record['litify_pm__Case_Type__r'].get('Name'):
            case_type = record['litify_pm__Case_Type__r']['Name']
        
        # Determine if this is in practice
        in_practice_types = [
            'Pedestrian', 'Automobile Accident', 'Wrongful Death', 'Premise Liability',
            'Public Entity', 'Personal injury', 'Habitability', 'Automobile Accident - Commercial',
            'Bicycle', 'Animal Incident', 'Wildfire 2025', 'Motorcycle', 'Slip and Fall',
            'Electric Scooter', 'Mold', 'Product Liability'
        ]
        
        in_practice = case_type in in_practice_types
        
        # Determine if converted (has retainer signed)
        retainer_date = record.get('Retainer_Signed_Date__c')
        status = record.get('litify_pm__Status__c', '')
        display_name = record.get('litify_pm__Display_Name__c', '').lower()
        is_dropped = record.get('isDroppedatIntake__c', False)
        
        # Conversion criteria
        is_converted = (
            retainer_date and 
            status not in ['Converted DAI', 'Referred Out'] and
            not is_dropped and
            display_name != 'test'
        )
        
        # Check for pending retainer
        is_pending = status in ['Retained', 'Pending Retainer', 'Retainer Sent']
        
        return {
            'id': record['Id'],
            'name': record.get('Name', ''),
            'display_name': record.get('litify_pm__Display_Name__c', ''),
            'status': status,
            'case_type': case_type,
            'matter_id': record.get('litify_pm__Matter__c'),
            'retainer_signed_date': retainer_date,
            'utm_campaign': record.get('UTM_Campaign__c', ''),
            'client_name': record.get('Client_Name__c', ''),
            'is_dropped': is_dropped,
            'created_date': record.get('CreatedDate'),
            'in_practice': in_practice,
            'is_converted': is_converted,
            'is_pending': is_pending,
            'bucket': self._map_utm_to_bucket(record.get('UTM_Campaign__c', ''))
        }
    
    def _map_utm_to_bucket(self, utm_campaign):
        """Map UTM campaign to bucket (placeholder - would use actual mapping)"""
        if not utm_campaign:
            return ''
        
        utm_lower = utm_campaign.lower()
        
        # Simple mapping logic - this would be enhanced with actual mapping data
        if 'california' in utm_lower or 'ca' in utm_lower:
            if 'brand' in utm_lower:
                return 'California Brand'
            elif 'lsa' in utm_lower:
                return 'California LSA'
            else:
                return 'California Prospecting'
        elif 'arizona' in utm_lower or 'az' in utm_lower:
            if 'brand' in utm_lower:
                return 'Arizona Brand'
            elif 'lsa' in utm_lower:
                return 'Arizona LSA'
            else:
                return 'Arizona Prospecting'
        elif 'georgia' in utm_lower or 'ga' in utm_lower:
            if 'brand' in utm_lower:
                return 'Georgia Brand'
            elif 'lsa' in utm_lower:
                return 'Georgia LSA'
            else:
                return 'Georgia Prospecting'
        elif 'texas' in utm_lower or 'tx' in utm_lower:
            if 'brand' in utm_lower:
                return 'Texas Brand'
            elif 'lsa' in utm_lower:
                return 'Texas LSA'
            else:
                return 'Texas Prospecting'
        
        return ''
    
    def get_demo_litify_leads(self, include_spam=False, include_abandoned=False, include_duplicate=False):
        """Generate demo Litify lead data for testing"""
        import random
        from datetime import datetime, timedelta
        
        demo_leads = []
        base_date = datetime.now() - timedelta(days=30)
        
        # Demo case types
        case_types = ['Automobile Accident', 'Pedestrian', 'Slip and Fall', 'Personal injury']
        if include_spam:
            case_types.append('Spam')
        if include_abandoned:
            case_types.append('Abandoned')
        if include_duplicate:
            case_types.append('Duplicate')
        
        # Generate demo leads
        for i in range(random.randint(50, 150)):
            case_type = random.choice(case_types)
            in_practice = case_type not in ['Spam', 'Abandoned', 'Duplicate']
            
            lead = {
                'id': f"demo_lead_{i:04d}",
                'name': f"Demo Lead {i}",
                'display_name': f"Demo Client {i}",
                'status': random.choice(['New', 'In Review', 'Qualified', 'Retained']),
                'case_type': case_type,
                'matter_id': f"matter_{random.randint(1000, 9999)}" if random.random() > 0.7 else None,
                'retainer_signed_date': (base_date + timedelta(days=random.randint(0, 30))).isoformat() if random.random() > 0.7 else None,
                'utm_campaign': random.choice(['california_brand', 'arizona_prospecting', 'georgia_lsa']),
                'client_name': f"Demo Client {i}",
                'is_dropped': False,
                'created_date': (base_date + timedelta(days=random.randint(0, 30))).isoformat(),
                'in_practice': in_practice,
                'is_converted': random.random() > 0.75 if in_practice else False,
                'is_pending': random.random() > 0.9 if in_practice else False,
                'bucket': random.choice(['California Brand', 'Arizona Prospecting', 'Georgia LSA'])
            }
            
            demo_leads.append(lead)
        
        logger.info(f"✅ Generated {len(demo_leads)} demo Litify leads")
        return demo_leads