"""Evaluate Keyword, Semantic, and Hybrid ranking on genuine labeled real candidate datasets."""

import json
import sys
from pathlib import Path
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.api.admin import execute_benchmark_evaluation
from app.core.database import SessionLocal


def main():
    db = SessionLocal()
    try:
        try:
            run = execute_benchmark_evaluation(db)
        except HTTPException as exc:
            print(json.dumps({"status": "skipped", "reason": exc.detail}, indent=2))
            return
        print(json.dumps({
            "benchmark_name": run.benchmark_name,
            "total_candidates": run.total_candidates,
            "model_comparison": run.model_comparison,
            "relevance_treatment_note": run.relevance_treatment_note,
            "dataset_disclaimer": run.dataset_disclaimer,
        }, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
