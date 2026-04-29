# 格致大学募集要項抽取系统 v1 使用说明

## 1. 这个工具做什么

本工具用于在 Windows 本地处理日本大学外国人留学生募集要項 PDF。

核心流程是：

```text
上传 PDF
→ AI 抽取字段
→ 人工复核
→ 确认入库
→ 导出标准 Excel 主表
```

Excel 是从本地数据库中的已确认记录导出的完整主表，不是每个 PDF 单独生成一份孤立 Excel。

## 2. 文件夹结构

交付文件夹通常如下：

```text
格致大学募集要項抽取系统_v1/
  v1.exe
  .env.example
  README_使用说明.md
  data/
    admissions.db
    uploads/
    exports/
  logs/
    app.log
  config/
```

说明：

- `v1.exe`：启动程序。
- `.env.example`：API key 配置示例。
- `data/admissions.db`：本地数据库，保存上传文档、待复核数据、已确认记录。
- `data/uploads/`：上传 PDF 保存目录。
- `data/exports/`：建议保存导出 Excel 的目录。
- `logs/app.log`：运行日志和错误信息。

## 3. 第一次使用前配置 API key

1. 复制 `.env.example`，命名为 `.env`。
2. 用记事本打开 `.env`。
3. 填入使用方自己的 API key。

支持以下配置：

```text
LLM_API_KEY=
OPENAI_API_KEY=
LLM_BASE_URL=
OPENAI_BASE_URL=
LLM_COMPAT_URL=
OPENAI_COMPAT_URL=
OPENAI_TEXT_MODEL=
OPENAI_VISION_MODEL=
```

至少需要填写 `LLM_API_KEY` 或 `OPENAI_API_KEY` 之一。

如果使用 OpenAI 兼容接口，可同时填写 `LLM_BASE_URL` / `OPENAI_BASE_URL` 或 `LLM_COMPAT_URL` / `OPENAI_COMPAT_URL`。

注意：API 调用费用由使用方自行承担。本交付版本不包含作者个人 API key。

## 4. 启动程序

双击：

```text
v1.exe
```

程序会自动：

1. 检查本地数据目录。
2. 初始化 SQLite 数据库。
3. 启动本地服务。
4. 打开浏览器访问系统页面。

默认访问地址：

```text
http://127.0.0.1:8000
```

如果浏览器没有自动打开，可以手动复制上面的地址到浏览器。

## 5. 上传 PDF

进入“导入”页面后：

1. 选择“本地上传”。
2. 拖入或点击选择募集要項 PDF。
3. 检查招生年份。
4. 点击“开始处理”。

处理过程中页面会显示进度条。复杂 PDF 可能需要几分钟。

## 6. 人工复核

抽取完成后点击“进入人工复核”。

在复核页可以：

- 查看文档列表。
- 查看待复核 records。
- 点击单条 record 查看详情。
- 编辑大学名、出願時期、学部、学科、EJU、英语、选考、日期、校区等字段。
- 右侧可查看对应 PDF 页面，可放大或在新窗口打开原 PDF。
- 保存修改。
- 标记已复核。
- 确认整份文档入库。

AI 抽取结果只是初稿。正式使用前必须人工确认。

## 7. 确认入库

系统的数据流是：

```text
AI 抽取结果 → staging 待复核区
人工确认 → confirmed records 正式记录
Excel 导出 → confirmed records
```

AI 不会自动覆盖已确认记录。

## 8. 导出 Excel

进入“记录”页面后：

1. 可按学校、学部、年份筛选。
2. 点击“导出当前结果”。
3. 浏览器会下载 Excel 文件。

Excel 包含 3 个 sheet：

```text
抽出結果
README
字段映射
```

主表固定列顺序为：

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

关键空字段会以浅黄色提示，需要重点复核。

## 9. 常见错误

### 页面提示服务异常

确认 `v1.exe` 是否仍在运行。如果已关闭，请重新双击启动。

### PDF 抽取失败

常见原因：

- API key 未配置。
- API key 额度不足。
- 网络无法访问模型接口。
- PDF 过大或页面结构复杂。
- 模型接口返回超时。

请先查看 `logs/app.log`。

### 检索 PDF 没有结果

自动检索只作为辅助入口。若检索不到，请使用“本地上传”或“指定链接”。

### Excel 没有数据

Excel 只导出 confirmed records。请先在复核页确认入库。

## 10. 使用边界

本版本是 Windows 本地 MVP 使用版。

不包含：

- 源码交付。
- GitHub 仓库权限。
- 云端部署权限。
- 作者个人 API key。
- 无限维护。
- 字段规则长期免费追加。

如需继续适配更多学校、调整字段规则、源码交接或机构级部署，需要另行确认范围和费用。
