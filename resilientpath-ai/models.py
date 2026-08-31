from pydantic import BaseModel, Field
from typing import Optional

class Coordinates(BaseModel):
    latitude: float
    longitude: float

class ProcessedData(BaseModel):
    is_emergency: bool = Field(description="True if the text is classified as a disaster emergency")
    extracted_location: str = Field(description="The extracted raw location string")
    coordinates: Optional[Coordinates] = Field(description="Geocoded GPS coordinates")
    geocoding_confidence: str = Field(description="Confidence of geocoding ('high', 'low', 'none')")
    water_depth: str = Field(description="Extracted water depth level ('Ankle', 'Knee', 'Waist', 'Vehicle Submerged', 'Unknown')")
    passability: str = Field(description="Passability status ('Pedestrian Only', '4x4', 'Boat', 'Completely Impassable', 'Unknown')")
    image_severity_score: int = Field(description="0 to 3 scale (0=Clear, 3=Major Inundation)")
    calculated_urgency_score: float = Field(description="0 to 100 normalized risk score")

class ReportOutput(BaseModel):
    report_id: str
    raw_text: str
    processed_data: ProcessedData
