# -*- coding: utf-8 -*-
import os
import json
import uuid

# 服务端网关主机
HOST_RUN = "https://run.gxapp.iydsj.com"
HOST_DISCOVERY = "https://discovery.gxapp.iydsj.com"
HOST_DATAPOINT = "https://datapoint.gxapp.iydsj.com"
HOST_PARTNER = "https://partner.iydsj.com"

# 7.3.92 通用设备占位配置 (标准 ARM64 真机特征)
DEFAULT_DEVICE_CONFIG = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "appVersion": "7.3.92",
    "physicPixel": "1080x2400",
    "logicPixel": "393x873",
    "isRoot": "0",
    "osType": "0",
    "cpuModel": "arm64-v8a",
    "deviceName": "Android Device",
    "DeviceId": "00000000000000000000000000000000",
    "osVersion": "13",
    "User-Agent": "okhttp/4.12.0"
}

def load_customer_device(config_path: str = None) -> dict:
    dev = dict(DEFAULT_DEVICE_CONFIG)
    dev["DeviceId"] = uuid.uuid4().hex
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                phone = cfg.get("setting", {}).get("phone", {})
                if phone:
                    if "brand" in phone or "model" in phone:
                        dev["deviceName"] = f"{phone.get('brand', 'Android')} {phone.get('model', 'Device')}"
                    if "vdid" in phone:
                        dev["DeviceId"] = phone["vdid"].replace("-", "")
        except Exception:
            pass
    return dev
