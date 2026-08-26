import argparse
import requests
from datetime import datetime, timedelta
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--start", required=True)
parser.add_argument("--end", required=True)
parser.add_argument("--output", default="gharchive")
args = parser.parse_args()

start = datetime.strptime(args.start, "%Y-%m-%d-%H")
end = datetime.strptime(args.end, "%Y-%m-%d-%H")

Path(args.output).mkdir(exist_ok=True)

while start <= end:
    filename = f"{start:%Y-%m-%d}-{start.hour}.json.gz"
    path = Path(args.output) / filename
    url = f"https://data.gharchive.org/{filename}"

    if not path.exists():
        print(f"Downloading {filename}")
        path.write_bytes(requests.get(url).content)

    start += timedelta(hours=1)