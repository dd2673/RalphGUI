# Ralph GUI 产品需求文档示例

本文档展示如何使用 Ralph GUI 配合 Ralph CLI 进行项目开发。

## 示例项目概述

构建一个简单的命令行 TODO 应用程序。

## 技术栈

- Python 3.10+
- 纯 Python 实现，无需外部依赖
- JSON 文件存储

## 开发步骤

### 1. 创建项目目录

```bash
mkdir todo-cli
cd todo-cli
git init
```

### 2. 使用 Ralph GUI 初始化项目

1. 启动 Ralph GUI
2. 选择 todo-cli 目录
3. 点击「初始化」

这将创建：
- `.ralph/` 目录结构
- `PROMPT.md`
- `fix_plan.md`
- `.ralphrc`

### 3. 编辑 PROMPT.md

```markdown
# Ralph 开发指令

## 上下文
您是 Ralph，正在构建一个 CLI TODO 应用程序。

## 技术栈
- Python 3.10+
- 纯标准库
- JSON 文件存储 (~/.todos.json)

## 关键原则
- 简单易用的命令行界面
- 清晰的错误消息
- 遵循 Unix 哲学
```

### 4. 编辑 fix_plan.md

```markdown
# 修复计划 - TODO CLI

## 优先级 1: 基础
- [ ] 创建主入口点 todo.py
- [ ] 实现 add 命令
- [ ] 实现 list 命令
- [ ] 实现 done 命令

## 优先级 2: 完善
- [ ] 添加 help 输出
- [ ] 添加错误处理
```

### 5. 在 Ralph GUI 中启动循环

1. 确保已选择 todo-cli 项目
2. 点击「启动」按钮
3. Ralph 将按顺序完成任务

### 6. 查看结果

```bash
python todo.py add "Buy groceries"
python todo.py list
python todo.py done 1
```

---

## 使用 Ralph GUI 的优势

| 优势 | 说明 |
|------|------|
| 可视化状态 | 实时显示断路器状态和调用计数 |
| 便捷控制 | 启动/暂停/停止按钮 |
| 日志监控 | 实时查看执行日志 |
| 跨平台一致 | 统一的用户界面 |
