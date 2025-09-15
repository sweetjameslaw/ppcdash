#!/usr/bin/env python3
"""
Enhanced Forecasting Endpoints for Sweet James Dashboard
Integrates with performance_boost.py for optimized caching and data fetching
"""

import calendar
from datetime import datetime, timedelta
from flask import jsonify, request
import logging

# Import performance optimization tools
from performance_boost import global_cache, daily_cache, time_it, parallel_fetch

logger = logging.getLogger(__name__)

# ==================== FORECASTING ENDPOINTS ====================

@app.route('/api/forecast-pacing')
@time_it
def api_forecast_pacing():
    """
    Get current month pacing data with performance optimization
    Leverages daily_cache for better performance
    """
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
    now = datetime.now()
    if start_date == datetime(now.year, now.month, 1).strftime('%Y-%m-%d'):
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