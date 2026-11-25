# 运动世界校园 7.3.92 纯协议套件 (SportShield Protocol Suite)

> **版本**：v7.3.92 (versionCode 406)  
> **抓包来源**：`xadsmartget.adgain.cn_2026_10_14_23_26_10.har` (登录-跑步) 与 `s.adxvip.com_2026_10_15_09_42_15.har` (已登录打开应用-跑步)  
> **协议加解密**：NetSecKit 4.2.4 (纯 Python 标准库自研实现，AES-128-CBC + Feistel KDF + RSA PKCS#1 v1.5)

---

## 模块化架构

```text
D:/Work/运动世界/协议/7.3.92/
├── core/                    # 通用网络与加密基类 (NetSecKit, tokenSign, BaseClient)
├── login/                   # 登录与极验 v4 滑块求解套件
├── profile/                 # 个人档案与服务器 GMT 时间对齐套件
├── policy/                  # 跑步规则与校区电子围栏/打卡点套件
├── telemetry/               # 启动埋点与页面曝光特征模拟套件 (防风控)
├── running/                 # 运动轨迹合成、华为云 OBS 异步推送与结算上报套件
├── history/                 # 跑后单次记录回查与打卡日历套件
├── sport_client.py          # 统一主客户端门面 (SportClient792)
├── cli.py                   # 统一主入口命令行终端工具
└── README.md                # 协议套件全景文档
```

---

## 真实全链路业务时序与防风控规约

根据 7.3.92 真实抓包，全流程生命周期包含以下 5 个关键阶段：

### 1. 冷启动与时间对齐 (Cold Start & Time Sync)
- `GET /api/v3/getserver/gmttime`：获取服务端绝对时间戳，校准本地时钟偏斜；
- `POST /api/v76/startup/pv`：上报冷启动特征（包含 `caid: 2023`, `appVersion: 7.3.92`, `deviceId` 等）；
- `GET /api/v70390/user/info`：拉取学生详细身份档案。

### 2. 规则与围栏预拉取 (Pre-flight Rules & Geofence)
- `POST /api/v77/home/page`：加载首页看板布局；
- `POST /api/v41/running/getPersonalSemesterInfo`：获取学期累计里程与目标；
- `POST /api/v1/getGeoFenceForRun`：获取校区电子围栏多边形与必经打卡点；
- `POST /api/v70103/runModePolicy`：获取配速、步频阈值与有效时段；
- `POST /api/v76/datacollection/pv`：上报页面曝光（`My_page_exposure` 等）。

### 3. 物理静默期 (Physical Running)
- 实机抓包表明：在 7~10 分钟运动期间，客户端**不发起任何跑步 HTTP 请求**，GPS 点位由本地加速度计与定位传感器离线采样。纯协议执行时应模拟该时间窗口，不可瞬间结算。

### 4. OBS 推送与成绩结算 (OBS Upload & Save Record)
- `GET /api/v3/getserver/gmttime`：**二次时间校准**，计算精确的 `stopTime` 与 `totalTime`；
- `POST /api/obs/temporary/url`：以 NetSec 加密申请华为云 `iydsj-hbase-hot` 存储桶的 PUT 预签名地址；
- `PUT https://...`：将 Gzip+Base64 压缩的轨迹、10秒步频桶、10秒速度桶直传 OBS；
- `POST /api/v70260/runnings/save/record`：携带 31 个运动学参数参与 MD5 签名的 `signature`（加盐 `2slhe02lsfiwowlcixisla_sls-_slaor`）与 `headerSign` 提交网关结算，返回流水号 `rrid`；
- `POST /api/v70320/runnings/get_one_record`：毫秒级回查单次成绩状态，验证是否判定合规通过。

### 5. 跑后数据回刷 (Post-run Refresh)
- 刷新首页看板、已跑总公里数与信用分弹窗，完成整套客户端行为闭环。

---

## 命令行快速使用

```powershell
Set-Location 'D:\Work\运动世界\协议\7.3.92'
$py = 'D:\Work\运动世界\.venv\Scripts\python.exe'

# 1. 服务端时钟对齐测试
& $py .\cli.py --sync-time

# 2. 账号密码全自动登录 (含极验 v4 滑块自动求解)
& $py .\cli.py -u <PHONE> -p <PASSWORD>

# 3. 传入 Token 查询规则、围栏与个人档案
& $py .\cli.py -t <Token> --uid <UID> --rules --profile

# 4. 执行全时序合规跑步提交与回查
& $py .\cli.py -t <Token> --uid <UID> --unid <UNID> --run --distance 2150 --time-sec 760

# 5. 查询跑步历史成绩与打卡日历
& $py .\cli.py -t <Token> --uid <UID> --history
```
