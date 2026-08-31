"""
classifier.py — Multi-Hazard Category Classifier
=================================================
Classifies disaster news into Pakistan-relevant hazard categories
using keyword pattern matching. Zero ML overhead — fast, deterministic,
and transparent. Supports both English and Roman Urdu keywords.

Categories (aligned with NDMA hazard taxonomy):
  Flood, GLOF, Landslide, Earthquake, Avalanche,
  Severe Storm, Drought, Heatwave, Cyclone, Wildfire
"""

import re
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger("news_aggregator.classifier")


class HazardCategory(str, Enum):
    FLOOD        = "Flood"
    GLOF         = "GLOF"
    LANDSLIDE    = "Landslide"
    EARTHQUAKE   = "Earthquake"
    AVALANCHE    = "Avalanche"
    SEVERE_STORM = "Severe Storm"
    DROUGHT      = "Drought"
    HEATWAVE     = "Heatwave"
    CYCLONE      = "Cyclone"
    WILDFIRE     = "Wildfire"
    UNKNOWN      = "Unknown"


CATEGORY_EMOJI: dict[str, str] = {
    HazardCategory.FLOOD:        "🌊",
    HazardCategory.GLOF:         "🧊",
    HazardCategory.LANDSLIDE:    "🏔️",
    HazardCategory.EARTHQUAKE:   "🌍",
    HazardCategory.AVALANCHE:    "❄️",
    HazardCategory.SEVERE_STORM: "⛈️",
    HazardCategory.DROUGHT:      "☀️",
    HazardCategory.HEATWAVE:     "🔥",
    HazardCategory.CYCLONE:      "🌀",
    HazardCategory.WILDFIRE:     "🔥",
    HazardCategory.UNKNOWN:      "⚠️",
}

CATEGORY_COLOR: dict[str, str] = {
    HazardCategory.FLOOD:        "#3b82f6",   # blue
    HazardCategory.GLOF:         "#06b6d4",   # cyan
    HazardCategory.LANDSLIDE:    "#92400e",   # brown
    HazardCategory.EARTHQUAKE:   "#dc2626",   # red
    HazardCategory.AVALANCHE:    "#e0f2fe",   # ice blue
    HazardCategory.SEVERE_STORM: "#7c3aed",   # purple
    HazardCategory.DROUGHT:      "#d97706",   # amber
    HazardCategory.HEATWAVE:     "#ea580c",   # orange
    HazardCategory.CYCLONE:      "#9333ea",   # violet
    HazardCategory.WILDFIRE:     "#ef4444",   # red-orange
    HazardCategory.UNKNOWN:      "#6b7280",   # gray
}

# Keyword patterns ordered by specificity (more specific first)
_KEYWORD_RULES: list[tuple[HazardCategory, list[str]]] = [
    (HazardCategory.GLOF, [
        r"\bglof\b", r"glacial lake outburst", r"glacial flood", r"glacier burst",
        r"glacial lake", r"shimshal", r"hunza.*lake", r"attabad",
    ]),
    (HazardCategory.AVALANCHE, [
        r"\bavalanche\b", r"snow slide", r"snowslide", r"snow collapse",
        r"برف\s*تودہ",
    ]),
    (HazardCategory.EARTHQUAKE, [
        r"\bearthquake\b", r"\bseismic\b", r"\bquake\b", r"\btemblor\b",
        r"magnitude\s*\d", r"richter", r"زلزلہ", r"bhukamp",
    ]),
    (HazardCategory.LANDSLIDE, [
        r"\blandslide\b", r"land slide", r"\blandfall\b", r"debris flow",
        r"mudslide", r"rockfall", r"slope failure", r"پہاڑی تودہ", r"landslip",
    ]),
    (HazardCategory.CYCLONE, [
        r"\bcyclone\b", r"\bhurricane\b", r"\btyphoon\b", r"\btropical storm\b",
        r"storm surge", r"طوفان",
    ]),
    (HazardCategory.FLOOD, [
        r"\bflood\b", r"\bflooding\b", r"\bflooded\b", r"inundation",
        r"flash flood", r"riverine flood", r"urban flood", r"\boverflow\b",
        r"\bsubmerged\b", r"seilab", r"سیلاب", r"بارش.*پانی",
        r"flood.*district", r"flood.*province", r"flood.*area",
    ]),
    (HazardCategory.SEVERE_STORM, [
        r"\btornado\b", r"severe storm", r"thunderstorm", r"lightning strike",
        r"hailstorm", r"hail storm", r"windstorm", r"dust storm",
        r"monsoon rain(?!.*flood)", r"heavy rain(?!.*flood)", r"آندھی", r"طوفانی بارش",
    ]),
    (HazardCategory.DROUGHT, [
        r"\bdrought\b", r"water scarcity", r"water shortage", r"dry spell",
        r"crop failure", r"قحط",
    ]),
    (HazardCategory.HEATWAVE, [
        r"\bheatwave\b", r"heat wave", r"extreme heat", r"scorching", r"temperature record",
        r"گرمی کی لہر", r"heat stroke",
    ]),
    (HazardCategory.WILDFIRE, [
        r"\bwildfire\b", r"forest fire", r"bushfire", r"jungle fire",
        r"جنگل.*آگ", r"آتشزدگی",
    ]),
]


def classify_hazard(title: str, summary: Optional[str] = None,
                    raw_category: Optional[str] = None) -> HazardCategory:
    """
    Classify a news item into a HazardCategory.

    Priority:
    1. Exact match on raw_category string (from source)
    2. Keyword scan of title + summary text
    3. Default: UNKNOWN
    """
    # 1. Try raw_category from source
    if raw_category:
        rc = raw_category.lower()
        if "eq" in rc or "earthquake" in rc or "seismic" in rc:
            return HazardCategory.EARTHQUAKE
        if "fl" in rc or "flood" in rc:
            return HazardCategory.FLOOD
        if "ls" in rc or "landslide" in rc:
            return HazardCategory.LANDSLIDE
        if "glof" in rc:
            return HazardCategory.GLOF
        if "tc" in rc or "cyclone" in rc or "hurricane" in rc:
            return HazardCategory.CYCLONE
        if "vo" in rc or "volcano" in rc:
            return HazardCategory.UNKNOWN  # not in taxonomy
        if "drought" in rc:
            return HazardCategory.DROUGHT

    # 2. Keyword scan on combined text
    combined = ((title or "") + " " + (summary or "")).lower()

    for category, patterns in _KEYWORD_RULES:
        for pattern in patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                logger.debug("[Classifier] '%s' → %s (pattern: %s)", title[:60], category, pattern)
                return category

    logger.debug("[Classifier] '%s' → UNKNOWN (no keyword match)", title[:60])
    return HazardCategory.UNKNOWN


def get_emoji(category: HazardCategory) -> str:
    return CATEGORY_EMOJI.get(category, "⚠️")


def get_color(category: HazardCategory) -> str:
    return CATEGORY_COLOR.get(category, "#6b7280")
