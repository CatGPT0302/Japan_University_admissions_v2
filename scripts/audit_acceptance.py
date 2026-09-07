"""Read-only structural/coverage audit; never certify facts or publish records."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from scripts.import_demo_data import validate_package


def audit(manifest_path, pdf_dir, extraction_dir, database=None):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    report = {"documents": 0, "records": 0, "errors": [], "coverage": [],
              "factual_accuracy": "requires_source_review", "publication_ready": False}
    packages = {}
    for path in sorted(Path(extraction_dir).glob("*.json")):
        try:
            package = json.loads(path.read_text(encoding="utf-8"))
            digest = package["document"]["sha256"]
            if digest in packages:
                raise ValueError("Duplicate extraction for the same source hash")
            packages[digest] = package
        except (ValueError, KeyError, TypeError) as exc:
            report["errors"].append(f"{path.name}: {exc}")
    if not packages:
        report["errors"].append("No extraction packages to audit")
    sources = {hashlib.sha256(p.read_bytes()).hexdigest(): p
               for p in Path(pdf_dir).glob("*.pdf")}
    identities = set()
    valid = []
    for digest, package in packages.items():
        try:
            if digest not in sources:
                raise ValueError("Matching local PDF is missing")
            validate_package(package, sources[digest])
            for row in package["records"]:
                identity = tuple(row.get(k, "") for k in (
                    "university", "admission_year", "faculty", "department", "admission_period"))
                if identity in identities:
                    raise ValueError("Duplicate program/route across packages")
                identities.add(identity)
            report["documents"] += 1
            report["records"] += len(package["records"])
            valid.append(package)
        except (ValueError, OSError, TypeError, KeyError) as exc:
            report["errors"].append(f"{digest}: {exc}")
    valid_hashes = {p["document"]["sha256"] for p in valid}
    for university in manifest["universities"]:
        excluded = university.get("acceptance_status") == "excluded_by_user"
        pending = [p["id"] for p in university["pdfs"] if p.get("sha256") not in valid_hashes]
        report["coverage"].append({"university": university["name"],
            "status": "excluded_by_user" if excluded else "pending" if pending else "drafts_only",
            "pending_pdf_ids": [] if excluded else pending,
            "route_coverage_certified": False})
    if database:
        conn = sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            for package in valid:
                fingerprint = hashlib.sha256(json.dumps(package, ensure_ascii=False,
                    sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                receipt = conn.execute("SELECT * FROM extraction_ingestions WHERE id=?", (fingerprint,)).fetchone()
                if not receipt:
                    report["errors"].append(f"Missing import receipt: {fingerprint}")
                    continue
                rows = conn.execute("SELECT * FROM admission_records_staging WHERE document_id=? ORDER BY id",
                                    (receipt["document_id"],)).fetchall()
                if len(rows) != len(package["records"]):
                    report["errors"].append(f"Record count mismatch: {fingerprint}")
                    continue
                for actual, expected in zip(rows, package["records"]):
                    for key, value in expected.items():
                        if key in {"warnings", "field_evidence"}:
                            continue
                        if actual[key] != value:
                            report["errors"].append(f"Draft differs from package: record {actual['id']} / {key}; inspect human edits")
                    evidence = json.loads(actual["field_evidence"] or "{}")
                    if evidence != expected["field_evidence"]:
                        report["errors"].append(f"Evidence differs: record {actual['id']}")
            report["confirmed_records"] = conn.execute("SELECT count(*) FROM admission_records").fetchone()[0]
        finally:
            conn.close()
    report["structural_status"] = "failed" if report["errors"] else "passed"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--pdfs", type=Path, required=True)
    parser.add_argument("--extractions", type=Path, required=True)
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    result = audit(args.manifest, args.pdfs, args.extractions, args.database)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
