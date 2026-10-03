# scripts/download_data.py
"""Download the Transfermarkt dataset from Kaggle into data/raw."""
import shutil
from pathlib import Path

import kagglehub

from config import RAW_DIR

path = Path(kagglehub.dataset_download("davidcariboo/player-scores"))
print("Downloaded to:", path)

RAW_DIR.mkdir(parents=True, exist_ok=True)
for f in path.iterdir():
    shutil.copy(f, RAW_DIR)
