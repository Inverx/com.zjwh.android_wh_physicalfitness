# 运动世界校园 App (v7.3.90) 纯 Python 协议

基于网易易盾 NetSecKit 4.2.4 纯 Python 密码学与极验 v4 (GeeTest v4) 滑块验证码自动化逆向求解实现，脱离 Android App 与 Native SO 依赖。
所有功能模块均独立解耦，终端输入对应参数与凭据（Token/UID）即可独立执行。

> 免责声明：本项目仅供学习与协议研究，请勿用于任何违反学校规定或法律法规的用途。

---

## 一、环境安装

```bash
# 1) 安装依赖
uv sync                     # 推荐（读取 pyproject.toml / uv.lock）
# 或： pip install -r requirements.txt

# 2) 安装 Playwright Chromium 内核（用于极验滑块渲染与拖拽）
playwright install chromium
```

> 也支持系统已装的 Chromium：设置 `GEETEST_CHROMIUM_EXECUTABLE=/usr/bin/chromium`
> （或 `PLAYWRIGHT_CHROMIUM_EXECUTABLE`）即可，无需 `playwright install`。

---

## 二、运行方式

推荐用统一入口：

```bash
python -m whsport <命令> [参数]
python -m whsport            # 查看全部命令
```

或使用安装后的独立命令（`uv sync` 后可用）：

| 命令 | 等价 |
|---|---|
| `wh-login`   | `python -m whsport login` |
| `wh-run`     | `python -m whsport run` |
| `wh-indoor`  | `python -m whsport indoor` |
| `wh-score`   | `python -m whsport score` |
| `wh-policy`  | `python -m whsport policy` |
| `wh-history` | `python -m whsport history` |
| `wh-rank`    | `python -m whsport rank` |
| `wh-gui`     | `python -m whsport gui` |

### 图形界面（最轻便，零额外依赖）

用 Python 标准库 Tkinter，不需要安装任何新依赖：

```bash
python -m whsport gui      # 或 wh-gui
```

界面分「跑步 / 查询」两页：
- **跑步**：登录、填写参数，点「**① 预览（本地 dry-run）**」会在本地生成轨迹并画出来（**不联网、不提交**），
  确认无误后再点「**② 提交到服务器**」（会二次确认）；
- **查询**：一键查学期成绩 / 规则 / 历史 / 排行榜。

> 安全默认：预览纯本地；提交必须先在预览页生成、并弹窗二次确认。

### 登录并保存凭据

登录成功会把 Token/UID/UNID 保存到 `~/.config/zjwh_sport/credentials.json`（权限 0600），
之后所有命令**无需再传 `-t/-u`**：

```bash
python -m whsport login
```

### 查询类

```bash
python -m whsport score                 # 学期成绩
python -m whsport policy -m 1           # 计分跑规则与围栏
python -m whsport history --type outdoor
python -m whsport rank --type 1 --sort 1
```

### 提交跑步记录

```bash
# 自由跑：--type 4
python -m whsport run --type 4 -d 2000 --time 720

# 计分跑：--type 1（需账号有学校跑步计划）
#   会自动拉取学校下发的打卡点，生成穿点轨迹并通过点位
python -m whsport run --type 1 -d 2000 --time 830 --steps 1100 --weight 62 \
    --latitude <纬度> --longitude <经度>

# 本地生成+校验、不上传：
python -m whsport run --type 1 -d 2000 --time 830 --latitude <纬度> --longitude <经度> --dry-run
```

### 室内锻炼

```bash
python -m whsport indoor --time 1200 --steps 2000
```

---

## 三、目录结构

```
.
├── src/whsport/
│   ├── __init__.py
│   ├── __main__.py            # 统一入口 python -m whsport
│   ├── coordinate_utils.py    # 经纬度校验与坐标值对象
│   ├── security_utils.py      # 日志脱敏
│   ├── credentials.py         # 本地凭据存储
│   ├── netsec_crypto.py       # NetSecKit 4.2.4 密码学引擎
│   ├── geetest_solver.py      # 极验 v4 滑块求解器
│   ├── rank_protocol.py       # 排行榜协议构造
│   ├── running_protocol.py    # 跑步/锻炼数据结构、轨迹生成、签名
│   ├── sport_client.py        # 核心请求客户端
│   └── cli/                   # 各命令行入口
│       ├── login_cli.py  run_cli.py   indoor_cli.py
│       ├── score_cli.py  policy_cli.py
│       └── history_cli.py rank_cli.py
├── tests/
│   └── test_coordinate_consistency.py
├── legacy/
│   └── credit_run.py          # 已废弃，请改用 run_cli
├── pyproject.toml
├── requirements.txt
└── README.md
```

### 模块职责

| 模块 | 说明 |
|---|---|
| `sport_client.py` | 核心协议请求客户端（统筹所有接口加密发送与响应解密） |
| `geetest_solver.py` | 极验 v4 自动化滑块求解器（反爬隐身注入 + OpenCV 边缘模板匹配 + Sigmoid 动力学轨迹） |
| `netsec_crypto.py` | NetSecKit 4.2.4 纯 Python 密码学引擎（tokenSign、p=101 加密、响应 KDF、v=101 解密） |
| `running_protocol.py` | 跑步与锻炼数据结构、GPS 轨迹生成与加盐签名计算器 |
| `rank_protocol.py` | 排行榜协议请求构造器 |
| `credentials.py` | 登录凭据本地存储（登录保存、其余命令自动读取） |

---

## 四、测试

```bash
python -m unittest discover -s tests
# 或： uv run python -m unittest discover -s tests
```
