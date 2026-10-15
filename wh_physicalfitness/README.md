# 运动世界校园 App (v7.3.40) 纯 Python 协议

基于网易易盾 NetSecKit 4.2.4 纯 Python 密码学与极验 v4 (GeeTest v4) 滑块验证码自动化逆向求解实现，脱离 Android App 与 Native SO 依赖。
所有功能模块均独立解耦，终端输入对应参数与凭据（Token/UID）即可独立执行。

---

## 一、环境安装

1. 安装 Python 依赖库：
   ```bash
   pip install -r requirements.txt
   ```
2. 安装 Playwright Chromium 内核（用于无头执行极验滑块渲染与拖拽）：
   ```bash
   playwright install chromium
   ```

---

## 二、独立模块运行指南

### 1. 登录认证换取凭证 (`login_cli.py`)
终端输入账号与密码（明文显示），自动识别并拖动滑块通过验证，输出登录成功/失败响应面板及 Token、UID、UNID：
```bash
python login_cli.py
```

### 2. 学期成绩与完成情况查询 (`score_cli.py`)
输入 Token 与 UID，查询学期总里程、达标状态与各模式完成统计：
```bash
python score_cli.py
```

### 3. 学校跑步规则与电子围栏查询 (`policy_cli.py`)
输入 Token 与 UID，查询单次起跑要求、配速上下限、每日有效打卡时段、人脸抽检区间及电子围栏：
```bash
python policy_cli.py
```

### 4. 历史运动记录查询 (`history_cli.py`)
输入 Token 与 UID，分页查询历史室外跑步或室内锻炼记录：
```bash
python history_cli.py --type outdoor
```

### 5. 校园多维排行榜查询 (`rank_cli.py`)
输入 Token、UID 与 UNID，查询个人日/月榜、班级榜、院系榜、室内榜、历史排名及违规通报：
```bash
python rank_cli.py --type 1 --sort 1
```

### 6. 室外跑步打卡提交 (`run_cli.py`)
输入 Token、UID、UNID 及跑步距离与用时，生成 GPS 点位、分桶速度与 31 字段签名包，上传 11 字段 OBS 轨迹对象后提交保存接口：
```bash
python run_cli.py --type 4 -d 2000 --time 720
```

`--type 1` 为计分跑，需要账号已有学校跑步计划；`--type 4` 为自由跑。

### 7. 室内锻炼打卡提交 (`indoor_cli.py`)
输入 Token、UID、UNID 及锻炼时长与步数，生成 16 字段签名包并提交保存接口：
```bash
python indoor_cli.py --time 1200 --steps 2000
```

---

## 三、模块架构与文件清单

| 文件 | 说明 |
|---|---|
| `login_cli.py` | 登录认证终端工具（账号密码 + 极验滑块求解 -> 输出 Token）。 |
| `score_cli.py` | 学期成绩与完成情况查询工具。 |
| `policy_cli.py` | 学校跑步规则与围栏配置查询工具。 |
| `history_cli.py` | 历史跑步与锻炼记录查询工具。 |
| `rank_cli.py` | 校园排行榜查询工具。 |
| `run_cli.py` | 室外跑步打卡提交工具（生成 GPS 轨迹、31 字段签名并上传 OBS 轨迹对象）。 |
| `indoor_cli.py` | 室内锻炼打卡提交工具（生成 16 字段签名并上传 OBS 步数对象）。 |
| `sport_client.py` | 核心协议请求客户端（统筹所有接口加密发送与响应解密）。 |
| `geetest_solver.py` | 极验 v4 自动化滑块求解器（反爬隐身注入 + OpenCV 边缘模板匹配 + Sigmoid 动力学轨迹）。 |
| `netsec_crypto.py` | NetSecKit 4.2.4 纯 Python 密码学引擎（tokenSign、p=101 加密、0x3b4b8 响应 KDF、v=101 解密）。 |
| `running_protocol.py` | 跑步与锻炼数据结构、GPS 轨迹生成与加盐签名计算器。 |
| `rank_protocol.py` | 排行榜协议请求构造器。 |
| `requirements.txt` | Python 运行依赖清单。 |
