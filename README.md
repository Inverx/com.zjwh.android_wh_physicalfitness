# 免责声明与致谢 (Disclaimer & Acknowledgments)

> **重要提示**：在使用、复制、修改或分发本仓库中的任何脱壳产物、分析文档、代码或模块前，请务必仔细阅读以下全部内容。一旦您下载、查看、使用或分发本项目，即视为您已充分理解并完全同意本声明中的所有条款。

---

## 核心声明

```text
1. 仅面向 Android 逆向工程、应用加固脱壳、动静态安全分析与网络协议研究（按应用包名与客户端版本独立分层归档）
2. 严禁任何形式的商业接单、有偿代跑、外挂制作与倒卖引流
3. 官方联系后将第一时间无条件停止相关软件维护并归档或下架对应资料
```

---

## 一、仓库定位与研究范围说明

### 1. 维护方向说明

本仓库为 **Android 客户端逆向工程与安全分析资料归档库**，按目标软件的 **Android Application ID（包名）** 进行顶层隔离，并在各软件目录下按照逆向工程标准流程（脱壳资料、静态分析、动态分析、接口与协议）及客户端版本号独立归档维护，各软件与各版本之间互不干扰，仅用于加固演进对比、移动安全分析与协议架构研究。

### 2. 技术研究目的

本项目仅面向以下技术领域的学习与交流：

```text
Android Unpacking & Dex Dumping (Android 加固脱壳与 Dex 提取研究)
Static Reverse Analysis (JADX / IDA / Ghidra 静态反编译与结构分析)
Dynamic Debugging & Hooking (Frida / Unidbg / Xposed 动态调试与插桩分析)
Cryptographic Algorithm Reconstruction (Native SO 与业务层密码学算法还原)
Network Protocol & Security Analysis (客户端网络通信协议与移动应用安全研究)
```

### 3. 授权环境限制

本仓库所有资料与代码仅限在本人合法所有的设备、本人账号、本地模拟器或已获得明确授权的测试环境中用于安全研究与技术探讨。

---

## 二、严禁商业接单与非法牟利

本项目为**完全免费、开源**的技术研究归档项目，受以下附加条款严格限制：

- **严禁商业代跑与接单**：严禁任何个人、团队、工作室或组织利用本仓库内容（包括脱壳 DEX/SO 资料、分析文档、协议源码、衍生修改版）进行**商业接单、收费代跑、按次或包月收费**等行为。

- **严禁倒卖与付费引流**：严禁将本项目的任何资料或构建产物用于**闲鱼、淘宝、拼多多、社交平台倒卖、打包售卖、建立收费群准入、付费教程捆绑**等任何直接或间接的商业牟利行为。

- **违规追责声明**：对于任何违反上述规定、利用本项目进行商业牟利的行为，均属违规使用者个人行为，与本项目作者无关。欢迎社区成员对违规商用行为进行监督与举报，一切由此引发的法律纠纷与责任均由违规者自行承担。

---

## 三、官方联系与停更下架机制

本项目旨在进行 Android 客户端逆向工程与移动安全的技术探索，**无意破坏任何目标软件的正常业务运营秩序**。

- 本项目完全尊重各目标软件开发团队及相关权利人的知识产权与合法权益。

- **若相关软件官方团队或权利人认为本仓库中的特定目录或资料对软件正常运营产生了不当影响并与本人取得联系，本人将在收到通知的第一时间无条件配合，立即停止对应软件的全部研究更新，并对相关目录或本 GitHub 仓库执行归档（Archive）或彻底移除下架处理。**

---

## 四、免责条款 (Legal Disclaimer)

- **合规使用**：使用者必须严格遵守所在国家或地区的法律法规、所在高校或机构的规章制度以及目标软件的用户服务协议。

- **禁止滥用**：严禁将本仓库资料用于破坏计算机信息系统、干扰目标服务器正常运转、未经授权获取他人数据或其他任何侵犯第三方合法权益的行为。

- **风险自担**：本项目按「原样（AS-IS）」提供，不附带任何明示或暗示的担保。使用者应自行承担因下载、查看、使用、修改或分发本项目内容所产生的一切直接或间接后果（包括但不限于：客户端异常、数据损坏、账号封禁、校规处分或相关法律责任）。本项目作者及贡献者不对任何因使用本项目而导致的损失或风险承担任何连带责任。

---

## 五、赞赏与感谢 (Sponsors)

开源项目的持续研究与归档维护离不开社区朋友的鼓励，特别感谢以下朋友对本项目的赞赏与支持：

| 赞赏者 | 致谢说明 |
| :---: | :---: |
| **VXiok** | 感谢对本项目的赞赏与支持 |

---

## 六、开源致谢 (Credits)

本项目在 Android 脱壳、动态插桩与 HTTPS 流量分析过程中曾参考或使用以下优秀开源工具辅助研究，相关版权及源代码归原作者所有：

```text
Frida / frida-dexdump (hluwa / frida-dexdump)
JustTrustMePro (hang666 / JustTrustMePro)
JADX / Ghidra / Reqable
```

---

## 七、联系方式与反馈渠道

- **GitHub Issues**：[https://github.com/Inverx/com.zjwh.android_wh_physicalfitness/issues](https://github.com/Inverx/com.zjwh.android_wh_physicalfitness/issues)

---

# Android 校园应用逆向与协议工程归档库

<p align="center">
  <b>Android Reverse Engineering · Unpacking Archives · Protocol Analysis</b>
</p>

<p align="center">
  面向 Android 移动客户端的脱壳资料归档、动静态逆向分析与网络协议工程化研究仓库。
</p>

---

## 仓库简介

本仓库长期维护多个 Android 客户端在各个历史版本下的 **原始脱壳产物（DEX / Native SO）**、**静态代码分析**、**动态调试脚本** 以及 **接口协议参考实现**。

通过对目标客户端开展标准化的分层研究：

```text
原始脱壳资料归档 (Frida Dex Dump / SO 提取)
    +
静态逆向分析 (JADX 反编译 / Native SO 符号与算法定位)
    +
动态调试与插桩 (Frida Hook / SSL Pinning Bypass / 内存漫游)
    +
接口与通信协议还原 (加解密还原 / 签名校验 / 业务时序建模)
```

实现跨软件、跨版本的加固策略演进对比与客户端安全机制研究。

---

## 已收录软件索引

当前仓库按软件 Application ID（包名）划分顶层目录，已收录及正在维护的目标软件如下：

| 软件名称 | 应用包名 (目录) | 当前归档内容概览 | 状态 |
|---|---|---|---|
| **运动世界校园** | [`com.zjwh.android_wh_physicalfitness/`](./com.zjwh.android_wh_physicalfitness/) | `7.3.92` ~ `7.4.21` 多版本 Frida 脱壳 Dex 归档；`7.3.40` / `7.3.92` 旧版本纯 Python 协议参考实现 | 脱壳持续归档 / 旧版协议停止维护 |
| **闪动校园** | [`com.huachenjie.shandong_school/`](./com.huachenjie.shandong_school/) | `8.8.5` 客户端 Frida 脱壳 Dex 归档 | 持续归档与分析中 |

---

## 仓库分层架构

为保证多个软件及多版本资料演进互不污染，仓库统一采用「**应用包名 → 逆向阶段 → 客户端版本**」的三级分层结构：

```text
Repository Root/
│
├── README.md                                      # 仓库总览与免责声明
│
├── com.zjwh.android_wh_physicalfitness/           # [软件 A] 运动世界校园
│   ├── README.md                                  # 软件专属说明与详细技术文档
│   ├── LICENSE                                    # 开源许可证
│   ├── 脱壳资料-Frida_Dex_Dump/                    # 原始脱壳资料 (7.3.92 ~ 7.4.21 Dex Dump)
│   ├── 静态分析/                                   # JADX / IDA / Ghidra 静态分析笔记与特征归档
│   ├── 动态分析/                                   # Frida Hook 脚本、调用栈追踪与内存分析
│   └── 旧版本协议参考/                             # 历史版本 (7.3.40 / 7.3.92) 接口与协议参考实现
│
├── com.huachenjie.shandong_school/                # [软件 B] 闪动校园
│   ├── README.md                                  # 软件专属说明文档
│   ├── 脱壳资料-Frida_Dex_Dump/                    # 原始脱壳资料 (8.8.5 Dex Dump)
│   ├── 静态分析/                                   # 静态逆向分析资料
│   ├── 动态分析/                                   # 动态调试与 Hook 脚本
│   └── 接口与协议/                                 # 接口分析与协议文档
│
└── <package.name.software_x>/                     # [后续扩展软件]
    ├── 原始脱壳资料/
    ├── 静态分析/
    ├── 动态分析/
    └── 接口与协议/
```

### 分层规范说明

每个软件子目录内部按逆向分析生命周期划分为四个标准维度：

```text
1. 原始脱壳资料 (脱壳资料-Frida_Dex_Dump)
   └── 存放各版本客户端通过 Frida / 内存 Dump 提取的原始 DEX、Native SO 压缩归档包，作为后续分析的基线样本。

2. 静态分析
   └── 存放基于 JADX、Ghidra、IDA Pro 的反编译结构梳理、关键类与混淆映射表、加固壳特征及密码学常量分析。

3. 动态分析
   └── 存放 Frida Hook 脚本、Unidbg 模拟执行代码、SSL Pinning 绕过脚本及运行时入参/返回值抓取记录。

4. 接口与协议 (旧版本协议参考)
   └── 存放客户端网络请求链路文档、Header/Payload 签名加解密还原逻辑及历史版本参考代码。
```

---

## 各软件归档详情

### 1. `com.zjwh.android_wh_physicalfitness`（运动世界校园）

- **原始脱壳资料**（[`com.zjwh.android_wh_physicalfitness/脱壳资料-Frida_Dex_Dump/`](./com.zjwh.android_wh_physicalfitness/脱壳资料-Frida_Dex_Dump/)）：
  - `运动世界7.3.92-FridaDump.zip`
  - `运动世界7.3.93-FridaDump.zip`
  - `运动世界7.4.0-FridaDump.zip`
  - `运动世界7.4.01-FridaDump.zip`
  - `运动世界7.4.02-FridaDump.zip`
  - `运动世界7.4.20-FridaDump.zip`
  - `运动世界7.4.21-FridaDump.zip`
- **旧版本协议参考**（[`com.zjwh.android_wh_physicalfitness/旧版本协议参考/`](./com.zjwh.android_wh_physicalfitness/旧版本协议参考/)）：
  - `7.3.40/`：单文件解耦 CLI 脚本架构（登录、规则、成绩、排行榜、室外跑/室内锻炼协议参考）
  - `7.3.92/`：模块化协议套件（NetSecKit 4.2.4 纯标准库实现、极验 v4 滑块、GMT 时钟对齐、电子围栏、OBS 轨迹合成与曝光埋点参考）
  - 详细文档请查阅：[`com.zjwh.android_wh_physicalfitness/README.md`](./com.zjwh.android_wh_physicalfitness/README.md)

### 2. `com.huachenjie.shandong_school`（闪动校园）

- **原始脱壳资料**（[`com.huachenjie.shandong_school/脱壳资料-Frida_Dex_Dump/`](./com.huachenjie.shandong_school/脱壳资料-Frida_Dex_Dump/)）：
  - `闪动校园8.8.5-FridaDump.zip`
- **分析文档**：
  - 详细文档请查阅：[`com.huachenjie.shandong_school/README.md`](./com.huachenjie.shandong_school/README.md)

---

## 标准研究流程

本仓库中各软件的逆向与分析均遵循以下标准工程链路：

```text
Target Android APK (加固样本)
    │
    ▼
Runtime Memory Dumping (Frida Dex Dump / SO Dump)
    │
    ▼
Static Analysis (JADX 反编译 / 定位核心业务类与 Native JNI 接口)
    │
    ▼
Dynamic Analysis & Hooking (Frida 追踪入参、密钥派生与签名盐值)
    │
    ▼
HTTPS Traffic Capture (SSL Pinning Bypass + HAR 流量差分对比)
    │
    ▼
Crypto & Protocol Documentation (算法还原与接口协议归档)
```

---

## 隐私与数据安全

在向本仓库提交分析资料、Issue 或 Pull Request 时，请 **不要** 包含任何真实用户的敏感信息：

```text
手机号 / 账号 / 密码
Token / Cookie / Session
UID / UNID / 学号 / 真实姓名
Device ID / CAID / OAID / Android ID / IMEI
学校 / 院系 / 班级信息
包含个人凭据的未脱敏 HAR 抓包文件与真实 GPS 轨迹
```

所有本地调试过程中产生的账号凭据、抓包日志及设备指纹参数应严格保留在本地并做好脱敏处理。

---

## License

本仓库基于 **MIT License** 开源，详见子目录或仓库中的 `LICENSE` 文件。

---

<p align="center">
  <b>Android Reverse Engineering · Unpacking Archives · Security & Protocol Analysis</b>
</p>
