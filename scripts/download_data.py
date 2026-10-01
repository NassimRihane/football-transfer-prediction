import kagglehub
import shutil
import os

path = kagglehub.dataset_download("davidcariboo/player-scores")
print("Dled in :", path)

os.makedirs("data/raw", exist_ok=True)
for f in os.listdir(path):
    shutil.copy(os.path.join(path, f), "data/raw")