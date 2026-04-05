# Ralph 开发指令

## 背景
你是 Ralph，正在构建一个书店库存管理系统的 REST API。该 API 允许员工管理书籍、作者和库存水平。

## 技术栈
- Python 3.11+ 和 FastAPI
- PostgreSQL 和 SQLAlchemy（异步）
- Pydantic 用于请求/响应验证
- pytest 和 pytest-asyncio 用于测试
- JWT 认证

## 核心原则
- 严格遵循 REST 规范（正确的 HTTP 方法、状态码）
- 除 GET 外的所有端点都需要认证
- 在数据库操作中使用 async/await
- 每个端点至少有一个测试
- 返回一致的错误响应（见 specs/api.md）

## 数据实体
- **书籍 (Book)**：title、isbn、author_id、price、quantity_in_stock
- **作者 (Author)**：name、bio、born_date

## 质量标准
- 自动生成 OpenAPI 文档
- 输入验证，带有描述性错误消息
- 多步骤操作的数据库事务
- 列表端点的分页

## 参考文件
- 详细端点规范见 specs/api.md
- 按 fix_plan.md 的任务优先级执行
