# 运动世界校园 App (v7.3.90) 纯 Python 协议

基于网易易盾 NetSecKit 4.2.4 纯 Python 密码学与极验 v4 (GeeTest v4) 滑块验证码自动化逆向求解实现，脱离 Android App 与 Native SO 依赖。

> 本仓库统一用 **uv** 管理依赖与环境。下文所有命令都通过 `uv run` 执行，
> 不需要手动激活虚拟环境。
>
> 免责声明：本项目仅供学习与协议研究，请勿用于任何违反学校规定或法律法规的用途。

---

## 一、环境安装

```bash
# 1) 安装/同步依赖（读取 pyproject.toml + uv.lock）
uv sync

# 2) 安装 Playwright Chromium 内核（极验滑块渲染用；也可用系统浏览器，见下）
uv run playwright install chromium
```

> 系统已装 Chromium 时无需第 2 步，设 `GEETEST_CHROMIUM_EXECUTABLE=/usr/bin/chromium`
> （或 `PLAYWRIGHT_CHROMIUM_EXECUTABLE`）即可。

---

## 二、运行方式

统一入口：

```bash
uv run python -m whsport <命令> [参数]
uv run python -m whsport          # 查看全部命令
```

或用安装后的独立命令（`uv sync` 后可用，等价写法加 `uv run` 前缀）：

| 命令 | 等价 |
| --- | --- |
| `uv run wh-login` | `uv run python -m whsport login` |
| `uv run wh-run` | `uv run python -m whsport run` |
| `uv run wh-indoor` | `uv run python -m whsport indoor` |
| `uv run wh-score` | `uv run python -m whsport score` |
| `uv run wh-policy` | `uv run python -m whsport policy` |
| `uv run wh-history` | `uv run python -m whsport history` |
| `uv run wh-rank` | `uv run python -m whsport rank` |
| `uv run wh-rpc` | `uv run python -m whsport rpc` |

### 登录并保存凭据

登录成功会把 Token/UID/UNID 保存到 `~/.config/zjwh_sport/credentials.json`（权限 0600），
之后所有命令**无需再传 `-t/-u`**：

```bash
uv run python -m whsport login
```

### 查询类

```bash
uv run python -m whsport score                 # 学期成绩
uv run python -m whsport policy -m 1           # 计分跑规则与围栏
uv run python -m whsport history --type outdoor
uv run python -m whsport rank --type 1 --sort 1
```

### 提交跑步记录

```bash
# 自由跑：--type 4
uv run python -m whsport run --type 4 -d 2000 --time 720

# 计分跑：--type 1（需账号有学校跑步计划）
#   会自动拉取学校下发的打卡点，生成穿点轨迹并按顺序经过
uv run python -m whsport run --type 1 -d 2000 --time 830 --steps 1100 --weight 62 \
    --latitude <纬度> --longitude <经度>

# 本地生成+校验、不上传：
uv run python -m whsport run --type 1 -d 2000 --time 830 --latitude <纬度> --longitude <经度> --dry-run
```

### 室内锻炼

```bash
uv run python -m whsport indoor --time 1200 --steps 2000
```

### 图形界面（EUI-NEO，跨三平台）

GUI 在 `gui/`：**UI 用 EUI-NEO（C++17），业务逻辑仍走 Python 引擎**，两者用 JSON-RPC 通信。
构建与打包见 [`gui/README.md`](gui/README.md)。

```bash
# 引擎（可与 GUI 分开跑，供调试）
uv run python -m whsport rpc

# GUI
cd gui && cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --parallel
```

---

## 三、目录结构

```text
.
├── src/whsport/                # Python 引擎（协议/加密/轨迹）
│   ├── __main__.py             # 统一入口 python -m whsport
│   ├── rpc.py                  # JSON-RPC 接口（供 GUI 调用）
│   ├── coordinate_utils.py  security_utils.py  credentials.py
│   ├── netsec_crypto.py        # NetSecKit 4.2.4 密码学引擎
│   ├── geetest_solver.py       # 极验 v4 滑块求解器
│   ├── rank_protocol.py  running_protocol.py
│   ├── sport_client.py         # 核心请求客户端
│   └── cli/                    # 各命令行入口
├── gui/                        # EUI-NEO C++ 前端 + CMake
├── packaging/                  # PyInstaller 冻结脚本
├── tests/                      # 单元测试
├── legacy/credit_run.py        # 已废弃，请改用 run
├── pyproject.toml  uv.lock
└── README.md
```

### 模块职责

| 模块 | 说明 |
| --- | --- |
| `sport_client.py` | 核心协议请求客户端（统筹所有接口加密发送与响应解密） |
| `geetest_solver.py` | 极验 v4 自动化滑块求解器（反爬隐身注入 + OpenCV 边缘模板匹配 + Sigmoid 动力学轨迹） |
| `netsec_crypto.py` | NetSecKit 4.2.4 纯 Python 密码学引擎（tokenSign、p=101 加密、响应 KDF、v=101 解密） |
| `running_protocol.py` | 跑步与锻炼数据结构、GPS 轨迹生成与加盐签名计算器 |
| `rank_protocol.py` | 排行榜协议请求构造器 |
| `credentials.py` | 登录凭据本地存储（登录保存、其余命令自动读取） |
| `rpc.py` | 机器可读的 JSON-RPC 引擎接口（GUI 的调用面） |

---

## 四、测试

```bash
uv run python -m unittest discover -s tests
# 或： uv run python -m pytest tests
```
