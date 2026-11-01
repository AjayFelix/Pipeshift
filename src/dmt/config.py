import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent.parent
STAGING_DIR = ROOT / "data" / "staging"

POSTGRES_DSN = os.environ["POSTGRES_DSN"]
MOTHERDUCK_TOKEN = os.environ.get("MOTHERDUCK_TOKEN", "")
MOTHERDUCK_DB = os.environ.get("MOTHERDUCK_DB", "dmt")

# studentVle has ~10.6M rows; extracted/loaded in batches of this size rather
# than as one unbounded query/write.
BATCH_SIZE = 500_000
