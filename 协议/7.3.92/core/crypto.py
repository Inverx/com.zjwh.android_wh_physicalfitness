import base64
import collections
import hashlib
import json
import os
import secrets
import struct
import subprocess
import time
import uuid
from pathlib import Path

# --- Pure Python AES-128 ---
S_BOX = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
]
INV_S_BOX = [0] * 256
for i, v in enumerate(S_BOX):
    INV_S_BOX[v] = i

RCON = [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]

def xtime(a):
    return ((a << 1) ^ 0x1B) & 0xFF if a & 0x80 else (a << 1) & 0xFF

def mul_gf(a, b):
    res = 0
    for _ in range(8):
        if b & 1: res ^= a
        a = xtime(a)
        b >>= 1
    return res

def key_expansion_128(key: bytes):
    w = [int.from_bytes(key[i:i+4], 'big') for i in range(0, 16, 4)]
    for i in range(4, 44):
        temp = w[i - 1]
        if i % 4 == 0:
            temp = ((temp << 8) | (temp >> 24)) & 0xFFFFFFFF
            b0 = S_BOX[(temp >> 24) & 0xFF]
            b1 = S_BOX[(temp >> 16) & 0xFF]
            b2 = S_BOX[(temp >> 8) & 0xFF]
            b3 = S_BOX[temp & 0xFF]
            temp = ((b0 ^ RCON[i // 4]) << 24) | (b1 << 16) | (b2 << 8) | b3
        w.append(w[i - 4] ^ temp)
    return w

def aes128_encrypt_block(block: bytes, round_keys):
    state = list(block)
    for i in range(16):
        rk_byte = (round_keys[i // 4] >> (24 - 8 * (i % 4))) & 0xFF
        state[i] ^= rk_byte
    for r in range(1, 10):
        state = [S_BOX[b] for b in state]
        state = [
            state[0], state[5], state[10], state[15],
            state[4], state[9], state[14], state[3],
            state[8], state[13], state[2], state[7],
            state[12], state[1], state[6], state[11]
        ]
        for c in range(4):
            idx = c * 4
            s0, s1, s2, s3 = state[idx:idx+4]
            state[idx]   = xtime(s0) ^ (s1 ^ xtime(s1)) ^ s2 ^ s3
            state[idx+1] = s0 ^ xtime(s1) ^ (s2 ^ xtime(s2)) ^ s3
            state[idx+2] = s0 ^ s1 ^ xtime(s2) ^ (s3 ^ xtime(s3))
            state[idx+3] = (s0 ^ xtime(s0)) ^ s1 ^ s2 ^ xtime(s3)
        rk_start = r * 4
        for i in range(16):
            rk_byte = (round_keys[rk_start + (i // 4)] >> (24 - 8 * (i % 4))) & 0xFF
            state[i] ^= rk_byte
    state = [S_BOX[b] for b in state]
    state = [
        state[0], state[5], state[10], state[15],
        state[4], state[9], state[14], state[3],
        state[8], state[13], state[2], state[7],
        state[12], state[1], state[6], state[11]
    ]
    rk_start = 10 * 4
    for i in range(16):
        rk_byte = (round_keys[rk_start + (i // 4)] >> (24 - 8 * (i % 4))) & 0xFF
        state[i] ^= rk_byte
    return bytes(state)

def aes128_decrypt_block(block: bytes, round_keys):
    state = list(block)
    rk_start = 10 * 4
    for i in range(16):
        rk_byte = (round_keys[rk_start + (i // 4)] >> (24 - 8 * (i % 4))) & 0xFF
        state[i] ^= rk_byte
    for r in range(9, 0, -1):
        state = [
            state[0], state[13], state[10], state[7],
            state[4], state[1], state[14], state[11],
            state[8], state[5], state[2], state[15],
            state[12], state[9], state[6], state[3]
        ]
        state = [INV_S_BOX[b] for b in state]
        rk_start = r * 4
        for i in range(16):
            rk_byte = (round_keys[rk_start + (i // 4)] >> (24 - 8 * (i % 4))) & 0xFF
            state[i] ^= rk_byte
        for c in range(4):
            idx = c * 4
            s0, s1, s2, s3 = state[idx:idx+4]
            state[idx]   = mul_gf(s0, 0x0e) ^ mul_gf(s1, 0x0b) ^ mul_gf(s2, 0x0d) ^ mul_gf(s3, 0x09)
            state[idx+1] = mul_gf(s0, 0x09) ^ mul_gf(s1, 0x0e) ^ mul_gf(s2, 0x0b) ^ mul_gf(s3, 0x0d)
            state[idx+2] = mul_gf(s0, 0x0d) ^ mul_gf(s1, 0x09) ^ mul_gf(s2, 0x0e) ^ mul_gf(s3, 0x0b)
            state[idx+3] = mul_gf(s0, 0x0b) ^ mul_gf(s1, 0x0d) ^ mul_gf(s2, 0x09) ^ mul_gf(s3, 0x0e)
    state = [
        state[0], state[13], state[10], state[7],
        state[4], state[1], state[14], state[11],
        state[8], state[5], state[2], state[15],
        state[12], state[9], state[6], state[3]
    ]
    state = [INV_S_BOX[b] for b in state]
    for i in range(16):
        rk_byte = (round_keys[i // 4] >> (24 - 8 * (i % 4))) & 0xFF
        state[i] ^= rk_byte
    return bytes(state)

def aes128_cbc_encrypt(data: bytes, key: bytes, iv: bytes = bytes(16)) -> bytes:
    pad_len = 16 - (len(data) % 16)
    padded = data + bytes([pad_len] * pad_len)
    round_keys = key_expansion_128(key)
    out = bytearray()
    prev = iv
    for i in range(0, len(padded), 16):
        block = bytes(b ^ p for b, p in zip(padded[i:i+16], prev))
        enc = aes128_encrypt_block(block, round_keys)
        out.extend(enc)
        prev = enc
    return bytes(out)

def aes128_cbc_decrypt(data: bytes, key: bytes, iv: bytes = bytes(16)) -> bytes:
    if not data or len(data) % 16:
        raise ValueError("AES-CBC ciphertext must contain complete blocks")
    if len(key) != 16 or len(iv) != 16:
        raise ValueError("AES-128-CBC requires a 16-byte key and IV")
    round_keys = key_expansion_128(key)
    out = bytearray()
    prev = iv
    for i in range(0, len(data), 16):
        block = data[i:i+16]
        dec = aes128_decrypt_block(block, round_keys)
        plain = bytes(b ^ p for b, p in zip(dec, prev))
        out.extend(plain)
        prev = block
    pad_len = out[-1]
    if not 1 <= pad_len <= 16 or out[-pad_len:] != bytes([pad_len]) * pad_len:
        raise ValueError("Invalid PKCS#7 padding")
    return bytes(out[:-pad_len])

def rsa_pkcs1_v15_encrypt(msg: bytes, n: int, e: int, k_len: int = 128) -> bytes:
    ps_len = k_len - len(msg) - 3
    ps = bytearray()
    while len(ps) < ps_len:
        b = os.urandom(1)[0]
        if b != 0: ps.append(b)
    em = b"\x00\x02" + bytes(ps) + b"\x00" + msg
    m_int = int.from_bytes(em, "big")
    c_int = pow(m_int, e, n)
    return c_int.to_bytes(k_len, "big")

def _byte_hash(data: bytes) -> int:
    h = 0
    for b in data:
        h = ((b | ((h << 8) & 0xFFFFFFFF)) ^ ((h >> 24) & 0xFF)) & 0xFFFFFFFF
    return h

def _feistel_transform(s0: int, s1: int, s2: int, s3: int):
    M = 0xFFFFFFFF
    t = (s2 ^ s0) & M
    mix = (((t >> 24) | (t << 8)) & M) ^ (((t >> 8) | (t << 24)) & M) ^ t
    mix &= M
    new_s1 = (mix ^ s1) & M
    new_s3 = (mix ^ s3) & M
    t2 = (new_s3 ^ new_s1) & M
    mix2 = (((t2 >> 24) | (t2 << 8)) & M) ^ (((t2 >> 8) | (t2 << 24)) & M) ^ t2
    mix2 &= M
    new_s0 = (mix2 ^ s0) & M
    new_s2 = (mix2 ^ s2) & M
    return new_s0, new_s1, new_s2, new_s3

def _final_mix(s0: int, s1: int, s2: int, s3: int) -> bytes:
    M = 0xFFFFFFFF
    a = (~(s2 | s3) & M) ^ s1
    b = ((s2 ^ s3) ^ a) & M
    c = ((a & s2) ^ s0) & M
    b = (b ^ c) & M
    a = (~(b | c) & M) ^ a
    d = ((a & b) ^ s3) & M
    return struct.pack("<IIII", d, a, b, c)

def response_kdf(kd1, kd2, kd3, kd4) -> bytes:
    if isinstance(kd1, str): kd1 = kd1.encode("utf-8")
    if isinstance(kd2, str): kd2 = kd2.encode("utf-8")
    if isinstance(kd3, str): kd3 = kd3.encode("utf-8")
    if isinstance(kd4, str): kd4 = kd4.encode("utf-8")
    h1, h2, h3, h4 = _byte_hash(kd1), _byte_hash(kd2), _byte_hash(kd3), _byte_hash(kd4)
    s0, s1, s2, s3 = _feistel_transform(h1, h2, h3, h4)
    return _final_mix(s0, s1, s2, s3)

REQ_RSA_PKCS1_B64 = (
    "MIGJAoGBALmmqVPOwY1mTVHGEfg7jHck1MNXsVtUfrqY99bm/W2cjLi3LvG/wMYw"
    "bhmf9O+y3CUlZ5g4AMd2Ly4XbWUloG/O8+1USGJ8ddmrzbl8j2EZi0OhpVCYI381"
    "+zZ0qa3z1cOuG2XdJnE7pO6Y4JNC37miqMXYmjejVi2QDIbONomfAgMBAAE="
)
class NetSecClient:
    def __init__(self):
        der = base64.b64decode(REQ_RSA_PKCS1_B64)
        modulus_offset = 7
        n_bytes = der[modulus_offset:modulus_offset + 128]
        self.n = int.from_bytes(n_bytes, "big")
        e_bytes = der[modulus_offset + 128 + 2:]
        self.e = int.from_bytes(e_bytes, "big")

    def encrypt_request(self, data_obj):
        raw_uuid = str(uuid.uuid4()).replace("-", "")
        candidate = raw_uuid + "ABCDEFGHIJKLMN12"
        kd1 = candidate[0:10]
        kd2 = candidate[10:20]
        kd3 = candidate[20:30]
        kd4 = candidate[30:40]
        resp_aes_key = response_kdf(kd1, kd2, kd3, kd4)

        if isinstance(data_obj, str):
            b64_data = base64.b64encode(data_obj.encode("utf-8")).decode("ascii")
        else:
            b64_data = base64.b64encode(json.dumps(data_obj, separators=(",", ":")).encode("utf-8")).decode("ascii")

        timestamp_sec = int(time.time())
        inner_dict = collections.OrderedDict([
            ("data", b64_data),
            ("keyDataFour", kd4),
            ("keyDataOne", kd1),
            ("keyDataThree", kd3),
            ("keyDataTwo", kd2),
            ("platform", 2),
            ("timeStamp", timestamp_sec),
        ])
        inner_json = json.dumps(inner_dict, separators=(",", ":"), ensure_ascii=False) + chr(10)
        inner_bytes = inner_json.encode("utf-8")
        h = hashlib.md5(inner_bytes).hexdigest().lower()

        req_aes_key = "".join(secrets.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(16)).encode("ascii")
        ciphertext = aes128_cbc_encrypt(inner_bytes, req_aes_key)
        d = base64.b64encode(ciphertext).decode("ascii")
        enc_k = rsa_pkcs1_v15_encrypt(req_aes_key, self.n, self.e)
        k = base64.b64encode(enc_k).decode("ascii")

        wire_req = {
            "d": d,
            "h": h,
            "k": k,
            "p": "101",
            "t": "0"
        }
        return wire_req, resp_aes_key

    def decrypt_response(self, resp_dict, resp_aes_key):
        if "r" in resp_dict:
            r_bytes = base64.b64decode(resp_dict["r"])
            decrypted = aes128_cbc_decrypt(r_bytes, resp_aes_key)
            inner_obj = json.loads(decrypted.decode("utf-8", errors="replace"))
            if "data" in inner_obj:
                biz_bytes = base64.b64decode(inner_obj["data"])
                try:
                    return json.loads(biz_bytes.decode("utf-8", errors="replace"))
                except Exception:
                    return biz_bytes.decode("utf-8", errors="replace")
        return resp_dict

def compute_token_sign(params, salt="2slhe02lsfiwowlcixisla_sls-_slaor"):
    valid_items = [(k, str(v)) for k, v in params.items() if v is not None and k.lower() != "signature"]
    valid_items.sort(key=lambda x: (x[0].lower(), x[0]))
    s = "&".join(f"{k}={v}" for k, v in valid_items) + salt
    return hashlib.md5(s.encode("utf-8")).hexdigest().lower()
