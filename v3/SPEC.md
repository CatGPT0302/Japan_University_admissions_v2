# admissions v3 需求文档

> 状态：草案（2026-11-26）　负责人：ZHANG FENG　实现：Claude Code
> v2（`admissions_v2/`）冻结，只作参考，不再修改。

## 0. 一句话

把大学募集要项 PDF 整理成**带原文页码、经人工确认**的数据，让留学生填一次成绩，就能看到「我能报哪些、什么时候截止、先做什么」。

## 1. 不可违反的原则（从 v2 继承）

1. **AI 结果只是草稿。** 任何字段未经人工确认，学生端都看不到。
2. **每个字段都有出处。** 记录来源 PDF、物理页码和原文片段。没有出处的值不能确认。
3. **原文矛盾不猜。** 原文前后不一致时，状态设为「需向大学确认」，在学生端明确显示，不替用户选一个。
4. **不静默丢字段。** 抽取不到就存空值并标记待复核，不能直接省略。
5. **必着和消印有效必须分开存、分开显示。** 例外规则（比如简易挂号速递）单独记录。
6. **不做资格判断的担保。** 学生端的「条件符合」只表示「按已确认的数据，你的成绩满足要求」，页面底部始终提示以原文为准。

## 2. 范围

### MVP 做

- **数据**：明治大学，私费外国人留学生入试，全部学部和学科。
- **管理端**：一个审核页面（第 6 节）。
- **学生端**：首页加详情页（第 7 节）。
- **评测**：用人工核对过的标准答案自动算准确率（第 8 节）。
- **部署**：公网能访问的一个网址。

### MVP 不做（全部推迟，不要提前设计扩展点）

账号和登录、合作方中心、授权 API、预约、收费、多所大学、通知推送、质量仪表盘、Streamlit、Excel 导出。

### 年度说明

明治 2027 年度入试的出愿已在 2026 年 8–9 月结束。MVP 先用 2027 年度的 PDF 开发和验证；2028 年度的 PDF 一公布就换数据上线。所以从第一天起，**年度就是一个普通字段**，代码里不能写死年份。

## 3. 验收标准（全部满足才算 MVP 完成）

1. 明治 2027 年度所有学部、学科的数据已经抽取，**每一条都经过人工确认**，或者标为「需向大学确认」。
2. 学生输入成绩后，能看到可报的学部列表、按时间排好的日程，以及每个学部要交的材料。
3. 评测脚本能输出字段级准确率，结果写进 README。
4. 部署在公网上，用一个链接就能打开。
5. 至少 3 个真实用户（正在准备报考的人）用过一遍，反馈记录在 `v3/USER_TRIAL.md`。

**时间盒：2027-03-31。** 到期没有完成，就停下来复盘，不继续加功能。

## 4. 架构

```
PDF（本地）
  → 抽取：由 coding agent 读页面，按 JSON Schema 写出结果
  → 校验：Pydantic 模型 + 规则检查
  → 草稿库（SQLite）
  → 管理端审核页：确认 / 修改 / 标记需确认
  → 已发布数据（只读视图）
  → 学生端：静态前端读取 API
```

- **后端**：Python 3.12、FastAPI、SQLModel、SQLite。所有代码合计不超过 2,000 行。
- **前端**：React、TypeScript、Vite，学生端和管理端放在同一个项目里，用路由区分。管理端只在本地运行，不部署到公网。
- **抽取**：不调用付费的模型 API。由 Claude Code 读取 PDF 页面图像或文本，按 `schema/program.schema.json` 输出 JSON，再交给 `python -m v3.ingest` 校验入库。以后需要接 API 时，只换掉这一层。
- **禁止**：为某一所学校单独写解析代码，或者写死某一所学校的页码。v2 的每校一个 extractor 不能再出现。

## 5. 数据模型（5 张表）

| 表 | 主要字段 | 说明 |
|---|---|---|
| `source_document` | id, university, year, url, sha256, page_count, fetched_at | 一份 PDF 一行 |
| `program` | id, university, year, faculty, department, route, campus, prefecture, published_at | 一个可报考单位（学部 × 学科 × 入试方式）一行 |
| `fact` | id, program_id, field, value_json, display_text, source_document_id, page, quote, status, note, updated_at | 一个字段一行。status ∈ `draft` / `confirmed` / `edited` / `needs_inquiry` / `missing` |
| `event` | id, program_id, kind, starts_at, ends_at, deadline_rule, exception_note, source_document_id, page, status | 日程。kind ∈ `overseas_contact` / `application` / `exam` / `result` / `enrollment`；deadline_rule ∈ `hikkyaku` / `keshiin` / `online` / `unknown` |
| `review_log` | id, target_table, target_id, action, before_json, after_json, at | 每一次确认或修改都留记录 |

### 必须的字段（来自 v2 的 `FIELD_HIGHEST_PRINCIPLE.md`）

university, faculty, department, application_period, deadline_rule, english_requirement, screening_method, screening_schedule, result_date, enrollment_period, prefecture, campus, eju_session, eju_japanese, eju_general, eju_math, eju_physics, eju_chemistry, eju_biology, required_documents, eligibility_notes。

### 结构化要求（供学生端匹配）

`value_json` 中的 EJU 和英语要求采用固定结构，不能只存一段文字（下例数值仅用来说明结构，不对应任何一所学校）：

```json
{
  "eju": {
    "sessions": ["2025-1", "2025-2", "2026-1"],
    "language": "ja",
    "japanese": {"required": true, "min": 280, "max": 400, "excludes_writing": true},
    "general": {"required": false},
    "math": {"required": true, "course": 2, "min": 120},
    "science": {"must": ["physics"], "choose": 1, "from": ["chemistry", "biology"]}
  },
  "english": {
    "tests": [{"name": "TOEFL iBT", "min": 45, "home_edition": true, "my_best": false}],
    "valid_from": "2024-08", "valid_to": "2026-06",
    "conflict": null
  }
}
```

原文有矛盾时，在 `conflict` 中写明两处页码和各自的写法，并把对应 fact 的 status 设为 `needs_inquiry`。

## 6. 管理端：审核页（只做一个页面）

- **左侧**：PDF 原页图像，点击某个字段时跳到它的出处页，并高亮原文片段。
- **右侧**：按学部分组的字段列表，每个字段显示值、状态和原文片段。
- **每个字段的操作**：`确认`、`修改并确认`、`标记需向大学确认`（必须填写原因）。
- **快捷键**：`J`/`K` 上下切换字段，`Enter` 确认，`E` 修改。
- **顶部进度**：明治共 N 个字段，已确认 X 个，需确认 Y 个，草稿 Z 个。
- 一个 program 的所有 fact 都确认后，才能点「发布」。

## 7. 学生端

设计稿：<https://claude.ai/artifact/5hefdWb7HPCifA3wCzxGUF>（首页加详情页，手机优先，宽 390 px）

- **我的条件**：EJU 各科分数、数学课程、理科选择、英语考试和分数。只存在浏览器本地（localStorage），不建账号。
- **能报的学校**：每个 program 显示三种状态之一：`条件符合` / `有 N 项需确认` / `不符合（原因）`。不符合的默认收起，可以展开查看。
- **接下来的日程**：已选学部的所有 event 按日期排序，必着用橙色、消印有效用灰色，例外规则写在下一行。
- **详情页**：需确认的项目放在最上方；日程、科目和选拔方式依次排列；每一项都附原文页码链接。
- **比较**：最多选 4 个学部并排比较（MVP 最后再做，时间不够就砍）。
- 界面语言为中文，日语术语保留原文（出愿、必着、消印有效、募集要项）。

### 匹配逻辑（纯函数，必须有单元测试）

`match(profile, program) -> {status, reasons[]}`：

- 只用 status 为 `confirmed` 或 `edited` 的 fact。
- 任何参与判断的 fact 为 `needs_inquiry` 或 `missing` → 结果至少是「需确认」。
- 有任何一项明确不满足 → 「不符合」，并在 reasons 中写明是哪一项。

## 8. 评测

- 标准答案：v2 的 `admissions_v2/quality_baselines/meiji_2027_schedule.expected.json`（`review_status: human_checked_seed`）复制到 `v3/eval/`。福井、京都工艺纤维的标准答案作为通用性检查。
- `python -m v3.eval` 输出：按字段的准确率、总准确率、漏抽字段数。
- 每次修改抽取提示词或 schema 后都要跑一次，结果追加到 `v3/eval/HISTORY.md`。
- 「准确」的定义：所有 `contains` 片段都出现在 display_text 中，并且页码一致。

## 9. 部署

- 学生端：构建为静态文件，部署到 Vercel 或 Cloudflare Pages。已发布的数据导出为 `published.json` 一起部署，**MVP 不需要线上后端**。
- 管理端和数据库：只在本地运行。
- 每次「发布」时重新生成 `published.json`，提交后自动部署。

## 10. 里程碑

| 截止 | 内容 |
|---|---|
| 12 月中 | v3 骨架：schema、5 张表、ingest、eval 能跑 |
| 12 月底 | 明治全部学部抽成草稿，eval 出第一个准确率 |
| 1 月 | 管理端审核页；人工复审明治全部字段 |
| 2–3 月 | 学生端按设计稿实现，导出 published.json，部署上线 |
| 3 月 | 3 人以上用户试用，写 USER_TRIAL.md，更新 README |

（2–3 月有回国安排，这期间的进度按实际情况调整，但 3/31 的截止日不变。）

## 11. 从 v2 拿什么

| 拿 | 不拿 |
|---|---|
| 字段清单和原则文档 | 所有 `*_extractor.py` |
| `quality_baselines/` 标准答案 | `db.py`、`api.py`、28 张表 |
| `data/acceptance_sources_2027.json` 的来源 URL 和 sha256 | 合作方、授权 API、预约、账号 |
| `docs/DEMO_CASE*.md` 里的案例（用作测试） | 5,530 行的 `index.css` |
