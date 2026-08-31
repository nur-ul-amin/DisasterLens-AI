"""
social_scraper.py — Simulated Social Media Ingestion
=====================================================
Direct scraping of X/Twitter, Facebook, and Instagram is actively blocked 
without paid enterprise APIs. This module simulates web scraping by generating 
highly realistic synthetic social media posts based on current trends.

In production, this would be replaced with the official Twitter API V2 
or a Facebook Graph API client.
"""

import random
from datetime import datetime, timezone, timedelta
from typing import List

from news_aggregator.normalizer import NormalizedNewsItem

# High-risk locations in Pakistan for realistic simulation
HOTSPOTS = [
    ("Swat Valley", 35.2227, 72.4258),
    ("Nowshera", 34.0158, 71.9812),
    ("Sukkur", 27.7132, 68.8622),
    ("Dadu", 26.7329, 67.7763),
    ("Karachi", 24.8607, 67.0011),
    ("Muzaffarabad", 34.3621, 73.4711),
    ("Chitral", 35.8510, 71.7864),
    ("Quetta", 30.1798, 66.9750),
    ("Gwadar", 25.1216, 62.3254),
]

TEMPLATES = [
    ("Urgent: Heavy flooding observed near {location}. Water levels rising rapidly! #FloodPakistan #NDMA", "Flood"),
    ("Road completely washed away due to landslide near {location}. Avoid travel! #DisasterLens #Alert", "Landslide"),
    ("Felt a massive earthquake tremor here in {location} just now. Everything shook. #EarthquakePK", "Earthquake"),
    ("River Indus breaching banks at {location}. Villages are evacuating right now! #FloodWarning", "Flood"),
    ("Severe thunderstorm hitting {location}, power is out everywhere. Stay safe! #WeatherAlert", "Severe Storm"),
]

def _generate_mock_post() -> NormalizedNewsItem:
    location_name, lat, lng = random.choice(HOTSPOTS)
    template, cat = random.choice(TEMPLATES)
    
    text = template.format(location=location_name)
    
    # 30% chance this post was intercepted and verified by AIDR
    is_aidr = random.random() < 0.30
    
    if is_aidr:
        source = "AIDR"
        source_url = "https://aidr.qcri.org/"
        source_tier = 2
        base_trust_score = 85
        title = f"AIDR Classified: {cat} at {location_name}"
    else:
        source = random.choice(["X (Twitter)", "Facebook", "Instagram"])
        source_url = f"https://{source.split()[0].lower()}.com"
        source_tier = 4
        base_trust_score = 40
        title = f"Social Media Alert: {cat} at {location_name}"
    
    # Randomize time within last 4 hours
    published_at = datetime.now(timezone.utc) - timedelta(minutes=random.randint(5, 240))
    
    item_id = f"{source.split()[0].lower()}_{random.randint(10000, 99999)}"
    
    return NormalizedNewsItem(
        item_id=item_id,
        title=title,
        summary=text,
        url=f"https://social.example.com/post/{item_id}",
        source_name=source,
        source_url=source_url,
        source_tier=source_tier,
        base_trust_score=base_trust_score,
        published_at=published_at,
        raw_category=cat,
        location_text=location_name,
        country="Pakistan",
        raw_lat=lat,
        raw_lng=lng
    )

def fetch_simulated_social_media(count: int = 3) -> List[NormalizedNewsItem]:
    """
    Generates a batch of simulated social media posts.
    """
    return [_generate_mock_post() for _ in range(count)]
