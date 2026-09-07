"""Standalone share-package entrypoint: validated drafts only, no database actions."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_batch import prepare_batch, write_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_dir", type=Path)
    parser.add_argument("--extractions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = write_bundle(prepare_batch(args.pdf_dir, args.extractions), args.output)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f"Cannot package drafts: {exc}\n")
    print(f"{result['documents']} documents, {result['records']} draft records. Human review required.")


if __name__ == "__main__":
    main()
