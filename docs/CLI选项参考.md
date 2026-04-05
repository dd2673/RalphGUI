# 功能参考

Ralph GUI 功能选项和配置的完整参考。

---

## 核心功能

### 循环控制

| 功能 | 说明 |
|------|------|
| 启动 | 开始执行 Ralph 循环任务 |
| 暂停 | 暂停当前运行的循环 |
| 恢复 | 继续被暂停的循环 |
| 停止 | 终止当前循环任务 |

### 断路器状态

| 状态 | 说明 |
|------|------|
| CLOSED | 正常运行，断路器未触发 |
| HALF_OPEN | 部分恢复，允许测试请求 |
| OPEN | 已触发保护，暂停调用 |

### 速率限制

- **最大调用次数/小时**: API 调用频率限制
- **倒计时**: 距离下次可用调用的时间
- **当前调用数**: 已使用的调用配额

---

## 配置选项

### 基本设置

| 选项 | 默认值 | 说明 |
|------|--------|------|
| Claude Code 命令 | `claude` | Claude Code CLI 调用的命令 |
| 最大调用次数/小时 | `100` | 每小时最大 API 调用次数 |
| 超时时间 | `15` 分钟 | 单次调用超时时间 |
| 会话连续性 | `true` | 是否保持会话连续性 |
| 会话过期时间 | `24` 小时 | 会话 ID 自动过期时间 |

### 断路器设置

| 选项 | 默认值 | 说明 |
|------|--------|------|
| 无进展阈值 | `3` | 连续无进展循环次数后打开断路器 |
| 相同错误阈值 | `5` | 连续相同错误次数后打开断路器 |
| 输出下降阈值 | `70%` | 输出大小下降百分比阈值 |
| 冷却时间 | `30` 分钟 | OPEN 状态后等待时间 |

### 工具权限

允许 Claude 使用的工具列表：
- `Write` - 写入文件
- `Read` - 读取文件
- `Edit` - 编辑文件
- `Glob` - 文件搜索
- `Grep` - 内容搜索
- `Bash` - 执行命令

---

## 快捷操作

| 操作 | 说明 |
|------|------|
| 选择项目目录 | 点击「选择目录」按钮选择包含 `.ralphrc` 的项目 |
| 查看日志 | 在日志输出区域滚动查看完整日志 |
| 重置断路器 | 当断路器打开时，点击「恢复」可重置 |
| 导入 PRD | 从外部源导入任务计划 |

---

## 项目配置文件

### .ralphrc 格式

```bash
# 项目配置示例
PROJECT_NAME="my-project"
PROJECT_TYPE="typescript"

# Claude Code 设置
CLAUDE_CODE_CMD="claude"
MAX_CALLS_PER_HOUR=100
CLAUDE_TIMEOUT_MINUTES=15
CLAUDE_OUTPUT_FORMAT="json"

# 工具权限
ALLOWED_TOOLS="Write,Read,Edit,Bash(git *)"

# 会话管理
SESSION_CONTINUITY=true
SESSION_EXPIRY_HOURS=24

# 断路器阈值
CB_NO_PROGRESS_THRESHOLD=3
CB_SAME_ERROR_THRESHOLD=5
```
