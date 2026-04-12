from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import sys
import tempfile
import time

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _create_docs(root: Path, count: int) -> None:
    for idx in range(count):
        content = f"# Doc {idx}\n\nThis is benchmark document {idx}.\n"
        _ = (root / f"doc{idx:04d}.md").write_text(content, encoding="utf-8")


def _run_once(source_dir: Path, workers: int) -> tuple[float, int]:
    ingest_module = importlib.import_module("docprep.ingest")
    ingestor_cls = getattr(ingest_module, "Ingestor")
    start = time.perf_counter()
    result = ingestor_cls().run(source_dir, workers=workers)
    elapsed = time.perf_counter() - start
    return elapsed, result.processed_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark ingest parse+chunk concurrency")
    parser.add_argument("--docs", type=int, default=100, help="Number of markdown files")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="docprep-bench-") as temp_dir:
        source_dir = Path(temp_dir)
        _create_docs(source_dir, args.docs)

        print(f"Benchmarking {args.docs} markdown files")
        print("workers | seconds | docs")
        print("--------+---------+-----")

        for workers in (1, 2, 4, 8):
            elapsed, processed = _run_once(source_dir, workers)
            print(f"{workers:7d} | {elapsed:7.3f} | {processed:4d}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
