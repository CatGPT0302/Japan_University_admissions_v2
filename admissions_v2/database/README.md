# database

本目录用于本地 SQLite 数据库。

默认数据库文件 `admissions_v2.db` 不放入 push-safe 包，避免误提交运行数据。
如需迁移本地数据到 Railway PostgreSQL，请从原始本地项目复制：

```text
database/admissions_v2.db
```

然后运行：

```bash
python scripts/migrate_to_pg.py
```
