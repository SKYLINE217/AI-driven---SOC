import os
from pathlib import Path

REPO_ROOT  = Path(__file__).resolve().parent.parent
BASE_DIR   = Path(__file__).resolve().parent

# Check if data directory exists at repo root or inside backend
_default_data = REPO_ROOT / "data" if (REPO_ROOT / "data").exists() else (BASE_DIR / "data")
DATA_DIR   = Path(os.getenv("SOC_DATA_DIR", str(_default_data)))
MODEL_DIR  = Path(os.getenv("SOC_MODEL_DIR", str(DATA_DIR / "models")))
OUTPUT_DIR = Path(os.getenv("SOC_OUTPUT_DIR", str(REPO_ROOT / "output")))
DB_PATH    = Path(os.getenv("SOC_DB_PATH", str(DATA_DIR / "soc_triager.db")))

_stix_candidate = DATA_DIR / "mitre" / "enterprise-attack-v15.1.json"
if not _stix_candidate.exists() and (REPO_ROOT / "data" / "mitre" / "enterprise-attack-v15.1.json").exists():
    _stix_candidate = REPO_ROOT / "data" / "mitre" / "enterprise-attack-v15.1.json"

MITRE_STIX = Path(os.getenv("SOC_MITRE_STIX", str(_stix_candidate)))

DEFAULT_THRESHOLD   = float(os.getenv("SOC_THRESHOLD",   "0.40"))

IF_WEIGHT           = float(os.getenv("SOC_IF_WEIGHT",   "0.60"))
AE_WEIGHT           = float(os.getenv("SOC_AE_WEIGHT",   "0.40"))
AE_BENIGN_P95       = float(os.getenv("SOC_AE_P95",      "0.50"))

WINDOW_1M  = 60
WINDOW_5M  = 300
WINDOW_1H  = 3600

CLUSTER_WINDOW_SECS = int(os.getenv("SOC_CLUSTER_WINDOW", "300"))

LOG_LEVEL = os.getenv("SOC_LOG_LEVEL", "WARNING")

DEFAULT_ACTOR = os.getenv("SOC_ACTOR", "analyst")
