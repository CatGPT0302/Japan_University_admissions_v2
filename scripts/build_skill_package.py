"""Build a portable skill ZIP from an explicit allowlist, without private runtime data."""
import argparse
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = "admissions-pdf-batch-extractor"


def build(output: Path) -> None:
    files = {
        "SKILL.md": ROOT / "skills" / NAME / "SKILL.md",
        "references/schema.md": ROOT / "skills" / NAME / "references/schema.md",
        "scripts/package_data.py": ROOT / "skills" / NAME / "scripts/package_data.py",
        "scripts/demo_batch.py": ROOT / "scripts/demo_batch.py",
        "scripts/import_demo_data.py": ROOT / "scripts/import_demo_data.py",
        "scripts/local_demo.py": ROOT / "scripts/local_demo.py",
        "scripts/submit_extraction.py": ROOT / "scripts/submit_extraction.py",
    }
    for source in files.values():
        if not source.is_file():
            raise FileNotFoundError(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{NAME}/scripts/__init__.py", "")
        for name, source in files.items():
            archive.write(source, f"{NAME}/{name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    build(parser.parse_args().output)

