"""Package already-read local PDFs; never perform model calls or auto-confirmation."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
import subprocess
import sys

from scripts.import_demo_data import TEXT_FIELDS, validate_package

ROOT = Path(__file__).resolve().parents[1]
DISPLAY = (
    ("application_period", "出愿时间"), ("deadline_rule", "截止规则"),
    ("eju_session", "EJU场次"), ("eju_japanese", "EJU日语"),
    ("eju_general", "EJU综合"), ("eju_math", "EJU数学"),
    ("eju_physics", "物理"), ("eju_chemistry", "化学"), ("eju_biology", "生物"),
    ("english_requirement", "英语要求"), ("screening_method", "选考方式"),
    ("screening_schedule", "考试时间"), ("result_date", "放榜"),
    ("enrollment_period", "入学手续"), ("eligibility", "资格"),
    ("required_documents", "材料"),
)


def prepare_batch(pdf_dir: Path, package_dir: Path) -> list[dict]:
    if not pdf_dir.is_dir() or not package_dir.is_dir():
        raise ValueError("PDF and extraction directories must exist")
    sources = {}
    for path in sorted(pdf_dir.iterdir()):
        if path.is_file() and path.suffix.lower() == ".pdf":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            sources.setdefault(digest, path)
    if not sources:
        raise ValueError("No PDFs in the input folder (subfolders are not scanned)")
    packages = {}
    for path in sorted(package_dir.glob("*.json")):
        package = json.loads(path.read_text(encoding="utf-8"))
        document = package.get("document") if isinstance(package, dict) else None
        digest = document.get("sha256") if isinstance(document, dict) else None
        if not isinstance(digest, str):
            raise ValueError(f"Invalid extraction package: {path.name}")
        if digest in packages:
            raise ValueError(f"Multiple extraction packages for one PDF: {path.name}")
        packages[digest] = (path, package)
    missing = [path.name for digest, path in sources.items() if digest not in packages]
    if missing:
        raise ValueError("Codex reading still needed for: " + ", ".join(missing))
    batch = []
    for digest, source in sources.items():
        path, package = packages[digest]
        validate_package(package, source)
        batch.append({"source": source, "package_path": path, "package": package})
    return batch


def _md(value: str) -> str:
    return html.escape(str(value)).replace("|", "&#124;").replace("\n", "<br>")


def _csv(value: str) -> str:
    # Protect spreadsheet readers; unmodified values remain in records.jsonl.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def write_bundle(batch: list[dict], output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    records, review = [], []
    report = ["# 招生资料阅读草稿", "", "全部待人工复核；结构校验通过不等于事实准确。日期按原文年度保留，不代表当前仍可申请。", ""]
    report.extend(["## 报考方向总览", "",
                   "| 大学 / 年度 | 学部 / 报考方向 | 入试方式 | 出愿时间 |",
                   "| --- | --- | --- | --- |"])
    for item in batch:
        for row in item["package"]["records"]:
            report.append("| " + " | ".join(_md(value) for value in (
                row["university"] + " / " + row["admission_year"],
                row["faculty"] + " / " + row["department"],
                row.get("admission_period", "未提供，需复核"),
                row["application_period"],
            )) + " |")
    report.extend(["", "以下逐项列出完整条件；总览不代替原文和人工复核。", ""])
    for item in batch:
        package = item["package"]
        document = package["document"]
        for index, record in enumerate(package["records"], 1):
            record_id = f"{document['sha256']}:{index}"
            public = {key: record[key] for key in TEXT_FIELDS if key in record}
            public.update(record_id=record_id, source=document,
                          field_evidence=record["field_evidence"], warnings=record.get("warnings", []),
                          review_status="needs_review")
            records.append(public)
            report.extend([f"## {_md(record['university'])} · {_md(record['admission_year'])}",
                           f"**{_md(record['faculty'])} / {_md(record['department'])}**", "",
                           f"入试方式：{_md(record.get('admission_period', '未提供，需复核'))}", "",
                           f"来源：{_md(document['source_url'])}", "",
                           "| 项目 | 当前值 | PDF页码 |", "| --- | --- | --- |"])
            for key, label in DISPLAY:
                value = record.get(key, "")
                evidence = record["field_evidence"].get(key, {})
                report.append(f"| {label} | {_md(value or '未提供，需复核')} | {evidence.get('page', '未提供')} |")
                review.append({"record_id": record_id, "university": record["university"],
                               "department": record["department"], "field": key, "current_value": value,
                               "page": evidence.get("page"), "quote": evidence.get("text", ""),
                               "review_action": "compare_source", "review_question": f"请核对{label}及其条件、例外；缺依据时补充原文，不猜测。"})
            report.extend(["", "待复核问题："] + [f"- {_md(w)}" for w in record.get("warnings", [])] + [""])
    (output / "records.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records), encoding="utf-8")
    (output / "records_readable.md").write_text("\n".join(report), encoding="utf-8")
    columns = ["university", "admission_year", "faculty", "department", *(key for key, _ in DISPLAY), "review_status"]
    with (output / "records_table.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows({key: _csv(str(row.get(key, ""))) for key in columns} for row in records)
    (output / "review_queue.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"status": "needs_human_review", "documents": len(batch), "records": len(records),
               "structural_validation": "passed", "factual_accuracy": "not_certified",
               "confirmed_records_written": 0}
    (output / "validation_report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_dir", type=Path)
    parser.add_argument("--extractions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New directory; existing output is never overwritten")
    parser.add_argument("--import-staging", action="store_true", help="Also import each document into isolated demo staging")
    args = parser.parse_args()
    try:
        batch = prepare_batch(args.pdf_dir, args.extractions)
        summary = write_bundle(batch, args.output)
        imports = []
        if args.import_staging:
            for item in batch:
                result = subprocess.run([sys.executable, "-m", "scripts.import_demo_data",
                                         str(item["package_path"].resolve()), "--source-pdf",
                                         str(item["source"].resolve()), "--apply"], cwd=ROOT,
                                        text=True, capture_output=True)
                imports.append({"source_sha256": item["package"]["document"]["sha256"],
                                "success": result.returncode == 0})
                (args.output / "import_status.json").write_text(json.dumps(imports, indent=2), encoding="utf-8")
                if result.returncode:
                    raise RuntimeError("Staging import stopped; earlier documents may be imported. Inspect import_status.json. The readable bundle remains available.")
        print(json.dumps(summary, ensure_ascii=False))
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f"Batch failed: {exc}\n")


if __name__ == "__main__":
    main()
