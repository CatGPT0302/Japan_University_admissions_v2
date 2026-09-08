from __future__ import annotations

import html
import sys
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import extract_direct as extract_direct  # noqa: E402
from scripts.db import (  # noqa: E402
    confirm_all_by_doc,
    get_conn,
    get_records,
    get_staging_records,
    init_db,
    update_staging_record,
)


INPUT_DIR = ROOT / "input_pdfs"
INPUT_DIR.mkdir(parents=True, exist_ok=True)


EDITABLE_FIELDS = [
    "university",
    "admission_year",
    "admission_period",
    "faculty",
    "department",
    "application_period",
    "deadline_rule",
    "eju_session",
    "eju_japanese",
    "eju_general",
    "eju_math",
    "eju_physics",
    "eju_chemistry",
    "eju_biology",
    "english_requirement",
    "screening_method",
    "screening_schedule",
    "result_date",
    "enrollment_period",
    "prefecture",
    "campus",
    "confidence",
    "needs_review",
]


def _value(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


def _save_uploaded_pdf(uploaded_file) -> Path:
    save_path = INPUT_DIR / Path(uploaded_file.name).name
    save_path.write_bytes(uploaded_file.getbuffer())
    return save_path


def _run_extraction(pdf_path: Path, university: str, year: str, url: str) -> dict[str, Any]:
    result = extract_direct.run_extraction(pdf_path, university, str(year), url or "")
    return {
        "doc_id": result.get("doc_id"),
        "status": result.get("status"),
        "records": result.get("records", 0),
        "failed_pages": result.get("failed_pages", []),
    }


def _record_count() -> int:
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) AS c FROM admission_records").fetchone()
    conn.close()
    return int(row["c"] if row else 0)


def _distinct_values(column: str) -> list[str]:
    conn = get_conn()
    if column == "university":
        sql = """
        SELECT DISTINCT COALESCE(NULLIF(TRIM(ar.university), ''), NULLIF(TRIM(sd.university), '')) AS value
        FROM admission_records ar
        LEFT JOIN source_documents sd ON sd.id = ar.document_id
        WHERE COALESCE(NULLIF(TRIM(ar.university), ''), NULLIF(TRIM(sd.university), '')) IS NOT NULL
          AND TRIM(COALESCE(NULLIF(TRIM(ar.university), ''), NULLIF(TRIM(sd.university), ''))) <> ''
        ORDER BY value
        """
    else:
        sql = f"""
        SELECT DISTINCT {column} AS value
        FROM admission_records
        WHERE {column} IS NOT NULL AND TRIM(CAST({column} AS TEXT)) <> ''
        ORDER BY {column}
        """
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [str(row["value"]) for row in rows if str(row["value"]).strip()]


def _distinct_universities() -> list[str]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT DISTINCT COALESCE(NULLIF(TRIM(ar.university), ''), sd.university) AS univ
        FROM admission_records ar
        LEFT JOIN source_documents sd ON sd.id = ar.document_id
        WHERE COALESCE(NULLIF(TRIM(ar.university), ''), sd.university) IS NOT NULL
          AND TRIM(COALESCE(NULLIF(TRIM(ar.university), ''), sd.university)) <> ''
        ORDER BY univ
        """
    ).fetchall()
    conn.close()
    return [str(r["univ"]) for r in rows]


def _load_records(university: str = "", year: str = "") -> list[dict[str, Any]]:
    conditions = []
    params: list[Any] = []
    if university:
        conditions.append("university = ?")
        params.append(university)
    if year:
        conditions.append("admission_year = ?")
        params.append(str(year))
    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    conn = get_conn()
    rows = conn.execute(
        f"""
        WITH records AS (
            SELECT
                ar.id AS sort_id,
                COALESCE(NULLIF(TRIM(ar.university), ''), NULLIF(TRIM(sd.university), '')) AS university,
                COALESCE(NULLIF(TRIM(ar.admission_year), ''), NULLIF(TRIM(sd.admission_year), '')) AS admission_year,
                ar.faculty,
                ar.department,
                ar.english_requirement,
                ar.screening_method,
                ar.result_date
            FROM admission_records ar
            LEFT JOIN source_documents sd ON sd.id = ar.document_id
        )
        SELECT university, admission_year, faculty, department, english_requirement, screening_method, result_date
        FROM records
        {where_sql}
        ORDER BY sort_id DESC
        """,
        params,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _render_table(rows: list[dict]) -> None:
    if not rows:
        st.info("无数据")
        return
    headers = list(rows[0].keys())
    header_row = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body_rows = ""
    for row in rows:
        cells = "".join(
            f"<td title='{html.escape(str(row.get(h, '')))}'>{html.escape(str(row.get(h, '')))}</td>"
            for h in headers
        )
        body_rows += f"<tr>{cells}</tr>"
    html_str = f"""
    <style>
    table {{width:100%;border-collapse:collapse;font-size:13px;table-layout:fixed;}}
    th {{background:#2563EB;color:white;padding:6px 10px;text-align:left;}}
    td {{
        padding:6px 10px;
        border-bottom:1px solid #e2e8f0;
        max-width:150px;
        overflow:hidden;
        text-overflow:ellipsis;
        white-space:nowrap;
        height:36px;
    }}
    tr:hover td {{background:#f1f5f9;}}
    </style>
    <table><thead><tr>{header_row}</tr></thead>
    <tbody>{body_rows}</tbody></table>
    """
    st.markdown(html_str, unsafe_allow_html=True)


def _page_upload() -> None:
    st.subheader("Upload")
    uploaded = st.file_uploader("PDF", type=["pdf"])
    university = st.text_input("University")
    year = st.text_input("Year")
    url = st.text_input("Source URL")

    if st.button("Start Extraction", type="primary", disabled=uploaded is None or not university or not year):
        pdf_path = _save_uploaded_pdf(uploaded)
        with st.spinner("Extracting..."):
            result = _run_extraction(pdf_path, university, year, url)
        st.success("Done")
        st.write(result)


def _page_staging() -> None:
    st.subheader("Staging")
    doc_id = st.number_input("doc_id", min_value=1, step=1, value=26, key="staging_doc_id_input")

    if st.button("Search", type="primary"):
        records = get_staging_records(int(doc_id))
        st.session_state["staging_records"] = records
        st.session_state["staging_doc_id"] = int(doc_id)

    records = st.session_state.get("staging_records", [])
    if not records:
        return

    needs_review_count = sum(1 for row in records if int(row.get("needs_review") or 0) == 1)
    st.caption(f"needs_review=1 count: {needs_review_count}")

    _render_table(records)

    options = {
        f"#{row['id']} {row.get('faculty', '')} / {row.get('department', '')}": row
        for row in records
    }
    selected_label = st.selectbox("选择 staging 记录", list(options.keys()))
    record = options[selected_label]

    with st.form(f"staging_form_{record['id']}"):
        values: dict[str, str] = {}
        for field in EDITABLE_FIELDS:
            values[field] = st.text_input(field, value=_value(record.get(field)), key=f"{record['id']}_{field}")
        submitted = st.form_submit_button("Save Changes")
        if submitted:
            updated = update_staging_record(int(record["id"]), values)
            if updated:
                st.success(f"Saved staging record {record['id']}")
            else:
                st.error(f"Failed to save staging record {record['id']}")


def _page_confirm() -> None:
    st.subheader("Confirm")
    doc_id = st.number_input("doc_id", min_value=1, step=1, value=26, key="confirm_doc_id")
    if st.button("Confirm Import", type="primary"):
        result = confirm_all_by_doc(int(doc_id))
        st.success("Confirmed")
        st.write({"confirmed": int(result.get("written", 0)), "skipped": int(result.get("skipped", 0))})


def _page_records() -> None:
    st.subheader("Records")
    universities = [""] + _distinct_universities()
    years = [""] + _distinct_values("admission_year")
    col1, col2 = st.columns(2)
    with col1:
        university = st.selectbox("University", universities, index=0)
    with col2:
        year = st.selectbox("Year", years, index=0)

    rows = _load_records(university=university, year=year)
    st.caption(f"Total rows: {len(rows)}")
    _render_table(rows)

    # Excel export
    if rows:
        if st.button("Export to Excel", type="secondary"):
            try:
                import io
                from openpyxl import Workbook
                from openpyxl.styles import Alignment, Font, PatternFill

                wb = Workbook()
                ws = wb.active
                ws.title = "募集要項"
                headers = list(rows[0].keys())
                header_font = Font(bold=True, color="FFFFFF", size=11)
                header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
                for ci, h in enumerate(headers, 1):
                    cell = ws.cell(row=1, column=ci, value=h)
                    cell.font = header_font
                    cell.fill = header_fill
                for ri, row in enumerate(rows, 2):
                    for ci, h in enumerate(headers, 1):
                        ws.cell(row=ri, column=ci, value=row.get(h, ""))
                ws.auto_filter.ref = ws.dimensions
                ws.freeze_panes = "A2"
                buf = io.BytesIO()
                wb.save(buf)
                st.download_button(
                    "Download Excel",
                    data=buf.getvalue(),
                    file_name="admissions_v2_export.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.xml",
                )
            except ImportError:
                st.error("openpyxl not installed. Run: pip install openpyxl")


def main() -> None:
    init_db()
    st.set_page_config(page_title="admissions_v2", layout="wide")
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Page", ["Upload", "Staging", "Confirm", "Records"])

    if page == "Upload":
        _page_upload()
    elif page == "Staging":
        _page_staging()
    elif page == "Confirm":
        _page_confirm()
    else:
        _page_records()


if __name__ == "__main__":
    main()
