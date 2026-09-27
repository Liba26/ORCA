from fastapi import FastAPI
from backend.services.marine_data_service import MarineDataService

app = FastAPI(
    title="ORCA Marine Intelligence API",
    version="1.0.0"
)

LOCAL_INCOIS_FILE = (
    r"C:\Users\Liba Shasmeen\Downloads\rsmc_combined_ww3_20260923.nc"
)

marine_service = MarineDataService(
    local_file=LOCAL_INCOIS_FILE
)


@app.get("/")
def root():
    return {
        "system": "ORCA",
        "status": "online"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/api/marine/decision")
def marine_decision(
    latitude: float,
    longitude: float,
    target_time: str
):
    result = marine_service.get_marine_decision(
        latitude=latitude,
        longitude=longitude,
        target_time=target_time
    )

    return result