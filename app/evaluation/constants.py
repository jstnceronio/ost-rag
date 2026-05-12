from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_PATH = ROOT_DIR / "resources" / "datasets" / "generated_cases.jsonl"
DEFAULT_RESULTS_DIR = ROOT_DIR / "resources" / "evaluation_runs"
