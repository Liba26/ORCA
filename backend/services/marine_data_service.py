import os
import sys
from datetime import datetime

from backend.integrations.incois_adapter import INCOISAdapter
from backend.integrations.svas_adapter import SVASAdapter
from backend.safety.safety_engine import SafetyEngine
from backend.safety.svas_safety import SVASSafetyChecker


# ---------------------------------------------------------
# Ensure ORCA project root is available
# ---------------------------------------------------------

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)


class MarineDataService:

    def __init__(
        self,
        local_file,
        vessel_profile=None
    ):
        """
        ORCA Marine Data Service.

        Combines:

        1. INCOIS WW3 marine forecast
        2. ORCA Safety Engine
        3. INCOIS SVAS vessel safety advisory
        """

        # -------------------------------------------------
        # INCOIS WW3
        # -------------------------------------------------

        self.adapter = INCOISAdapter(
            local_file=local_file
        )

        # -------------------------------------------------
        # ORCA Safety Engine
        # -------------------------------------------------

        self.safety_engine = SafetyEngine(
            vessel_profile=vessel_profile
        )

        # -------------------------------------------------
        # INCOIS SVAS
        # -------------------------------------------------

        self.svas_adapter = SVASAdapter()

        # Retrieve current SVAS rules

        self.svas_rules = self.svas_adapter.get_rules()

        self.svas_checker = SVASSafetyChecker(
            self.svas_rules
        )

        self.vessel_profile = vessel_profile

    # -----------------------------------------------------
    # Get combined marine + safety decision
    # -----------------------------------------------------

    def get_marine_decision(
        self,
        latitude,
        longitude,
        target_time,
        district=None,
        distance_from_coast_km=None
    ):
        """
        Retrieve INCOIS marine forecast and combine it with
        the ORCA Safety Engine and INCOIS SVAS safety rules.

        distance_from_coast_km is optional for now because
        Navigation is still being developed.
        """

        # =================================================
        # 1. Get INCOIS WW3 marine forecast
        # =================================================

        forecast = self.adapter.get_forecast_at_time(
            latitude=latitude,
            longitude=longitude,
            target_time=target_time
        )

        # =================================================
        # 2. Evaluate WW3 forecast
        # =================================================

        marine_safety = self.safety_engine.evaluate(
            forecast
        )

        # =================================================
        # 3. Evaluate SVAS
        # =================================================

        svas_decision = {
            "status": "UNKNOWN",
            "safety_veto": False,
            "reason": (
                "SVAS could not be evaluated because "
                "vessel profile or travel date is unavailable."
            ),
            "applicable_rules": []
        }

        if self.vessel_profile is not None:

            # ---------------------------------------------
            # Convert target_time into a date
            # ---------------------------------------------

            if isinstance(target_time, datetime):

                travel_date = target_time.date()

            else:

                travel_date = datetime.fromisoformat(
                    str(target_time)
                ).date()

            # ---------------------------------------------
            # Vessel width
            # ---------------------------------------------

            vessel_width_m = (
                self.vessel_profile.beam_width_m
            )

            # ---------------------------------------------
            # SVAS evaluation
            # ---------------------------------------------

            svas_decision = self.svas_checker.evaluate(
                vessel_width_m=vessel_width_m,
                travel_date=travel_date,
                district=district,
                distance_from_coast_km=(
                    distance_from_coast_km
                ),
                latitude=latitude,
                longitude=longitude
            )

        # =================================================
        # 4. Combine decisions
        # =================================================

        if svas_decision.get("safety_veto"):

            overall_status = "DO_NOT_SAIL"

            overall_reason = (
                "INCOIS SVAS contains an applicable "
                "DO_NOT_SAIL advisory for this vessel."
            )

        elif marine_safety.get("status") == "UNSAFE":

            overall_status = "UNSAFE"

            overall_reason = (
                "Marine forecast conditions exceed "
                "the current ORCA prototype safety thresholds."
            )

        elif marine_safety.get("status") == "CAUTION":

            overall_status = "CAUTION"

            overall_reason = (
                "Marine conditions are approaching "
                "the current ORCA prototype thresholds."
            )

        elif svas_decision.get("status") == "SAFE_TO_SAIL":

            overall_status = "SAFE_TO_SAIL"

            overall_reason = (
                "Marine conditions are within the current "
                "ORCA prototype thresholds and the applicable "
                "SVAS advisory permits sailing."
            )

        else:

            overall_status = marine_safety.get(
                "status",
                "UNKNOWN"
            )

            overall_reason = (
                "Marine safety was evaluated, but a complete "
                "SVAS decision could not be established."
            )

        # =================================================
        # 5. Return combined ORCA result
        # =================================================

        return {

            "overall_safety": {
                "status": overall_status,
                "reason": overall_reason
            },

            "marine_forecast": forecast,

            "marine_safety": marine_safety,

            "svas_safety": svas_decision
        }


# ---------------------------------------------------------
# Test
# ---------------------------------------------------------

if __name__ == "__main__":

    from backend.safety.vessel_profile import VesselProfile

    vessel = VesselProfile(
        vessel_type="small_fishing_vessel",
        beam_width_m=4.5
    )

    service = MarineDataService(

        local_file=(
            r"C:\Users\Liba Shasmeen\Downloads"
            r"\rsmc_combined_ww3_20260923.nc"
        ),

        vessel_profile=vessel
    )

    result = service.get_marine_decision(

        latitude=11.34456936143883,

        longitude=75.15600460168531,

        target_time="2026-09-27 06:00:00",

        district="Kozhikode",

        distance_from_coast_km=2.0
    )

    print("\nORCA COMBINED MARINE SAFETY")
    print("=" * 60)

    print("\nOverall Safety:")
    print(
        result["overall_safety"]["status"]
    )

    print(
        result["overall_safety"]["reason"]
    )

    print("\nMarine Safety:")
    print(
        result["marine_safety"]["status"]
    )

    print("\nSVAS Safety:")
    print(
        result["svas_safety"]["status"]
    )

    print(
        "Safety Veto:",
        result["svas_safety"]["safety_veto"]
    )

    print(
        "\nApplicable SVAS Rules:",
        len(
            result["svas_safety"]["applicable_rules"]
        )
    )