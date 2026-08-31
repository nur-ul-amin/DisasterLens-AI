import uuid
import random
from datetime import datetime, timedelta
from database import SessionLocal, Incident, Base, engine

# Ensure tables exist
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Realistic flood photos (disaster imagery)
FLOOD_IMAGES = [
    "https://images.unsplash.com/photo-1547683905-f686c993aae5?w=600&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1515694346937-94d85e41e6f0?w=600&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?w=600&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1579684385127-1ef15d508118?w=600&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1541888946425-d0fbb186a5b3?w=600&auto=format&fit=crop"
]

# Verified Sources & Attached Post/Article Links
RELIABLE_SOURCES = [
    {
        "platform": "X (Twitter)",
        "source": "X (@NDMA_pk)",
        "base_url": "https://x.com/NDMA_pk/status/1824"
    },
    {
        "platform": "X (Twitter)",
        "source": "X (@PDMASindhPK)",
        "base_url": "https://x.com/PDMASindhPK/status/1824"
    },
    {
        "platform": "X (Twitter)",
        "source": "X (@RadioPakistan)",
        "base_url": "https://x.com/RadioPakistan/status/1824"
    },
    {
        "platform": "Facebook",
        "source": "Facebook (PDMA Punjab Official)",
        "base_url": "https://facebook.com/PDMAPunjabOfficial/posts/"
    },
    {
        "platform": "Facebook",
        "source": "Facebook (NDMA Pakistan Emergency Control)",
        "base_url": "https://facebook.com/NDMAPakistan/posts/"
    },
    {
        "platform": "Instagram",
        "source": "Instagram (@NDMA_Floods_Live)",
        "base_url": "https://instagram.com/p/C9x8"
    },
    {
        "platform": "News Article",
        "source": "Dawn News (Pakistan Floods Desk)",
        "base_url": "https://www.dawn.com/news/182490"
    },
    {
        "platform": "News Article",
        "source": "Geo News (Live Flood Updates)",
        "base_url": "https://www.geo.tv/latest/55940"
    },
    {
        "platform": "PWA Report",
        "source": "PWA Field Agent (Verified Agent)",
        "base_url": "http://localhost:3000/#report-"
    }
]

# Verified Pakistan Disaster Hotzones (Strictly inside Pakistan)
PAKISTAN_HOTZONES = [
    {
        "name": "Nowshera Kabul River Bypass, KP",
        "lat": 34.0152,
        "lng": 71.9747,
        "depth": "Vehicle Submerged",
        "passability": "Completely Impassable",
        "texts": [
            "Nowshera bypass road py Kabul river flood water waist height tk agaya hai. GT Road completely blocked for light transport.",
            "ALERT: Kabul River at Nowshera in High Flood level (300,000 cusecs). GT Road bypass bridge submerged under water.",
            "نوشہرہ بائی پاس پر دریائے کابل کا پانی سڑک پر آگیا ہے۔ گاڑیاں مکمل بند ہیں۔"
        ]
    },
    {
        "name": "Sukkur Barrage Bypass, Sindh",
        "lat": 27.7032,
        "lng": 68.8589,
        "depth": "Waist",
        "passability": "Boat Required",
        "texts": [
            "Sukkur Barrage upstream right bank embankment breach reported. Water entering village access roads.",
            "Sukkur highway under 3 feet of standing Indus river overflow. Only heavy 4x4 trucks or rescue boats passing.",
            "سکھر بیراج کے قریب بند توڑنے کی خبر، قومی شاہراہ پر پانی کا شدید بہاؤ۔"
        ]
    },
    {
        "name": "Dadu Highway (N-55), Sindh",
        "lat": 26.7328,
        "lng": 67.7763,
        "depth": "Vehicle Submerged",
        "passability": "Completely Impassable",
        "texts": [
            "N-55 Indus Highway near Dadu completely submerged. Water depth reaching waist to chest level.",
            "Dadu bypass breached by Manchar Lake overflow. Heavy vehicles stranded on both sides.",
            "دادو انڈس ہائی وے پر منچھار جھیل کے پانی سے رابطہ منقطع ہوگیا ہے۔"
        ]
    },
    {
        "name": "Swat River Valley Bypass, Mingora KP",
        "lat": 35.2227,
        "lng": 72.4258,
        "depth": "Knee",
        "passability": "4x4 Accessible",
        "texts": [
            "Swat Expressway bypass near Fizagat flooded by river surge. Sedans unable to cross.",
            "Flash flood in Swat River damages riverside road section near Mingora bypass.",
            "سوات بائی پاس سڑک پر سیلابی ریلہ گزر رہا ہے، صر 4x4 گاڑیاں قابل سفر ہیں۔"
        ]
    },
    {
        "name": "Rajanpur District Highway, Punjab",
        "lat": 29.1044,
        "lng": 70.3301,
        "depth": "Waist",
        "passability": "Completely Impassable",
        "texts": [
            "Hill torrents (Kaha Sultan) inundated Rajanpur-Jampur highway section.",
            "Rajanpur Indus Highway submerged under 4 feet torrent water. Rescue teams deployed.",
            "راجن پور کوہ سلیمان سے آنے والا رود کوہی کا ریلہ انڈس ہائی وے کو بہا لے گیا۔"
        ]
    },
    {
        "name": "Charsadda Kabul River Bridge, KP",
        "lat": 34.1483,
        "lng": 71.7406,
        "depth": "Vehicle Submerged",
        "passability": "Completely Impassable",
        "texts": [
            "Khyber Khyber bridge Charsadda flooded. Water crossed dangerous marks near Subhan Khwar.",
            "High flood alert in Khyber Charsadda belt. Roads blocked by debris and water.",
            "چار سدہ میں خیالی ندی کا پانی آبادی اور سڑکوں میں داخل۔"
        ]
    },
    {
        "name": "Swabi Indus Highway Link, KP",
        "lat": 34.1202,
        "lng": 72.4700,
        "depth": "Knee",
        "passability": "4x4 Accessible",
        "texts": [
            "Torrential rains cause urban flooding on Swabi-Topi main artery road.",
            "Swabi bypass bridge approach damaged due to flash flood runoff."
        ]
    },
    {
        "name": "Tank Bypass Road, KP",
        "lat": 32.2173,
        "lng": 70.3831,
        "depth": "Waist",
        "passability": "Boat Required",
        "texts": [
            "Tank district link road washed away by hill torrent from South Waziristan border.",
            "Tank city main road under waist-deep water. Emergency response initiated."
        ]
    },
    {
        "name": "D.I. Khan Bund Road, KP",
        "lat": 31.8314,
        "lng": 70.9019,
        "depth": "Waist",
        "passability": "Completely Impassable",
        "texts": [
            "Indus River embankment near D.I. Khan Prova road breached. Traffic suspended."
        ]
    },
    {
        "name": "Karachi Malir River Bed Road, Sindh",
        "lat": 24.8934,
        "lng": 67.1654,
        "depth": "Knee",
        "passability": "Pedestrian Only",
        "texts": [
            "Malir river overflow inundated causeway link connecting Korangi to highway.",
            "Korangi causeway closed for traffic due to Malir spillway surge."
        ]
    },
    {
        "name": "Hyderabad National Highway Bypass, Sindh",
        "lat": 25.3960,
        "lng": 68.3578,
        "depth": "Knee",
        "passability": "4x4 Accessible",
        "texts": [
            "Heavy rain water stagnant on Hyderabad-Latifabad bypass highway."
        ]
    },
    {
        "name": "Larkana Rice Canal Link Road, Sindh",
        "lat": 27.5580,
        "lng": 68.2120,
        "depth": "Waist",
        "passability": "Completely Impassable",
        "texts": [
            "Rice canal bank breach floods nearby road link in Larkana district."
        ]
    },
    {
        "name": "Shikarpur City Connecting Highway, Sindh",
        "lat": 27.9570,
        "lng": 68.6380,
        "depth": "Vehicle Submerged",
        "passability": "Completely Impassable",
        "texts": [
            "Shikarpur highway section inundated under 3.5 ft water after monsoon heavy downpour."
        ]
    },
    {
        "name": "Jampur Indus Highway Section, Punjab",
        "lat": 29.6430,
        "lng": 70.5950,
        "depth": "Waist",
        "passability": "Completely Impassable",
        "texts": [
            "Hill torrent flood water inundated Jampur bypass road connecting South Punjab to Sindh."
        ]
    },
    {
        "name": "Quetta Western Bypass Road, Balochistan",
        "lat": 30.1798,
        "lng": 66.9750,
        "depth": "Ankle",
        "passability": "Pedestrian Only",
        "texts": [
            "Flash flood water from mountains inundated Western Bypass in Quetta."
        ]
    },
    {
        "name": "Gwadar Coastal Highway Link, Balochistan",
        "lat": 25.1264,
        "lng": 62.3225,
        "depth": "Knee",
        "passability": "4x4 Accessible",
        "texts": [
            "Gwadar expressway flooded following extreme coastal torrential rainfall."
        ]
    },
    {
        "name": "Gilgit Karakoram Highway (KKH), Gilgit-Baltistan",
        "lat": 35.9208,
        "lng": 74.3089,
        "depth": "Knee",
        "passability": "4x4 Accessible",
        "texts": [
            "Landslide and mudflow blocked KKH near Hunza-Gilgit border road."
        ]
    },
    {
        "name": "Muzaffarabad Neelum Valley Highway, AJK",
        "lat": 34.3700,
        "lng": 73.4700,
        "depth": "Ankle",
        "passability": "Pedestrian Only",
        "texts": [
            "Neelum river overflow eroded road bank near Muzaffarabad city limits."
        ]
    }
]

def generate_pakistan_disaster_data(total_records=60):
    print(f"Purging existing DB records and seeding {total_records} PAKISTAN-ONLY verified disaster reports...")
    
    # Wipe old non-conforming test data
    db.query(Incident).delete()
    db.commit()

    incidents = []

    for i in range(total_records):
        # Pick a Pakistan hotzone or generate jittered coordinates strictly inside Pakistan bounds
        hz = random.choice(PAKISTAN_HOTZONES)
        
        # Add small random micro-jitter within 0.03 deg (~3 km radius inside Pakistan)
        lat = round(hz["lat"] + random.uniform(-0.03, 0.03), 5)
        lng = round(hz["lng"] + random.uniform(-0.03, 0.03), 5)
        
        # Ensure lat/lng stay strictly bounded within Pakistan box: (23.6 <= lat <= 37.1), (60.8 <= lng <= 77.8)
        lat = max(23.6, min(37.1, lat))
        lng = max(60.8, min(77.8, lng))

        depth = hz["depth"] if random.random() < 0.7 else random.choice(["Ankle", "Knee", "Waist", "Vehicle Submerged"])
        passability = hz["passability"] if random.random() < 0.7 else random.choice(["Pedestrian Only", "4x4", "Boat", "Completely Impassable"])
        raw_text = random.choice(hz["texts"])

        # Calculate realistic urgency score (0.0 to 100.0)
        depth_weights = {"Ankle": 20, "Knee": 45, "Waist": 75, "Vehicle Submerged": 95}
        pass_weights = {"Pedestrian Only": 30, "4x4": 50, "Boat": 80, "Completely Impassable": 95}
        
        d_val = depth_weights.get(depth, 50)
        p_val = pass_weights.get(passability, 50)
        urgency = round(min(100.0, max(15.0, (0.5 * d_val + 0.5 * p_val) + random.uniform(-5, 5))), 1)

        # Assign verified source, attached post URL, and photo image
        src_info = random.choice(RELIABLE_SOURCES)
        source_name = src_info["source"]
        random_id = str(random.randint(1000000000000000, 9999999999999999))
        source_url = f"{src_info['base_url']}{random_id}" if not source_name.startswith("PWA") else f"{src_info['base_url']}NDMA-{uuid.uuid4().hex[:6].upper()}"
        image_url = random.choice(FLOOD_IMAGES)

        geom_wkt = f"POINT({lng} {lat})"
        time_offset = timedelta(hours=random.uniform(0.1, 36.0))
        created_at = datetime.now() - time_offset

        incident = Incident(
            id=f"NDMA-PK-{uuid.uuid4().hex[:6].upper()}",
            source=source_name,
            raw_text=raw_text,
            geom=geom_wkt,
            latitude=lat,
            longitude=lng,
            water_depth=depth,
            passability_type=passability,
            urgency_score=urgency,
            verified_status=random.choice([True, True, False]), # Higher verification rate for reliable sources
            image_url=image_url,
            source_url=source_url,
            created_at=created_at
        )
        incidents.append(incident)

    db.add_all(incidents)
    db.commit()
    print(f"Successfully seeded {len(incidents)} Pakistan-only disaster incidents with verified social/news sources!")

if __name__ == "__main__":
    generate_pakistan_disaster_data(60)
