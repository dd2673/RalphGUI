# Ralph CLI 选项参考

`ralph` 命令行标志和 `.ralphrc` 配置模式的完整参考。

> **快速开始**: 运行 `ralph --help` 获取摘要。本文档深入介绍每个标志，包括示例和常见 `.ralphrc` 模式。

---

## 核心标志

### `-h, --help`
显示帮助消息并退出。

```bash
ralph --help
```

---

### `-c, --calls NUM`
在速率限制生效前，每小时最大 API 调用次数。

| 默认值 | `.ralphrc` 键 |
|---------|----------------|
| `100` | `MAX_CALLS_PER_HOUR` |

```bash
ralph --calls 50          # 保守 — 慢速、谨慎的项目
ralph --calls 200         # 激进 — 大型任务积压
```

> **提示**: 在初始项目设置期间将此值设置较低，以避免在您的 `.ralph/PROMPT.md` 仍在调整时出现失控循环。

---

### `-p, --prompt FILE`
驱动每个循环迭代的提示文件路径。

| 默认值 | `.ralphrc` 键 |
|---------|----------------|
| `.ralph/PROMPT.md` | `PROMPT_FILE` |

```bash
ralph --prompt .ralph/PROMPT_experimental.md
```

---

### `-s, --status`
打印当前循环状态从 `.ralph/status.json` 并退出。不启动循环。

```bash
ralph --status
```

---

### `-m, --monitor`
启动集成的 tmux 会话，循环在左侧窗格，实时监控仪表板在右侧窗格。需要 `tmux`。

```bash
ralph --monitor
ralph --monitor --calls 50 --prompt my_prompt.md
```

> **建议用于交互使用。** 无需单独的终端即可实时查看循环进度、断路器状态和 API 调用计数。

---

### `-v, --verbose`
在执行期间显示详细进度更新 (记录到 stdout 和日志文件)。

```bash
ralph --verbose
ralph --live --verbose    # 实时流式传输 + 详细日志
```

---

### `-l, --live`
将 Claude Code 输出实时流式传输到终端。如果设置为 `text`，自动切换 `--output-format` 到 `json`。

```bash
ralph --live
ralph --live --timeout 30
```

> **注意**: 实时模式通过流式管道传输输出。输出是详细的 - 对于长时间运行，考虑 `--monitor` 以获得更清晰的视图。

---

### `-t, --timeout MIN`
允许单个 Claude Code 调用运行的最大时间 (以分钟为单位)，然后以退出代码 124 终止。

| 默认值 | `.ralphrc` 键 |
|---------|----------------|
| `15` | `CLAUDE_TIMEOUT_MINUTES` |

```bash
ralph --timeout 5     # 快速任务 / 紧密反馈循环
ralph --timeout 60    # 长时间重构或大型代码库
```

当超时时，Ralph 检查 git 是否有运行期间所做的更改：
- **文件已更改** → 生产性超时：分析运行，循环继续
- **文件未更改** → 空闲超时：计为失败的迭代

---

## 断路器标志

### `--reset-circuit`
将断路器重置为 `CLOSED` (正常) 状态并退出。在解决导致断路器跳闸的底层问题后使用。

```bash
ralph --reset-circuit
```

---

### `--circuit-status`
打印当前断路器状态 (`CLOSED`、`HALF_OPEN` 或 `OPEN`) 并退出。

```bash
ralph --circuit-status
```

---

### `--auto-reset-circuit`
在启动时将断路器重置为 `CLOSED`，绕过冷却计时器。仅应用于单次运行；不持久化。

| `.ralphrc` 键 | 默认值 |
|----------------|---------|
| `CB_AUTO_RESET` | `false` |

```bash
ralph --auto-reset-circuit    # 一次性重置 + 运行
```

> **使用场景**: 完全无人值守的部署 (CI、cron 作业)，在没有人类会手动运行 `--reset-circuit` 的情况下。对于交互使用，优先使用 `--reset-circuit` 以便首先检查原因。

---

### `--reset-session`
清除保存的 Claude 会话 ID 并退出。强制下一个循环开始新的对话，无先前上下文。

```bash
ralph --reset-session
```

> 当会话已偏离或 Claude 陷入非生产性模式时使用。会话状态位于 `.ralph/.claude_session_id`。

---

## 现代 CLI 标志

### `--output-format FORMAT`
设置 Claude Code 响应的输出格式。

| 值 | 行为 |
|-------|-----------|
| `json` (默认) | 结构化 JSON — 启用会话连续性、退出信号检测和 token 计数 |
| `text` | 传统纯文本 — 仅启发式退出检测，较高误报率 |

| 默认值 | `.ralphrc` 键 |
|---------|----------------|
| `json` | `CLAUDE_OUTPUT_FORMAT` |

```bash
ralph --output-format json    # 默认；推荐
ralph --output-format text    # 传统后备
```

> **强烈推荐 JSON 模式。** 在文本模式下，启发式退出检测需要 `confidence_score >= 70` AND `has_completion_signal=true` 以防止文档关键字的误报退出。在 JSON 模式下，启发式完全被抑制 — 只有 `RALPH_STATUS` 块中的显式 `EXIT_SIGNAL: true` 可以触发退出。

---

### `--allowed-tools TOOLS`
Claude 允许使用的工具的逗号分隔列表。覆盖此运行的 `.ralphrc` 默认值。

| 默认值 | `.ralphrc` 键 |
|---------|----------------|
| 见下文 | `ALLOWED_TOOLS` |

**默认值:**
```
Write,Read,Edit,Bash(git add *),Bash(git commit *),Bash(git diff *),Bash(git log *),
Bash(git status),Bash(git status *),Bash(git push *),Bash(git pull *),Bash(git fetch *),
Bash(git checkout *),Bash(git branch *),Bash(git stash *),Bash(git merge *),Bash(git tag *),
Bash(npm *),Bash(pytest)
```

```bash
# 限制为只读审计运行
ralph --allowed-tools "Read,Grep,Glob"

# 允许所有 git 命令 (安全性较低 — 包括 git clean、git rm)
ralph --allowed-tools "Write,Read,Edit,Bash(git *),Bash(npm *)"
```

> **为什么是特定的 git 子命令？** 默认值故意省略 `Bash(git *)` 以防止可能删除 `.ralph/` 配置文件的 `git clean`、`git rm` 和 `git reset`。参见 [文件保护](../CLAUDE.md#file-protection-issue-149)。

---

### `--no-continue`
禁用会话连续性。每个循环迭代开始一个完全新鲜的 Claude 对话，无先前迭代的记忆。

| 默认值 | `.ralphrc` 键 |
|---------|----------------|
| 启用连续性 | `SESSION_CONTINUITY=true` |

```bash
ralph --no-continue
```

> 当会话积累了太多上下文且 Claude 基于过时假设做决策时使用。也适用于隔离单个迭代以进行调试。

---

### `--session-expiry HOURS`
覆盖会话 ID 在自动丢弃并开始新会话之前保留的小时数。

| 默认值 | `.ralphrc` 键 |
|---------|----------------|
| `24` | `SESSION_EXPIRY_HOURS` |

```bash
ralph --session-expiry 48    # 具有稳定上下文的大型项目
ralph --session-expiry 4     # 短期任务，新鲜上下文更好
```

---

## 常见 `.ralphrc` 模式

项目根目录的 `.ralphrc` 文件在每个循环之前被读取。环境变量始终优先于 `.ralphrc` 值。

### 本地工作站 (默认)

```bash
MAX_CALLS_PER_HOUR=100
CLAUDE_TIMEOUT_MINUTES=15
CLAUDE_OUTPUT_FORMAT="json"
CLAUDE_AUTO_UPDATE=true
SESSION_CONTINUITY=true
SESSION_EXPIRY_HOURS=24
```

---

### Docker 容器

```bash
# 版本在镜像构建时固定 — 跳过 npm registry 检查
CLAUDE_AUTO_UPDATE=false

# 容器是临时的 — 持久化会话没有意义
SESSION_CONTINUITY=false

# 更紧的超时以实现可预测的 CI 运行时间
CLAUDE_TIMEOUT_MINUTES=10
```

---

### 空气隔离 / 离线环境

```bash
# npm registry 不可达 — 防止超时和警告泛滥
CLAUDE_AUTO_UPDATE=false

# 如果不在 PATH 上，使用特定的本地 Claude CLI 路径
CLAUDE_CODE_CMD="/opt/local/bin/claude"
```

---

### 无人值守 / cron 操作

```bash
# 降低调用率以避免夜间失控消费
MAX_CALLS_PER_HOUR=50

# 每小时 token 预算 (0 = 禁用)。预算用尽后阻止调用。
# 在整点与调用计数器一起重置。
MAX_TOKENS_PER_HOUR=50000

# 批处理工作的较长超时
CLAUDE_TIMEOUT_MINUTES=30

# 自动从断路器恢复，无需人工干预
CB_AUTO_RESET=false           # false = 使用冷却 (更安全)
CB_COOLDOWN_MINUTES=30        # OPEN 后等待 30 分钟再重试
```

---

### 断路器调优

```bash
# N 次无文件更改的循环后打开电路 (默认: 3)
CB_NO_PROGRESS_THRESHOLD=3

# N 次相同错误重复的循环后打开电路 (默认: 5)
CB_SAME_ERROR_THRESHOLD=5

# 输出大小下降超过 N% 时打开电路 (默认: 70)
CB_OUTPUT_DECLINE_THRESHOLD=70

# OPEN 状态等待分钟数 before transitioning to HALF_OPEN (默认: 30)
# 设置为 0 表示立即重试
CB_COOLDOWN_MINUTES=30

# 跳过冷却并在启动时直接重置为 CLOSED (默认: false)
# 谨慎使用 — 降低无人值守运行的安全性
CB_AUTO_RESET=false
```

---

### 限制工具权限

```bash
# 广泛 (开发): 允许所有 git 子命令
ALLOWED_TOOLS="Write,Read,Edit,Bash(git *),Bash(npm *),Bash(pytest)"

# 安全 (默认): 仅特定的 git 子命令，无破坏性 git 命令
ALLOWED_TOOLS="Write,Read,Edit,Bash(git add *),Bash(git commit *),Bash(git diff *),Bash(git log *),Bash(git status),Bash(git push *),Bash(npm *),Bash(pytest)"

# 只读审计
ALLOWED_TOOLS="Read,Grep,Glob"
```

---

### 模型和努力覆盖

```bash
# 使用特定的 Claude 模型而不是 CLI 默认
CLAUDE_MODEL="claude-sonnet-4-6"

# 设置努力级别 (high = 更彻底，low = 更快/更便宜)
CLAUDE_EFFORT="high"
```

两者也可以设置为环境变量，优先于 `.ralphrc`:

```bash
CLAUDE_MODEL=claude-opus-4-6 ralph --monitor
```

---

### 自定义 shell 初始化

```bash
# 在每个循环之前获取脚本 (例如，激活 virtualenv 或设置 PATH)
RALPH_SHELL_INIT_FILE=".ralph/init.sh"
```

如果文件已设置但缺失，Ralph 会发出警告，如果不存在则跳过获取。

---

## 仅 `.ralphrc` 键

这些键没有 CLI 标志等价物 — 只能通过 `.ralphrc` 或环境变量设置。

| 键 | 默认值 | 描述 |
|-----|---------|-------------|
| `CLAUDE_CODE_CMD` | `"claude"` | Claude Code CLI 命令。对于非全局安装，覆盖 (例如，`"npx @anthropic-ai/claude-code"`)。 |
| `CLAUDE_AUTO_UPDATE` | `true` | 在启动时自动检查 npm registry 并更新 Claude CLI。对于 Docker/空气隔离环境设置为 `false`。 |
| `CLAUDE_MIN_VERSION` | `"2.0.76"` | 所需的最低 Claude CLI 版本。如果安装的版本较旧，Ralph 警告并退出。 |
| `MAX_TOKENS_PER_HOUR` | `0` | 每小时 token 预算 (`input + output`)。`0` = 禁用。用尽后阻止进一步调用；在整点与调用计数器一起重置。 |
| `RALPH_VERBOSE` | `false` | 启用详细进度日志记录。等同于使用 `--verbose` 运行。 |
| `CB_NO_PROGRESS_THRESHOLD` | `3` | 在 N 次连续无文件更改的循环后打开断路器。 |
| `CB_SAME_ERROR_THRESHOLD` | `5` | 在 N 次连续相同错误后打开断路器。 |
| `CB_OUTPUT_DECLINE_THRESHOLD` | `70` | 如果输出大小下降超过 N%，则打开断路器。 |
| `CB_COOLDOWN_MINUTES` | `30` | OPEN 状态分钟数 before transitioning to HALF_OPEN 进行恢复尝试。 |
| `CB_AUTO_RESET` | `false` | 跳过冷却并在启动时直接重置为 CLOSED。降低安全性；优先用于完全无人值守的 CI 运行。 |
| `PROJECT_NAME` | `"my-project"` | 在提示和日志输出中用于标识。 |
| `PROJECT_TYPE` | `"unknown"` | 项目类型提示: `javascript`、`typescript`、`python`、`rust`、`go`、`unknown`。 |

---

## 环境变量优先级

```
环境变量   ← 最高优先级
    ↓
.ralphrc 值
    ↓
Ralph 默认值          ← 最低优先级
```

所有 `.ralphrc` 键都可以使用相同的名称作为环境变量设置:

```bash
MAX_CALLS_PER_HOUR=200 ralph --monitor   # 仅覆盖此次运行
```
