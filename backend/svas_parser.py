"""
ORCA - INCOIS SVAS Advisory Parser

Converts the advisory text provided by the official
INCOIS SVAS GeoJSON into structured safety rules.

Current scope:
    GeoJSON feature properties
        -> ENG4 / ENG6 / ENG7
        -> vessel-width limit
        -> Day-1 / Day-2 / Day-3
        -> advisory date
        -> distance range
        -> sail status
        -> advisory color

Route intersection / coastal-distance calculation is intentionally
NOT implemented here. That will be handled separately.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------
# Regular expressions
# ---------------------------------------------------------------------

# Example:
#   Boat Width < 4m
#   Boat Width < 6m
#   Boat Width < 7m
WIDTH_RE = re.compile(
    r"Boat\s+Width\s*<\s*(\d+(?:\.\d+)?)\s*m",
    re.IGNORECASE,
)


# Example:
#   Day-1 (27-09-2026)
#   Day-2 (28-09-2026)
#   Day-3 (29-09-2026)
DAY_RE = re.compile(
    r"Day\s*-\s*(1|2|3)"
    r"\s*\(\s*(\d{2}-\d{2}-\d{4})\s*\)",
    re.IGNORECASE,
)


# Example:
#   (0-5)km
#   (10-100)km
#   (30-90) km
DISTANCE_RE = re.compile(
    r"\(\s*"
    r"(\d+(?:\.\d+)?)"
    r"\s*-\s*"
    r"(\d+(?:\.\d+)?)"
    r"\s*\)\s*km",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------

def clean_html(text: Any) -> str:
    """
    Remove simple HTML tags used by the SVAS advisory text.

    INCOIS advisory strings contain HTML such as <br>.
    We preserve the text while converting those tags to spaces.
    """

    if text is None:
        return ""

    text = str(text)

    # Convert common line-break tags to spaces first.
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)

    # Remove remaining HTML tags.
    text = re.sub(r"<[^>]+>", " ", text)

    # Decode a few common HTML entities without requiring
    # an additional dependency.
    replacements = {
        "&nbsp;": " ",
        "&lt;": "<",
        "&gt;": ">",
        "&amp;": "&",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Normalize whitespace.
    text = re.sub(r"\s+", " ", text).strip()

    return text


def parse_boat_width(text: str) -> Optional[float]:
    """
    Extract vessel-width threshold.

    Example:
        'Boat Width < 4m' -> 4.0
    """

    match = WIDTH_RE.search(text)

    if not match:
        return None

    return float(match.group(1))


def parse_distance_range(
    text: str,
) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract coastal-distance range.

    Examples:
        '(0-5)km'       -> (0.0, 5.0)
        '(10-100)km'    -> (10.0, 100.0)

    Returns:
        (None, None)
    if the advisory does not contain a distance range.
    """

    match = DISTANCE_RE.search(text)

    if not match:
        return None, None

    minimum = float(match.group(1))
    maximum = float(match.group(2))

    return minimum, maximum


def parse_status(text: str) -> str:
    """
    Convert the natural-language SVAS advisory into a normalized status.

    Possible values:
        DO_NOT_SAIL
        SAFE_TO_SAIL
        UNKNOWN
    """

    normalized = text.lower()

    if "should not sail" in normalized:
        return "DO_NOT_SAIL"

    if "shouldn't sail" in normalized:
        return "DO_NOT_SAIL"

    if "do not sail" in normalized:
        return "DO_NOT_SAIL"

    if "can safely sail" in normalized:
        return "SAFE_TO_SAIL"

    if "safe to sail" in normalized:
        return "SAFE_TO_SAIL"

    return "UNKNOWN"


def parse_advisory_date(date_text: str) -> str:
    """
    Convert DD-MM-YYYY into ISO YYYY-MM-DD.

    Example:
        27-09-2026 -> 2026-09-27
    """

    parsed = datetime.strptime(
        date_text,
        "%d-%m-%Y",
    )

    return parsed.date().isoformat()


# ---------------------------------------------------------------------
# Day-level parsing
# ---------------------------------------------------------------------

def parse_day_advisories(
    advisory_text: str,
) -> List[Dict[str, Any]]:
    """
    Parse Day-1 / Day-2 / Day-3 sections from one SVAS advisory string.

    Example source text may contain:

        Day-1 (27-09-2026): ... (0-5)km ...
        Day-2 (28-09-2026): ... (0-5)km ...
        Day-3 (29-09-2026): ... can safely sail ...

    Returns a list of normalized day-level dictionaries.
    """

    text = clean_html(advisory_text)

    matches = list(DAY_RE.finditer(text))

    if not matches:
        return []

    results: List[Dict[str, Any]] = []

    for index, match in enumerate(matches):

        day = int(match.group(1))
        date_text = match.group(2)

        # Text belonging to this day continues until the
        # beginning of the next Day-N section.
        start = match.end()

        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            end = len(text)

        day_text = text[start:end].strip()

        distance_min_km, distance_max_km = parse_distance_range(
            day_text
        )

        status = parse_status(day_text)

        results.append(
            {
                "day": day,
                "date": parse_advisory_date(date_text),
                "distance_min_km": distance_min_km,
                "distance_max_km": distance_max_km,
                "status": status,
                "advisory_text": day_text,
            }
        )

    return results


# ---------------------------------------------------------------------
# Single ENG field parser
# ---------------------------------------------------------------------

def parse_width_advisory(
    district: str,
    advisory_text: str,
    color: Optional[str],
    source_field: str,
) -> List[Dict[str, Any]]:
    """
    Parse one INCOIS SVAS vessel-width advisory field.

    IMPORTANT:
    We extract the boat-width limit BEFORE removing HTML tags,
    because INCOIS writes the threshold as:

        Boat Width < 4m

    and the '<' character can otherwise be mistaken for an
    HTML tag.
    """

    # -------------------------------------------------------------
    # Extract vessel width from the ORIGINAL HTML
    # -------------------------------------------------------------

    width_limit = parse_boat_width(
        advisory_text
    )

    if width_limit is None:
        return []

    # -------------------------------------------------------------
    # Now safely clean the HTML for the day-level text
    # -------------------------------------------------------------

    cleaned = clean_html(
        advisory_text
    )

    # -------------------------------------------------------------
    # Parse Day-1 / Day-2 / Day-3
    # -------------------------------------------------------------

    day_rules = parse_day_advisories(
        cleaned
    )

    rules: List[Dict[str, Any]] = []

    for day_rule in day_rules:

        rule = {
            "district": district,

            "boat_width_limit_m":
                width_limit,

            "day":
                day_rule["day"],

            "date":
                day_rule["date"],

            "distance_min_km":
                day_rule["distance_min_km"],

            "distance_max_km":
                day_rule["distance_max_km"],

            "status":
                day_rule["status"],

            "color":
                color,

            "source_field":
                source_field,

            "advisory_text":
                day_rule["advisory_text"],
        }

        rules.append(rule)

    return rules


# ---------------------------------------------------------------------
# GeoJSON feature parser
# ---------------------------------------------------------------------

def parse_feature(
    feature: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Parse one complete GeoJSON Feature.

    The normalized SVAS rules retain the original GeoJSON
    geometry so the safety layer can later determine whether
    a vessel location or route intersects the advisory zone.
    """

    properties = feature.get(
        "properties",
        {}
    )

    if not isinstance(properties, dict):
        return []

    geometry = feature.get(
        "geometry"
    )

    district = clean_html(
        properties.get("ENG", "")
    )

    if not district:
        district = "UNKNOWN"

    rules: List[Dict[str, Any]] = []

    categories = [
        ("ENG4", "Color4"),
        ("ENG6", "Color6"),
        ("ENG7", "Color7"),
    ]

    for advisory_field, color_field in categories:

        advisory_text = properties.get(
            advisory_field
        )

        if not advisory_text:
            continue

        color = properties.get(
            color_field
        )

        parsed_rules = parse_width_advisory(
            district=district,
            advisory_text=advisory_text,
            color=color,
            source_field=advisory_field,
        )

        for rule in parsed_rules:

            # Preserve the original GeoJSON geometry.
            rule["geometry"] = geometry

            # Preserve the GeoJSON feature ID when available.
            rule["feature_id"] = feature.get(
                "id"
            )

        rules.extend(
            parsed_rules
        )

    return rules

# ---------------------------------------------------------------------
# Complete GeoJSON parser
# ---------------------------------------------------------------------

def parse_geojson(
    geojson: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Parse an entire INCOIS SVAS GeoJSON FeatureCollection.

    Returns:
        A flat list of normalized SVAS safety rules.
    """

    if not isinstance(geojson, dict):
        raise TypeError(
            "geojson must be a Python dictionary"
        )

    if geojson.get("type") != "FeatureCollection":
        raise ValueError(
            "Expected a GeoJSON FeatureCollection"
        )

    features = geojson.get("features", [])

    if not isinstance(features, list):
        raise ValueError(
            "GeoJSON 'features' must be a list"
        )

    all_rules: List[Dict[str, Any]] = []

    for feature in features:

        if not isinstance(feature, dict):
            continue

        properties = feature.get("properties", {})

        if not isinstance(properties, dict):
            continue

        feature_rules = parse_feature(feature)

        # Keep the feature ID when available.
        feature_id = feature.get("id")

        for rule in feature_rules:
            rule["feature_id"] = feature_id

        all_rules.extend(feature_rules)

    return all_rules


# ---------------------------------------------------------------------
# Simple helper functions
# ---------------------------------------------------------------------

def get_do_not_sail_rules(
    rules: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Return only rules explicitly marked DO_NOT_SAIL.
    """

    return [
        rule
        for rule in rules
        if rule.get("status") == "DO_NOT_SAIL"
    ]


def get_safe_to_sail_rules(
    rules: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Return only rules explicitly marked SAFE_TO_SAIL.
    """

    return [
        rule
        for rule in rules
        if rule.get("status") == "SAFE_TO_SAIL"
    ]


# ---------------------------------------------------------------------
# Debug / local test
# ---------------------------------------------------------------------

if __name__ == "__main__":

    print(
        "SVAS parser loaded successfully."
    )

    print(
        "This module is ready to receive "
        "an INCOIS SVAS GeoJSON FeatureCollection."
    )