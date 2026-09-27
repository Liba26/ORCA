"""
ORCA - SVAS Safety Checker

Evaluates whether an INCOIS SVAS advisory applies to a vessel
based on:

    - vessel beam width
    - location/district
    - travel date
    - distance from coast
    - SVAS polygon geometry

Route geometry/intersection is NOT handled here yet.
"""

import sys
import os

from datetime import date
from typing import Any, Dict, List, Optional

from shapely.geometry import Point, shape


# -------------------------------------------------------------
# Make ORCA project root importable
# -------------------------------------------------------------

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)


class SVASSafetyChecker:

    def __init__(
        self,
        rules: List[Dict[str, Any]]
    ):
        """
        Args:
            rules:
                Normalized SVAS rules produced by svas_parser.py
        """

        self.rules = rules

    # -------------------------------------------------------------
    # Check vessel width
    # -------------------------------------------------------------

    def _width_applies(
        self,
        vessel_width_m: float,
        rule: Dict[str, Any]
    ) -> bool:
        """
        INCOIS wording is:

            Boat Width < Xm

        Therefore a vessel is covered only when:

            vessel_width_m < X
        """

        width_limit = rule.get(
            "boat_width_limit_m"
        )

        if width_limit is None:
            return False

        return vessel_width_m < float(
            width_limit
        )

    # -------------------------------------------------------------
    # Check date
    # -------------------------------------------------------------

    def _date_applies(
        self,
        travel_date: date,
        rule: Dict[str, Any]
    ) -> bool:
        """
        Check whether the advisory applies to the
        requested travel date.
        """

        rule_date = rule.get(
            "date"
        )

        if not rule_date:
            return False

        return (
            travel_date.isoformat()
            == rule_date
        )

    # -------------------------------------------------------------
    # Check district
    # -------------------------------------------------------------

    def _district_applies(
        self,
        district: Optional[str],
        rule: Dict[str, Any]
    ) -> bool:
        """
        Match the requested district against the
        district represented by the SVAS rule.

        If no district is supplied, the district check
        is skipped. Geographic checking can then be used.
        """

        if district is None:
            return True

        rule_district = rule.get(
            "district"
        )

        if not rule_district:
            return False

        return (
            district.strip().lower()
            ==
            str(rule_district).strip().lower()
        )

    # -------------------------------------------------------------
    # Check location against SVAS polygon
    # -------------------------------------------------------------

    def _location_applies(
        self,
        latitude: Optional[float],
        longitude: Optional[float],
        rule: Dict[str, Any]
    ) -> bool:
        """
        Check whether the vessel's location lies
        inside or on the boundary of the SVAS polygon.

        GeoJSON coordinates use:

            [longitude, latitude]

        Shapely Point therefore receives:

            Point(longitude, latitude)

        'covers' is deliberately used instead of 'contains'
        so a point exactly on the advisory boundary is treated
        as being inside the advisory zone.
        """

        if latitude is None or longitude is None:
            return False

        geometry = rule.get(
            "geometry"
        )

        if not geometry:
            return False

        try:

            polygon = shape(
                geometry
            )

            point = Point(
                float(longitude),
                float(latitude)
            )

            return polygon.covers(
                point
            )

        except Exception:
            return False

    # -------------------------------------------------------------
    # Check coastal distance
    # -------------------------------------------------------------

    def _distance_applies(
        self,
        distance_from_coast_km: Optional[float],
        rule: Dict[str, Any]
    ) -> bool:
        """
        Check the advisory's coastal-distance range.

        If the SVAS rule has no distance range,
        the distance condition is considered satisfied.

        If a distance range exists but the caller has not
        supplied a distance, the rule cannot be evaluated
        and is therefore not considered applicable.
        """

        minimum = rule.get(
            "distance_min_km"
        )

        maximum = rule.get(
            "distance_max_km"
        )

        # No distance restriction.
        if minimum is None or maximum is None:
            return True

        # Distance is required for this rule.
        if distance_from_coast_km is None:
            return False

        return (
            float(minimum)
            <= float(distance_from_coast_km)
            <= float(maximum)
        )

    # -------------------------------------------------------------
    # Find applicable rules
    # -------------------------------------------------------------

    def find_applicable_rules(
        self,
        vessel_width_m: float,
        travel_date: date,
        district: Optional[str] = None,
        distance_from_coast_km: Optional[float] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Return all SVAS rules that apply to the vessel.

        Applicability is checked using:

            1. Vessel width
            2. Advisory date
            3. District, when supplied
            4. Geographic polygon, when coordinates supplied
            5. Coastal distance, when supplied

        The method checks ALL rules before returning.
        """

        applicable = []

        for rule in self.rules:

            # -----------------------------------------------------
            # Vessel width
            # -----------------------------------------------------

            if not self._width_applies(
                vessel_width_m,
                rule
            ):
                continue

            # -----------------------------------------------------
            # Date
            # -----------------------------------------------------

            if not self._date_applies(
                travel_date,
                rule
            ):
                continue

            # -----------------------------------------------------
            # District
            # -----------------------------------------------------

            if not self._district_applies(
                district,
                rule
            ):
                continue

            # -----------------------------------------------------
            # Geographic location
            # -----------------------------------------------------

            if (
                latitude is not None
                and longitude is not None
            ):

                if not self._location_applies(
                    latitude,
                    longitude,
                    rule
                ):
                    continue

            # -----------------------------------------------------
            # Coastal distance
            # -----------------------------------------------------

            if not self._distance_applies(
                distance_from_coast_km,
                rule
            ):
                continue

            applicable.append(
                rule
            )

        return applicable

    # -------------------------------------------------------------
    # Safety decision
    # -------------------------------------------------------------

    def evaluate(
        self,
        vessel_width_m: float,
        travel_date: date,
        district: Optional[str] = None,
        distance_from_coast_km: Optional[float] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Evaluate the SVAS safety status.

        Safety rule:

            If ANY applicable SVAS advisory says
            DO_NOT_SAIL, the final result is DO_NOT_SAIL.

        This is important because INCOIS may provide overlapping
        ENG4 / ENG6 / ENG7 advisories with different width limits
        and statuses.

        Returns:

            DO_NOT_SAIL
            SAFE_TO_SAIL
            NO_APPLICABLE_ADVISORY
            UNKNOWN
        """

        applicable_rules = self.find_applicable_rules(
            vessel_width_m=vessel_width_m,
            travel_date=travel_date,
            district=district,
            distance_from_coast_km=distance_from_coast_km,
            latitude=latitude,
            longitude=longitude
        )

        # ---------------------------------------------------------
        # No applicable advisory
        # ---------------------------------------------------------

        if not applicable_rules:

            return {
                "status": "NO_APPLICABLE_ADVISORY",
                "safety_veto": False,
                "reason": (
                    "No applicable INCOIS SVAS advisory "
                    "was found."
                ),
                "applicable_rules": []
            }

        # ---------------------------------------------------------
        # SAFETY VETO
        #
        # Any applicable DO_NOT_SAIL rule blocks sailing.
        # ---------------------------------------------------------

        do_not_sail_rules = [
            rule
            for rule in applicable_rules
            if rule.get("status") == "DO_NOT_SAIL"
        ]

        if do_not_sail_rules:

            return {
                "status": "DO_NOT_SAIL",
                "safety_veto": True,
                "reason": (
                    "At least one applicable INCOIS SVAS "
                    "advisory states that the vessel should "
                    "not sail."
                ),
                "applicable_rules": applicable_rules,
                "blocking_rules": do_not_sail_rules
            }

        # ---------------------------------------------------------
        # SAFE TO SAIL
        #
        # Only reached when there are applicable rules and
        # NONE of them are DO_NOT_SAIL.
        # ---------------------------------------------------------

        safe_rules = [
            rule
            for rule in applicable_rules
            if rule.get("status") == "SAFE_TO_SAIL"
        ]

        if safe_rules:

            return {
                "status": "SAFE_TO_SAIL",
                "safety_veto": False,
                "reason": (
                    "All applicable INCOIS SVAS advisories "
                    "permit safe sailing for the vessel."
                ),
                "applicable_rules": applicable_rules,
                "safe_rules": safe_rules
            }

        # ---------------------------------------------------------
        # UNKNOWN
        # ---------------------------------------------------------

        return {
            "status": "UNKNOWN",
            "safety_veto": False,
            "reason": (
                "An applicable INCOIS SVAS advisory was found, "
                "but its sailing status could not be determined."
            ),
            "applicable_rules": applicable_rules
        }


# -----------------------------------------------------------------
# Test
# -----------------------------------------------------------------

if __name__ == "__main__":

    from backend.integrations.svas_adapter import (
        SVASAdapter
    )

    print()
    print("ORCA - SVAS Safety Checker Test")
    print("=" * 50)

    # -------------------------------------------------------------
    # Retrieve live INCOIS SVAS data
    # -------------------------------------------------------------

    adapter = SVASAdapter()

    rules = adapter.get_rules()

    print()
    print("Retrieved SVAS rules:")
    print(len(rules))

    # -------------------------------------------------------------
    # Create checker
    # -------------------------------------------------------------

    checker = SVASSafetyChecker(
        rules=rules
    )

    # -------------------------------------------------------------
    # Example vessel
    # -------------------------------------------------------------

    vessel_width = 4.5

    travel_date = date(
        2026,
        9,
        27
    )

    # -------------------------------------------------------------
    # Basic district test
    #
    # No coordinates supplied yet.
    # -------------------------------------------------------------

    result = checker.evaluate(
        vessel_width_m=vessel_width,
        travel_date=travel_date,
        district="Kozhikode"
    )

    print()
    print("Vessel width:")
    print(vessel_width, "m")

    print()
    print("Travel date:")
    print(travel_date)

    print()
    print("District:")
    print("Kozhikode")

    print()
    print("SVAS decision:")
    print(result["status"])

    print()
    print("Safety veto:")
    print(result["safety_veto"])

    print()
    print("Reason:")
    print(result["reason"])