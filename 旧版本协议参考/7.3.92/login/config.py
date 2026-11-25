# -*- coding: utf-8 -*-
DEFAULT_HOST_RUN = "https://run.gxapp.iydsj.com"
DEFAULT_HOST_DISCOVERY = "https://discovery.gxapp.iydsj.com"

# 接口端点
URL_CHECK_GEE_USE = f"{DEFAULT_HOST_RUN}/api/v65/security/checkGeeUse"
URL_GEE_VALIDATE = f"{DEFAULT_HOST_RUN}/api/v70270/security/geevalidate"
URL_LOGIN = f"{DEFAULT_HOST_RUN}/api/v70100/login"

# 极验登录 Captcha ID
LOGIN_CAPTCHA_ID = "3b02ad39bd099fd3a8336d9347a189ab"

# 通用设备与系统占位指纹 (通用占位参数)
DEFAULT_DEVICE_CONFIG = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "appVersion": "7.3.92",
    "physicPixel": "1080x2400",
    "logicPixel": "393x873",
    "isRoot": "0",
    "osType": "0",
    "uid": "-1",
    "IMEI": "",
    "blMac": "",
    "token": "",
    "tokenSign": "",
    "cpuModel": "arm64-v8a",
    "deviceName": "Android Device",
    "appInstallTime": "0",
    "androidId": "",
    "DeviceId": "00000000000000000000000000000000",
    "appUpdateTime": "0",
    "wifiMac": "",
    "CustomDeviceId": "",
    "osVersion": "13",
    "User-Agent": "okhttp/4.12.0"
}
