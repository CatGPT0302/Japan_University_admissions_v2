# admissions_v2 — 接手说明

## 项目结构

```
admissions_v2/
├── database/
│   └── admissions_v2.db        ← 新数据库（旧库保持不动）
├── input_pdfs/                 ← 放入要处理的PDF
├── output_pages/               ← PDF转图片后存放的PNG
├── prompts/
│   └── vision_prompt.md        ← LLM视觉抽取的Prompt
└── scripts/
    ├── db.py                   ← 数据库初始化和CRUD
    ├── pdf_render.py           ← PDF → PNG
    ├── validator.py            ← 字段校验器
    ├── vision_extractor.py     ← Anthropic Vision API调用（纯urllib，无pydantic依赖）
    ├── pipeline.py             ← 主流程（含水平分割支持）
    └── regression_waseda_2027.py ← 回归测试
```

## 环境说明

- Python 3.13，Windows 11
- Windows Defender 会拦截 pydantic-core 的 DLL，因此 anthropic SDK **不可用**
- `vision_extractor.py` 已改为纯 `urllib` 直接调 Anthropic REST API，无任何 pydantic 依赖
- API Key 存于 `.env`（UTF-8 BOM 编码），读取时用 `utf-8-sig`
- 依赖：`pip install pypdfium2 Pillow`（anthropic SDK 不需要装）

## API 配置

- **使用 Anthropic API**，模型：`claude-sonnet-4-6`
- API URL：`https://api.anthropic.com/v1/messages`
- Key：`.env` 中 `ANTHROPIC_API_KEY=<your_key>`（本包不包含实际密钥）

## 已修复的 Bug（本次会话）

| Bug | 位置 | 修复方式 |
|-----|------|----------|
| 代码调用 OpenAI API 但 key 是 Anthropic 的 | `vision_extractor.py` | 整体重写为 Anthropic urllib |
| `gpt-5.4-mini` 模型 + OpenAI URL | `vision_extractor.py` | 改为 `claude-sonnet-4-6` + Anthropic URL |
| pydantic-core DLL 被 Defender 拦截 | `vision_extractor.py` | 去掉 SDK 依赖，纯 urllib |
| `.env` UTF-8 BOM 导致 key 读取失败 | `vision_extractor.py` | `read_text(encoding='utf-8-sig')` |
| `validator.py` 写 `r["warnings"]` 但 DB 读 `warnings_json` | `validator.py` | 改为 `r["warnings_json"]` |

## 当前状态（2026-04-26）

### 已跑通
- pipeline 全链路可用：PDF → PNG → Anthropic Vision → SQLite
- 第5页（早稻田核心表格页）可提取，12/12 学部全部识别

### 未解决的问题

**1. 英语字段漏提取（主要问题）**

以下学科 `english_requirement` 为空（实际上应有值）：
- `基幹理工学部` 学系Ⅰ/Ⅱ/Ⅳ（学系Ⅲ整条记录也消失了）
- `先進理工学部` 全部6个学科
- `創造理工学部` 建築学科、総合機械工学科

**根因**：第5页表格宽度3308px，英语列在最右侧，200 DPI 下 LLM 读取困难。

**正在尝试的方案：水平左右分割（Option C）**

`pipeline.py` 已实现 `_split_image_horizontally` 和 `_call_llm_horizontal`，但测试时出现 **0 条记录**的问题——左半边提取结果尚未验证，需要调试 merge 逻辑。

**2. confidence 普遍偏低（0.60~0.72）**

全部记录触发 `needs_review=1`（阈值 0.85）。原因未明，可能是：
- 早稻田表格结构复杂（合并单元格多）
- prompt 中 confidence 的语义对 Claude 模型偏保守
- 考虑把阈值调低到 0.70，或在 prompt 中说明置信度标准

## 运行方式

### 标准运行（单页）
```powershell
python scripts/pipeline.py `
  --pdf input_pdfs/01_2027_gaikokugakusei_nyushiyoukou.pdf `
  --university 早稲田大学 `
  --year 2027 `
  --pages 5
```

### 水平分割模式（调试英语列漏提取）
```powershell
python scripts/pipeline.py `
  --pdf input_pdfs/01_2027_gaikokugakusei_nyushiyoukou.pdf `
  --university 早稲田大学 `
  --year 2027 `
  --pages 5 `
  --hsplit 5
```

### 回归测试
```powershell
python scripts/regression_waseda_2027.py
```

## 下一步任务（优先级排序）

1. **调试水平分割的 0 条记录问题**
   - 检查 `output_pages/.../page_005_left.png` 和 `page_005_right.png` 是否生成
   - 单独调用 `extract_page(left_path, meta)` 看左半边返回什么
   - `_merge_horizontal_results` 的 `(faculty, dept)` key 匹配可能失败（左右两次提取的学部名称可能格式不一致）

2. **确认理工学部英语要求的实际内容**
   - 查看原始 PDF 第5页的英语列（基幹/先進/創造理工）
   - 如果英语要求在不同页（如后续说明页），需要把那几页也加入pipeline

3. **confidence 阈值调整**
   - 当前 0.85 导致 100% needs_review，建议降到 0.70

## 数据库字段

| 字段 | 说明 |
|------|------|
| university | 大学名 |
| pdf_url | PDF链接 |
| admission_year | 年度 |
| admission_period | 前期/後期/全一期等 |
| faculty | 学部 |
| department | 学科・専修等 |
| application_period | 出願期間 |
| deadline_rule | 必着/消印等 |
| eju_session | EJU実施回 |
| eju_japanese | EJU日本語 |
| eju_general | EJU総合科目 |
| eju_math | EJU数学 |
| eju_physics | EJU物理 |
| eju_chemistry | EJU化学 |
| eju_biology | EJU生物 |
| english_requirement | 英語外部資格試験 |
| screening_method | 選考方法 |
| screening_schedule | 選考日程 |
| result_date | 合格発表日 |
| enrollment_period | 入学手続期間 |
| prefecture | 都道府県 |
| campus | キャンパス |

## 注意事项

1. 早稻田只有一个出願期（全一期），不分前后期
2. 早稻田EJU没有分数线，只有○/－
3. 第5页是核心表格，先跑这一页验证字段对齐
4. 旧数据库 `admissions.db` 保持不动，新系统用 `admissions_v2.db`
5. DB 里有大量测试跑产生的旧记录（doc_id 1-18），正式结果用最新的 doc_id
