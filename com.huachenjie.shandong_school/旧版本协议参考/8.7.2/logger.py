"""日志输出组件。中文、短句、无装饰、状态优先、结果字段化、失败展开细节。"""
import json
import sys
from typing import Any

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def log_status(action: str, ok: bool = True, status_text: str = None) -> None:
    text = status_text if status_text else ("成功" if ok else "失败")
    print(f"[状态] {action} ... {text}")

def log_fields(**kwargs) -> None:
    items = []
    for k, v in kwargs.items():
        if v is None:
            v = "无"
        elif isinstance(v, bool):
            v = "是" if v else "否"
        items.append(f"{k}={v}")
    if items:
        print(f"[字段] {' '.join(items)}")

def log_error(message: str) -> None:
    print(f"[错误] {message}")

def log_detail(detail: Any) -> None:
    if isinstance(detail, (dict, list)):
        text = json.dumps(detail, ensure_ascii=False, indent=2)
    else:
        text = str(detail)
    print(f"[细节] {text}")
