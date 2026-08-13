# Repo Brain

面向编程代理的持久化代码仓库记忆。

[English](README.md) · [Português do Brasil](README.pt-BR.md) · [简体中文](README.zh-CN.md)

Repo Brain 是一个离线优先的技能、CLI、SQLite 记忆库和 MCP 服务器。它帮助编程代理在开始任务时快速找到正确的文件，而不必每次都重新阅读整个仓库。

> 记忆用于发现线索；当前源代码才是真相。

## 技能的工作方式

`repo-brain` 技能为代理提供一套可重复、以证据为先的流程：

1. 检查仓库健康状态并执行增量扫描。
2. 根据任务搜索记忆，排列相关文件、符号、测试和依赖。
3. 修改前通过可审计的读取操作读取当前源代码。
4. 检查过期分析、直接依赖者和架构决策。
5. 对功能、重构、迁移、安全变更或跨模块缺陷创建持久化计划。
6. 修改代码、运行项目测试并再次扫描。
7. 使用新的源代码哈希更新分析并结束会话。

技能不会授权代理只凭旧摘要进行修改。文件哈希变化后，对应分析会变为 `stale`；直接依赖者可能变为 `needs_review`。在关键修改前必须重新读取当前文件。

## 按目录隔离记忆并节省 token

记忆按仓库规范化目录分区。每个索引文件属于自己的直接目录；每个目录还保存子树统计、简短摘要、职责、入口、风险和新鲜度状态。目录分析只是帮助代理定位的短路由层，不能代替读取当前源代码。

先查看目录地图，再限制检索范围：

```bash
repo-brain directories --json
repo-brain directory src/auth --json
repo-brain context "rotate password reset tokens" --directory src/auth --limit 8 --json
repo-brain analyze-directory src/auth --json-file auth-directory.json
```

`context` 返回按目录分组的 `groups`、目录摘要和状态、有意设计的 `read_order`、过期警告以及 `estimated_tokens`。系统不提供手动 token 上限。建议一次只检索一个目录，并为任务选择合适的结果数量；自动压缩会删除重复的符号和职责，同时保留可执行的发现交接。随后使用返回路径调用 `repo-brain read`，编辑前再次确认当前哈希。


## 环境要求

- Python 3.11 或更高版本。
- 支持 WAL 的 SQLite 3（Python 自带）。
- Git 可选。Git 仓库的多个 worktree 共享记忆；非 Git 项目使用 `.repo-brain/`。
- 正常使用不需要 API 密钥、云账户、外部数据库、模型或互联网。
- 如果可用则使用 FTS5；否则使用确定性的 SQL/排序回退实现搜索。

## 安装

安装已发布的软件包：

```bash
python -m pip install repo-brain
```

从本仓库开发安装：

```bash
python -m pip install -e ".[dev]"
```

然后在需要建立记忆的项目中安装代理集成：

```bash
cd /path/to/your-project
repo-brain install --all
repo-brain init
```

`install --codex` 会创建 `.agents/skills/repo-brain/SKILL.md` 和 `AGENTS.md` 中的受管理区块。`install --claude` 会创建 Claude 技能和 `CLAUDE.md` 中的受管理区块。已有用户内容会被保留。使用 `--dry-run` 可预览改动。

## 首次运行和数据库位置

`repo-brain init` 会创建配置、执行迁移、建立文件清单、计算哈希、提取静态符号和依赖、填充 bootstrap 队列，并生成 `.repo-brain/INDEX.md`。

查看实际使用的数据库：

```bash
repo-brain db path
```

Git 仓库默认使用 `<git-common-dir>/repo-brain/brain.db`，因此不同 worktree 共享同一份记忆。非 Git 项目使用 `.repo-brain/brain.db`。数据库和 WAL 文件不应提交；`INDEX.md` 是可重新生成的简短人工仪表盘。

## 代理的日常流程

```text
status → scan → context → 阅读当前代码 → plan（需要时）
      → 修改 → 测试 → scan → 更新分析 → index/结束会话
```

常用命令：

```bash
repo-brain status
repo-brain scan
repo-brain context "change password reset token expiration and email flow"
repo-brain read src/auth/password_reset.py
repo-brain impact src/auth/token.py --depth 3
repo-brain analyze src/auth/password_reset.py --json-file analysis.json
repo-brain scan
```

状态、上下文、搜索、覆盖率、读取、变更、图关系和 bootstrap 等命令支持 `--json`，便于代理和脚本消费。

## 存储内容

SQLite 存储仓库身份、相对/规范化路径、哈希、语言/类别、行数、分析状态、目录分区、目录分析、符号、依赖、模块、会话、读取记录、变更、计划、决策、观察和标签。文件分析历史保存在 `analysis_history` 中；目录分析使用带源指纹的 `directory_analyses` 版本记录。

默认不保存完整源代码。疑似秘密文件（`.env`、密钥、证书、凭据等）不会进行深度语义分析。读取和写入 hooks 只记录路径、哈希、工具、会话和时间戳，不记录写入的完整内容。

## 主要命令

| 领域 | 命令 |
| --- | --- |
| 设置 | `init`、`install`、`uninstall`、`migrate`、`doctor` |
| 健康 | `status`、`coverage`、`stale`、`index`、`db path`、`db check`、`db vacuum` |
| 发现 | `search`、`context`、`directories`、`directory`、`efficiency`、`file`、`symbols`、`modules` |
| 关系图 | `deps FILE`、`dependents FILE`、`impact FILE --depth N` |
| 审计 | `read FILE`、`reads`、`changes`、`history` |
| 代理记忆 | `session`、`analyze`、`analyze-directory`、`plan`、`decision` |
| Bootstrap | `bootstrap status`、`claim`、`complete`、`fail` |
| 可移植性 | `export`、`import` |
| 集成 | `mcp serve`、`ui`、`integrate codex`、`integrate claude` |

使用 `repo-brain COMMAND --help` 查看完整参数。

## Bootstrap 模式

大型项目可以由多个代理协作分析：

```bash
repo-brain bootstrap claim --limit 10
repo-brain read path/to/file.py --purpose bootstrap
repo-brain analyze path/to/file.py --json-file analysis.json
repo-brain bootstrap complete path/to/file.py
```

claim 使用租约机制，多个代理不会同时得到同一项。代理失败后，租约到期即可重新领取。

## 分析和证据

代理可以保存简洁、事实性的分析：

```json
{
  "summary": "创建并轮换密码重置令牌。",
  "responsibilities": ["验证过期时间", "防止重放"],
  "security_notes": ["轮换后使旧令牌失效"],
  "risks": ["轮换不具备原子性时可能被重放"],
  "tags": ["auth", "security"],
  "confidence": 0.9
}
```

重要观察应尽可能包含文件、源代码哈希、行号范围和置信度。不要保存模型的私有推理过程或秘密。

## MCP 服务器

启动本地 stdio 服务器：

```bash
repo-brain mcp serve
```

服务器提供状态、扫描、上下文、搜索、文件读取、符号、依赖、影响分析、会话、分析、计划、决策、bootstrap 和索引刷新工具。`brain_read_file` 会验证路径、读取指定行范围、记录读取并返回当前哈希和分析状态。

在 MCP 主机中配置命令 `repo-brain` 和参数 `mcp serve`。仓库同时提供 Claude 插件清单和 `.mcp.json` 模板。

## 本地界面

本地仪表盘与相同的服务层工作，不需要额外的 Web 框架：

```bash
repo-brain ui --host 127.0.0.1 --port 8765
```

打开 <http://127.0.0.1:8765>。页面显示文件数量、语义覆盖率、fresh/stale 状态以及上下文搜索结果。除非主动绑定其他地址，否则服务器只在本机提供服务。

## Codex 和 Claude Code

规范技能位于 `skills/repo-brain/SKILL.md`。可分发的 Claude 插件位于 `integrations/claude-plugin/`，包含技能、hooks 配置、安全脚本和 MCP 配置。hooks 采用 best-effort 方式：Repo Brain 出错绝不能阻塞用户编辑。

## 配置

`repo-brain init` 会创建 `.repo-brain/config.toml`。可配置 include/exclude、最大文件大小、允许/忽略的扩展名、秘密模式、排序限制和 bootstrap 租约时间。请勿将数据库、WAL 文件和本地日志加入版本控制。

## 导出和导入

```bash
repo-brain export
repo-brain import .repo-brain/export/snapshot.jsonl
```

快照包含经过清理的元数据、哈希、分析、关系和决策，不包含完整源代码。导入的信息仍与源哈希绑定；如果当前源代码不同，必须视为 stale 并重新阅读。

## 安全与隐私

- 离线优先，无外部遥测；效率指标只保存在本地 SQLite 中。
- 规范化路径，防止路径穿越和逃出仓库根目录。
- 参数化 SQL，防止注入。
- 秘密、二进制和超大文件不会被语义加载。
- WAL、外键、busy timeout 和短事务支持并发代理。
- 当前代码始终优先于记忆。

请阅读 [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md) 了解威胁模型。

## 示例和开发

验收示例位于 `examples/demo-project/`：

```bash
repo-brain --root examples/demo-project init
repo-brain --root examples/demo-project context "change password reset token expiration and update its email flow"
```

运行测试和构建：

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src tests
python -m build
```

更多信息请查看 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)、[docs/DATABASE.md](docs/DATABASE.md)、[docs/MCP.md](docs/MCP.md)、[docs/CODEX.md](docs/CODEX.md)、[docs/CLAUDE.md](docs/CLAUDE.md) 和 [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)。

## 许可证

Apache License 2.0。参见 [LICENSE](LICENSE)。
本地界面也保持相同边界：侧栏和范围选择器一次显示一个目录（含其子目录）；跨目录搜索仍按目录分组显示，不会把文件混成一个列表。

## 记录 token 和时间效率

每次 `context` 调用都会在 `retrieval_runs` 中记录不含内容的本地元数据：任务哈希和长度、目录、结果数量限制、候选/结果数量、候选/选中/压缩 token 的近似值以及毫秒级耗时。不会保存任务文本、源代码或模型私有推理。这些估计用于比较检索，不是模型供应商账单。

查看趋势：

```bash
repo-brain efficiency --limit 100 --json
repo-brain efficiency --directory src/auth --json
```

报告也可以通过 MCP 的 `brain_efficiency`、本地界面的 `/api/efficiency`、`status.retrieval.recorded_runs`、`.repo-brain/INDEX.md` 和导出快照访问。请参阅[ token 效率计划](docs/TOKEN_EFFICIENCY_PLAN.md)，其中记录目标、公式、阶段、隐私规则和决策模板。

## 目录更新与 SQL 变更

`repo-brain scan` 会在 `changes` 中自动记录文件变化，包括旧/新哈希、原因和时间戳，但不会自动重写 SQL 文件。数据库 schema 变更必须在 `src/repo_brain/migrations/` 下创建新的编号 migration；已经应用的 migration 不可修改。`repo-brain db check --json` 会报告完整性、待处理版本以及 migration 源漂移。请参阅[目录与 SQL 改进计划](docs/DIRECTORY_IMPROVEMENT_PLAN.md)，了解升级清单和组织规则。
