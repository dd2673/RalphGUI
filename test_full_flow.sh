#!/bin/bash
# Ralph GUI 完整流程测试脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RALPH_GUI_DIR="$SCRIPT_DIR"

echo "========================================"
echo "Ralph GUI 完整流程测试"
echo "========================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }
info() { echo -e "${YELLOW}[INFO]${NC} $1"; }

cd "$RALPH_GUI_DIR"

# ========================================
# Step 1: 检查Python环境
# ========================================
echo ""
echo "========================================"
echo "Step 1: 检查Python环境"
echo "========================================"

if command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version 2>&1)
    pass "Python: $PYTHON_VERSION"
else
    fail "Python 未安装"
    exit 1
fi

# ========================================
# Step 2: 安装依赖
# ========================================
echo ""
echo "========================================"
echo "Step 2: 安装依赖"
echo "========================================"

info "安装Ralph GUI包（开发模式）..."
pip install -e ".[dev]" -q

info "验证PySide6安装..."
python -c "from PySide6.QtCore import QVersionNumber; print('PySide6 OK')" 2>/dev/null
if [ $? -eq 0 ]; then
    pass "PySide6 安装成功"
else
    fail "PySide6 安装失败"
    exit 1
fi

info "验证pytest安装..."
python -c "import pytest; print(f'pytest {pytest.__version__}')" 2>/dev/null
if [ $? -eq 0 ]; then
    pass "pytest 安装成功"
else
    fail "pytest 安装失败"
    exit 1
fi

# ========================================
# Step 3: 单元测试
# ========================================
echo ""
echo "========================================"
echo "Step 3: 单元测试"
echo "========================================"

info "运行pytest测试..."
cd "$RALPH_GUI_DIR"
PYTHONPATH="$(pwd)/src" python -m pytest tests/ -v --tb=short

if [ $? -eq 0 ]; then
    pass "所有单元测试通过"
else
    fail "单元测试失败"
    exit 1
fi

# ========================================
# Step 4: 导入验证
# ========================================
echo ""
echo "========================================"
echo "Step 4: 导入验证"
echo "========================================"

info "验证所有模块可导入..."

python -c "
from src.ralph_gui.models import CircuitBreakerModel, LoopStateModel, Project, RateLimitModel, SessionModel
from src.ralph_gui.services import CLIService, StateService, ConfigService, LogService
from src.ralph_gui.presenters import StartupPresenter, DashboardPresenter, LoopPresenter, SettingsPresenter
from src.ralph_gui.i18n import TRANSLATIONS
print('所有模块导入成功')
"

if [ $? -eq 0 ]; then
    pass "所有模块导入验证通过"
else
    fail "模块导入验证失败"
    exit 1
fi

# ========================================
# Step 5: 模型单元测试
# ========================================
echo ""
echo "========================================"
echo "Step 5: 模型单元测试"
echo "========================================"

info "测试CircuitBreakerModel状态转换..."
python -c "
from src.ralph_gui.models.circuit_breaker import CircuitBreakerModel, CircuitBreakerState
model = CircuitBreakerModel()
assert model.state == CircuitBreakerState.CLOSED
model.record_no_progress(1)
model.record_no_progress(2)
model.record_no_progress(3)
assert model.state == CircuitBreakerState.OPEN
print('CircuitBreakerModel 测试通过')
"

if [ $? -eq 0 ]; then
    pass "CircuitBreakerModel 状态转换测试通过"
else
    fail "CircuitBreakerModel 测试失败"
    exit 1
fi

info "测试LoopStateModel..."
python -c "
from src.ralph_gui.models.loop_state import LoopStateModel
model = LoopStateModel()
assert model.status == 'stopped'
assert model.loop_count == 0
model.increment_loop()
assert model.loop_count == 1
model.increment_calls(tokens=500)
assert model.tokens_used_this_hour == 500
print('LoopStateModel 测试通过')
"

if [ $? -eq 0 ]; then
    pass "LoopStateModel 测试通过"
else
    fail "LoopStateModel 测试失败"
    exit 1
fi

info "测试RateLimitModel..."
python -c "
from src.ralph_gui.models.rate_limit import RateLimitModel
model = RateLimitModel()
assert model.calls_remaining == 100  # 默认100次/小时
model.increment()
assert model.calls_remaining == 99
assert model.can_make_call() == True
# 测试无限制
model.max_calls_per_hour = 0
assert model.calls_remaining == -1
print('RateLimitModel 测试通过')
"

if [ $? -eq 0 ]; then
    pass "RateLimitModel 测试通过"
else
    fail "RateLimitModel 测试失败"
    exit 1
fi

info "测试SessionModel..."
python -c "
from src.ralph_gui.models.session import SessionModel
model = SessionModel()
assert model.is_expired() == True
model.set_session_id('test_123')
assert model.is_expired() == False
assert model.session_id == 'test_123'
print('SessionModel 测试通过')
"

if [ $? -eq 0 ]; then
    pass "SessionModel 测试通过"
else
    fail "SessionModel 测试失败"
    exit 1
fi

# ========================================
# Step 6: 服务测试
# ========================================
echo ""
echo "========================================"
echo "Step 6: 服务测试"
echo "========================================"

info "测试ConfigService..."
python -c "
from src.ralph_gui.services.config_service import ConfigService
from pathlib import Path
import tempfile
with tempfile.TemporaryDirectory() as tmpdir:
    config_file = Path(tmpdir) / '.ralphrc'
    service = ConfigService(config_file)
    service.set('MAX_CALLS_PER_HOUR', 200)
    service.save(service.as_dict())
    # 重新加载
    new_service = ConfigService(config_file)
    new_service.load()
    assert new_service.get('MAX_CALLS_PER_HOUR') == 200
print('ConfigService 测试通过')
"

if [ $? -eq 0 ]; then
    pass "ConfigService 测试通过"
else
    fail "ConfigService 测试失败"
    exit 1
fi

info "测试StateService..."
python -c "
from src.ralph_gui.services.state_service import StateService
from pathlib import Path
import tempfile
with tempfile.TemporaryDirectory() as tmpdir:
    # 创建模拟项目
    ralph_dir = Path(tmpdir) / '.ralph'
    ralph_dir.mkdir()
    (ralph_dir / 'PROMPT.md').write_text('# Test')
    (ralph_dir / 'fix_plan.md').write_text('- [ ] Test')
    (ralph_dir / 'AGENT.md').write_text('# Agent')
    service = StateService(Path(tmpdir))
    assert service.is_ralph_enabled() == True
print('StateService 测试通过')
"

if [ $? -eq 0 ]; then
    pass "StateService 测试通过"
else
    fail "StateService 测试失败"
    exit 1
fi

# ========================================
# Step 7: 翻译验证
# ========================================
echo ""
echo "========================================"
echo "Step 7: 翻译验证"
echo "========================================"

info "验证中文翻译完整性..."
python -c "
from src.ralph_gui.i18n import TRANSLATIONS
essential_keys = [
    'app_title', 'select_project_directory', 'start', 'stop', 'pause',
    'circuit_breaker', 'loop_count', 'api_calls', 'logs', 'settings'
]
for key in essential_keys:
    assert key in TRANSLATIONS, f'Missing key: {key}'
    assert TRANSLATIONS[key], f'Empty value for key: {key}'
print(f'翻译完整性验证通过 ({len(TRANSLATIONS)} keys)')
"

if [ $? -eq 0 ]; then
    pass "翻译完整性验证通过"
else
    fail "翻译验证失败"
    exit 1
fi

# ========================================
# Step 8: GUI组件验证
# ========================================
echo ""
echo "========================================"
echo "Step 8: GUI组件验证"
echo "========================================"

info "验证GUI组件可实例化..."
python -c "
import sys
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

from src.ralph_gui.views.startup_dialog import StartupDialog
from src.ralph_gui.views.dashboard import Dashboard
from src.ralph_gui.views.circuit_status import CircuitStatusCard
from src.ralph_gui.views.loop_controls import LoopControls
from src.ralph_gui.views.log_viewer import LogViewer

# 测试实例化
dialog = StartupDialog()
dashboard = Dashboard()
circuit = CircuitStatusCard()
controls = LoopControls()
viewer = LogViewer()

print('所有GUI组件实例化成功')
"

if [ $? -eq 0 ]; then
    pass "GUI组件实例化验证通过"
else
    fail "GUI组件实例化失败"
    exit 1
fi

# ========================================
# Step 9: CLI命令验证
# ========================================
echo ""
echo "========================================"
echo "Step 9: CLI命令验证"
echo "========================================"

info "检查Ralph CLI工具..."
python -c "
from src.ralph_gui.services.cli_service import CLIService
service = CLIService()
print(f'Ralph home: {service.ralph_home}')
print(f'RALPH available: {service.is_ralph_available()}')
"

if [ $? -eq 0 ]; then
    pass "CLI服务验证通过"
else
    info "CLI服务验证跳过（可能没有安装Ralph）"
fi

# ========================================
# 测试完成
# ========================================
echo ""
echo "========================================"
echo -e "${GREEN}所有测试通过！${NC}"
echo "========================================"
echo ""
echo "Ralph GUI 项目验证完成。"
echo ""
echo "下一步："
echo "  1. 运行GUI: python src/ralph_gui/main.py"
echo "  2. 运行pytest: pytest tests/"
echo "  3. 打包: build.bat"
echo ""
