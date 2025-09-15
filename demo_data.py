#!/usr/bin/env python3
"""
Demo Data Module for Sweet James Dashboard
Contains all demo/sample data for testing when APIs are not connected
"""

from datetime import datetime, timedelta
import random

# Campaign Bucket Mapping Configuration (for demo purposes)
DEMO_CAMPAIGN_BUCKETS = {
    "California Brand": ["CA-EN-Brand"],
    "California Prospecting": [
        "GS_NonBrand - CA",
        "CA-Pmax-EN-MVA",
        "CA-SF-Pmax-EN-MVA",
        "CA-SC-Pmax-EN-MVA",
        "SC-S-EN-MVA Manual w/ ECPC"
    ],
    "California LSA": [
        "LocalServicesCampaign:CA",
        "CA-NB-LSA", 
        "CA-LA-LSA"
    ],
    "Arizona Brand": ["AZ-EN-Brand", "GS_Brand - AZ"],
    "Arizona Prospecting": [
        "GS_NonBrand - AZ",
        "AZ-Pmax-EN-MVA",
        "AZ-PX-Pmax-EN-MVA",
        "PMAX_AZ"
    ],
    "Arizona LSA": [
        "LocalServicesCampaign:AZ",
        "AZ-PX-LSA"
    ],
    "Georgia Brand": [
        "GA-EN-Brand",
        "GS_Brand - GA",
        "GS_Brand - GA - ATLPI"
    ],
    "Georgia Prospecting": [
        "GS_NonBrand - GA",
        "GS_NonBrand - GA - ATLPI",
        "GA-AT-Pmax-EN-MVA",
        "PMAX_GA"
    ],
    "Georgia LSA": [
        "LocalServicesCampaign:GA",
        "GA-RO-LSA"
    ],
    "Texas Brand": ["TX-EN-Brand"],
    "Texas LSA": ["LocalServicesCampaign:TX"]
}

# Demo UTM to Bucket Mapping
DEMO_UTM_TO_BUCKET_MAPPING = {
    # California Brand
    "CA-EN-Brand": "California Brand",
    
    # California Prospecting
    "gs_nonbrand-ca": "California Prospecting",
    "ca-pmax-en-mva": "California Prospecting",
    "pmax_ca": "California Prospecting",
    
    # California LSA
    "CA-NB-LSA": "California LSA",
    "CA-LA-LSA": "California LSA",
    
    # Arizona Brand  
    "AZ-EN-Brand": "Arizona Brand",
    "gs_brand-az": "Arizona Brand",
    
    # Arizona Prospecting
    "gs_nonbrand-az": "Arizona Prospecting",
    "pmax_az": "Arizona Prospecting",
    
    # Arizona LSA
    "AZ-PX-LSA": "Arizona LSA",
    
    # Georgia Brand
    "GA-EN-Brand": "Georgia Brand",
    
    # Georgia Prospecting
    "gs_nonbrand-ga": "Georgia Prospecting",
    "gs_nonbrand-ga-atlpi": "Georgia Prospecting",
    "pmax_ga": "Georgia Prospecting",
    
    # Georgia LSA
    "GA-RO-LSA": "Georgia LSA",
    
    # Texas Brand
    "TX-EN-Brand": "Texas Brand",
    
    # GMB and other sources
    "GMB - Newport Beach": "California Prospecting",
}

# Demo campaign names
DEMO_CAMPAIGNS = [
    "CA-EN-Brand",
    "GS_NonBrand - CA",
    "CA-Pmax-EN-MVA",
    "CA-SF-Pmax-EN-MVA",
    "CA-SC-Pmax-EN-MVA",
    "SC-S-EN-MVA Manual w/ ECPC",
    "LocalServicesCampaign:CA",
    "CA-NB-LSA",
    "CA-LA-LSA",
    "AZ-EN-Brand",
    "GS_Brand - AZ",
    "GS_NonBrand - AZ",
    "AZ-Pmax-EN-MVA",
    "AZ-PX-Pmax-EN-MVA",
    "PMAX_AZ",
    "LocalServicesCampaign:AZ",
    "AZ-PX-LSA",
    "GA-EN-Brand",
    "GS_Brand - GA",
    "GS_Brand - GA - ATLPI",
    "GS_NonBrand - GA",
    "GS_NonBrand - GA - ATLPI",
    "GA-AT-Pmax-EN-MVA",
    "PMAX_GA",
    "LocalServicesCampaign:GA",
    "GA-RO-LSA",
    "TX-EN-Brand",
    "LocalServicesCampaign:TX"
]

def get_demo_bucket_data(include_spam=False, include_abandoned=False, include_duplicate=False):
    """Return comprehensive demo data with realistic LSA numbers and exclusion filters"""
    # Adjust lead counts based on inclusion filters
    base_leads = 220
    if include_spam:
        base_leads += 10
    if include_abandoned:
        base_leads += 8
    if include_duplicate:
        base_leads += 7
    
    # Define bucket priority for demo data
    bucket_priority = [
        "California Brand", "California Prospecting", "California LSA",
        "Arizona Brand", "Arizona Prospecting", "Arizona LSA",
        "Georgia Brand", "Georgia Prospecting", "Georgia LSA",
        "Texas Brand", "Texas Prospecting", "Texas LSA"
    ]
    
    return {
        'buckets': [
            {
                'name': 'California Brand',
                'state': 'California',
                'campaigns': ['CA-EN-Brand'],
                'cost': 120000,
                'leads': base_leads,
                'inPractice': 180,
                'inPracticePercent': 0.818 if base_leads == 220 else 180/base_leads,
                'unqualified': 40,  
                'unqualifiedPercent': 0.222,  
                'costPerLead': 120000/base_leads,
                'cases': 45,  
                'cpa': 2667,
                'retainers': 60,  
                'pendingRetainers': 5,  
                'totalRetainers': 65,  
                'costPerRetainer': 1846,
                'conversionRate': 0.361  
            },
            {
                'name': 'California Prospecting',
                'state': 'California',
                'campaigns': ['GS_NonBrand - CA', 'CA-Pmax-EN-MVA'],
                'cost': 180000,
                'leads': 380 + (15 if include_spam else 0) + (10 if include_abandoned else 0) + (8 if include_duplicate else 0),
                'inPractice': 300,
                'inPracticePercent': 300/(380 + (15 if include_spam else 0) + (10 if include_abandoned else 0) + (8 if include_duplicate else 0)),
                'unqualified': 75,  
                'unqualifiedPercent': 0.250,  
                'costPerLead': 180000/(380 + (15 if include_spam else 0) + (10 if include_abandoned else 0) + (8 if include_duplicate else 0)),
                'cases': 70,  
                'cpa': 2571,
                'retainers': 90,  
                'pendingRetainers': 5,  
                'totalRetainers': 95,  
                'costPerRetainer': 1895,
                'conversionRate': 0.317  
            },
            {
                'name': 'California LSA',
                'state': 'California',
                'campaigns': ['CA-NB-LSA', 'CA-LA-LSA'],
                'cost': 85000,
                'leads': 150,
                'inPractice': 135,
                'inPracticePercent': 0.900,
                'unqualified': 20,
                'unqualifiedPercent': 0.148,
                'costPerLead': 567,
                'cases': 35,
                'cpa': 2429,
                'retainers': 50,
                'pendingRetainers': 8,
                'totalRetainers': 58,
                'costPerRetainer': 1466,
                'conversionRate': 0.430
            },
            {
                'name': 'Arizona Brand',
                'state': 'Arizona',
                'campaigns': ['AZ-EN-Brand'],
                'cost': 50000,
                'leads': 80,
                'inPractice': 65,
                'inPracticePercent': 0.813,
                'unqualified': 20,
                'unqualifiedPercent': 0.308,
                'costPerLead': 625,
                'cases': 15,
                'cpa': 3333,
                'retainers': 20,
                'pendingRetainers': 2,
                'totalRetainers': 22,
                'costPerRetainer': 2273,
                'conversionRate': 0.338
            },
            {
                'name': 'Arizona Prospecting',
                'state': 'Arizona',
                'campaigns': ['GS_NonBrand - AZ', 'PMAX_AZ'],
                'cost': 120000,
                'leads': 200,
                'inPractice': 150,
                'inPracticePercent': 0.750,
                'unqualified': 50,
                'unqualifiedPercent': 0.333,
                'costPerLead': 600,
                'cases': 25,
                'cpa': 4800,
                'retainers': 35,
                'pendingRetainers': 3,
                'totalRetainers': 38,
                'costPerRetainer': 3158,
                'conversionRate': 0.253
            }
        ],
        'unmapped_campaigns': [],
        'unmapped_utms': [],
        'litify_leads': [],
        'available_buckets': bucket_priority,
        'excluded_lead_counts': {
            'spam': 25 if include_spam else 0,
            'abandoned': 18 if include_abandoned else 0,
            'duplicate': 15 if include_duplicate else 0,
            'total': (25 if include_spam else 0) + (18 if include_abandoned else 0) + (15 if include_duplicate else 0)
        }
    }

def get_demo_litify_leads(utm_to_bucket_mapping, include_spam=False, include_abandoned=False, include_duplicate=False):
    """Return demo Litify leads data with bucket mapping and exclusion filters"""
    demo_leads = []
    statuses = ['Open', 'Working', 'Under Review', 'Retainer Sent', 'Signed', 'Unqualified', 'Converted DAI', 'Referred Out']
    case_types = ['Motor Vehicle Accident', 'Slip and Fall', 'Dog Bite', 'Premises Liability', 'Wrongful Death', 
                  'Product Liability', 'Spam', 'Abandoned', 'Duplicate']
    utm_campaigns = ['CA-EN-Brand', 'CA-Pmax-EN-MVA', 'gs_nonbrand-ca', 'gs_brand-az', 'pmax_az', 'gs_brand-ga', 
                     'CA-NB-LSA', 'CA-LA-LSA', 'AZ-PX-LSA', 'GA-RO-LSA']
    
    # Create some cases with companions (using matter_id to group them)
    case_groups = [
        {'matter_id': 'MATTER001', 'case_id': 'CASE001', 'num_companions': 3, 'converted': True},
        {'matter_id': 'MATTER002', 'case_id': 'CASE002', 'num_companions': 1, 'converted': True},
        {'matter_id': 'MATTER003', 'case_id': 'CASE003', 'num_companions': 2, 'converted': False},
        {'matter_id': '', 'case_id': 'CASE004', 'num_companions': 0, 'converted': True},
        {'matter_id': 'MATTER005', 'case_id': 'CASE005', 'num_companions': 4, 'converted': False},
    ]
    
    # Add some spam/abandoned/duplicate leads for testing
    excluded_leads_data = [
        {'case_type': 'Spam', 'include': include_spam},
        {'case_type': 'Abandoned', 'include': include_abandoned},
        {'case_type': 'Duplicate', 'include': include_duplicate},
        {'case_type': 'Spam', 'include': include_spam},
        {'case_type': 'Abandoned', 'include': include_abandoned},
    ]
    
    lead_id = 0
    
    # Add excluded type leads
    for excluded_data in excluded_leads_data:
        if not excluded_data['include']:
            continue  # Skip if not included
            
        lead_time = datetime.now() - timedelta(hours=lead_id*2)
        case_type = excluded_data['case_type']
        in_practice = False  # Excluded types are not in practice
        utm_campaign = utm_campaigns[lead_id % len(utm_campaigns)]
        bucket = utm_to_bucket_mapping.get(utm_campaign, '')
        
        demo_leads.append({
            'id': f'DEMO{lead_id:04d}',
            'salesforce_url': f'https://sweetjames.lightning.force.com/lightning/r/litify_pm__Intake__c/DEMO{lead_id:04d}/view',
            'created_date': lead_time.isoformat(),
            'status': 'Unqualified',
            'client_name': f'{case_type} Lead {lead_id+1}',
            'is_converted': False,
            'is_pending': False,
            'case_type': case_type,
            'in_practice': in_practice,
            'utm_campaign': utm_campaign,
            'bucket': bucket,
            'is_excluded_type': True,
            'has_companion': False,
            'matter_id': '',
            'companion_case_id': '',
            'is_dropped': False,
        })
        lead_id += 1
    
    # Add regular demo leads
    for case_group in case_groups:
        # Main lead
        lead_time = datetime.now() - timedelta(hours=lead_id*2)
        status = 'Signed' if case_group['converted'] else statuses[lead_id % len(statuses)]
        case_type = case_types[lead_id % 6]  # Only use first 6 (non-excluded) case types
        utm_campaign = utm_campaigns[lead_id % len(utm_campaigns)]
        bucket = utm_to_bucket_mapping.get(utm_campaign, '')
        
        # Determine in_practice based on case type (exclude spam, abandoned, duplicate)
        in_practice = case_type not in ['Spam', 'Abandoned', 'Duplicate']
        is_converted = case_group['converted']
        is_pending = status == 'Retainer Sent'
        is_dropped = False
        
        demo_leads.append({
            'id': f'DEMO{lead_id:04d}',
            'salesforce_url': f'https://sweetjames.lightning.force.com/lightning/r/litify_pm__Intake__c/DEMO{lead_id:04d}/view',
            'created_date': lead_time.isoformat(),
            'status': status,
            'client_name': f'Demo Client {lead_id+1}',
            'is_converted': is_converted,
            'is_pending': is_pending,
            'case_type': case_type,
            'in_practice': in_practice,
            'utm_campaign': utm_campaign,
            'bucket': bucket,
            'is_excluded_type': False,
            'has_companion': case_group['num_companions'] > 0,
            'matter_id': case_group['matter_id'],
            'companion_case_id': f"CASE{lead_id+1:03d}" if case_group['num_companions'] > 0 else '',
            'is_dropped': is_dropped,
        })
        lead_id += 1
        
        # Add companion leads
        for comp_idx in range(case_group['num_companions']):
            lead_time = datetime.now() - timedelta(hours=lead_id*2)
            status = 'Signed' if case_group['converted'] else statuses[lead_id % len(statuses)]
            case_type = case_types[lead_id % 6]
            utm_campaign = utm_campaigns[lead_id % len(utm_campaigns)]
            bucket = utm_to_bucket_mapping.get(utm_campaign, '')
            
            in_practice = case_type not in ['Spam', 'Abandoned', 'Duplicate']
            is_converted = case_group['converted']
            is_pending = status == 'Retainer Sent'
            
            demo_leads.append({
                'id': f'DEMO{lead_id:04d}',
                'salesforce_url': f'https://sweetjames.lightning.force.com/lightning/r/litify_pm__Intake__c/DEMO{lead_id:04d}/view',
                'created_date': lead_time.isoformat(),
                'status': status,
                'client_name': f'Demo Companion {lead_id+1}',
                'is_converted': is_converted,
                'is_pending': is_pending,
                'case_type': case_type,
                'in_practice': in_practice,
                'utm_campaign': utm_campaign,
                'bucket': bucket,
                'is_excluded_type': False,
                'has_companion': True,
                'matter_id': case_group['matter_id'],
                'companion_case_id': case_group['case_id'],
                'is_dropped': is_dropped,
            })
            lead_id += 1
    
    return demo_leads

def get_demo_pacing_data():
    """Return demo pacing data for states"""
    return {
        'states': {
            'CA': {
                'spend': 450000,
                'leads': 650,
                'cases': 140,
                'retainers': 160
            },
            'AZ': {
                'spend': 200000,
                'leads': 180,
                'cases': 40,
                'retainers': 45
            },
            'GA': {
                'spend': 75000,
                'leads': 110,
                'cases': 24,
                'retainers': 28
            },
            'TX': {
                'spend': 0,
                'leads': 0,
                'cases': 0,
                'retainers': 0
            }
        }
    }

def get_demo_monthly_summary():
    """Generate demo monthly summary data for annual analytics"""
    return {
        'spend': random.randint(500000, 1500000),
        'leads': random.randint(400, 800),
        'cases': random.randint(80, 200),
        'retainers': random.randint(100, 250),
        'in_practice': random.randint(350, 700),
        'unqualified': random.randint(50, 150),
        'cpl': 0,
        'cpa': 0,
        'cpr': 0,
        'conversion_rate': 0
    }

def get_demo_forecast_data():
    """Return demo forecast data"""
    return {
        'current_month_actual': {
            'spend': 750000,
            'leads': 550,
            'retainers': 120,
            'cases': 95
        },
        'projection': {
            'total_spend': 1200000,
            'total_leads': 880,
            'total_retainers': 192,
            'total_cases': 152
        },
        'daily_average': {
            'spend': 38710,
            'leads': 28,
            'retainers': 6,
            'cases': 5
        },
        'remaining': {
            'days': 15,
            'spend': 450000,
            'leads': 330,
            'retainers': 72,
            'cases': 57
        }
    }


# Add this function to your demo_data.py file

def get_demo_current_month_daily():
    """
    Generate demo data for current month daily performance
    Used as fallback when APIs are not available
    """
    from datetime import datetime, date, timedelta
    import calendar
    import random
    
    now = datetime.now()
    month_start = date(now.year, now.month, 1)
    month_end = date(now.year, now.month, calendar.monthrange(now.year, now.month)[1])
    today = now.date()
    
    daily_data = []
    month_totals = {
        'total_spend': 0,
        'total_leads': 0,
        'total_cases': 0,
        'total_retainers': 0,
        'total_in_practice': 0,
        'total_unqualified': 0
    }
    
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
    
    available_buckets = [
        "California Brand",
        "California Prospecting",
        "California LSA",
        "Arizona Brand",
        "Arizona LSA",
        "Georgia Brand",
        "Georgia LSA",
        "Texas Brand"
    ]
    
    previous_day_data = None
    
    # Generate data for each day up to today
    for day_num in range(1, min(today.day + 1, month_end.day + 1)):
        current_date = date(now.year, now.month, day_num)
        date_str = current_date.strftime('%Y-%m-%d')
        
        # Generate random but realistic data
        is_weekend = current_date.weekday() >= 5
        
        # Lower metrics on weekends
        weekend_factor = 0.7 if is_weekend else 1.0
        
        # Base metrics with some randomness
        spend = random.randint(45000, 75000) * weekend_factor
        leads = random.randint(35, 65) * weekend_factor
        in_practice = int(leads * random.uniform(0.7, 0.9))
        retainers = int(in_practice * random.uniform(0.20, 0.35))
        cases = int(retainers * random.uniform(0.75, 0.95))
        unqualified = in_practice - retainers
        
        day_data = {
            'date': date_str,
            'dayNum': day_num,
            'dayName': current_date.strftime('%a'),
            'isToday': current_date == today,
            'isFuture': False,
            'isWeekend': is_weekend,
            'spend': spend,
            'leads': leads,
            'inPractice': in_practice,
            'unqualified': unqualified,
            'cases': cases,
            'retainers': retainers,
            'cpl': round(spend / leads, 2) if leads > 0 else 0,
            'cpa': round(spend / cases, 2) if cases > 0 else 0,
            'cpr': round(spend / retainers, 2) if retainers > 0 else 0,
            'convRate': round((retainers / in_practice) * 100, 1) if in_practice > 0 else 0,
            'buckets': []
        }
        
        # Generate bucket breakdown
        bucket_allocations = {
            "California Brand": 0.25,
            "California Prospecting": 0.20,
            "California LSA": 0.15,
            "Arizona Brand": 0.15,
            "Arizona LSA": 0.10,
            "Georgia Brand": 0.08,
            "Georgia LSA": 0.05,
            "Texas Brand": 0.02
        }
        
        for bucket_name, allocation in bucket_allocations.items():
            bucket_spend = spend * allocation * random.uniform(0.8, 1.2)
            bucket_leads = int(leads * allocation * random.uniform(0.7, 1.3))
            bucket_in_practice = int(bucket_leads * random.uniform(0.7, 0.9))
            bucket_retainers = int(bucket_in_practice * random.uniform(0.20, 0.35))
            
            bucket_data = {
                'name': bucket_name,
                'spend': round(bucket_spend, 2),
                'leads': bucket_leads,
                'inPractice': bucket_in_practice,
                'unqualified': bucket_in_practice - bucket_retainers,
                'cases': int(bucket_retainers * 0.85),
                'retainers': bucket_retainers,
                'cpl': round(bucket_spend / bucket_leads, 2) if bucket_leads > 0 else 0,
                'cpa': round(bucket_spend / (bucket_retainers * 0.85), 2) if bucket_retainers > 0 else 0,
                'cpr': round(bucket_spend / bucket_retainers, 2) if bucket_retainers > 0 else 0,
                'convRate': round((bucket_retainers / bucket_in_practice) * 100, 1) if bucket_in_practice > 0 else 0
            }
            
            # Add deltas for buckets
            if previous_day_data:
                prev_bucket = next((b for b in previous_day_data.get('buckets', []) if b['name'] == bucket_name), None)
                if prev_bucket:
                    bucket_data['spendDelta'] = round(
                        ((bucket_data['spend'] - prev_bucket['spend']) / prev_bucket['spend'] * 100) 
                        if prev_bucket['spend'] > 0 else 0, 1
                    )
                    bucket_data['leadsDelta'] = bucket_data['leads'] - prev_bucket['leads']
                else:
                    bucket_data['spendDelta'] = None
                    bucket_data['leadsDelta'] = None
            else:
                bucket_data['spendDelta'] = None
                bucket_data['leadsDelta'] = None
            
            day_data['buckets'].append(bucket_data)
        
        # Calculate deltas vs previous day
        if previous_day_data:
            day_data['spendDelta'] = round(
                ((day_data['spend'] - previous_day_data['spend']) / previous_day_data['spend'] * 100) 
                if previous_day_data['spend'] > 0 else 0, 1
            )
            day_data['leadsDelta'] = day_data['leads'] - previous_day_data['leads']
            day_data['casesDelta'] = day_data['cases'] - previous_day_data['cases']
            day_data['retainersDelta'] = day_data['retainers'] - previous_day_data['retainers']
            day_data['cplDelta'] = round(
                ((day_data['cpl'] - previous_day_data['cpl']) / previous_day_data['cpl'] * 100) 
                if previous_day_data['cpl'] > 0 else 0, 1
            )
            day_data['cpaDelta'] = round(
                ((day_data['cpa'] - previous_day_data['cpa']) / previous_day_data['cpa'] * 100) 
                if previous_day_data['cpa'] > 0 else 0, 1
            )
            day_data['convDelta'] = round(day_data['convRate'] - previous_day_data['convRate'], 1)
        else:
            day_data['spendDelta'] = None
            day_data['leadsDelta'] = None
            day_data['casesDelta'] = None
            day_data['retainersDelta'] = None
            day_data['cplDelta'] = None
            day_data['cpaDelta'] = None
            day_data['convDelta'] = None
        
        # Update totals
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
            
            if not worst_days['lowest_conversion'] or day_data['convRate'] < worst_days['lowest_conversion']['convRate']:
                worst_days['lowest_conversion'] = {
                    'date': date_str,
                    'convRate': day_data['convRate'],
                    'retainers': day_data['retainers']
                }
        
        # Track inefficient days (high spend, low returns)
        efficiency_score = day_data['retainers'] / (day_data['spend'] / 10000) if day_data['spend'] > 0 else 0
        if not worst_days['inefficient'] or efficiency_score < worst_days['inefficient']['efficiency']:
            worst_days['inefficient'] = {
                'date': date_str,
                'spend': day_data['spend'],
                'retainers': day_data['retainers'],
                'efficiency': efficiency_score
            }
        
        daily_data.append(day_data)
        previous_day_data = day_data
    
    # Add future days as empty
    for day_num in range(today.day + 1, month_end.day + 1):
        current_date = date(now.year, now.month, day_num)
        daily_data.append({
            'date': current_date.strftime('%Y-%m-%d'),
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
            'convDelta': None
        })
    
    # Calculate month summary
    days_elapsed = today.day
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
        'spendDelta': today_data['spendDelta'] if today_data else 0,
        'leadsDelta': today_data['leadsDelta'] if today_data else 0,
        'casesDelta': today_data['casesDelta'] if today_data else 0,
        'retainersDelta': today_data['retainersDelta'] if today_data else 0,
        'cplDelta': today_data['cplDelta'] if today_data else 0,
        'cpaDelta': today_data['cpaDelta'] if today_data else 0,
        'convDelta': today_data['convDelta'] if today_data else 0
    }
    
    return {
        'daily_data': daily_data,
        'month_summary': month_summary,
        'best_days': best_days,
        'worst_days': worst_days,
        'available_buckets': available_buckets,
        'data_source': 'Demo Data',
        'performance_stats': {
            'optimization': 'DEMO',
            'api_calls_saved': 0,
            'cache_stats': {'hits': 0, 'misses': 0, 'hit_rate': '0%'}
        },
        'timestamp': datetime.now().isoformat()
    }