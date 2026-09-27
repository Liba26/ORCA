import sys
import os

from backend.safety import vessel_profile

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )
)

from backend.integrations.incois_adapter import INCOISAdapter
from backend.safety.safety_engine import SafetyEngine


class MarineDataService:

    def __init__(
        self,
        local_file,
        vessel_profile
    ):
        self.adapter = INCOISAdapter(
        local_file=local_file
    )

        self.safety_engine = SafetyEngine(
        vessel_profile=vessel_profile
    )

    def get_marine_decision(
        self,
        latitude,
        longitude,
        target_time
    ):
        # 1. Get marine forecast from INCOIS
        forecast = self.adapter.get_forecast_at_time(
            latitude=latitude,
            longitude=longitude,
            target_time=target_time
        )

        # 2. Evaluate the forecast using Safety Engine
        safety_decision = self.safety_engine.evaluate(forecast)

        # 3. Return combined ORCA result
        return {
            "marine_forecast": forecast,
            "safety_decision": safety_decision
        }


if __name__ == "__main__":

    service = MarineDataService(
        local_file=r"C:\Users\Liba Shasmeen\Downloads\rsmc_combined_ww3_20260923.nc"
    )

    result = service.get_marine_decision(
        latitude=10.0,
        longitude=85.0,
        target_time="2026-09-25 06:00:00"
    )

    print("\nORCA MARINE DATA SERVICE")
    print("=" * 50)

    print("\nMarine Forecast:")
    print(result["marine_forecast"])

    print("\nSafety Decision:")
    print(result["safety_decision"]["status"])

    print("\nWarnings:")
    for warning in result["safety_decision"]["warnings"]:
        print("-", warning)