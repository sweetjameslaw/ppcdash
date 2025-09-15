#!/usr/bin/env python3
"""
Performance optimization utilities for Sweet James Dashboard
Includes caching, compression, and query optimization
OPTIMIZED FOR DAY-BY-DAY FETCHING
"""

import os
import json
import logging
import time
from datetime import datetime, timedelta
from functools import wraps
from threading import Thread, Lock
import concurrent.futures
from collections import defaultdict
import hashlib
import calendar

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try importing optional performance libraries
try:
    from flask_compress import Compress
    COMPRESS_AVAILABLE = True
except ImportError:
    COMPRESS_AVAILABLE = False
    logger.warning("flask-compress not available - compression disabled")

# Performance configuration - OPTIMIZED FOR DAILY DATA
PERFORMANCE_CONFIG = {
    'cache_ttl': 600,  # Increased to 10 minutes for daily data
    'max_cache_size': 200,  # Increased to handle 30+ days
    'daily_cache_ttl': 1800,  # 30 minutes for single-day fetches
    'background_refresh': True,
    'compression_level': 6,
    'query_batch_size': 200,
    'parallel_fetch': True,
    'api_timeout': 30,
}

class SmartCache:
    """Smart caching with TTL and size limits"""
    
    def __init__(self, ttl=300, max_size=100):
        self.cache = {}
        self.ttl = ttl
        self.max_size = max_size
        self.lock = Lock()
        self.hits = 0
        self.misses = 0
        
    def _make_key(self, key_parts):
        """Create a hash key from parts"""
        key_str = json.dumps(key_parts, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, key_parts):
        """Get item from cache"""
        with self.lock:
            key = self._make_key(key_parts)
            
            if key in self.cache:
                item, timestamp = self.cache[key]
                if time.time() - timestamp < self.ttl:
                    self.hits += 1
                    return item
                else:
                    del self.cache[key]
            
            self.misses += 1
            return None
    
    def set(self, key_parts, value):
        """Set item in cache"""
        with self.lock:
            key = self._make_key(key_parts)
            
            # Remove oldest items if cache is full
            if len(self.cache) >= self.max_size:
                oldest_key = min(self.cache, key=lambda k: self.cache[k][1])
                del self.cache[oldest_key]
            
            self.cache[key] = (value, time.time())
    
    def clear(self):
        """Clear all cache"""
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    def clear_pattern(self, pattern):
        """Clear cache entries matching a pattern"""
        with self.lock:
            keys_to_remove = []
            for key_parts in self.cache.keys():
                if pattern in str(key_parts):
                    keys_to_remove.append(key_parts)
            
            for key in keys_to_remove:
                del self.cache[key]
            
            return len(keys_to_remove)
    
    def get_stats(self):
        """Get cache statistics"""
        with self.lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0
            return {
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': f"{hit_rate:.1f}%",
                'size': len(self.cache),
                'max_size': self.max_size
            }

class DailyDataCache(SmartCache):
    """Special cache optimized for daily performance data"""
    
    def __init__(self):
        # Use longer TTL and bigger size for daily data
        super().__init__(
            ttl=PERFORMANCE_CONFIG.get('daily_cache_ttl', 1800),  # 30 minutes
            max_size=250  # Enough for ~2 months of daily data
        )
    
    def get_day_key(self, date_str, data_type='combined'):
        """Create a cache key for a specific day's data"""
        return ['daily', date_str, data_type]
    
    def get_day(self, date_str, data_type='combined'):
        """Get cached data for a specific day"""
        return self.get(self.get_day_key(date_str, data_type))
    
    def set_day(self, date_str, data, data_type='combined'):
        """Cache data for a specific day"""
        self.set(self.get_day_key(date_str, data_type), data)
    
    def clear_month(self, year, month):
        """Clear all cached data for a specific month"""
        pattern = f"{year}-{month:02d}"
        cleared = self.clear_pattern(pattern)
        logger.info(f"Cleared {cleared} cached entries for {pattern}")
        return cleared

# Global cache instances
global_cache = SmartCache(
    ttl=PERFORMANCE_CONFIG['cache_ttl'],
    max_size=PERFORMANCE_CONFIG['max_cache_size']
)

# Special cache for daily data with longer TTL
daily_cache = DailyDataCache()

def time_it(func):
    """Decorator to measure function execution time"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        logger.info(f"⏱️ {func.__name__} took {duration:.2f}s")
        return result
    return wrapper

def parallel_fetch(fetch_functions, timeout=30):
    """Execute multiple fetch functions in parallel"""
    results = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_key = {}
        
        for key, fetch_func in fetch_functions.items():
            future = executor.submit(fetch_func)
            future_to_key[future] = key
        
        for future in concurrent.futures.as_completed(future_to_key, timeout=timeout):
            key = future_to_key[future]
            try:
                results[key] = future.result()
            except Exception as e:
                logger.error(f"Error fetching {key}: {e}")
                results[key] = None
    
    return results

class BackgroundRefresher:
    """Background cache refresher"""
    
    def __init__(self, refresh_interval=240):  # 4 minutes
        self.refresh_interval = refresh_interval
        self.refresh_funcs = []
        self.running = False
        self.thread = None
        
    def register(self, func, args=(), kwargs={}):
        """Register a function to refresh"""
        self.refresh_funcs.append((func, args, kwargs))
    
    def start(self):
        """Start background refresh"""
        if not self.running:
            self.running = True
            self.thread = Thread(target=self._refresh_loop, daemon=True)
            self.thread.start()
            logger.info("🔄 Background cache refresh started")
    
    def stop(self):
        """Stop background refresh"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
    
    def _refresh_loop(self):
        """Background refresh loop"""
        while self.running:
            time.sleep(self.refresh_interval)
            
            for func, args, kwargs in self.refresh_funcs:
                try:
                    func(*args, **kwargs)
                    logger.info(f"🔄 Refreshed {func.__name__}")
                except Exception as e:
                    logger.error(f"Error refreshing {func.__name__}: {e}")

def optimize_google_ads_fetch(ads_manager, start_date=None, end_date=None, active_only=True, force_refresh=False):
    """
    Optimized Google Ads fetch with caching and parallel processing.
    Now optimized for single-day fetches.
    """
    # Special handling for single-day fetches - use daily cache with longer TTL
    if start_date and end_date and start_date == end_date:
        if not force_refresh:
            # Check daily cache first
            cached = daily_cache.get_day(start_date, f'google_ads_{active_only}')
            if cached:
                logger.info(f"✅ Returning daily cached Google Ads data for {start_date}")
                return cached
    
    # Regular cache for date ranges
    cache_key = ['google_ads', start_date or 'none', end_date or 'none', active_only]
    
    if not force_refresh:
        cached = global_cache.get(cache_key)
        if cached:
            logger.info("✅ Returning cached Google Ads data")
            return cached
    
    if not ads_manager.client or not ads_manager.connected:
        return None
    
    all_campaigns = []
    
    # Parallel fetch from multiple accounts if available
    if len(ads_manager.customer_ids) > 1:
        fetch_funcs = {}
        for customer_id in ads_manager.customer_ids:
            fetch_funcs[customer_id] = lambda cid=customer_id: fetch_single_account(
                ads_manager, cid, start_date, end_date, active_only
            )
        
        results = parallel_fetch(fetch_funcs, timeout=PERFORMANCE_CONFIG['api_timeout'])
        
        for customer_id, campaigns in results.items():
            if campaigns:
                all_campaigns.extend(campaigns)
                logger.info(f"✅ Fetched {len(campaigns)} campaigns from {customer_id}")
    else:
        # Single account, fetch normally
        campaigns = fetch_single_account(
            ads_manager, 
            ads_manager.customer_ids[0], 
            start_date, 
            end_date, 
            active_only
        )
        if campaigns:
            all_campaigns = campaigns
    
    # Cache results
    global_cache.set(cache_key, all_campaigns)
    
    # If single day, also cache in daily cache with longer TTL
    if start_date and end_date and start_date == end_date:
        daily_cache.set_day(start_date, all_campaigns, f'google_ads_{active_only}')
    
    return all_campaigns

def fetch_single_account(ads_manager, customer_id, start_date, end_date, active_only):
    """Helper function to fetch from a single Google Ads account"""
    try:
        ga_service = ads_manager.client.get_service("GoogleAdsService")
        
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
        
        status_filter = "AND campaign.status = 'ENABLED'" if active_only else ""
        
        # Optimized query with only needed fields
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
            LIMIT 200
        """
        
        response = ga_service.search_stream(customer_id=customer_id, query=query)
        
        campaigns = []
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
                campaigns.append(campaign_data)
        
        return campaigns
        
    except Exception as e:
        logger.error(f"Error fetching from {customer_id}: {e}")
        return []

def optimize_litify_fetch(litify_manager, start_date=None, end_date=None, limit=1000,
                         include_spam=False, include_abandoned=False, include_duplicate=False,
                         force_refresh=False, count_by_conversion_date=True):
    """
    Optimized Litify fetch with caching and batching.
    Now optimized for single-day fetches.
    """
    from datetime import datetime
    
    # Special handling for single-day fetches
    if start_date and end_date and start_date == end_date:
        if not force_refresh:
            # Check daily cache first
            cache_type = f'litify_{include_spam}_{include_abandoned}_{include_duplicate}'
            cached = daily_cache.get_day(start_date, cache_type)
            if cached:
                logger.info(f"✅ Returning daily cached Litify data for {start_date}")
                return cached
    
    # Regular cache
    cache_key = ['litify', start_date or 'none', end_date or 'none', limit, 
                 include_spam, include_abandoned, include_duplicate, count_by_conversion_date]
    
    if not force_refresh:
        cached = global_cache.get(cache_key)
        if cached:
            logger.info("✅ Returning cached Litify data")
            return cached
    
    if not litify_manager.client or not litify_manager.connected:
        return litify_manager.get_demo_litify_leads(include_spam, include_abandoned, include_duplicate)
    
    all_records = []
    
    # Query 1: Leads CREATED in date range (for lead metrics)
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
        AND CreatedDate >= {start_date if start_date else datetime.now().strftime('%Y-%m-%d')}T00:00:00Z 
        AND CreatedDate <= {end_date if end_date else datetime.now().strftime('%Y-%m-%d')}T23:59:59Z
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
        AND Retainer_Signed_Date__c >= {start_date if start_date else datetime.now().strftime('%Y-%m-%d')} 
        AND Retainer_Signed_Date__c <= {end_date if end_date else datetime.now().strftime('%Y-%m-%d')}
        ORDER BY Retainer_Signed_Date__c DESC
        LIMIT {limit}
    """
    
    try:
        # Execute both queries
        created_leads = {}
        converted_leads = {}
        
        # Get leads created in period
        logger.info("Fetching leads CREATED in date range...")
        result = litify_manager.client.query(leads_query)
        for record in result['records']:
            created_leads[record['Id']] = record
        
        # Get leads converted in period
        logger.info("Fetching leads CONVERTED in date range...")
        result = litify_manager.client.query(conversions_query)
        for record in result['records']:
            converted_leads[record['Id']] = record
        
        # Merge the results intelligently
        all_records_dict = created_leads.copy()
        
        # Add conversions that weren't created in this period
        for lead_id, lead_data in converted_leads.items():
            if lead_id not in all_records_dict:
                # Mark this as a conversion from a previous period
                lead_data['from_previous_period'] = True
                all_records_dict[lead_id] = lead_data
        
        all_records = list(all_records_dict.values())
        
        # Process leads - same as before
        leads = []
        excluded_count = 0
        
        # Get IN_PRACTICE_CASE_TYPES and EXCLUDED_CASE_TYPES
        try:
            from app import IN_PRACTICE_CASE_TYPES, EXCLUDED_CASE_TYPES, UTM_TO_BUCKET_MAPPING
        except ImportError:
            IN_PRACTICE_CASE_TYPES = [
                'Pedestrian', 'Automobile Accident', 'Wrongful Death', 'Premise Liability',
                'Public Entity', 'Personal injury', 'Habitability', 'Automobile Accident - Commercial',
                'Bicycle', 'Animal Incident', 'Wildfire 2025', 'Motorcycle', 'Slip and Fall',
                'Electric Scooter', 'Mold', 'Product Liability'
            ]
            EXCLUDED_CASE_TYPES = ['Spam', 'Abandoned', 'Duplicate']
            UTM_TO_BUCKET_MAPPING = {}
        
        for record in all_records:
            # Get UTM Campaign
            utm_campaign = record.get('litify_pm__UTM_Campaign__c', '')
            
            # Get case type NAME from relationship field
            case_type = ''
            if 'litify_pm__Case_Type__r' in record and record['litify_pm__Case_Type__r']:
                case_type = record['litify_pm__Case_Type__r'].get('Name', '')
            
            # Determine if in practice
            in_practice = False
            if case_type and case_type in IN_PRACTICE_CASE_TYPES:
                in_practice = True
            
            # Check if it's an excluded type
            is_excluded = case_type in EXCLUDED_CASE_TYPES
            
            # Track and skip excluded types if not included
            if is_excluded:
                excluded_count += 1
                if case_type == 'Spam' and not include_spam:
                    continue
                elif case_type == 'Abandoned' and not include_abandoned:
                    continue
                elif case_type == 'Duplicate' and not include_duplicate:
                    continue
            
            # Check for companion case
            has_companion = bool(record.get('litify_ext__Companion__c'))
            
            # Determine conversion status
            retainer_signed = record.get('Retainer_Signed_Date__c')
            status = record.get('litify_pm__Status__c', '')
            display_name = (record.get('litify_pm__Display_Name__c', '') or '').lower()
            is_dropped = record.get('isDroppedatIntake__c', False)
            
            # Status values that indicate successful conversion
            CONVERTED_STATUSES = ['Retained', 'Converted', 'Signed']
            
            # Check if converted
            is_converted = (
                (retainer_signed is not None or status in CONVERTED_STATUSES) and 
                status not in ['Converted DAI', 'Referred Out'] and
                not is_dropped and
                display_name != 'test'
            )
            
            # Check if pending
            is_pending = status == 'Retainer Sent'
            
            # Map UTM Campaign to bucket
            bucket = UTM_TO_BUCKET_MAPPING.get(utm_campaign, '')
            if not bucket and utm_campaign:
                utm_lower = utm_campaign.lower()
                for utm_key, bucket_name in UTM_TO_BUCKET_MAPPING.items():
                    if utm_key.lower() == utm_lower:
                        bucket = bucket_name
                        break
            
            # Build Salesforce URL
            instance_url = litify_manager.client.base_url if litify_manager.client else ""
            if '.my.salesforce.com' in instance_url:
                instance_name = instance_url.split('//')[1].split('.')[0]
                salesforce_url = f"https://{instance_name}.lightning.force.com/lightning/r/litify_pm__Intake__c/{record.get('Id')}/view"
            else:
                salesforce_url = f"https://sweetjames.lightning.force.com/lightning/r/litify_pm__Intake__c/{record.get('Id')}/view"
            
            # Build lead data object
            lead_data = {
                'id': record.get('Id', ''),
                'salesforce_url': salesforce_url,
                'created_date': record.get('CreatedDate', ''),
                'status': status or 'Unknown',
                'client_name': (
                    record.get('litify_pm__Display_Name__c', '') or
                    record.get('Client_Name__c', '') or
                    f"{record.get('litify_pm__First_Name__c', '')} {record.get('litify_pm__Last_Name__c', '')}".strip() or
                    record.get('Name', '') or
                    'Unknown'
                ),
                'is_converted': is_converted,
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
                'from_previous_period': record.get('from_previous_period', False),
                'count_for_leads': not record.get('from_previous_period', False),
                'count_for_conversions': is_converted
            }
            
            leads.append(lead_data)
        
        logger.info(f"✅ Fetched {len(leads)} total records")
        logger.info(f"   - {len(created_leads)} created in period")
        logger.info(f"   - {len(converted_leads)} converted in period")
        logger.info(f"   - {len([l for l in leads if l['from_previous_period']])} conversions from previous periods")
        
        # Cache the processed results
        global_cache.set(cache_key, leads)
        
        # If single day, also cache in daily cache
        if start_date and end_date and start_date == end_date:
            cache_type = f'litify_{include_spam}_{include_abandoned}_{include_duplicate}'
            daily_cache.set_day(start_date, leads, cache_type)
        
        return leads
        
    except Exception as e:
        logger.error(f"❌ Litify query error: {e}")
        # Return demo data on error
        return litify_manager.get_demo_litify_leads(include_spam, include_abandoned, include_duplicate)

def warm_cache_for_month(ads_manager, litify_manager, year=None, month=None):
    """
    Pre-warm the cache for an entire month by fetching all days.
    Useful for pre-loading data during off-peak hours.
    """
    from datetime import date, timedelta
    
    if not year or not month:
        now = datetime.now()
        year = now.year
        month = now.month
    
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    today = datetime.now().date()
    
    logger.info(f"🔥 Warming cache for {year}-{month:02d}")
    
    current = month_start
    days_cached = 0
    
    while current <= min(month_end, today):
        date_str = current.strftime('%Y-%m-%d')
        
        # Check if already cached
        if not daily_cache.get_day(date_str, 'combined'):
            # Fetch and cache
            if ads_manager and ads_manager.connected:
                ads_manager.fetch_campaigns(date_str, date_str, active_only=False)
            
            if litify_manager and litify_manager.connected:
                litify_manager.fetch_detailed_leads(date_str, date_str, limit=500)
            
            days_cached += 1
            logger.info(f"  Cached {date_str}")
        else:
            logger.info(f"  Skipped {date_str} (already cached)")
        
        current += timedelta(days=1)
    
    logger.info(f"✅ Cache warmed: {days_cached} new days cached")
    return days_cached

def enable_compression(app):
    """
    Enable gzip compression for Flask app.
    Call this after creating your Flask app:
    
    app = Flask(__name__)
    enable_compression(app)
    """
    if COMPRESS_AVAILABLE:
        Compress(app)
        logger.info("✅ Response compression enabled")
    else:
        logger.warning("⚠️ Compression not available - install flask-compress")
    return app

def create_performance_endpoints(app, cache=None):
    """
    Add performance monitoring endpoints to your Flask app.
    
    Usage:
        create_performance_endpoints(app)
    """
    if cache is None:
        cache = global_cache
    
    @app.route('/api/performance/stats')
    def performance_stats():
        """Get performance statistics"""
        return {
            'cache': cache.get_stats(),
            'daily_cache': daily_cache.get_stats(),
            'config': PERFORMANCE_CONFIG,
            'compression': COMPRESS_AVAILABLE
        }
    
    @app.route('/api/performance/clear-cache', methods=['POST'])
    def clear_cache():
        """Clear the cache"""
        cache.clear()
        daily_cache.clear()
        return {'success': True, 'message': 'All caches cleared'}
    
    @app.route('/api/performance/clear-month-cache/<int:year>/<int:month>', methods=['POST'])
    def clear_month_cache(year, month):
        """Clear cache for a specific month"""
        cleared = daily_cache.clear_month(year, month)
        return {'success': True, 'message': f'Cleared {cleared} entries for {year}-{month:02d}'}
    
    @app.route('/api/performance/warm-cache', methods=['POST'])
    def warm_cache_endpoint():
        """Warm the cache for the current month"""
        from app import ads_manager, litify_manager
        days_cached = warm_cache_for_month(ads_manager, litify_manager)
        return {'success': True, 'days_cached': days_cached}
    
    logger.info("✅ Performance endpoints added")

def optimize_app(app, ads_manager=None, litify_manager=None):
    """
    Apply all optimizations to your Flask app.
    
    Usage:
        from performance_boost import optimize_app
        optimize_app(app, ads_manager, litify_manager)
    """
    # Enable compression
    enable_compression(app)
    
    # Add performance endpoints
    create_performance_endpoints(app)
    
    # Replace fetch methods with optimized versions if managers provided
    if ads_manager:
        ads_manager.fetch_campaigns_original = ads_manager.fetch_campaigns
        ads_manager.fetch_campaigns = lambda *args, **kwargs: optimize_google_ads_fetch(ads_manager, *args, **kwargs)
        logger.info("✅ Google Ads fetch optimized")
    
    if litify_manager:
        litify_manager.fetch_detailed_leads_original = litify_manager.fetch_detailed_leads
        # Make sure wrapper accepts and passes force_refresh
        litify_manager.fetch_detailed_leads = lambda *args, **kwargs: optimize_litify_fetch(
            litify_manager, *args, **kwargs
        )
        logger.info("✅ Litify fetch optimized")
    
    logger.info("✅ App optimization complete!")
    
    return app

# Export all utilities
__all__ = [
    'SmartCache',
    'global_cache',
    'daily_cache',
    'DailyDataCache',
    'warm_cache_for_month',
    'time_it',
    'parallel_fetch',
    'optimize_google_ads_fetch',
    'optimize_litify_fetch',
    'enable_compression',
    'create_performance_endpoints',
    'BackgroundRefresher',
    'optimize_app',
    'PERFORMANCE_CONFIG'
]