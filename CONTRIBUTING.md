# 为 Ralph for Claude Code 做贡献

感谢您有兴趣为 Ralph 做贡献！本指南将帮助您入门，并确保您的贡献符合我们既定的模式和质量标准。

**每一份贡献都很重要** - 从修复错别字到实现主要功能。我们感谢您在让 Ralph 变得更好方面的帮助！

## 目录

1. [入门](#入门)
2. [开发工作流程](#开发工作流程)
3. [代码风格指南](#代码风格指南)
4. [测试要求](#测试要求)
5. [拉取请求流程](#拉取请求流程)
6. [代码审查指南](#代码审查指南)
7. [质量标准](#质量标准)
8. [社区指南](#社区指南)

---

## 入门

### 先决条件

在贡献之前，请确保您已安装以下工具：

- **Bash 4.0+** - 用于脚本执行
- **jq** - JSON 处理（必需）
- **git** - 版本控制（必需）
- **tmux** - 终端多路复用器（推荐）
- **Node.js 18+** - 用于通过 npm 运行测试

### 克隆仓库

```bash
# 首先在 GitHub 上 fork 仓库，然后克隆您的 fork
git clone https://github.com/YOUR_USERNAME/ralph-claude-code.git
cd ralph-claude-code
```

### 安装依赖

```bash
# 安装 BATS 测试框架和依赖
npm install

# 验证 BATS 可用
./node_modules/.bin/bats --version

# 可选：全局安装 Ralph 用于测试
./install.sh
```

### 验证您的设置

```bash
# 运行测试套件以确保一切正常
npm test

# 您应该看到类似以下的输出：
# ✓ 276 个测试通过 (100% 通过率)
```

### 项目结构

```
ralph-claude-code/
├── ralph_loop.sh        # 主循环脚本
├── ralph_monitor.sh     # 实时监控面板
├── setup.sh             # 项目初始化
├── ralph_import.sh      # PRD 导入工具
├── install.sh           # 全局安装脚本
├── lib/                 # 模块化库组件
│   ├── circuit_breaker.sh
│   ├── response_analyzer.sh
│   └── date_utils.sh
├── templates/           # 项目模板
├── tests/               # 测试套件
│   ├── unit/            # 单元测试
│   ├── integration/     # 集成测试
│   ├── e2e/             # 端到端测试
│   └── helpers/         # 测试工具
└── docs/                # 文档
```

---

## 开发工作流程

### 分支命名约定

始终创建功能分支 - 永远不要直接在 `main` 上工作：

| 分支类型 | 格式 | 示例 |
|----------|--------|---------|
| 新功能 | `feature/<feature-name>` | `feature/log-rotation` |
| Bug 修复 | `fix/<issue-name>` | `fix/rate-limit-reset` |
| 文档 | `docs/<doc-update>` | `docs/api-reference` |
| 测试 | `test/<test-area>` | `test/circuit-breaker` |
| 重构 | `refactor/<area>` | `refactor/response-analyzer` |

```bash
# 创建新功能分支
git checkout -b feature/my-awesome-feature
```

### 提交消息格式

我们使用 [Conventional Commits](https://www.conventionalcommits.org/) 来保持清晰、结构化的提交历史：

```
<type>(<scope>): <description>

[可选正文]

[可选页脚]
```

**类型：**

| 类型 | 描述 | 示例 |
|------|-------------|---------|
| `feat` | 新功能 | `feat(loop): add dry-run mode` |
| `fix` | Bug 修复 | `fix(monitor): correct refresh rate` |
| `docs` | 仅文档 | `docs(readme): update installation steps` |
| `test` | 添加/更新测试 | `test(setup): add template validation tests` |
| `refactor` | 代码变更（无功能/修复） | `refactor(analyzer): simplify error detection` |
| `chore` | 维护任务 | `chore(deps): update bats-assert` |

**近期提交示例：**

```bash
# 功能添加
feat(import): add JSON output format support

# 带范围的 Bug 修复
fix(loop): replace non-existent --prompt-file with -p flag

# 文档更新
docs(status): update IMPLEMENTATION_STATUS.md with phased structure

# 测试添加
test(cli): add 27 comprehensive CLI parsing tests
```

**编写好的提交消息：**

- 使用祈使语气（"add" 而不是 "added"）
- 解释 WHAT 改变了和 WHY（而不是 HOW）
- 主题行保持在 72 个字符以内
- 在适用时引用问题（`fixes #123`）

### 工作流程图

```
┌─────────────────────────────────────────────────────────────────────┐
│                    贡献工作流程                                      │
└─────────────────────────────────────────────────────────────────────┘

  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │  1. Fork │────>│ 2. 克隆  │────>│ 3. 分支  │────>│ 4. 编码  │
  └──────────┘     └──────────┘     └──────────┘     └──────────┘
                                                           │
                                                           v
  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ 8. 合并  │<────│  7. PR   │<────│ 6. 推送  │<────│ 5. 测试  │
  └──────────┘     │ 通过     │     └──────────┘     │ (100%)   │
                   └──────────┘                      └──────────┘
                        ^
                        │
                   ┌──────────┐
                   │  CI/CD   │
                   │  通过    │
                   └──────────┘
```

---

## 代码风格指南

### Bash 最佳实践

Ralph 在所有脚本中遵循一致的 bash 约定：

**文件结构：**

```bash
#!/bin/bash
# 脚本描述
# 目的和使用说明

# 引入依赖
source "$(dirname "${BASH_SOURCE[0]}")/lib/date_utils.sh"

# 配置常量（大写）
MAX_CALLS_PER_HOUR=100
CB_NO_PROGRESS_THRESHOLD=3
STATUS_FILE="status.json"

# 输出颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 辅助函数（snake_case）
helper_function() {
    local param1=$1
    local param2=$2
    # 实现
}

# 主逻辑
main() {
    # 入口点
}

# 导出函数供重用
export -f helper_function

# 如果是直接运行则执行 main
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```

**命名约定：**

| 元素 | 约定 | 示例 |
|---------|------------|---------|
| 函数 | snake_case | `get_circuit_state()` |
| 局部变量 | snake_case | `local loop_count=0` |
| 常量 | UPPER_SNAKE_CASE | `MAX_CALLS_PER_HOUR` |
| 文件名 | snake_case.sh | `circuit_breaker.sh` |
| 控制文件 | snake_case.md | `fix_plan.md`, `AGENT.md` |

**函数文档：**

```bash
# 获取当前断路器状态
# 将状态返回为字符串：CLOSED、HALF_OPEN 或 OPEN
# 如果状态文件不存在则回退到 CLOSED
get_circuit_state() {
    if [[ ! -f "$CB_STATE_FILE" ]]; then
        echo "$CB_STATE_CLOSED"
        return
    fi

    jq -r '.state' "$CB_STATE_FILE" 2>/dev/null || echo "$CB_STATE_CLOSED"
}
```

**错误处理：**

```bash
# 始终验证输入
if [[ -z "$1" ]]; then
    echo -e "${RED}错误：缺少必需参数${NC}" >&2
    exit 1
fi

# 使用正确的退出码
# 0 = 成功, 1 = 一般错误, 2 = 无效用法
```

**跨平台兼容性：**

```bash
# 使用可移植的日期命令
if command -v gdate &> /dev/null; then
    DATE_CMD="gdate"  # macOS 使用 coreutils
else
    DATE_CMD="date"   # Linux
fi
```

**JSON 状态管理：**

```bash
# 在解析前始终验证 JSON
if ! jq '.' "$STATE_FILE" > /dev/null 2>&1; then
    echo "错误：状态文件中的 JSON 无效"
    return 1
fi

# 使用 jq 进行安全解析
local state=$(jq -r '.state' "$STATE_FILE" 2>/dev/null || echo "CLOSED")
```

---

## 测试要求

### 强制测试标准

**所有新功能必须包含测试。这是不可协商的。**

| 要求 | 标准 | 执行 |
|-------------|----------|-------------|
| 测试通过率 | 100% | **强制** - CI 阻止合并 |
| 测试覆盖率 | 85% | 期望 - 仅供参考 |

> **关于覆盖率的说明：** Bash 代码覆盖率使用 kcov 无法追踪子进程执行。测试通过率是强制的质量门槛，而不是覆盖率百分比。

### 测试组织

```
tests/
├── unit/                       # 快速、隔离的测试
│   ├── test_cli_parsing.bats   # CLI 参数测试
│   ├── test_json_parsing.bats  # JSON 输出解析
│   ├── test_exit_detection.bats
│   ├── test_rate_limiting.bats
│   ├── test_session_continuity.bats
│   └── test_cli_modern.bats
├── integration/                # 多组件测试
│   ├── test_loop_execution.bats
│   ├── test_edge_cases.bats
│   ├── test_installation.bats
│   ├── test_project_setup.bats
│   └── test_prd_import.bats
├── e2e/                        # 端到端工作流
└── helpers/
    └── test_helper.bash        # 共享测试工具
```

### 运行测试

| 命令 | 目的 | 何时使用 |
|---------|---------|---------|
| `npm test` | 运行所有测试 | 提交前、PR 前 |
| `npm run test:unit` | 仅单元测试 | 开发期间 |
| `npm run test:integration` | 仅集成测试 | 测试交互 |
| `bats tests/unit/test_file.bats` | 单个测试文件 | 调试特定测试 |

### 编写测试

**测试结构：**

```bash
#!/usr/bin/env bats
# 功能 X 的单元测试

load '../helpers/test_helper'

# 在每个测试前运行 setup
setup() {
    source "$(dirname "$BATS_TEST_FILENAME")/../helpers/test_helper.bash"

    # 创建隔离的测试环境
    export TEST_TEMP_DIR="$(mktemp -d /tmp/ralph-test.XXXXXX)"
    cd "$TEST_TEMP_DIR"

    # 初始化测试状态
    echo "0" > ".call_count"
}

# 在每个测试后运行 teardown
teardown() {
    cd /
    rm -rf "$TEST_TEMP_DIR"
}

# 测试：描述性名称说明正在测试的内容
@test "can_make_call 在限制以下时返回成功" {
    echo "50" > ".call_count"
    export MAX_CALLS_PER_HOUR=100

    run can_make_call
    assert_success
}

# 测试：失败情况
@test "can_make_call 在达到限制时返回失败" {
    echo "100" > ".call_count"
    export MAX_CALLS_PER_HOUR=100

    run can_make_call
    assert_failure
}
```

**测试最佳实践：**

1. **测试成功和失败两种情况**
2. **使用描述性的测试名称** 来解释场景
3. **隔离测试** - 每个测试应该是独立的
4. **模拟外部依赖**（Claude CLI、tmux 等）
5. **测试边缘情况**（空文件、无效输入、边界值）
6. **为复杂的测试场景添加注释**

**可用的测试辅助函数：**

```bash
# 来自 tests/helpers/test_helper.bash

assert_success      # 检查命令成功（退出 0）
assert_failure      # 检查命令失败（退出 != 0）
assert_equal        # 比较两个值
assert_output       # 检查命令输出
assert_file_exists  # 验证文件存在
assert_dir_exists   # 验证目录存在
strip_colors        # 移除 ANSI 颜色代码
create_mock_prompt  # 创建测试 PROMPT.md
create_mock_fix_plan # 创建测试 fix_plan.md
create_mock_status  # 创建测试 status.json
```

---

## 拉取请求流程

### 创建 PR 之前

运行以下检查清单：

- [ ] 所有测试在本地通过（`npm test`）
- [ ] 新代码包含适当的测试
- [ ] 提交遵循常规格式
- [ ] 文档已根据需要更新
- [ ] 没有调试代码或 console.log 语句
- [ ] 没有提交密钥或凭证

### 创建 PR

1. **推送您的分支：**
   ```bash
   git push origin feature/my-feature
   ```

2. **在 GitHub 上打开拉取请求**，包含：

**PR 标题：** 遵循常规提交格式
```
feat(loop): add dry-run mode for testing
```

**PR 描述模板：**
```markdown
## 摘要

简要描述此 PR 的作用（1-3 个要点）。

- 添加 dry-run 模式预览循环执行
- 包含新的 CLI 标志 `--dry-run`
- 记录操作而不进行实际更改

## 测试计划

- [ ] 单元测试已添加/更新
- [ ] 集成测试已添加/更新
- [ ] 手动测试已完成

## 相关问题

修复 #123
与 #456 相关

## 截图（如适用）

[为 UI/输出更改添加截图]

## 破坏性变更

[列出任何破坏性变更，或 "无"]
```

### PR 创建之后

1. **等待 CI/CD** - GitHub Actions 将运行所有测试
2. **处理审查反馈** - 及时做出请求的更改
3. **保持 PR 更新** - 如果 main 分支有变更则进行变基

---

## 代码审查指南

### 对于贡献者

**响应反馈：**

- 感谢审查者的时间
- 如果要求不清楚则提问
- 及时做出请求的更改
- 随着更改的发展更新 PR 描述
- 不要对反馈进行个人化理解 - 这是关于代码的

**如果您不同意：**

- 清楚地解释您的理由
- 为您的决策提供上下文
- 对替代方法持开放态度
- 有疑问时听从维护者的判断

### 对于审查者

**检查内容：**

| 区域 | 要问的问题 |
|------|------------------|
| **正确性** | 代码是否做了它声称做的事情？ |
| **测试** | 测试是否全面？它们是否通过？ |
| **风格** | 它是否遵循 bash 约定？ |
| **文档** | 注释和文档是否已更新？ |
| **破坏性变更** | 这会影响现有用户吗？ |
| **性能** | 是否有明显的性能问题？ |

**审查最佳实践：**

1. **建设性** - 关注改进而不是批评
2. **具体** - 尽可能指出确切的行
3. **解释原因** - 帮助贡献者学习
4. **认可好的工作** - 注意写得好的代码
5. **准备就绪时批准** - 不要把 PR 当作人质

---

## 质量标准

### 质量门槛

所有 PR 必须通过以下自动检查：

| 门槛 | 要求 | 执行 |
|------|-------------|-------------|
| 单元测试 | 100% 通过 | **阻止合并** |
| 集成测试 | 100% 通过 | **阻止合并** |
| 覆盖率 | 85% | 仅供参考 |
| 常规提交 | 必需 | 手动审查 |
| 文档 | 已更新 | 手动审查 |

### 文档标准

**何时更新文档：**

- 添加新的 CLI 标志 → 更新 README.md、CLAUDE.md
- 添加新功能 → 更新 README.md "功能" 部分
- 更改行为 → 更新相关文档
- 添加新模式 → 更新 CLAUDE.md

**保持同步：**

1. **CLAUDE.md** - 技术规范、质量标准
2. **README.md** - 面向用户的文档、安装
3. **模板** - 保持模板文件最新
4. **内联注释** - 代码更改时更新

### 功能完成检查清单

在标记任何功能完成之前：

- [ ] 所有测试通过（100% 通过率）
- [ ] 脚本功能经过手动测试
- [ ] 提交遵循常规格式
- [ ] 所有提交推送到远程
- [ ] CI/CD 管道通过
- [ ] CLAUDE.md 已更新（如果是新模式）
- [ ] README.md 已更新（如果是面向用户的）
- [ ] 破坏性变更已记录
- [ ] 安装已验证（如适用）

---

## 社区指南

### 优先贡献领域

**高优先级 - 需要帮助！**

1. **测试实现** - 扩展测试覆盖率
   - 参见 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) 了解规范

2. **功能开发**
   - 日志轮换功能
   - Dry-run 模式
   - 配置文件支持 (.ralphrc)
   - 指标跟踪
   - 桌面通知
   - 备份/回滚系统

3. **文档**
   - 使用教程和示例
   - 故障排除指南
   - 视频演练

4. **真实世界测试**
   - 在您的项目上使用 Ralph
   - 报告错误和边缘情况
   - 分享您的经验

### 沟通

**重大变更之前：**

- 开启问题进行讨论
- 检查现有问题了解计划工作
- 加入拉取请求的讨论

**获取帮助：**

- 首先查看文档（README.md、CLAUDE.md）
- 检查 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) 了解路线图
- 为问题开启问题
- 在讨论中引用相关问题

### 行为准则

- 尊重和职业
- 欢迎新人并帮助他们成功
- 关注建设性反馈
- 假设好意
- 庆祝多元化观点

### 认可

- 所有贡献者在发布说明中被致谢
- 重大贡献在 README 中注明
- 活跃的贡献者可能成为维护者

---

## 额外资源

- [README.md](README.md) - 项目概览和快速入门
- [CLAUDE.md](CLAUDE.md) - 技术规范
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) - 开发路线图
- [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) - 进度跟踪
- [GitHub Issues](https://github.com/frankbria/ralph-claude-code/issues) - 错误报告和功能请求

---

**感谢您为 Ralph 做贡献！** 您的努力帮助让自主 AI 开发对每个人都更易用。