import re
# pyrefly: ignore [missing-import]
from transformers import pipeline

class NLPEngine:
    def __init__(self):
        # We use a lightweight multilingual zero-shot classifier 
        # mDeBERTa-v3-base handles English, Urdu, and Roman Urdu reasonably well.
        print("[NLPEngine] Loading Zero-Shot Classification Model (CPU)...")
        self.classifier = pipeline(
            "zero-shot-classification", 
            model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
            device=-1 # Force CPU to avoid CUDA issues across environments
        )
        
        self.emergency_labels = ["Emergency Disaster", "Irrelevant Noise"]
        print("[NLPEngine] Model Loaded.")

    def classify_emergency(self, text: str) -> bool:
        """Classifies if the text is a flood emergency."""
        result = self.classifier(text, self.emergency_labels)
        top_label = result['labels'][0]
        return top_label == "Emergency Disaster"

    def extract_entities(self, text: str):
        """
        Extracts location, depth, and passability using regex/heuristics.
        This handles Roman Urdu & English variations.
        """
        text_lower = text.lower()
        
        # 1. Extract Water Depth
        depth_mapping = {
            r'\bankle\b|takhn': 'Ankle',
            r'\bknee\b|ghutn': 'Knee',
            r'\bwaist\b|kamar': 'Waist',
            r'submerged|doob|roof': 'Vehicle Submerged'
        }
        extracted_depth = 'Unknown'
        for pattern, label in depth_mapping.items():
            if re.search(pattern, text_lower):
                extracted_depth = label
                # Prioritize worst condition found, so if waist and ankle, waist wins.
                # Here we just take the first match as a simplification, 
                # but sorting dict appropriately works. The current dict order is fine.

        # 2. Extract Passability
        passability_mapping = {
            r'pedestrian|foot|paidal': 'Pedestrian Only',
            r'4x4|truck|heavy': '4x4',
            r'boat|kashti': 'Boat',
            r'blocked|impassable|stuck|band|phass': 'Completely Impassable'
        }
        extracted_passability = 'Unknown'
        for pattern, label in passability_mapping.items():
            if re.search(pattern, text_lower):
                extracted_passability = label

        # 3. Extract Location (Simple Heuristic for PoC)
        # Look for keywords like "near", "bypass", "road", "street", "highway", "river", "bridge"
        # and capture the surrounding context.
        location = "Unknown"
        loc_patterns = [
            r'(.{0,20}\b(bypass|road|street|highway|river|bridge|near)\b.{0,20})'
        ]
        for pattern in loc_patterns:
            match = re.search(pattern, text_lower)
            if match:
                # Clean up the extracted snippet to use as location
                raw_loc = match.group(1).strip()
                # Capitalize words for better geocoding
                location = " ".join([word.capitalize() for word in raw_loc.split()])
                break
                
        return {
            "location": location,
            "depth": extracted_depth,
            "passability": extracted_passability
        }
