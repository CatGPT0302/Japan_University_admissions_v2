# Appsmith 本地接入说明

这份说明用于把 `admissions_v2` 的本地 FastAPI 接口接到 Appsmith，快速搭出一个最小可用后台。

## 1. 本地安装 Appsmith

先确保本机已经安装并启动 Docker Desktop。

一条命令启动 Appsmith 本地容器：

```bash
docker run -d --name appsmith --restart unless-stopped -p 8080:80 -v appsmith_stacks:/appsmith-stacks appsmith/appsmith-ce:latest
```

启动后，在浏览器打开：

```text
http://localhost:8080
```

第一次进入时按页面提示完成初始化账号即可。

## 2. 连接本地 FastAPI

先在项目目录启动后端：

```bash
uvicorn scripts.api:app --reload --port 8000
```

在 Appsmith 里新建一个 REST API Datasource，Base URL 填：

```text
http://host.docker.internal:8000
```

说明：

- 这是 Windows + Docker 场景下，容器访问宿主机最常用的地址
- Appsmith 运行在 Docker 容器里时，不能直接写 `127.0.0.1:8000`
- 如果以后 FastAPI 改端口，这里同步改掉即可

---

## 3. 需要创建的页面

建议先做 4 个页面：

1. `Upload`
2. `Staging`
3. `Confirm`
4. `Records`

下面是每个页面的最小配置。

---

## 4. Upload 页

### 目标

上传 PDF，填写 `university` 和 `year`，然后触发抽取。

### 页面组件

- `File Picker`：选择 PDF 文件
- `Input`：输入大学名
- `Input`：输入年度
- `Input`：输入来源网址
- `Button`：开始抽取
- `Text` 或 `Text Area`：显示返回结果

### 需要绑定的 API

#### 4.1 `uploadPdf`

- 方法：`POST`
- 路径：`/upload`
- 发送方式：文件上传
- 表单字段名：`file`

用途：

- 把用户选中的 PDF 保存到 `input_pdfs/`
- 返回 `file_name` 和 `saved_path`

#### 4.2 `extractPdf`

- 方法：`POST`
- 路径：`/extract`
- 请求体类型：JSON

请求体示例：

```json
{
  "file_name": "{{uploadPdf.data.file_name}}",
  "university": "{{InputUniversity.text}}",
  "year": "{{InputYear.text}}",
  "url": "{{InputUrl.text}}"
}
```

### 按钮动作建议

按钮点击时按这个顺序执行：

1. 先调用 `uploadPdf`
2. 上传成功后，再调用 `extractPdf`
3. 把 `extractPdf` 的返回结果显示在页面上

### 页面提示

- 抽取完成后显示 `doc_id`
- 显示 `records`
- 显示 `failed_pages`

---

## 5. Staging 页

### 目标

输入 `doc_id` 查询 staging 数据，支持查看和局部编辑。

### 页面组件

- `Input`：输入 `doc_id`
- `Button`：查询
- `Table`：展示 staging 记录
- `Button`：保存修改
- `Text`：显示保存结果

### 需要绑定的 API

#### 5.1 `getStagingByDoc`

- 方法：`GET`
- 路径：`/staging/{{InputDocId.text}}`

返回字段建议直接展示：

- `id`
- `faculty`
- `department`
- `eju_session`
- `eju_japanese`
- `eju_general`
- `eju_math`
- `eju_physics`
- `eju_chemistry`
- `eju_biology`
- `english_requirement`
- `screening_method`
- `result_date`
- `confidence`
- `needs_review`

#### 5.2 `patchStaging`

- 方法：`PATCH`
- 路径：`/staging/{{Table.selectedRow.id}}`
- 请求体类型：JSON

请求体示例：

```json
{
  "data": {
    "faculty": "{{Table.selectedRow.faculty}}",
    "department": "{{Table.selectedRow.department}}",
    "english_requirement": "{{Table.selectedRow.english_requirement}}",
    "screening_method": "{{Table.selectedRow.screening_method}}",
    "result_date": "{{Table.selectedRow.result_date}}"
  }
}
```

### 行内编辑建议

- 先让 `Table` 可编辑
- 用户改完后点 `保存修改`
- 保存时把当前选中行的数据发给 `PATCH /staging/{staging_id}`

### 页面提示

- 查询到多少条记录
- 哪些记录 `needs_review=1`
- 保存成功后刷新表格

---

## 6. Confirm 页

### 目标

输入 `doc_id`，一键把该批 staging 记录确认入库。

### 页面组件

- `Input`：输入 `doc_id`
- `Button`：确认入库
- `Text`：显示确认结果

### 需要绑定的 API

#### `confirmDoc`

- 方法：`POST`
- 路径：`/confirm/{{InputDocId.text}}`

返回结果建议显示：

- `confirmed`
- `skipped`

### 页面提示

- 确认前先展示 `doc_id`
- 确认后显示写入条数

---

## 7. Records 页

### 目标

查看已经确认入库的 `admission_records`。

### 推荐做法

这个页面建议绑定一个只读接口，例如：

- `GET /records`

如果当前后端还没有这个接口，建议先补一个只读查询接口，再接 Appsmith。

### 页面组件

- `Table`：展示已确认记录
- `Input`：关键词筛选
- `Dropdown`：按大学名或年度筛选
- `Button`：刷新

### 需要展示的字段

- `university`
- `admission_year`
- `faculty`
- `department`
- `admission_period`
- `english_requirement`
- `screening_method`
- `result_date`
- `prefecture`
- `campus`

### 页面提示

- 这是最终已入库的数据
- 只读查看即可

---

## 8. 推荐的页面连接顺序

建议先按这个顺序搭：

1. 先配好 REST API Datasource
2. 再做 `Upload` 页
3. 再做 `Staging` 页
4. 再做 `Confirm` 页
5. 最后做 `Records` 页

这样可以先跑通“上传 PDF -> 抽取 -> 校对 -> 确认入库”的最小闭环。

---

## 9. 最小验收标准

搭完后，至少确认这些动作能成功：

- 能上传 PDF
- 能触发抽取
- 能拿到 `doc_id`
- 能查出 staging 记录
- 能保存 staging 修改
- 能一键确认入库

如果后面要继续扩展，可以再加：

- 批量确认
- 批量删除
- 过滤器
- 审计日志
- 导出按钮

