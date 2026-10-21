"""Persistent per-account protocol device fields (no passwords or tokens)."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import time
import uuid

from .config import DEFAULT_DEVICE_CONFIG

# Physical displays / launch Android versions: Google Pixel hardware specs:
# https://support.google.com/pixelphone/answer/7158570?hl=en
# Logical viewports are derived template values, not device attestation.
DEVICE_TEMPLATES = (
    {"deviceName": "Google Pixel 7", "physicPixel": "1080x2400",
     "logicPixel": "412x915", "osVersions": ("13", "14")},
    {"deviceName": "Google Pixel 7 Pro", "physicPixel": "1440x3120",
     "logicPixel": "412x892", "osVersions": ("13", "14")},
    {"deviceName": "Google Pixel 8", "physicPixel": "1080x2400",
     "logicPixel": "412x915", "osVersions": ("14",)},
    {"deviceName": "Google Pixel 8 Pro", "physicPixel": "1344x2992",
     "logicPixel": "448x997", "osVersions": ("14",)},
)


def account_key(account):
    if not isinstance(account, str):
        raise ValueError("Account must be a string")
    value = account.strip()
    if not value or any(ord(c) < 32 for c in value):
        raise ValueError("Account must be nonempty and contain no control characters")
    compact = re.sub(r"[\s()-]", "", value)
    if re.fullmatch(r"(?:\+86|0086)?1[0-9]{10}", compact):
        value = compact[-11:]
    return hashlib.sha256(("account:" + value).encode("utf-8")).hexdigest()


def uid_key(uid):
    if isinstance(uid, bool) or not isinstance(uid, (int, str)) or int(uid) <= 0:
        raise ValueError("UID must be a positive integer")
    return hashlib.sha256(("uid:" + str(int(uid))).encode("ascii")).hexdigest()


def validate_device(device):
    allowed = set(DEFAULT_DEVICE_CONFIG) | {"androidId", "appInstallTime", "appUpdateTime"}
    if not isinstance(device, dict) or not set(device) <= allowed:
        raise ValueError("Invalid stored device fields")
    if not all(isinstance(v, str) and "\r" not in v and "\n" not in v for v in device.values()):
        raise ValueError("Stored device fields must be single-line strings")
    if not set(DEFAULT_DEVICE_CONFIG) <= set(device):
        raise ValueError("Stored device is incomplete")
    if not re.fullmatch(r"[0-9a-f]{32}", device["DeviceId"]) or device["DeviceId"] == "0" * 32:
        raise ValueError("Invalid stored DeviceId")
    if not device["deviceName"].strip() or not re.fullmatch(r"[0-9]+", device["osVersion"]):
        raise ValueError("Invalid stored model or OS version")
    for field in ("physicPixel", "logicPixel"):
        if not re.fullmatch(r"[1-9][0-9]*x[1-9][0-9]*", device[field]):
            raise ValueError("Invalid stored screen dimensions")
    return dict(device)


class DeviceStore:
    def __init__(self, directory=None):
        default = Path(__file__).resolve().parents[1] / ".device_profiles"
        self.directory = Path(directory or os.environ.get("SPORT_DEVICE_DIR") or default).expanduser().resolve()
        self.path = self.directory / "devices.json"

    @contextlib.contextmanager
    def _locked(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock = self.directory / "devices.lock"
        deadline = time.monotonic() + 5
        while True:
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Device store is locked; no device was changed")
                time.sleep(0.05)
        try:
            yield
        finally:
            os.close(fd)
            lock.unlink()

    def _read(self):
        if not self.path.exists():
            return {"version": 1, "accounts": {}, "uids": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if (not isinstance(data, dict) or data.get("version") != 1
                    or not isinstance(data.get("accounts"), dict)
                    or not isinstance(data.get("uids"), dict)):
                raise ValueError("Invalid device store schema")
            for key, device in data["accounts"].items():
                if not re.fullmatch(r"[0-9a-f]{64}", key):
                    raise ValueError("Invalid account key")
                validate_device(device)
            for key, account in data["uids"].items():
                if not re.fullmatch(r"[0-9a-f]{64}", key) or account not in data["accounts"]:
                    raise ValueError("Invalid UID mapping")
            return data
        except (ValueError, TypeError) as exc:
            raise ValueError("Device store is invalid; refusing to replace saved identities") from exc

    def _write(self, data):
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory,
                                             prefix="devices-", suffix=".tmp", delete=False) as output:
                name = output.name
                json.dump(data, output, ensure_ascii=False, indent=2)
                output.flush()
                os.fsync(output.fileno())
            os.replace(name, self.path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    def for_account(self, account):
        key = account_key(account)
        with self._locked():
            data = self._read()
            if key not in data["accounts"]:
                used = {p["deviceName"] for p in data["accounts"].values()}
                templates = [p for p in DEVICE_TEMPLATES if p["deviceName"] not in used] or DEVICE_TEMPLATES
                template = secrets.choice(templates)
                device = dict(DEFAULT_DEVICE_CONFIG)
                device.update({k: v for k, v in template.items() if k != "osVersions"})
                device["osVersion"] = secrets.choice(template["osVersions"])
                existing_ids = {p["DeviceId"] for p in data["accounts"].values()}
                device["DeviceId"] = uuid.uuid4().hex
                while device["DeviceId"] in existing_ids:
                    device["DeviceId"] = uuid.uuid4().hex
                device["androidId"] = secrets.token_hex(8)
                now_ms = int(time.time() * 1000)
                installed = now_ms - (1 + secrets.randbelow(365)) * 86400000
                device["appInstallTime"] = str(installed)
                device["appUpdateTime"] = str(installed)
                data["accounts"][key] = validate_device(device)
                self._write(data)
            return validate_device(data["accounts"][key])

    def bind_uid(self, account, uid):
        key, user = account_key(account), uid_key(uid)
        with self._locked():
            data = self._read()
            if key not in data["accounts"]:
                raise ValueError("No saved device for this account")
            previous = data["uids"].get(user)
            if previous is not None and previous != key:
                raise ValueError("UID is already associated with another saved account")
            if previous != key:
                data["uids"][user] = key
                self._write(data)

    def for_uid(self, uid):
        key = uid_key(uid)
        with self._locked():
            data = self._read()
            account = data["uids"].get(key)
            if account is None:
                raise ValueError("No device saved for this UID; first log in with -u in this device directory")
            return validate_device(data["accounts"][account])
