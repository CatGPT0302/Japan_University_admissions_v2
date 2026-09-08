# 分享给另一个 Codex 用户

分享文件：`runtime/share/admissions-pdf-batch-extractor.zip`。

接收者解压后，将完整的 `admissions-pdf-batch-extractor` 文件夹放入自己的 Codex skills 目录（默认 `~/.codex/skills/`），重新打开一个 Codex 会话，然后请求：

> 用 $admissions-pdf-batch-extractor 直接阅读我这个本地文件夹中的招生PDF，生成能看懂的报告和结构化草稿。不要调用另外的模型API，所有结果保留待人工复核。

给出实际PDF文件夹位置即可。机器需要能运行Python 3.11+，打包脚本使用pypdfium2读取页数；缺少时让Codex在专用虚拟环境中安装。PDF的语义阅读由当前Codex完成，脚本只校验和整理已经读出的JSON。

## 已验证与未验证

- 已将ZIP解压到与仓库分离的临时目录，从两份真实PDF对应的已读JSON生成2份文档、12条草稿。
- 已通过Codex附带的skill格式验证器，并安装到本机 `~/.codex/skills/admissions-pdf-batch-extractor`。
- 后续会话上下文已实际列出 `admissions-pdf-batch-extractor`，本机发现机制已验证；调用安装位置的入口也再次生成了12条草稿。这不替代另一位用户从全新PDF开始的实际试用。
- 独立分享入口不提供数据库导入或自动确认。使用当前项目工作台的导入是另一个可选流程。

ZIP采用固定文件清单，只包含skill说明、字段约定和必需脚本，不包含PDF、数据库、账号、环境变量文件或示例个人数据。脚本从主项目构建时复制，以免手工维护两个版本；更新主项目脚本后应重新构建并重新测试分享包。

```bash
.venv/bin/python -m scripts.build_skill_package runtime/share/admissions-pdf-batch-extractor-next.zip
```

源码目录 `skills/admissions-pdf-batch-extractor` 是构建输入，不是完整发布包；请分享构建出的ZIP，而不是只复制这个源码目录。

## 关于“防蒸馏”

接收者必须读取本地skill才能使用，因此不能承诺它无法被查看、复制或改写。可做的是不把内部提示、推理过程、凭据和无关实现笔记混入数据交付；不能把这说成技术防复制。需要更强的访问控制时，应另行讨论服务端交付方式，不属于当前本地skill演示范围。
