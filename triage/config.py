import os
from dotenv import load_dotenv

load_dotenv()

NEBIUS_BASE_URL = os.getenv("NEBIUS_BASE_URL",
                            "https://api.tokenfactory.nebius.com/v1/")
MODELS = {
    "intake":  os.getenv("MODEL_INTAKE"),
    "intel":   os.getenv("MODEL_INTEL"),
    "mapper":  os.getenv("MODEL_MAPPER"),
    "triage":  os.getenv("MODEL_TRIAGE"),
    "advisor": os.getenv("MODEL_ADVISOR"),
}
missing = [k for k, v in MODELS.items() if not v]
if missing:
    raise SystemExit(f"Set MODEL_* in .env for: {missing}")
