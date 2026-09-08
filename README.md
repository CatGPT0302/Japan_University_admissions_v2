# admissions_v2

日本大学募集要项的信息整理与查询项目。

项目代码、文档、测试和 Skill 统一位于 **[admissions_v2/](admissions_v2/)**。
仓库根目录仅保留说明、许可证、项目规范和构建部署入口。

## 项目入口

- [项目说明与开发环境](admissions_v2/README.md)
- [本机启动](admissions_v2/docs/LOCAL_DEMO.md)
- [学生账号与管理员创建](admissions_v2/docs/ACCOUNTS.md)
- [项目路线图](admissions_v2/docs/PROJECT_ROADMAP.md)
- [所有权声明](OWNERSHIP.md)

## 本机运行

Mac 已安装依赖后，双击根目录的 `start_demo.command`。
也可以从仓库根目录运行：

```sh
cd admissions_v2
.venv/bin/python -m scripts.local_demo
```

后续 Python、npm 和测试命令均在 `admissions_v2/` 内执行。
Windows 启动脚本也位于该目录。全新环境安装步骤见项目说明。

## 构建部署

Docker 从仓库根目录构建，镜像只复制 `admissions_v2/` 的项目内容。
Railway 保留根目录的部署配置；其他平台的代码根目录应设为
`admissions_v2`，前端项目根目录为 `admissions_v2/frontend`。

数据库、原始 PDF、运行产物和凭据只保留在本地，不上传 GitHub。
