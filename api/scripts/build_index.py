#!/usr/bin/env python3
"""Build (or rebuild) the FAISS index from api/data/records.json."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.rag import build_index, load_records


def main():
    settings = get_settings()
    records = load_records(settings.records_path)
    print(f"Building FAISS index from {len(records)} records…")
    build_index(settings, force=True)
    print(f"Saved → {settings.faiss_dir}")


if __name__ == "__main__":
    main()
