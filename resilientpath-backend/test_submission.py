import base64
import requests
import json

# Setup
URL = "http://localhost:8000/api/v1/reports/submit"
IMAGE_PATH = r"C:\Users\LENOVO\Downloads\chris-gallagher-4zxp5vlmvnI-unsplash.jpg"

print("Encoding image to base64...")
with open(IMAGE_PATH, "rb") as f:
    image_bytes = f.read()
    b64_string = base64.b64encode(image_bytes).decode("utf-8")
    size_kb = len(image_bytes) // 1024

print(f"Image loaded: {size_kb} KB")

# Yasin Valley approximate coordinates
lat = 36.3622
lng = 73.3283

payload = {
    "timestamp": "2026-08-13T00:00:00Z",
    "location": {
        "lat": lat,
        "lng": lng,
        "address": "Yasin Valley, Gilgit Baltistan, Pakistan"
    },
    "assessment": {
        "waterDepth": "Waist",
        "vehiclePassability": "Completely Impassable",
        "hazardType": "Submerged Road"
    },
    "notes": "Emergency test report from Yasin Valley. Heavy flooding covering the roads.",
    "photo": b64_string,
    "photoSizeKB": size_kb
}

print(f"Submitting report to {URL}...")
response = requests.post(URL, json=payload)

if response.ok:
    print("Success!")
    print(json.dumps(response.json(), indent=2))
else:
    print("Failed!")
    print(response.status_code, response.text)
