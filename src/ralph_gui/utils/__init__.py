"""JSON辅助函数"""
import json
from pathlib import Path
from typing import Any, Dict, Optional

def read_json(file_path: Path) -> Optional[Dict[str, Any]]:
    """读取JSON文件"""
    try:
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return None

def write_json(file_path: Path, data: Dict[str, Any]) -> bool:
    """写入JSON文件"""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except (IOError, json.JSONDecodeError):
        return False

def update_json(file_path: Path, updates: Dict[str, Any]) -> bool:
    """更新JSON文件（保留现有数据）"""
    data = read_json(file_path) or {}
    data.update(updates)
    return write_json(file_path, data)
