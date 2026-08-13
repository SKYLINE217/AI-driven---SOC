import os
from pathlib import Path

BASE_DIR   = Path(__file__).parent
DATA_DIR   = Path(os.getenv("SOC_DATA_DIR",   str(BASE_DIR / "data")))
MODEL_DIR  = Path(os.getenv("SOC_MODEL_DIR",  str(DATA_DIR / "models")))
OUTPUT_DIR = Path(os.getenv("SOC_OUTPUT_DIR", str(BASE_DIR / "output")))
DB_PATH    = Path(os.getenv("SOC_DB_PATH",    str(DATA_DIR / "soc_triager.db")))
MITRE_STIX = Path(os.getenv("SOC_MITRE_STIX", str(DATA_DIR / "mitre" /
                             "enterprise-attack-v15.1.json")))

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
