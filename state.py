"""
Shared state management for Sweet James Dashboard
Centralizes all global variables to avoid import/global issues
"""

from datetime import datetime

# Cache management
CACHE_DATA = None
CACHE_TIME = None
CACHE_DURATION = 300  # 5 minutes in seconds

# Campaign and UTM mappings
CAMPAIGN_BUCKETS = {}
UTM_TO_BUCKET_MAPPING = {}

# Bucket priority order for UI
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

# Manager instances (will be set by main app)
ads_manager = None
litify_manager = None

def clear_cache():
    """Helper function to clear cache"""
    global CACHE_DATA, CACHE_TIME
    CACHE_DATA = None
    CACHE_TIME = None

def set_managers(ads_mgr, litify_mgr):
    """Set manager instances from main app"""
    global ads_manager, litify_manager
    ads_manager = ads_mgr
    litify_manager = litify_mgr