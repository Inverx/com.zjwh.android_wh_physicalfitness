"""密码学加解密与签名工具 (8.7.2)。支持 AES、DES、哈希签名与点位加密。"""
import base64
import hashlib
import json
from typing import Optional, Union, Dict, Any
from Crypto.Cipher import AES, DES
from Crypto.Util.Padding import pad, unpad

# 客户端版本常量
APP_VERSION = "8.7.2"
BUILD_VERSION = "26091115"
APP_CODE = "SD001"

# 密钥与初始向量
AES_SIGN_KEY = b"RHXL092CDOYTQJVP" + bytes(16)
AES_FIELD_KEY = b"F44B0282BEA83557" + bytes(16)
AES_IV = b"01234ABCDEF56789"
SLIDER_KEY = b"Ukp3hmSe7BmMcgbE"
RUN_IMG_RECORD_KEY = "2V8BQ8MYXWU10Y9Z"

DES_KEYS = [
    b"c6bd901f", b"0ddf44be", b"950e5927", b"6460d8df",
    b"11fb887f", b"117e4900", b"bd113950", b"a99f6f97",
]

def aes_cbc_encrypt(data: Union[str, bytes], key: bytes = AES_SIGN_KEY, iv: bytes = AES_IV) -> str:
    """AES-CBC 加密。返回 Base64 字符串。"""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(raw, AES.block_size))
    return base64.b64encode(encrypted).decode("utf-8")

def aes_cbc_decrypt(cipher_b64: str, key: bytes = AES_SIGN_KEY, iv: bytes = AES_IV) -> str:
    """AES-CBC 解密。返回明文字符串。失败返回原串。"""
    try:
        raw_cipher = base64.b64decode(cipher_b64)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(raw_cipher), AES.block_size)
        return decrypted.decode("utf-8")
    except Exception:
        return cipher_b64

def encrypt_password(password: str) -> str:
    """加密登录密码。使用字段密钥。"""
    return aes_cbc_encrypt(password, key=AES_FIELD_KEY, iv=AES_IV)

def decrypt_password(cipher_b64: str) -> str:
    """解密登录密码。使用字段密钥。"""
    return aes_cbc_decrypt(cipher_b64, key=AES_FIELD_KEY, iv=AES_IV)

def encrypt_field(plain_text: str) -> str:
    """加密学籍敏感字段。"""
    return aes_cbc_encrypt(plain_text, key=AES_FIELD_KEY, iv=AES_IV)

def decrypt_field(cipher_b64: str) -> str:
    """解密学籍敏感字段。"""
    return aes_cbc_decrypt(cipher_b64, key=AES_FIELD_KEY, iv=AES_IV)

def get_sign(raw_body_text_or_dict: Union[str, Dict[str, Any]]) -> str:
    """计算请求头签名 sign。SHA256 哈希置换后 AES 加密。"""
    if isinstance(raw_body_text_or_dict, dict):
        clean_dict = {k: v for k, v in raw_body_text_or_dict.items() if k != "sign"}
        text = json.dumps(clean_dict, separators=(",", ":"), ensure_ascii=False)
    else:
        text = str(raw_body_text_or_dict)

    sha = hashlib.sha256(text.encode("utf-8")).hexdigest().lower()
    swapped = sha[-8:] + sha[8:-8] + sha[:8]
    return aes_cbc_encrypt(swapped, key=AES_SIGN_KEY, iv=AES_IV)

def encrypt_slider_point(raw_x: float, y: float = 15.0) -> str:
    """加密滑块缺口点位坐标。使用 AES-ECB 模式。"""
    e_real = int(raw_x - 6.5)
    e_send = e_real + 16.5
    data_dict = {"x": e_send, "y": float(y)}
    raw_json = json.dumps(data_dict, separators=(",", ":")).encode("utf-8")
    cipher = AES.new(SLIDER_KEY, AES.MODE_ECB)
    padded = pad(raw_json, AES.block_size)
    return base64.b64encode(cipher.encrypt(padded)).decode("utf-8")

def calculate_run_img_record(
    run_record_code: str,
    timestamp_str: str,
    build_version: str = BUILD_VERSION,
    app_version: str = APP_VERSION
) -> str:
    """计算完赛防篡改签名 runImgRecord。"""
    raw_str = f"{run_record_code}{build_version}{app_version}{RUN_IMG_RECORD_KEY}{timestamp_str}"
    return hashlib.md5(raw_str.encode("utf-8")).hexdigest().lower()

def des_decrypt(encrypted_b64: str, r_index: int) -> Optional[str]:
    """多媒体资源 DES 文件解密。"""
    try:
        key = DES_KEYS[r_index % len(DES_KEYS)]
        cipher = DES.new(key, DES.MODE_ECB)
        data = base64.b64decode(encrypted_b64)
        return unpad(cipher.decrypt(data), DES.block_size).decode("utf-8")
    except Exception:
        return None
