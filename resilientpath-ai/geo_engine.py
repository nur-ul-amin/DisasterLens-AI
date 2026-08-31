import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

class GeoEngine:
    def __init__(self):
        # Unique User-Agent required by Nominatim policy
        self.geolocator = Nominatim(user_agent="NDMA_DisasterLens_PoC_Phase2")
        self.default_country = "Pakistan"

    def geocode(self, location_text: str):
        """
        Attempts to geocode the location text.
        Returns:
            dict with 'latitude', 'longitude', 'confidence'
        """
        if not location_text or location_text == "Unknown":
            return {"latitude": None, "longitude": None, "confidence": "none"}
            
        # Add context to help Nominatim
        search_query = f"{location_text}, {self.default_country}"
        
        try:
            # Respect rate limit (1 req/sec)
            time.sleep(1) 
            location = self.geolocator.geocode(search_query, timeout=5)
            
            if location:
                # High confidence if the exact location was found
                return {
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    "confidence": "high"
                }
            
            # Fallback: Extract potential city/district from the text
            # (Simple heuristic for PoC: take the last word assuming it might be a city)
            words = location_text.split()
            if len(words) > 1:
                fallback_query = f"{words[-1]}, {self.default_country}"
                time.sleep(1)
                fallback_location = self.geolocator.geocode(fallback_query, timeout=5)
                
                if fallback_location:
                    return {
                        "latitude": fallback_location.latitude,
                        "longitude": fallback_location.longitude,
                        "confidence": "low"
                    }

            return {"latitude": None, "longitude": None, "confidence": "none"}
            
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"[GeoEngine] Geocoding error: {e}")
            return {"latitude": None, "longitude": None, "confidence": "none"}
