"""Generate the explicitly synthetic two-page PDF and ingest it locally."""
import json
from hydroguard.cases.riverside import prepare

if __name__ == "__main__":
    print(json.dumps(prepare(),indent=2))
