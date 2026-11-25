# 运动世界 7.3.92 独立登录自包含模块 (Login Module)

本目录为运动世界 7.3.92 纯协议套件的独立登录子模块。全部静态资源、证书、密码学引擎与滑块求解器已 100% 收敛至本目录下，形成完全独立的“开箱即用”自包含包。

---

## 1. 完整目录与资源分布

D:/Work/运动世界/协议/7.3.92/login/
├── __init__.py           # 模块统一对外导出接口 (LoginClient, LoginResult, UserProfile 等)
├── config.py             # 接口端点、Captcha ID 与 7.3.92 实机抓包设备指纹规范
├── models.py             # 强类型数据模型 (GeetestResult, UserProfile, LoginResult)
├── crypto.py             # 登录专属纯 Python NetSecKit 密码学引擎 (零 pip 依赖)
├── captcha.py            # 极验 4 代滑块执行器封装 (GeetestV4Solver)
├── client.py             # 纯协议登录核心业务实现 (LoginClient)
├── cli.py                # 终端命令行一键执行与卡片展示入口
├── geetest_solver.js     # 本地无头 Chromium 图像二值化与轨迹模拟脚本
├── certs/                # 本地 HTTPS 桥接专属证书（自包含，无需依赖临时目录）
│   ├── cert.pem
│   └── key.pem
├── assets/               # 7.3.92 原包提取极验静态资产
│   ├── gt4.js           # 极验官方离线 JS 库 (v4.2.0)
│   ├── gt4-index.html   # 极验官方桥接中间页
│   ├── gt4-loading.gif  # 官方加载动画
│   └── samples/         # 实机抓包样本图片（用于算法离线校验）
│       ├── sample_bg.png
│       └── sample_slice.png
└── README.md             # 本技术文档

---

## 2. 客户端集成调用规范

在任何上层项目（GUI 桌面应用、Web 后台或定时脚本）中，只需将本 login 目录放置在源码路径下即可：

python:
from login import LoginClient, LoginResult

# 1. 实例化登录客户端
client = LoginClient()

# 2. 绑定界面回调函数
def on_progress(msg: str):
    print(f"[进度] {msg}")

# 3. 发起全流程登录（自动完成 checkGeeUse -> 滑块 -> geevalidate -> login）
result: LoginResult = client.login("<PHONE>", "<PASSWORD>", progress_callback=on_progress)

if result.success and result.user:
    print(f"登录成功: {result.user.name} ({result.user.campus_name})")
    print(f"核心 Token: {result.user.token}")
    print(f"学号: {result.user.campus_id}, UID: {result.user.uid}")
else:
    print(f"登录失败: [{result.error_code}] {result.message}")

---

## 3. 命令行独立验证

powershell:
Set-Location 'D:\Work\运动世界\协议.3.92\login'
& 'D:/Work/运动世界/.venv/Scripts/python.exe' '.\cli.py'
