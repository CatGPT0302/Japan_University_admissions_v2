# admissions_v2 clean package

这是一个精简打包版，已去掉以下非必要/高风险内容：

- node_modules
- frontend/dist
- .git 历史目录
- .env 与本地密钥文件
- 数据库文件
- 运行日志
- 本地缓存文件

保留内容：

- FastAPI 后端脚本
- React 前端源码
- 人工复查页面
- 中文化 UI
- handoff 文档
- trace_debug.json
- prompts
- input_pdfs 样例 PDF
- demo 页面与录屏脚本

## 启动方式

后端：

```powershell
pip install -r requirements.txt
python -m uvicorn scripts.api:app --reload --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

浏览器打开：

```text
http://localhost:5173
```

如需实际抽取，请在项目根目录创建 `.env` 并填入你的 `OPENAI_API_KEY`。
