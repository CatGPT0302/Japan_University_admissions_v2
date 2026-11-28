# admissions v3 需求文档

> 状态：草案 r3（2026-11-29）　负责人：ZHANG FENG　实现：Claude Code
> v2（`admissions_v2/`）冻结，只作参考，不再修改。

## 0. 一句话

把大学募集要项 PDF 整理成**带原文页码、经人工确认**的数据，让留学生填一次条件，就能看到「我能报哪些、什么时候截止、先做什么」。

## 1. 不可违反的原则（从 v2 继承）

1. **AI 结果只是草稿。** 任何字段未经人工确认，学生端都看不到。
2. **每个字段都有出处。** 记录来源 PDF、物理页码和原文片段。没有出处的值不能确认。
3. **原文矛盾不猜。** 原文前后不一致，或两次读取结果不一致时，状态设为「需向大学确认」，在学生端明确显示，不替用户选一个。
4. **不静默丢字段。** 抽取不到就存空值并标记 `missing`，不能直接省略。
5. **必着和消印有效必须分开存、分开显示**，并且按寄出地（日本国内 / 海外）分别记录。例外规则（比如简易挂号速递）单独记录。
6. **不做资格判断的担保。** 学生端的「条件符合」只表示「按已确认的数据，你的条件满足要求」，页面底部始终提示以原文为准。

## 2. 范围

### MVP 做

- **数据**：明治大学，私费外国人留学生入试，全部学部和入试类型（Ⅰ型 / Ⅱ型）。
- **复审工具**：命令行复审（第 6 节）。不做网页后台。
- **学生端**：首页加详情页（第 7 节）。
- **评测**：用人工核对过的标准答案自动算准确率（第 8 节）。
- **部署**：公网能访问的一个网址。

### MVP 不做（全部推迟，不要提前设计扩展点）

网页管理后台、账号和登录、多用户协作、合作方中心、授权 API、预约、收费、通知推送、质量仪表盘、Streamlit、Excel 导出。

背景：v2 的后台按「多人协作」设计。v3 只有一个开发者兼复审者，所以后台全部砍掉，只保留数据库和命令行。

### 年度说明

明治 2027 年度入试的出愿已在 2026 年 8–9 月结束。MVP 先用 2027 年度的 PDF 开发和验证；2028 年度的 PDF 一公布就换数据上线。所以从第一天起，**年度就是一个普通字段**，代码里不能写死年份。

## 3. 验收标准

### 必须（全部满足才算 MVP 完成）

1. 明治 2027 年度所有报考单位的数据已经抽取，**每一条都经过人工确认**，或者标为「需向大学确认」。
2. 学生输入条件后，能看到可报的单位列表、按时间排好的日程，以及每个单位要交的材料。
3. 评测脚本能输出字段级准确率，结果写进 README。
4. 部署在公网上，用一个链接就能打开。
5. 至少 3 个真实用户（正在准备报考的人）用过一遍，反馈记录在 `v3/USER_TRIAL.md`。**注意**：3 月试用时，2027 年度的日程已经过期，这次试用只能检验「界面能不能看懂、能不能找到下一步」，不能检验「是否真的需要」。这一点要在 USER_TRIAL.md 开头写明。

### 加分（时间够再做）

6. 再加入一所学校（福井大学，已有标准答案），**不改任何代码**，只加数据就能在学生端正常显示。用来验证「新增学校只靠数据」这一原则。

**时间盒：2027-03-31。** 到期没有完成，就停下来复盘，不继续加功能。

## 4. 架构

```
PDF（本地）
  → 页面转图像（每页一张 PNG）
  → 抽取：Claude Code 按 prompts/extract.md 读页面图像，按 JSON Schema 输出
  → 校验并入库：python -m v3.ingest（Pydantic + 规则检查），一律写成 draft
  → 复审：python -m v3.review（命令行）
  → 导出：python -m v3.publish → published.json
  → 学生端：静态前端读取 published.json
```

- **语言和库**：Python 3.12、SQLModel、SQLite。**没有 Web 后端**（不需要 FastAPI）。Python 代码合计不超过 1,500 行。
- **前端**：React、TypeScript、Vite，只有学生端。
- **抽取读图像，不读文字。** v2 和 r1 试抽取都证明：从 PDF 提取文字时，日程表的列会错位，日期和学部的对应关系会出错。所以日程表、科目表这类表格，必须读页面图像。
- **抽取可复现。** 抽取提示词固定在 `v3/prompts/extract.md`，每次修改都提交到 git。每条 draft 记录用的是哪个提示词版本（git commit 的短哈希）。
- **不调用付费模型 API。** 抽取由 Claude Code 在本地完成。以后需要接 API 时，只换掉「抽取」这一步。
- **禁止**：为某一所学校单独写解析代码，或者写死某一所学校的页码。

## 5. 数据模型（SQLite，5 张表）

| 表 | 主要字段 | 说明 |
|---|---|---|
| `source_document` | id, university, year, url, sha256, page_count, fetched_at | 一份 PDF 一行 |
| `program` | id, university, year, faculty, department, route, published_at | 一个报考单位一行。**默认粒度是「学部 × 入试类型」**（如「国際日本学部 Ⅰ型」），只有原文按学科区分要求时才拆到学科。这几列是报考单位的标识，不进 `fact`，也不逐条复审 |
| `fact` | id, program_id, field, value_json, display_text, source_document_id, page, quote, status, prompt_version, note, updated_at | 一个字段一行。status ∈ `draft` / `confirmed` / `edited` / `needs_inquiry` / `missing` |
| `event` | id, program_id, kind, starts_at, ends_at, submission_rules_json, exception_note, source_document_id, page, quote, status | 日程。**所有日期只存在这里**，`fact` 里不存日期 |
| `review_log` | id, target_table, target_id, action, before_json, after_json, at | 每一次确认或修改都留记录 |

### event

- 所有时间一律带时区存储（`2026-09-01T23:30+09:00`）。学生端统一按日本时间显示，并明确标注「日本时间」，不按浏览器所在时区换算。
- `kind` ∈ `mypage_open` / `overseas_contact` / `application` / `fee_payment` / `stage1_result` / `exam` / `result` / `enrollment`
- `submission_rules_json`：按提交方式和寄出地分别记录，例如：

```json
{"online_form": "deadline_2330", "mail_from_japan": "keshiin", "mail_from_abroad": "hikkyaku"}
```

取值：`hikkyaku`（必着）/ `keshiin`（消印有效）/ `online` / `not_allowed` / `unknown`。

### fact 的字段清单

来自 v2 的 `FIELD_HIGHEST_PRINCIPLE.md`，去掉日期类字段（已移到 event），再加上费用和资格条件：

campus, prefecture, eju, english, screening_method, required_documents, eligibility, fee, refund_policy。

university、faculty、department、route 只存在 `program` 表；campus、prefecture 需要溯源，只存在 `fact`。同一个信息只有一个存放位置。

### 结构化要求（供学生端匹配）

下例数值仅用来说明结构，不对应任何一所学校。

```json
{
  "eju": {
    "sessions": ["2025-2", "2026-1"],
    "language": "ja",
    "required": [
      {"subject": "japanese", "min": 280, "excludes_writing": true}
    ],
    "choose": [
      {"n": 1, "from": [{"subject": "general"}, {"subject": "math", "course": [1, 2]}]},
      {"n": 1, "from": [{"subject": "chemistry"}, {"subject": "biology"}]}
    ]
  },
  "english": {
    "not_required": false,
    "any_of": [
      {"test": "TOEFL iBT", "taken_on_or_before": "2026-01-20", "min": 45},
      {"test": "TOEFL iBT", "taken_on_or_after": "2026-01-21", "min": 3},
      {"test": "TOEIC L&R", "min": 565},
      {"test": "IELTS", "min": 4.0}
    ],
    "valid_from": null,
    "conflict": null
  },
  "eligibility": {
    "japan_residence_registration": "must_not_have",
    "period": null
  },
  "fee": {"amount_jpy": 35000, "handling_fee_jpy": 1045}
}
```

要点：

- **EJU**：只用 `required`（必考）和 `choose`（N 选 1）两种结构，「N 选 1」可以跨科目（例如「综合科目或数学」）。「物理必考、化学生物选一」就是物理放进 `required`、化学生物放进 `choose`。如果遇到「方案 A 或方案 B」这种多套并列的组合，先标 `needs_inquiry` 并在 note 里写明，出现两次以上再扩展 schema。
- **英语**：多种考试是「任选其一」（`any_of`）。同一考试的门槛可能随**受验日期**变化（TOEFL 在 2026 年改为新分数制，新旧分数并存）。不要求英语时写 `not_required: true`。
- **资格条件**：Ⅱ型等路线有「在规定期间内不能在日本登记住民票」这类条件，必须结构化，学生端匹配要用到。
- 原文有矛盾时，在 `conflict` 中写明两处页码和各自的写法，并把对应 fact 的 status 设为 `needs_inquiry`。

## 6. 复审：命令行工具

`python -m v3.review [--university meiji --year 2027]`

- **按页分组复审**：按 (program_id, source_document_id, page) 排序。进入新的一页时先显示这一页的图像路径，按 `o` 打开一次，然后把这一页上的所有 fact 和 event 连续审完，再进入下一页。
- 每条显示：字段、值、原文片段。
- 操作：`Enter` 确认，`e` 修改后确认，`i` 标记需向大学确认（必须填写原因），`s` 跳过。
- 每次操作都写入 `review_log`。
- 开头显示进度：共 N 条，已确认 X，需确认 Y，草稿 Z。
- 一个 program 的所有 fact 和 event 都不是 `draft` 后，才能被 `v3.publish` 导出。

**升级条件**：复审时如果对照原文很费力、频繁看漏，再做一个只在本地运行的单页查看器（左边 PDF 页面，右边字段）。在那之前不做。

## 7. 学生端

设计稿：<https://claude.ai/artifact/5hefdWb7HPCifA3wCzxGUF>（首页加详情页，手机优先，宽 390 px）

- **我的条件**：EJU 各科分数、数学课程、理科选择、英语考试种类、分数和**受验日期**、**目前是否住在日本（有无住民票）**。只存在浏览器本地（localStorage），不建账号。
- **能报的单位**：每个 program 显示三种状态之一：`条件符合` / `有 N 项需确认` / `不符合（原因）`。不符合的默认收起，可以展开查看。
- **接下来的日程**：已选单位的所有 event 按日期排序。截止规则按用户所在地显示：住在日本就显示国内的规则，住在海外就显示海外的规则。必着用橙色，消印有效用灰色，例外规则写在下一行。
- **详情页**：需确认的项目放在最上方；日程、科目、选拔方式和费用依次排列；每一项都附原文页码链接。
- **原文链接**：直接链接到大学官网 PDF 的对应页（URL 加 `#page=N`）。手机浏览器可能忽略这个页码参数，所以链接旁边必须用文字写出物理页码（如「原文第 12 页」），方便用户手动翻到。**不在公网上放 PDF 页面截图或全文**，只引用短片段。
- **比较**：最多选 4 个单位并排比较（MVP 最后再做，时间不够就砍）。
- 界面语言为中文，日语术语保留原文（出愿、必着、消印有效、募集要项）。

### 匹配逻辑（纯函数，必须有单元测试）

`match(profile, program) -> {status, reasons[]}`：

- 只用 status 为 `confirmed` 或 `edited` 的 fact 做「明确判断」。
- **优先级：不符合 > 需确认 > 条件符合。**
  1. 任何一项已确认的要求明确不满足 → 「不符合」，即使其他项目需确认。例：EJU 日语 200 分，门槛 280 分，就算英语要求是 `needs_inquiry`，也判「不符合（EJU 日语未达标）」。
  2. 没有不满足项，但有参与判断的 fact 为 `needs_inquiry` 或 `missing` → 「需确认」。
  3. 以上都不是 → 「条件符合」。
- reasons 列出所有不满足项和所有需确认项。
- 英语按受验日期选用对应的门槛；`any_of` 中满足任意一项即可。
- 资格条件（如住民票）也参与判断。

## 8. 评测

- 标准答案：v2 的 `admissions_v2/quality_baselines/meiji_2027_schedule.expected.json`（`review_status: human_checked_seed`，12 条，按学部）复制到 `v3/eval/`。福井、京都工艺纤维的标准答案作为通用性检查。
- **覆盖范围的缺口**：现有的明治标准答案只来自 `2027intexam.pdf`（科目和日程表），没有覆盖募集要项正文（资格、材料、费用）。人工复审完成后，把确认过的正文字段补进标准答案。
- **比对方式**：先把全角数字和半角数字统一、去掉空白，再比较。结构化字段按值比较；只有文字字段才用「包含」比较。
- `python -m v3.eval` 输出：按字段的准确率、总准确率、漏抽字段数，以及使用的提示词版本。
- 每次修改抽取提示词或 schema 后都要跑一次，结果追加到 `v3/eval/HISTORY.md`。

## 9. 部署

- 学生端：构建为静态文件，部署到 Vercel 或 Cloudflare Pages。`published.json` 和前端一起部署，**不需要线上后端**。
- 数据库、PDF、页面图像：只在本地保存，不提交到公开仓库。
- 每次运行 `v3.publish` 都会重新生成 `published.json`，提交后自动部署。

## 10. 里程碑

| 截止 | 内容 |
|---|---|
| 12 月中 | v3 骨架：schema、5 张表、页面转图像、ingest、eval 能跑 |
| 12 月底 | 明治全部报考单位抽成草稿，eval 出第一个准确率 |
| 1 月 | 命令行复审工具；人工复审明治全部条目（约 300 条，预计约 5 小时） |
| 2–3 月 | 学生端按设计稿实现，导出 published.json，部署上线 |
| 3 月 | 3 人以上用户试用，写 USER_TRIAL.md，更新 README |

（1 月搬家，2–3 月回国，这期间的进度按实际情况调整，但 3/31 的截止日不变。）

## 11. 从 v2 拿什么

| 拿 | 不拿 |
|---|---|
| 字段清单和原则文档 | 所有 `*_extractor.py` |
| `quality_baselines/` 标准答案 | `db.py`、`api.py`、28 张表、65 个接口 |
| `data/acceptance_sources_2027.json` 的来源 URL 和 sha256 | 合作方、授权 API、预约、账号、管理后台 |
| `docs/DEMO_CASE*.md` 里的案例（用作测试） | 5,530 行的 `index.css` |

## 附：r1 → r2 的修改依据

2026-11-26 对明治 2027 年度募集要项做了一次试抽取（法学部Ⅰ型、国際日本学部Ⅰ型 / Ⅱ型），发现 r1 的 schema 有以下问题，已在 r2 修正：

1. 截止规则因寄出地而不同（国内消印有效、海外必着），入学手续也一样 → `submission_rules_json`。
2. TOEFL 门槛按受验日期分新旧两种分数制；多种英语考试任选其一 → `english.any_of`。
3. EJU 有跨科目的「N 选 1」（综合科目或数学）→ `eju.choose`。
4. Ⅱ型有「不能在日本登记住民票」的资格条件；报考单位应为「学部 × 入试类型」→ `eligibility`、program 粒度、学生端增加「是否住在日本」。
5. 文字提取时日程表的列会错位，两次读取对同一考试日期的结果不一致 → 抽取改为读页面图像，并保留人工复审。
6. 日期在 fact 和 event 中重复 → 只存在 event 中。
7. 一个人开发，不需要多人后台 → 去掉 Web 后端和管理页面，改为命令行复审，保留数据库。

## 附：r2 → r3 的修改依据（外部评审）

1. program 和 fact 字段重复 → 标识字段只放 program，campus、prefecture 只放 fact。
2. 逐条复审需要频繁切换图片 → 按页分组复审。
3. match 的优先级未写明 → 不符合 > 需确认 > 条件符合。
4. `with_required` 让结构变复杂 → 删除，只用 required + choose。
5. 手机端可能忽略 `#page=N`；海外用户可能按本地时区看错截止时间 → 页码明文显示；时间带 +09:00 存储，按日本时间显示。
