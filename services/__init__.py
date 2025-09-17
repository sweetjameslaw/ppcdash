"""
Services package initialization
"""

# Import and expose the state module
from . import state

# Import other services
try:
    from .google_ads_services import GoogleAdsManager
except ImportError:
    GoogleAdsManager = None

try:
    from .litify_services import LitifyManager
except ImportError:
    LitifyManager = None

__all__ = ['state', 'GoogleAdsManager', 'LitifyManager']