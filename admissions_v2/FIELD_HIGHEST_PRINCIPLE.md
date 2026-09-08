# 字段最高原则（强制执行）

本项目后续所有抽取与展示，必须遵守以下最高原则：

1. 字段展示不允许随意删改。
2. 字段内容必须尽力抽取，不允许用“看不到字段”替代抽取。
3. 抽取失败时必须保留空值并标记复核，不允许静默丢字段。
4. 本规则优先级高于临时 UI 调整。

## 必须包含字段（当前标准）

- 大学名（`university`）
- 出愿时期（`admission_period`）
- 学部（`faculty`）
- 学科・専修等（`department`）
- 出願期間（`application_period`）
- 必着/消印（`deadline_rule`）
- 出願要件・基準点など（`warnings_json` + `field_evidence`）
- 英語外部資格試験（`english_requirement`）
- 選考方法（`screening_method`）
- 選考日程（`screening_schedule`）
- 合格発表日（`result_date`）
- 入学手続期間（`enrollment_period`）
- 都道府県（`prefecture`）
- キャンパス（`campus`）
- 更新日期（`updated_at`）
- EJUの実施回（`eju_session`）
- 日本語（`eju_japanese`）
- 综合科目（`eju_general`）
- 数学（`eju_math`）
- 物理（`eju_physics`）
- 化学（`eju_chemistry`）
- 生物（`eju_biology`）

## 术语固定

- 必须使用“综合科目”，不使用“总合科目”。
- “入试难度”不作为必填展示字段。

## 执行要求

- 每次改动后都要检查上述字段是否仍可见、可编辑（适用于复核页）并可抽取。
- 如字段值缺失，必须进入风险复核流程，不得直接忽略。
