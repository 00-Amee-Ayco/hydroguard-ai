"""Regenerate genuine API outputs: python -m scripts.generate_examples."""
import json
from pathlib import Path
from fastapi.testclient import TestClient
from hydroguard.api import app


def main():
    directory = Path(__file__).resolve().parents[1]
    with TestClient(app) as client:
        for file in sorted((directory / "input_examples").glob("*.json")):
            response = client.post("/run", json=json.loads(file.read_text()))
            response.raise_for_status()
            (directory / "output_examples" / file.name).write_text(
                json.dumps(response.json(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
