"""PyInstaller 入口：把 Python 引擎冻结成单文件可执行程序（whsport-engine）。

构建：
    uv sync
    uv pip install pyinstaller
    pyinstaller packaging/whsport-engine.spec
产物：dist/whsport-engine(.exe) —— GUI 通过 `WHS_ENGINE` 指向它。
"""

from whsport.rpc import main

if __name__ == "__main__":
    raise SystemExit(main())
