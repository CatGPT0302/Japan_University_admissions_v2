# admissions_v2

项目代码根目录为本文件所在的 `admissions_v2/`；下文命令均从这里开始。
仓库级构建入口见[根目录说明](../README.md)。

## Project Overview

admissions_v2 is a personal, AI-assisted Japanese university admissions information project.

当前目标是一个大一学生能展示、能解释的 Vibe Coding 原型：把官方募集要項 PDF 整理成可人工复核、可查询和复用的数据。项目不代表任何大学的官方服务，也不承诺自动判断申请资格。

产品主线：官方 PDF → Codex／多模态 AI 抽取 → 自动入草稿库 → 人工复核发布 → 学生查询与比较。当前完成自动导入基础能力；独立发布版本、简化维护端和新的学生端仍在建设。现有合作方等旧页面暂时保留，不再扩展。

- 总项目方向：[项目路线图](docs/PROJECT_ROADMAP.md)
- AI 自动入库：[提交接口与使用方法](docs/AI_INGESTION.md)
- 七校验收来源：[2027 年度来源清单](data/acceptance_sources_2027.json)
- Mac 演示启动与数据隔离：[本地演示说明](docs/LOCAL_DEMO.md)
- 学生注册与管理员创建：[账号说明](docs/ACCOUNTS.md)
- 本轮验收清单：[展示版计划](docs/DEMO_PLAN.md)
- 直接给别人使用：[Skill 分享与安装](docs/SKILL_SHARING.md)
- 文件夹整理入口：[批量数据包说明](docs/BATCH_DEMO.md)
- 阅读案例：[福井大学](docs/DEMO_CASE.md)、[京都工艺纤维大学](docs/DEMO_CASE_KIT.md)
- 展示与试用：[三分钟演示稿](docs/PROJECT_DEMO.md)、[用户试用任务](docs/USER_TRIAL.md)

当前可复现：两份真实 PDF、12 条带来源依据的待复核草稿、JSONL/Markdown/CSV 阅读数据包、本机可发现的 skill。技术测试不等于事实准确率或真实用户认可。合成数据的 UI 确认流程已验证；七校完整抽取、人工复审和真实用户试用尚未完成。

The sections below describe existing capabilities, not a claim of production readiness.

It has three product surfaces:

- Owner/admin workspace: upload admissions PDFs or source URLs, run extraction, review uncertain content, confirm records, and export the master Excel workbook.
- Partner service center: issue limited access, receive submitted PDFs or links, track processing progress, and keep final data confirmation under the owner.
- Student/parent frontend: collect a student's profile, show schools worth checking, and explain requirements in plain language. It does not collect consultation bookings.

These are retained application capabilities, not the current demo scope. The current project is a local MVP focused on source-backed drafts and human review; it is not presented as a production SaaS.

## Current Workflow

```text
Partner user or owner submits source material
-> system stores the submission
-> owner starts the existing extraction workflow
-> extracted content enters review
-> owner confirms it into the main database
-> student frontend and licensed API read confirmed data only
```

## Product Websites

Use separate deployments/sites for the three systems. They can share this repository and backend, but they should not be exposed as different hash routes on one public URL.

- Owner data workspace site: `VITE_APP_SURFACE=owner`
- Owner partner-management site: `VITE_APP_SURFACE=owner-service`
- Partner service center site: `VITE_APP_SURFACE=partner`
- Student/parent frontend site: `VITE_APP_SURFACE=student`

`VITE_APP_SURFACE=combined` is only for local debugging. It is disabled unless `VITE_ENABLE_COMBINED_SURFACE=true` is set, and should not be used as the public product entry.

## Backend Interfaces

- Admin workflow: `/upload`, `/agent/run`, `/staging/*`, `/confirm/*`, `/records`, `/export/excel`
- Public student API: `/public/programs`, `/public/recommendations`
- Licensed API: `/v1/programs`, `/v1/recommendations`, `/v1/documents/submissions`
- Owner queue: `/admin/submissions`

Booking endpoints may still exist for legacy compatibility, but they are not part of the active student or partner product flow.

Licensed API keys are stored as hashes. The full secret is only shown once when created.

## Tech Stack

- Backend: Python, FastAPI
- Frontend: React, TypeScript, Vite
- Database: SQLite for local use, PostgreSQL-compatible deployment option
- Export: openpyxl
- Demo reading: Codex directly reads PDFs; no additional model API calls
- Existing optional extraction backend: OpenAI-compatible chat completion API

## Local Setup

### Backend

```powershell
cd <project-root>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn scripts.api:app --reload --host 127.0.0.1 --port 8000
```

For local development and the full test suite, install the development
dependencies instead:

```powershell
pip install -r requirements-dev.txt
```

### Frontend

```powershell
cd <project-root>\frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

The frontend should point to the local backend:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

For local split-site testing, run separate Vite servers with different surfaces:

```powershell
.\start_all_surfaces.bat
```

Or open only one surface:

- `start_owner.bat`: owner data workspace, `http://127.0.0.1:5173`
- `start_owner_service.bat`: owner partner-management site, `http://127.0.0.1:5174`
- `start_partner.bat`: partner service center, `http://127.0.0.1:5175`
- `start_student.bat`: student/parent frontend, `http://127.0.0.1:5176`

Do not use hash routes such as `#/student` on the owner site as the product model. The surfaces are separate local websites that happen to share code and backend APIs.

For the owner partner-management site, set `VITE_OWNER_WORKSPACE_URL` to the separate owner data workspace URL. This lets the partner-management site send the owner back to the review workspace after a submitted source has been processed.

## Environment Variables

Use `.env.example` in the project root and `frontend/.env.example` for local configuration templates.

Required for extraction:

- `OPENAI_API_KEY` or `LLM_API_KEY`

Optional:

- `OPENAI_TEXT_MODEL`
- `OPENAI_VISION_MODEL`
- `OPENAI_BASE_URL` or `LLM_BASE_URL`
- `OPENAI_COMPAT_URL` or `LLM_COMPAT_URL`

Resolution order:

- API key: `LLM_API_KEY` -> `OPENAI_API_KEY`
- Endpoint: `OPENAI_COMPAT_URL` -> `LLM_COMPAT_URL` -> `OPENAI_URL` -> `OPENAI_BASE_URL` -> `LLM_BASE_URL` -> official OpenAI default

## Data Boundary

This repository is designed for public admissions information, official university publications, publicly available admissions documents, and manually prepared sample data.

Do not commit private datasets, real student information, private operational data, secrets, or customer-specific files.

Owner data assets remain in the owner-hosted database. Partner users receive limited use rights through issued access, not ownership of the master database or extraction logic.

## Seed Data Package

Human-checked seed extractors are quality assets, not automatically confirmed production data. To inspect them as a portable starter dataset without mutating the database:

```powershell
python scripts/seed_data_package.py --output-dir data/exports/seed_data_package
```

This writes `package_summary.json`, `documents.json`, `records.jsonl`, `records_table.csv`, and `review_queue.json`. Every row is marked `database_status: not_imported` so it can be reviewed before any future import into the owner database.

To preview a staging import without writing to the database:

```powershell
python scripts/import_seed_package_to_staging.py --package-dir data/exports/seed_data_package
```

Add `--apply` only when you intentionally want to create owner-review staging rows. The importer never writes directly to confirmed records.

## Verification

```powershell
python -m pytest -q
cd frontend
npm run build
npm run build:owner
npm run build:owner-service
npm run build:partner
npm run build:student
npm run smoke:surfaces
npm run smoke:browser
```

The four `build:*` commands create separate frontend bundles (`dist-owner`, `dist-owner-service`, `dist-partner`, `dist-student`) so the owner workspace, partner service center, and student-facing site can be deployed as separate sites instead of relying on guessed hash routes.

`smoke:browser` uses the local Chrome or Edge installation, starts a temporary SQLite-backed API, signs into the owner and partner surfaces with throwaway accounts, checks export presets, submits one partner source, verifies the owner-side submission detail panel, runs the owner processing/review/confirmation path, checks the review page's unsaved-change summary, verifies the confirmed record detail can expose quick school/faculty export actions, verifies export preview/CSV output without internal quality-screening details, and checks that the student surface can search and open confirmed school details without exposing booking or internal review UI.
Run the two frontend smoke commands one after another because both rebuild `frontend/dist`.

## Ownership

See [OWNERSHIP.md](../OWNERSHIP.md).
