from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional, List
import uuid
import random

from database import get_db, Incident

router = APIRouter()

# --- Pydantic Schemas ---
class LocationInput(BaseModel):
    lat: float
    lng: float
    address: Optional[str] = None

class AssessmentInput(BaseModel):
    waterDepth: str
    vehiclePassability: str
    hazardType: str

class PwaReport(BaseModel):
    timestamp: str
    location: LocationInput
    assessment: AssessmentInput
    notes: Optional[str] = ""
    photo: Optional[str] = None
    photoSizeKB: Optional[int] = 0

class RawTextReport(BaseModel):
    text: str
    source: str = "SocialMedia"
    source_url: Optional[str] = None
    image_url: Optional[str] = None

# --- Endpoints ---

@router.post("/submit")
def submit_report(report: PwaReport, db: Session = Depends(get_db)):
    """
    Ingests a structured report directly from the Phase 1 PWA.
    """
    incident_id = f"NDMA-{uuid.uuid4().hex[:8].upper()}"
    
    # Calculate urgency score (Phase 2 logic replicated)
    depth_scores = {'Unknown': 0, 'Ankle': 1, 'Knee': 2, 'Waist': 3, 'Vehicle Submerged': 4}
    pass_scores = {'Unknown': 0, 'Pedestrian Only': 1, '4x4': 2, 'Boat': 3, 'Completely Impassable': 4}
    
    # Normalizing PWA labels to match Phase 2 logic loosely
    d_val = depth_scores.get(report.assessment.waterDepth, 2) 
    p_val = pass_scores.get(report.assessment.vehiclePassability, 2)
    cv_score = 0 # Default to 0 since CV is handled in AI Engine
    
    urgency = round(min(((0.4 * d_val) + (0.3 * p_val) + (0.3 * cv_score)) / 3.7 * 100, 100.0), 1)

    # Convert coordinates to WKT POINT for PostGIS/SpatiaLite
    geom_wkt = f"POINT({report.location.lng} {report.location.lat})"

    new_incident = Incident(
        id=incident_id,
        source="PWA Field Agent (Verified Agent)",
        raw_text=report.notes or f"{report.assessment.waterDepth} standing water reported.",
        geom=geom_wkt,
        latitude=report.location.lat,
        longitude=report.location.lng,
        water_depth=report.assessment.waterDepth,
        passability_type=report.assessment.vehiclePassability,
        urgency_score=urgency,
        verified_status=False,
        image_url=report.photo,
        source_url=f"http://localhost:3000/#report-{incident_id}"
    )
    
    db.add(new_incident)
    db.commit()
    
    return {"status": "success", "incident_id": incident_id, "urgency": urgency}


@router.post("/process-raw-text")
def process_raw_text(payload: RawTextReport, db: Session = Depends(get_db)):
    """
    Ingests unstructured text (Phase 2), simulates AI processing, and saves.
    In a full production environment, this calls the NLPEngine/GeoEngine from Phase 2.
    """
    # SIMULATING Phase 2 AI Pipeline extraction for PoC speed
    incident_id = f"NDMA-AI-{uuid.uuid4().hex[:6].upper()}"
    
    # Generate coordinates strictly bounded in Pakistan flood hotzones
    lat = round(25.0 + random.random() * 9.0, 5)
    lng = round(67.0 + random.random() * 6.0, 5)
    geom_wkt = f"POINT({lng} {lat})"
    
    urgency = round(random.uniform(40.0, 95.0), 1)
    
    new_incident = Incident(
        id=incident_id,
        source=payload.source,
        raw_text=payload.text,
        geom=geom_wkt,
        latitude=lat,
        longitude=lng,
        water_depth="Knee",
        passability_type="4x4",
        urgency_score=urgency,
        verified_status=False,
        image_url=payload.image_url or "https://images.unsplash.com/photo-1547683905-f686c993aae5?w=600&auto=format&fit=crop",
        source_url=payload.source_url or f"https://x.com/NDMA_pk/status/1824{random.randint(10000000, 99999999)}"
    )
    db.add(new_incident)
    db.commit()
    
    return {"status": "success", "incident_id": incident_id, "simulated_urgency": urgency}


@router.get("/map-layers")
def get_map_layers(db: Session = Depends(get_db)):
    """
    Returns a GeoJSON FeatureCollection of all incidents.
    Used by the NEOC Dashboard to render spatial markers.
    """
    incidents = db.query(Incident).all()
    
    features = [inc.to_geojson() for inc in incidents]
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


@router.post("/{incident_id}/verify")
def verify_incident(incident_id: str, db: Session = Depends(get_db)):
    """
    Toggles the verified status of a report (NEOC Operator action).
    """
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    incident.verified_status = True
    db.commit()
    
    return {"status": "success", "incident_id": incident_id, "verified": True}
