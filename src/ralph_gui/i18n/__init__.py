"""i18n - Internationalization support"""
from .zh_CN import TRANSLATIONS as ZH_TRANSLATIONS
from .en_US import TRANSLATIONS as EN_TRANSLATIONS

# Default to Chinese (Simplified)
TRANSLATIONS = ZH_TRANSLATIONS

def tr(key: str, **kwargs) -> str:
    """Translate a key to the current locale"""
    text = TRANSLATIONS.get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text


def translate_circuit_reason(reason: str) -> str:
    """
    翻译断路器原因字符串为当前语言

    Args:
        reason: 断路器原因字符串（英文）

    Returns:
        翻译后的原因字符串
    """
    # 手动重置
    if reason == "Manual reset":
        return tr("cb_reason_manual_reset")

    # 进度检测恢复
    if reason == "Progress detected, circuit recovered":
        return tr("cb_reason_progress_detected")

    # 卡循环
    if reason == "Stuck loop detected":
        return tr("cb_reason_stuck_loop")

    # 冷却完成
    if reason == "Cooldown complete, attempting recovery":
        return tr("cb_reason_cooldown_complete")

    # 回路已打开
    if reason == "Circuit breaker is open, execution halted":
        return tr("cb_reason_circuit_open")

    # 解析带数字的原因
    import re

    # 无进度检测
    match = re.match(r"No progress detected in (\d+) consecutive loops", reason)
    if match:
        return tr("cb_reason_no_progress", count=int(match.group(1)))

    # 相同错误重复
    match = re.match(r"Same error repeated in (\d+) consecutive loops", reason)
    if match:
        return tr("cb_reason_same_error", count=int(match.group(1)))

    # 相同输出重复
    match = re.match(r"Same output repeated (\d+) times", reason)
    if match:
        return tr("cb_reason_same_output", count=int(match.group(1)))

    # 权限拒绝
    match = re.match(r"Permission denied in (\d+) consecutive loops", reason)
    if match:
        return tr("cb_reason_permission_denied", count=int(match.group(1)))

    # 监控中
    match = re.match(r"Monitoring: (\d+) loops without progress", reason)
    if match:
        return tr("cb_reason_monitoring", count=int(match.group(1)))

    # 恢复失败
    match = re.match(r"No recovery, opening circuit after (\d+) loops", reason)
    if match:
        return tr("cb_reason_recovery_failed", count=int(match.group(1)))

    # 未知原因
    return tr("cb_reason_unknown")
