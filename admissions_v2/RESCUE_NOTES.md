# RESCUE NOTES

本包是在 Agent 中断后的 admissions_v2.zip 基础上整理出的可继续推进版本。

## 已修复

1. 前端 TypeScript 构建失败
   - 删除未使用的旧页面/组件：
     - DashboardPage / UploadPage / StagingPage / ConfirmPage / ReviewWorkspacePage
     - Sidebar / DataTable / EditModal / StatsBar
   - 修复 ReviewPage 中 StagingRecord 到 Record<string, unknown> 的类型转换问题
   - `npm run build` 已通过

2. 后端 PostgreSQL/SQLite 兼容隐患
   - `DELETE /staging/{staging_id}` 改为调用 db.py 的 `get_staging_record()` / `delete_staging_record()`
   - `/stats` 改为调用 db.py 的 `get_stats()`
   - 避免 API 层直接使用 SQLite 风格的 `conn.execute(...)`

3. 清理重复项目目录
   - 删除嵌套的 `Japan_University_admissions_v2/`

4. 安全清理
   - 未包含 `.env`
   - 未发现明文 API Key
   - 清理 node_modules / dist / 缓存 / 日志 / .git

## 已验证

```bash
cd frontend
npm install --cache .npm-cache
npm run build
```

通过。

```bash
python -c "import scripts.api; print('api import OK')"
```

通过，SQLite 模式可 import。

## 下一步

1. 推送到 GitHub `codex-frontend`
2. 等 Railway 自动重新部署
3. 访问 `/stats` 验证 PostgreSQL 连接
4. 如需迁移本地数据，使用 `scripts/migrate_to_pg.py`
