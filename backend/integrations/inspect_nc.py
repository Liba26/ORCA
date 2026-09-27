from netCDF4 import Dataset

FILE = r"C:\Users\Liba Shasmeen\Downloads\rsmc_combined_ww3_20260923.nc"

with Dataset(FILE, "r") as ds:

    variables = [
        "HS",
        "PWP",
        "MWD",
        "UWND",
        "VWND"
    ]

    print("\nINCOIS Variable Metadata")
    print("=" * 70)

    for name in variables:

        var = ds.variables[name]

        print(f"\n{name}")
        print("-" * 70)

        print("Long name:", getattr(var, "long_name", "Not available"))
        print("Units:", getattr(var, "units", "Not available"))
        print("Standard name:", getattr(var, "standard_name", "Not available"))
        print("Dimensions:", var.dimensions)