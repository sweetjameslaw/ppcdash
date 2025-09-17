"""
Global state management for the application
Provides centralized access to manager instances and application state
"""

# Global references to managers
ads_manager = None
litify_manager = None

def set_managers(ads_mgr, litify_mgr):
    """Set the global manager references"""
    global ads_manager, litify_manager
    ads_manager = ads_mgr
    litify_manager = litify_mgr

def get_ads_manager():
    """Get the Google Ads manager instance"""
    return ads_manager

def get_litify_manager():
    """Get the Litify manager instance"""
    return litify_manager

def get_managers():
    """Get both manager instances"""
    return ads_manager, litify_manager

def clear_managers():
    """Clear the global manager references"""
    global ads_manager, litify_manager
    ads_manager = None
    litify_manager = None