# Final Acceptance And Agent Prompts

This project scope is frozen. Do not redesign the product or expand it into a C-end app, generic PDF parser, complex agent system, competitor feature set, or legacy Excel migration.

## 1. Final Acceptance Standard

### 1.1 Final Project Definition

The final delivery target is:

```text
募集要項 PDF
→ field extraction
→ field normalization
→ staging / records database
→ standard Excel master export
```

The product is an internal admissions data production tool for extracting Japanese university 募集要項 fields into a unified Excel master table.

### 1.2 Extraction Layer

The single MVP extraction command must remain:

```powershell
python scripts/extract_fields.py <pdf_path> --output output.json
```

Optional staging save:

```powershell
python scripts/extract_fields.py <pdf_path> --output output.json --save-staging
```

The output JSON must contain:

```json
{
  "university": "",
  "admission_year": "",
  "admission_system": "",
  "application_period": "",
  "deadline_rule": "",
  "records": []
}
```

Each record must preserve at least these keys:

```text
faculty
department
application_period
deadline_rule
eju_session
eju_japanese
eju_general
eju_math
eju_physics
eju_chemistry
eju_biology
english_requirement
screening_method
screening_schedule
result_date
enrollment_period
prefecture
campus
confidence
needs_review
warnings
field_evidence
```

For the Waseda 2027 complex PDF baseline:

```text
records >= 10
extra_records <= 3
deadline_rule is non-empty
English/EJU cross-contamination = 0
No obvious invented departments such as 法学科 / 商学科 / 基幹理工学科
```

For normal PDFs:

```text
records are non-empty
university / year / faculty / department are readable
deadline_rule is extracted when present, otherwise a warning is acceptable
```

### 1.3 Normalization Layer

`scripts/normalize_fields.py` must expose:

```text
normalize_record()
normalize_extraction_result()
expand_department_rows()
normalize_eju_display()
normalize_english_requirement()
normalize_deadline_rule()
normalize_dates()
```

EJU final display values:

```text
〇
△
-
要確認
score condition text
```

Rules:

```text
Required subject -> 〇
Not required -> -
Selectable subject -> △
Unknown -> 要確認
Score requirement -> 日本語200点以上 / 数学150点以上
数学コース1 -> 〇（コース1）
数学コース2 -> 〇（コース2）
数学コース1または2 -> 〇（コース1または2）
物理・化学・生物から2科目 -> 物理=△, 化学=△, 生物=△, note in 出願要件・基準点など
物理・化学・生物から1科目 -> 物理=△, 化学=△, 生物=△, note in 出願要件・基準点など
```

English rules:

```text
TOEFL -> TOEFL iBT
IELTS -> IELTS Academic Module
TOEIC -> TOEIC L&R
Multiple accepted exams -> join with " / "
Not required -> -
Unknown -> 要確認
```

Cross-contamination rules:

```text
EJU columns must never contain TOEFL / IELTS / TOEIC / 英検 / ドイツ語 / フランス語
英語外部資格試験 must never contain 日本語 / 総合科目 / 数学 / 物理 / 化学 / 生物 / EJU
If contamination is detected, clean conservatively and add a warning.
```

Department expansion:

```text
Multiple actual departments / specializations -> split into multiple rows
学部一括 -> preserve
学科一括 -> preserve
Do not invent departments
```

### 1.4 TSV And Excel Export

TSV command:

```powershell
python scripts/export_tsv.py input.json --output output.tsv
```

Excel command:

```powershell
python scripts/export_excel.py input.json --output output.xlsx
```

Database master export:

```powershell
python scripts/export_excel.py --from-db --output admissions_master.xlsx
```

Excel must contain three sheets:

```text
抽出結果
README
字段映射
```

`抽出結果` sheet:

```text
Row 1: 日本大学留学生入試 募集要項抽出結果
Row 2: generated time / source note
Row 4: headers
Row 5+: data
Freeze panes: D5
Autofilter enabled
Fixed sensible widths
Long text wrapped
Dark blue-gray header, white bold text
Critical empty fields highlighted light yellow
```

Critical fields:

```text
出願期間
必着/消印
EJUの実施回
英語外部資格試験
選考方法
合格発表日
```

Final column order:

```text
大学名
出願時期
学部
学科・専修等
出願期間
必着/消印
出願要件・基準点など
EJUの実施回
日本語
総合科目
数学
物理
化学
生物
英語外部資格試験
選考方法
選考日程
合格発表日
入学手続期間
都道府県
キャンパス
更新人/更新日期
```

### 1.5 Database And UI

Database flow:

```text
AI extraction writes staging data.
Human review confirms staging into records.
Confirmed records are the source for final master Excel export.
AI extraction must never overwrite confirmed records automatically.
```

UI flow:

```text
Upload PDF
Start extraction
Show extraction status
Enter review
Confirm into records
Export Excel
```

Do not add:

```text
C-end app
professor database
AI chat
complex dashboard
competitor features
large visual redesign
```

## 2. Backend Optimization Prompt

```text
You are working on Japan_University_admissions_v2.

The project scope is frozen.

Backend goal:
Make the backend/data pipeline production-ready for the MVP:

PDF 募集要項
→ extract_fields.py
→ normalize_fields.py
→ staging DB
→ confirmed records
→ export_excel.py

Do NOT redesign the product.
Do NOT build a complex agent.
Do NOT rewrite extract_fields.py from scratch.
Do NOT change frontend UI in this task.
Do NOT process the old 2GB Excel.
Do NOT commit .env, DB files, rendered images, temp JSON, temp XLSX, or output_pages.

Focus only on backend/data flow.

Current important files:
- scripts/extract_fields.py
- scripts/normalize_fields.py
- scripts/export_tsv.py
- scripts/export_excel.py
- scripts/db.py
- scripts/api.py
- scripts/validator.py

Tasks:
1. Verify scripts/extract_fields.py as the single extraction CLI.
2. Verify scripts/normalize_fields.py applies final field rules.
3. Keep existing db.py and avoid schema rewrites unless absolutely necessary.
4. Ensure confirmed records export through scripts/export_excel.py.
5. Run py_compile, normalize/export tests, TSV export, Excel export, and DB export smoke.

Acceptance:
- No import/syntax errors.
- normalize_fields.py passes tests.
- export_tsv.py produces fixed-column TSV.
- export_excel.py produces 3-sheet formatted Excel.
- --from-db export works or fails gracefully with a clear message.
- No API/frontend migration unless explicitly needed.
- No temporary output files committed.
```

## 3. Frontend Optimization Prompt

```text
You are working on Japan_University_admissions_v2 frontend.

The UI already exists.
Do NOT redesign the entire UI.
Do NOT build a C-end app.
Do NOT add competitor features.
Do NOT add AI chat, professor database, timeline, or new product modules.
Do NOT change backend schema.
Do NOT change extraction logic.

Frontend goal:
Keep the existing UI flow, but align it with the final MVP workflow:

Upload PDF
→ start extraction
→ show staging/review state
→ export full Excel master table

Current desired pages:
- 导入
- 复核
- 记录

Tasks:
1. 导入 page keeps upload/extract and shows document status, extracted count, review count, and review entry.
2. 复核 page keeps staging/review list and editable record detail where existing API supports it.
3. 记录 page keeps confirmed records browsing and exposes real Excel export through the backend route.
4. UI copy stays concise and internal-workflow oriented.
5. Keep existing visual direction; do not do large redesign.

Build:
cd frontend
npm run build

Acceptance:
- Build passes.
- Upload/extract flow is accessible.
- Review flow is accessible.
- Records/export entry is visible.
- No API contract broken.
- No backend logic modified in frontend-only tasks.
```

## 4. Master Rule

The final product standard is:

```text
After a PDF is uploaded or specified, the system extracts fields, enters a human-reviewable data flow, and exports a complete Excel master table where one department/specialization is one row and EJU columns use 〇 / △ / - / score conditions.
```
