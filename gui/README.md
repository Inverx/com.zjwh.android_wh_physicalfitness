# whsport GUI（EUI-NEO）

跨三平台（Windows / Linux / macOS）桌面前端。**UI 用 EUI-NEO（C++17），业务逻辑仍走 Python 引擎**，
两者通过 stdin/stdout 上的 **JSON-RPC** 通信（见 `../src/whsport/rpc.py`）。

```text
┌────────────────────────┐   一行一个 JSON     ┌──────────────────────────┐
│ whsport_gui (EUI-NEO)  │ ─────────────────▶ │ whsport-engine (Python)   │
│  登录 / 跑步 / 查询      │ ◀───────────────── │  协议/加密/轨迹生成        │
└────────────────────────┘                    └──────────────────────────┘
```

## 为什么这样分层

- 协议、加密、极验、轨迹生成等复杂逻辑已经稳定在 Python，**不重写**
- C++ 侧只做 UI，天然获得 EUI-NEO 的 **HiDPI + 自定义字体**（Tkinter 的两个硬伤）
- 引擎可被 **PyInstaller 冻结成单文件**，随 GUI 一起分发

## 引擎定位顺序

1. 环境变量 `WHS_ENGINE` → 直接当可执行文件启动（`whsport-engine rpc`）
2. 环境变量 `WHS_PYTHON` → 用该解释器跑 `-m whsport rpc`
3. 依次尝试 `whsport-engine`（冻结产物）、`python3`

### 本地调试（不打包，直接用 uv 跑引擎）

```bash
# 终端 A：启动引擎（uv 环境）
uv run python -m whsport rpc

# 终端 B：让 GUI 用 uv 的解释器启动引擎
WHS_PYTHON="$(uv run python -c 'import sys;print(sys.executable)')" ./build/whsport_gui
```

## 构建

需要 CMake ≥ 3.16、C++17 编译器；依赖（EUI-NEO、nlohmann/json）由 `FetchContent` 自动拉取。

```bash
cd gui
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
```

### 平台系统依赖

| 平台 | 需要 |
| --- | --- |
| Linux | `xorg-dev libgl1-mesa-dev libglu1-mesa-dev libwayland-dev libxkbcommon-dev`（托盘还需 GLib/GIO） |
| macOS | `brew install glfw` |
| Windows | MSVC 2019+ / MinGW-w64；用 vcpkg 或 CMake 自动拉取依赖 |

### 用已安装的 EUI-NEO SDK（可选）

```bash
cmake -S . -B build -DEUI_NEO_SDK=/path/to/eui-neo-sdk
```

### UniDesktop（UDA，可选）

`-DWITH_UDA=ON`（默认）会在 **Windows/Linux** 上用 cargo 构建 `libuda_ffi`，用于系统通知/托盘/跟随主题。
**macOS 自动关闭**（UDA 目前只覆盖 Win/Linux），此时退回 EUI-NEO 自带平台能力。

## 打包

```bash
# 1) 冻结 Python 引擎
cd ../packaging
uv pip install pyinstaller
uv run pyinstaller --noconfirm whsport-engine.spec   # → dist/whsport-engine

# 2) 构建 GUI（见上），然后把 dist/whsport-engine 放到 GUI 可执行文件旁边，
#    或设置 WHS_ENGINE=/abs/path/whsport-engine
```

三平台 CI（`.github/workflows/build.yml`）会分别产出 `whsport-engine` 与 `whsport_gui`。

## 安全默认

- 「**① 预览**」是纯本地生成，**不联网、不提交**
- 「**② 提交**」才会真正发服务器，且按钮在忙碌时禁用
- 开发/联调期间请只用预览
