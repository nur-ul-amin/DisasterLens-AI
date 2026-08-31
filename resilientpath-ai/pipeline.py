import json
from nlp_engine import NLPEngine
from geo_engine import GeoEngine
from cv_engine import CVEngine
from models import ReportOutput, ProcessedData, Coordinates

class DisasterLensPipeline:
    def __init__(self):
        print("--- Initializing DisasterLens AI Pipeline ---")
        self.nlp = NLPEngine()
        self.geo = GeoEngine()
        self.cv = CVEngine()
        print("--- Initialization Complete ---")
        
    def calculate_urgency(self, depth: str, passability: str, cv_score: int) -> float:
        """
        Urgency Score = (0.4 * Depth) + (0.3 * Passability) + (0.3 * Vision Score)
        Normalized to 0-100.
        """
        # 1. Map text attributes to numeric (0-3 scale)
        depth_scores = {
            'Unknown': 0, 'Ankle': 1, 'Knee': 2, 'Waist': 3, 'Vehicle Submerged': 4
        }
        passability_scores = {
            'Unknown': 0, 'Pedestrian Only': 1, '4x4': 2, 'Boat': 3, 'Completely Impassable': 4
        }
        
        d_val = depth_scores.get(depth, 0)
        p_val = passability_scores.get(passability, 0)
        
        # Max theoretical raw score: (0.4 * 4) + (0.3 * 4) + (0.3 * 3) = 1.6 + 1.2 + 0.9 = 3.7
        raw_score = (0.4 * d_val) + (0.3 * p_val) + (0.3 * cv_score)
        
        # Normalize to 100
        normalized = (raw_score / 3.7) * 100
        return round(min(normalized, 100.0), 1)

    def process_report(self, report_id: str, raw_text: str, image_data: str = None) -> str:
        """Processes a raw report and returns structured JSON."""
        print(f"\n[Pipeline] Processing Report: {report_id}")
        
        # 1. NLP Classification & Extraction
        is_emergency = self.nlp.classify_emergency(raw_text)
        entities = self.nlp.extract_entities(raw_text)
        
        location_str = entities['location']
        if location_str != "Unknown":
            location_str += ", KP, Pakistan" # Adding context per prompt requirements
            
        # 2. Geocoding
        geo_data = self.geo.geocode(location_str)
        
        # 3. CV Processing
        cv_score = self.cv.estimate_severity(image_data) if image_data else 0
        
        # 4. Scoring
        urgency = self.calculate_urgency(entities['depth'], entities['passability'], cv_score)
        
        # 5. Serialization
        coords = None
        if geo_data['latitude']:
            coords = Coordinates(latitude=geo_data['latitude'], longitude=geo_data['longitude'])
            
        processed = ProcessedData(
            is_emergency=is_emergency,
            extracted_location=location_str,
            coordinates=coords,
            geocoding_confidence=geo_data['confidence'],
            water_depth=entities['depth'],
            passability=entities['passability'],
            image_severity_score=cv_score,
            calculated_urgency_score=urgency
        )
        
        report = ReportOutput(
            report_id=report_id,
            raw_text=raw_text,
            processed_data=processed
        )
        
        return report.model_dump_json(indent=2)

if __name__ == "__main__":
    # Test the pipeline
    pipeline = DisasterLensPipeline()
    
    sample_text = "Nowshera bypass road py pani waist height tk agaya hai, sedans completely blocked"
    sample_id = "NDMA-2026-00821"
    
    # We will pass None for image to let it default to 0 for this quick test, 
    # or you can pass a path to a real image.
    print(f"\nInput Text: '{sample_text}'")
    result_json = pipeline.process_report(sample_id, sample_text, image_data=None)
    
    print("\n--- Final JSON Output ---")
    print(result_json)
