# Ralph GUI 测试指南

**框架**: pytest | **覆盖率**: 100% 核心模块

---

## 快速开始

### 先决条件

```bash
python --version  # Python 3.10+
pip --version
```

### 安装依赖

```bash
pip install -r requirements.txt
pip install pytest pytest-cov
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定目录
pytest tests/test_models/

# 带覆盖率运行
pytest --cov=src/ralph_gui --cov-report=html
```

---

## 测试组织

```
tests/
├── test_models/           # 模型单元测试
├── test_services/        # 服务单元测试
├── test_presenters/      # Presenter 单元测试
├── test_lib/            # 库模块测试
└── test_scripts/        # 脚本集成测试
```

---

## 编写测试

### 测试结构

```python
import pytest
from src.ralph_gui.models import CircuitBreakerModel

class TestCircuitBreakerModel:
    """CircuitBreakerModel 的测试。"""

    def test_initial_state_is_closed(self):
        """断路器从 CLOSED 状态开始。"""
        cb = CircuitBreakerModel()
        assert cb.state == "CLOSED"

    def test_transition_to_open(self):
        """断路器在出错时转换为 OPEN。"""
        cb = CircuitBreakerModel()
        cb.record_error("测试错误")
        assert cb.state == "OPEN"
```

### Fixtures

```python
import pytest
from pathlib import Path
import tempfile
import shutil

@pytest.fixture
def temp_project_dir():
    """创建临时项目目录。"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)

@pytest.fixture
def sample_status_json(temp_project_dir):
    """创建示例 status.json。"""
    status_file = temp_project_dir / ".ralph" / "status.json"
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text('{"loop_number": 1}')
    return status_file
```

---

## Mocking

### Mocking CLI 调用

```python
from unittest.mock import Mock, patch

def test_start_loop_cli_call(temp_project_dir):
    """测试 start_loop 调用 Claude Code CLI。"""
    with patch('subprocess.Popen') as mock_popen:
        mock_popen.return_value.stdout.readline.return_value = b""
        # ... 测试逻辑
```

---

## 覆盖率要求

| 模块 | 目标 |
|--------|--------|
| 模型 | 100% |
| 服务 | 100% |
| Presenters | 100% |
| 库 | 100% |

---

## CI/CD

测试在以下情况自动运行：
- 推送到 main/develop
- 拉取请求

---

**最后更新**: 2026-04-03