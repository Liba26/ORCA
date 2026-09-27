class VesselProfile:

    def __init__(
        self,
        vessel_type,
        beam_width_m
    ):
        self.vessel_type = vessel_type
        self.beam_width_m = beam_width_m

    def to_dict(self):
        return {
            "vessel_type": self.vessel_type,
            "beam_width_m": self.beam_width_m
        }


# ---------------------------------------------------------
# Test
# ---------------------------------------------------------

if __name__ == "__main__":

    vessel = VesselProfile(
        vessel_type="small_fishing_vessel",
        beam_width_m=4.5
    )

    print("\nORCA Vessel Profile")
    print("=" * 50)

    print(vessel.to_dict())