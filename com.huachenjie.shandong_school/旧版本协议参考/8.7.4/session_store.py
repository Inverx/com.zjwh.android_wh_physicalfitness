"""本地会话持久化存储模块。负责保存与读取 Token 和设备指纹。"""
import json
import os
from typing import Dict, Any, Optional

SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session.json")

def load_session() -> Dict[str, Any]:
    """读取本地会话配置。优先读取当前目录，回退读取 8.7.2 目录。"""
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    fallback_872 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "8.7.2", "session.json")
    if os.path.exists(fallback_872):
        try:
            with open(fallback_872, "r", encoding="utf-8") as f:
                data = json.load(f)
                save_session(data)
                return data
        except Exception:
            pass
    return {}

def save_session(session_data: Dict[str, Any]) -> None:
    """保存当前会话到本地 session.json。"""
    try:
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def clear_session() -> None:
    """清除本地保存的会话文件。"""
    if os.path.exists(SESSION_FILE):
        try:
            os.remove(SESSION_FILE)
        except Exception:
            pass
