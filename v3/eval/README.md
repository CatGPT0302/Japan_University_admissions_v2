# 评测用标准答案

## meiji_2027.expected.json

- 来源：v2 的 `admissions_v2/quality_baselines/meiji_2027_schedule.expected.json`，复制后修正。
- 依据：明治大学 2027 年度外国人留学生入学试验要项 `yoko.pdf`（sha256 `189cd4adf14055bf297312259457d10a10914ef32da5eb6a83c22bd788608abe`），物理第 5 页的科目・日程一览表。
- 比对方式：`contains`，比对前先做 NFKC 统一全角半角。

### 2026-11-29 的修正

| 条目 | 字段 | v2 原值 | 修正后 |
|---|---|---|---|
| 商学部Ⅰ型 | screening_schedule | 12月5日 | 2026年11月28日（オンライン） |
| 商学部Ⅰ型 | result_date | 12月11日 | 2026年12月3日 |
| 情報コミュニケーション学部 | screening_schedule | 12月15日 | 2026年12月5日 |
| 経営学部 | english_requirement | TOEFL / TOEIC / IELTS、出願基準点なし | TOEFL iBT のみ、41以上 / 3以上 |
| 国際日本学部Ⅱ型 | screening_schedule | 12月24日 | 删除（Ⅱ型没有考试，12/24 是合格发表） |

v2 原值看起来是从相邻行抄串的。修正由 Claude 对照第 5 页页面图像做出，负责人看过截图后再合并本 PR。

### 覆盖范围

只覆盖日程、EJU 科目、英语、选拔方式。费用、提交材料、出愿资格还没有标准答案，人工复审确认后再补进来。**AI 抽取的草稿不能直接当标准答案**，否则评测等于拿抽取结果检查它自己。
