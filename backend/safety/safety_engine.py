from datetime import datetime, timezone


class SafetyEngine:

    # ---------------------------------------------------------
    # ORCA PROTOTYPE THRESHOLDS
    #
    # These are engineering prototype values, NOT official
    # fishing-vessel safety limits.
    #
    # They must be validated before real-world deployment.
    # ---------------------------------------------------------

    MAX_WAVE_HEIGHT_M = 3.0
    MAX_WIND_SPEED_MS = 12.0

    # ---------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------

    def __init__(self, vessel_profile=None):
        """
        Initialize the ORCA Safety Engine.

        vessel_profile is accepted so that MarineDataService
        can pass the vessel profile into the Safety Engine.

        SVAS-specific safety logic is handled separately by
        SVASSafetyChecker for now.
        """

        self.vessel_profile = vessel_profile

    # ---------------------------------------------------------
    # Check data freshness
    # ---------------------------------------------------------

    def check_data_freshness(self, marine_data):

        retrieved_at = marine_data.get("retrieved_at_utc")

        if not retrieved_at:
            return {
                "status": "UNKNOWN",
                "age_minutes": None,
                "message": "Data retrieval time is unavailable."
            }

        try:

            retrieved_time = datetime.fromisoformat(
                retrieved_at.replace("Z", "+00:00")
            )

            now = datetime.now(timezone.utc)

            age_minutes = (
                now - retrieved_time
            ).total_seconds() / 60

            if age_minutes <= 60:
                status = "FRESH"
            else:
                status = "STALE"

            return {
                "status": status,
                "age_minutes": round(age_minutes, 2),
                "message": (
                    f"Data age is "
                    f"{round(age_minutes, 2)} minutes."
                )
            }

        except (ValueError, TypeError):

            return {
                "status": "UNKNOWN",
                "age_minutes": None,
                "message": "Invalid data retrieval timestamp."
            }

    # ---------------------------------------------------------
    # Evaluate marine conditions
    # ---------------------------------------------------------

    def evaluate(self, marine_data):

        reasons = []
        warnings = []

        # -----------------------------------------------------
        # Check data freshness
        # -----------------------------------------------------

        freshness = self.check_data_freshness(
            marine_data
        )

        if freshness["status"] == "STALE":

            return self._build_result(
                status="UNKNOWN",
                reasons=[
                    "Marine data is older than 60 minutes. "
                    "A reliable safety decision cannot be made."
                ],
                warnings=[],
                marine_data=marine_data,
                freshness=freshness
            )

        if freshness["status"] == "UNKNOWN":

            return self._build_result(
                status="UNKNOWN",
                reasons=[
                    "Marine data freshness could not be verified. "
                    "A reliable safety decision cannot be made."
                ],
                warnings=[],
                marine_data=marine_data,
                freshness=freshness
            )

        # -----------------------------------------------------
        # Extract marine parameters
        # -----------------------------------------------------

        wave_height = marine_data.get(
            "wave_height_m"
        )

        wind_speed = marine_data.get(
            "wind_speed_ms"
        )

        # -----------------------------------------------------
        # Validate required data
        # -----------------------------------------------------

        if wave_height is None:

            reasons.append(
                "Wave height data is unavailable."
            )

        if wind_speed is None:

            reasons.append(
                "Wind speed data is unavailable."
            )

        if reasons:

            return self._build_result(
                status="UNKNOWN",
                reasons=reasons,
                warnings=warnings,
                marine_data=marine_data,
                freshness=freshness
            )

        # -----------------------------------------------------
        # Wave height safety check
        # -----------------------------------------------------

        if wave_height >= self.MAX_WAVE_HEIGHT_M:

            reasons.append(
                f"Wave height is "
                f"{wave_height:.2f} m, "
                f"which exceeds the ORCA prototype "
                f"threshold of "
                f"{self.MAX_WAVE_HEIGHT_M:.1f} m."
            )

        elif wave_height >= (
            self.MAX_WAVE_HEIGHT_M * 0.8
        ):

            warnings.append(
                f"Wave height is "
                f"{wave_height:.2f} m "
                f"and is approaching the "
                f"prototype threshold."
            )

        # -----------------------------------------------------
        # Wind speed safety check
        # -----------------------------------------------------

        if wind_speed >= self.MAX_WIND_SPEED_MS:

            reasons.append(
                f"Wind speed is "
                f"{wind_speed:.2f} m/s, "
                f"which exceeds the ORCA prototype "
                f"threshold of "
                f"{self.MAX_WIND_SPEED_MS:.1f} m/s."
            )

        elif wind_speed >= (
            self.MAX_WIND_SPEED_MS * 0.8
        ):

            warnings.append(
                f"Wind speed is "
                f"{wind_speed:.2f} m/s "
                f"and is approaching the "
                f"prototype threshold."
            )

        # -----------------------------------------------------
        # Final decision
        # -----------------------------------------------------

        if reasons:

            status = "UNSAFE"

        elif warnings:

            status = "CAUTION"

        else:

            status = "SAFE"

            reasons.append(
                "Marine conditions are within "
                "the ORCA prototype thresholds."
            )

        return self._build_result(
            status=status,
            reasons=reasons,
            warnings=warnings,
            marine_data=marine_data,
            freshness=freshness
        )

    # ---------------------------------------------------------
    # Build standardized Safety Engine response
    # ---------------------------------------------------------

    def _build_result(
        self,
        status,
        reasons,
        warnings,
        marine_data,
        freshness
    ):

        return {
            "status": status,

            "reasons": reasons,

            "warnings": warnings,

            "marine_data": marine_data,

            "data_freshness": freshness,

            "decision_source": "ORCA Safety Engine",

            "threshold_type": "prototype"
        }


# -------------------------------------------------------------
# Test
# -------------------------------------------------------------

if __name__ == "__main__":

    engine = SafetyEngine()

    test_data = {

        "source": "INCOIS",

        "data_type": "marine_forecast",

        "location": {
            "latitude": 10.0,
            "longitude": 85.0
        },

        "forecast_time":
            "2026-09-25 06:00:00",

        "wave_height_m": 2.85,

        "wave_period_s": 8.04,

        "wave_direction_deg": 214.67,

        "wind_speed_ms": 11.25,

        "data_status": "forecast",

        "dataset": "RSMC WW3",

        "retrieved_at_utc":
            "2026-09-26T18:23:29.813764+00:00"
    }

    result = engine.evaluate(
        test_data
    )

    print("\nORCA Safety Decision")
    print("=" * 50)

    print("Status:")
    print(result["status"])

    print("\nData Freshness:")

    print(
        result["data_freshness"]["status"]
    )

    print(
        result["data_freshness"]["message"]
    )

    print("\nReasons:")

    for reason in result["reasons"]:
        print("-", reason)

    print("\nWarnings:")

    for warning in result["warnings"]:
        print("-", warning)