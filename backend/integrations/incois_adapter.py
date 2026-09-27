import re
import requests
import numpy as np
from datetime import datetime, timezone
from netCDF4 import Dataset, num2date


class INCOISAdapter:

    DOWNLOAD_PAGE = (
        "https://www.incois.gov.in/"
        "oceanservices/rsmc_download.jsp"
    )

    FILE_BASE_URL = (
        "https://www.incois.gov.in/"
        "thredds/fileServer/osf/ww3/"
    )

    def __init__(self, local_file=None):
        self.local_file = local_file

    # ---------------------------------------------------------
    # Find latest INCOIS WW3 file
    # ---------------------------------------------------------

    def find_latest_file(self):

        response = requests.get(
            self.DOWNLOAD_PAGE,
            timeout=30
        )

        response.raise_for_status()

        matches = re.findall(
            r"rsmc_combined_ww3_(\d{8})\.nc",
            response.text
        )

        if not matches:
            raise RuntimeError(
                "No INCOIS WW3 files found."
            )

        latest = max(matches)

        filename = (
            f"rsmc_combined_ww3_{latest}.nc"
        )

        url = self.FILE_BASE_URL + filename

        return {
            "filename": filename,
            "url": url,
            "date": latest
        }

    # ---------------------------------------------------------
    # Find nearest INCOIS grid point
    # ---------------------------------------------------------

    def find_nearest_grid_point(
        self,
        ds,
        latitude,
        longitude
    ):

        lats = ds.variables["IOYAXIS"][:]
        lons = ds.variables["IOXAXIS"][:]

        lat_index = np.abs(
            lats - latitude
        ).argmin()

        lon_index = np.abs(
            lons - longitude
        ).argmin()

        return (
            lat_index,
            lon_index,
            float(lats[lat_index]),
            float(lons[lon_index])
        )

    # ---------------------------------------------------------
    # Get all forecasts
    # ---------------------------------------------------------

    def get_forecast(
        self,
        latitude,
        longitude
    ):

        if self.local_file is None:
            raise RuntimeError(
                "No local INCOIS NetCDF file configured."
            )

        with Dataset(
            self.local_file,
            "r"
        ) as ds:

            # -------------------------------------------------
            # Find nearest grid point
            # -------------------------------------------------

            (
                lat_index,
                lon_index,
                actual_lat,
                actual_lon
            ) = self.find_nearest_grid_point(
                ds,
                latitude,
                longitude
            )

            # -------------------------------------------------
            # Core INCOIS marine variables
            # -------------------------------------------------

            wave_height = ds.variables[
                "HS"
            ][:, lat_index, lon_index]

            peak_wave_period = ds.variables[
                "PWP"
            ][:, lat_index, lon_index]

            wave_direction = ds.variables[
                "MWD"
            ][:, lat_index, lon_index]

            wave_steepness = ds.variables[
                "STP"
            ][:, lat_index, lon_index]

            directional_spreading = ds.variables[
                "SPR"
            ][:, lat_index, lon_index]

            # -------------------------------------------------
            # Wind components
            # -------------------------------------------------

            wind_u = ds.variables[
                "UWND"
            ][:, lat_index, lon_index]

            wind_v = ds.variables[
                "VWND"
            ][:, lat_index, lon_index]

            # -------------------------------------------------
            # Forecast time
            # -------------------------------------------------

            times = ds.variables["TIME"][:]

            time_units = ds.variables[
                "TIME"
            ].units

            forecast_times = num2date(
                times,
                units=time_units,
                calendar="standard"
            )

            forecasts = []

            # -------------------------------------------------
            # Record when ORCA read the dataset
            # -------------------------------------------------

            retrieved_at = datetime.now(
                timezone.utc
            ).isoformat()

            # -------------------------------------------------
            # Build forecast records
            # -------------------------------------------------

            for i in range(
                len(forecast_times)
            ):

                # Skip records where required values
                # are missing/masked.

                if (
                    np.ma.is_masked(
                        wave_height[i]
                    )
                    or np.ma.is_masked(
                        peak_wave_period[i]
                    )
                    or np.ma.is_masked(
                        wave_direction[i]
                    )
                    or np.ma.is_masked(
                        wave_steepness[i]
                    )
                    or np.ma.is_masked(
                        directional_spreading[i]
                    )
                    or np.ma.is_masked(
                        wind_u[i]
                    )
                    or np.ma.is_masked(
                        wind_v[i]
                    )
                ):
                    continue

                # -------------------------------------------------
                # Calculate wind speed
                # -------------------------------------------------

                wind_speed = np.sqrt(
                    float(wind_u[i]) ** 2
                    + float(wind_v[i]) ** 2
                )

                # -------------------------------------------------
                # Create forecast record
                # -------------------------------------------------

                forecasts.append({

                    "source": "INCOIS",

                    "data_type":
                        "marine_forecast",

                    "location": {
                        "latitude": actual_lat,
                        "longitude": actual_lon
                    },

                    "forecast_time":
                        str(forecast_times[i]),

                    # ---------------------------------------------
                    # Wave parameters
                    # ---------------------------------------------

                    "wave_height_m":
                        float(wave_height[i]),

                    "peak_wave_period_s":
                        float(peak_wave_period[i]),

                    "wave_direction_deg":
                        float(wave_direction[i]),

                    "wave_steepness":
                        float(wave_steepness[i]),

                    "directional_spreading_deg":
                        float(
                            directional_spreading[i]
                        ),

                    # ---------------------------------------------
                    # Wind parameters
                    # ---------------------------------------------

                    "wind_u_ms":
                        float(wind_u[i]),

                    "wind_v_ms":
                        float(wind_v[i]),

                    "wind_speed_ms":
                        float(wind_speed),

                    # ---------------------------------------------
                    # Metadata
                    # ---------------------------------------------

                    "data_status":
                        "forecast",

                    "dataset":
                        "RSMC WW3",

                    "retrieved_at_utc":
                        retrieved_at
                })

            return forecasts

    # ---------------------------------------------------------
    # Get forecast for a specific time
    # ---------------------------------------------------------

    def get_forecast_at_time(
        self,
        latitude,
        longitude,
        target_time
    ):

        forecasts = self.get_forecast(
            latitude,
            longitude
        )

        if not forecasts:
            raise RuntimeError(
                "No forecast data available."
            )

        target_time = target_time.replace(
            "T",
            " "
        ).replace(
            "Z",
            ""
        )

        closest = min(
            forecasts,
            key=lambda item: abs(
                np.datetime64(
                    item["forecast_time"]
                )
                - np.datetime64(
                    target_time
                )
            )
        )

        return closest


# -------------------------------------------------------------
# Test
# -------------------------------------------------------------

if __name__ == "__main__":

    import sys
    import os

    # Add ORCA project root to Python path
    sys.path.append(
        os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                ".."
            )
        )
    )

    from backend.safety.safety_engine import SafetyEngine

    # ---------------------------------------------------------
    # Local INCOIS NetCDF file
    # ---------------------------------------------------------

    adapter = INCOISAdapter(
        local_file=r"C:\Users\Liba Shasmeen\Downloads\rsmc_combined_ww3_20260923.nc"
    )

    # ---------------------------------------------------------
    # Get forecast
    # ---------------------------------------------------------

    forecast = adapter.get_forecast_at_time(
        latitude=10.0,
        longitude=85.0,
        target_time="2026-09-25 06:00:00"
    )

    print("\nINCOIS Marine Forecast")
    print("=" * 50)

    print(forecast)

    # ---------------------------------------------------------
    # Safety Engine test
    # ---------------------------------------------------------

    safety_engine = SafetyEngine()

    result = safety_engine.evaluate(
        forecast
    )

    print("\nORCA Safety Decision")
    print("=" * 50)

    print("Status:")
    print(result["status"])

    print("\nReasons:")

    for reason in result["reasons"]:
        print("-", reason)

    print("\nWarnings:")

    for warning in result["warnings"]:
        print("-", warning)