# Ralph 开发指令

## 背景
你是 Ralph，正在使用 Node.js 构建一个命令行待办事项应用。这是一个个人生产力工具，在本地存储任务，并提供简单的命令来管理任务。

## 当前目标
1. 创建一个支持 add、list、complete 和 delete 命令的 CLI
2. 使用 ~/.todos.json 存储待办事项，自动创建文件
3. 为所有操作提供清晰、有用的输出
4. 优雅地处理错误，提供可操作的错误消息

## 技术栈
- Node.js 18+
- commander.js 用于 CLI 参数解析
- Native fs/promises 用于文件操作
- Jest 用于测试

## 核心原则
- 单一职责：每个命令做好一件事
- 优雅失败：文件不存在 = 返回空列表，而不是报错
- 清晰的输出：用户应始终知道发生了什么
- 可测试：核心逻辑与 CLI 层分离

## 命令规格

### `todo add "任务描述"`
- 添加新任务，ID 自动递增
- 输出："Added task #3: Buy groceries"（已添加任务 #3：购买杂货）

### `todo list`
- 显示所有任务及其状态标识
- [ ] 表示待办，[x] 表示已完成
- 空时输出："No tasks yet"（暂无任务）

### `todo complete <id>`
- 标记任务为已完成
- 如果 ID 不存在则报错

### `todo delete <id>`
- 永久删除任务
- 如果 ID 不存在则报错

## 数据格式
```json
{
  "nextId": 4,
  "tasks": [
    {"id": 1, "text": "购买杂货", "completed": false},
    {"id": 2, "text": "打电话给妈妈", "completed": true}
  ]
}
```

## 质量标准
- 所有命令都有 --help 文档
- 存储模块的单元测试
- CLI 命令的集成测试
