"""
ORCA - INCOIS SVAS Adapter

Retrieves the latest SVAS advisory directly from the
official INCOIS GeoJSON endpoint and converts it into
normalized SVAS safety rules using svas_parser.py.

Source:
    https://www.incois.gov.in/oceanservices/SVAS/SVAS_Advisory.geojson

This adapter does NOT make safety decisions.
It only:
    1. Downloads the official SVAS GeoJSON.
    2. Validates the response.
    3. Passes the GeoJSON to the SVAS parser.
    4. Returns normalized SVAS rules.

Safety decision / route veto will be implemented separately.
"""

import sys
import os

import requests


# ---------------------------------------------------------------------
# Make backend importable when this file is run directly
# ---------------------------------------------------------------------

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)


from backend.svas_parser import parse_geojson


class SVASAdapter:

    # Official INCOIS SVAS advisory endpoint.
    SVAS_URL = (
        "https://www.incois.gov.in/"
        "oceanservices/SVAS/SVAS_Advisory.geojson"
    )

    def __init__(
        self,
        url=None,
        timeout=30
    ):
        """
        Create an SVAS adapter.

        Args:
            url:
                Optional custom URL. Useful for testing.

            timeout:
                HTTP request timeout in seconds.
        """

        self.url = url or self.SVAS_URL
        self.timeout = timeout

    # -----------------------------------------------------------------
    # Download official SVAS GeoJSON
    # -----------------------------------------------------------------

    def fetch_geojson(self):
        """
        Retrieve the latest SVAS GeoJSON directly from INCOIS.

        Returns:
            Python dictionary containing the GeoJSON.
        """

        response = requests.get(
            self.url,
            timeout=self.timeout
        )

        response.raise_for_status()

        # Make sure the response can actually be interpreted
        # as JSON.
        try:
            data = response.json()

        except ValueError as exc:
            raise RuntimeError(
                "INCOIS SVAS endpoint did not return valid JSON."
            ) from exc

        if not isinstance(data, dict):
            raise RuntimeError(
                "INCOIS SVAS response is not a JSON object."
            )

        if data.get("type") != "FeatureCollection":
            raise RuntimeError(
                "INCOIS SVAS response is not a "
                "GeoJSON FeatureCollection."
            )

        if "features" not in data:
            raise RuntimeError(
                "INCOIS SVAS GeoJSON does not contain "
                "a 'features' field."
            )

        return data

    # -----------------------------------------------------------------
    # Get normalized SVAS rules
    # -----------------------------------------------------------------

    def get_rules(self):
        """
        Download the official INCOIS SVAS GeoJSON and
        convert it into normalized safety rules.

        Returns:
            List of normalized SVAS rules.
        """

        geojson = self.fetch_geojson()

        rules = parse_geojson(
            geojson
        )

        return rules

    # -----------------------------------------------------------------
    # Get both raw GeoJSON and parsed rules
    # -----------------------------------------------------------------

    def get_advisory_data(self):
        """
        Retrieve the official SVAS data and return both:

            raw GeoJSON
            normalized rules

        Useful for debugging and later API integration.
        """

        geojson = self.fetch_geojson()

        rules = parse_geojson(
            geojson
        )

        return {
            "source": "INCOIS",
            "data_type": "SVAS",
            "source_url": self.url,
            "feature_count": len(
                geojson.get("features", [])
            ),
            "rule_count": len(rules),
            "geojson": geojson,
            "rules": rules,
        }


# ---------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------

if __name__ == "__main__":

    print()
    print("ORCA - INCOIS SVAS Adapter Test")
    print("=" * 50)

    adapter = SVASAdapter()

    try:

        data = adapter.get_advisory_data()

        print()
        print("SVAS endpoint:")
        print(data["source_url"])

        print()
        print("GeoJSON features:")
        print(data["feature_count"])

        print()
        print("Parsed SVAS rules:")
        print(data["rule_count"])

        print()
        print("First few rules")
        print("-" * 50)

        for rule in data["rules"][:10]:

            print(
                f"{rule['district']} | "
                f"{rule['source_field']} | "
                f"Day-{rule['day']} | "
                f"{rule['date']} | "
                f"Width < {rule['boat_width_limit_m']}m | "
                f"{rule['status']} | "
                f"Color: {rule['color']}"
            )

    except Exception as exc:

        print()
        print("SVAS retrieval/parsing failed:")
        print(type(exc).__name__)
        print(str(exc))