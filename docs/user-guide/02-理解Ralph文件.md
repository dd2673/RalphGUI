# 理解 Ralph 文件

Ralph GUI 管理 Ralph for Claude Code 项目。本指南解释每个文件的作用。

## Ralph 项目文件结构

```
my-project/
├── .ralph/                 # Ralph 配置目录
│   ├── PROMPT.md          # 项目指令 (您编写)
│   ├── fix_plan.md        # 任务列表 (您 + Ralph 更新)
│   ├── AGENT.md           # 构建指令 (自动维护)
│   ├── specs/             # 详细规范 (可选)
│   │   └── stdlib/        # 标准库模式 (可选)
│   ├── logs/              # 执行日志 (只读)
│   └── status.json        # 循环状态 (只读)
├── .ralphrc               # 项目配置文件
└── ...                   # 您的项目文件
```

## 核心文件

### PROMPT.md - 项目愿景

**目的**: Ralph 在每个循环开始时读取的高级指令。

**应包含**:
- 项目描述和目标
- 技术栈和框架
- 关键原则或约束
- 质量标准

**示例**:
```markdown
# Ralph 开发指令

## 上下文
您是 Ralph，正在构建一个 REST API 项目。

## 技术栈
- Python 3.11+ 使用 FastAPI
- PostgreSQL 数据库
- pytest 测试框架

## 关键原则
- 遵循 RESTful 约定
- 所有端点需要测试
- 使用 Pydantic 进行验证
```

### fix_plan.md - 任务列表

**目的**: Ralph 处理的优先级任务清单。

**关键特征**:
- Ralph 完成后会勾选 `[x]` 项目
- 您可以随时添加、重新排序或删除任务
- 更具体的任务 = 更好的结果

**好的任务结构**:
```markdown
## 优先级 1: 基础
- [ ] 创建数据库模型
- [ ] 设置 API 路由

## 优先级 2: 功能
- [ ] 实现 GET /items 端点
- [ ] 实现 POST /items 端点
```

### .ralphrc - 项目配置

**目的**: 特定于项目的 Ralph 设置。

**默认内容**:
```bash
PROJECT_NAME="my-project"
PROJECT_TYPE="python"
MAX_CALLS_PER_HOUR=100
ALLOWED_TOOLS="Write,Read,Edit,Bash(git *)"
```

## 文件关系

```
┌─────────────────────────────────────────────┐
│                   PROMPT.md                  │
│              (高级目标和原则)                   │
└─────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│                 fix_plan.md                  │
│              (具体任务列表)                   │
└─────────────────────────────────────────────┘
```

## Ralph GUI 管理的文件

| 文件 | GUI 显示位置 | 说明 |
|------|-------------|------|
| status.json | 主界面状态区 | 当前循环状态 |
| .ralph/logs/ | 日志输出面板 | 执行日志 |

## 常见问题

### Ralph GUI 和 CLI 的 .ralph 目录一样吗？

是的。Ralph GUI 和 Ralph CLI 使用相同的 `.ralph/` 目录结构，可以互相操作。

### 我可以直接编辑这些文件吗？

可以。Ralph GUI 不会锁定这些文件。您可以直接编辑 PROMPT.md 和 fix_plan.md。
