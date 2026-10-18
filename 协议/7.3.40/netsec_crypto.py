import base64
import collections
import hashlib
import json
import os
import random
import struct
import time
import uuid
from typing import Dict, Optional, Tuple, Union

from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad, unpad

SPORT_STATIC_SALT = "2slhe02lsfiwowlcixisla_sls-_slaor"
SPORT_FALLBACK_SALT = "&wh2016_swcampus"

REQUEST_RSA_PUBKEY_PKCS1_B64 = (
    "MIGJAoGBALmmqVPOwY1mTVHGEfg7jHck1MNXsVtUfrqY99bm/W2cjLi3LvG/wMYw"
    "bhmf9O+y3CUlZ5g4AMd2Ly4XbWUloG/O8+1USGJ8ddmrzbl8j2EZi0OhpVCYI381"
    "+zZ0qa3z1cOuG2XdJnE7pO6Y4JNC37miqMXYmjejVi2QDIbONomfAgMBAAE="
)

RESPONSE_VERIFY_PUBKEY_SPKI_B64 = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDMs6bFhb5lrf/xqwtNcKVHW09c"
    "oMbtLAmr9Rti7vnSnVroFuLHJEzxMqPQeItByr1Fu4RAQMR/aq/oknn53kCOuSaV"
    "sd9mnDCusrs7GmExDxlKe2pNAKTEZnT1FITQYT2SJkeCZ8iBKujqN61C3SXQ4Xa8"
    "QRr2uMTicec6XC08WQIDAQAB"
)

DEFAULT_HOST_RUN = "https://run.gxapp.iydsj.com"
DEFAULT_HOST_DISCOVERY = "https://discovery.gxapp.iydsj.com"
DEFAULT_HOST_DATAPOINT = "https://datapoint.gxapp.iydsj.com"


def compute_token_sign(params: Dict[str, Union[str, int, float, None]],
                       salt: str = SPORT_STATIC_SALT) -> str:
    valid_items = []
    for k, v in params.items():
        if v is None:
            continue
        if k.lower() == "signature":
            continue
        valid_items.append((k, str(v)))
    valid_items.sort(key=lambda x: (x[0].lower(), x[0]))
    canonical_str = "&".join(f"{k}={v}" for k, v in valid_items)
    to_hash = (canonical_str + salt).encode("utf-8")
    return hashlib.md5(to_hash).hexdigest().lower()


def _byte_hash(data: bytes) -> int:
    h = 0
    for b in data:
        h = ((b | ((h << 8) & 0xFFFFFFFF)) ^ ((h >> 24) & 0xFF)) & 0xFFFFFFFF
    return h


def _feistel_transform(s0: int, s1: int, s2: int, s3: int) -> Tuple[int, int, int, int]:
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


def response_kdf(kd1: Union[str, bytes],
                 kd2: Union[str, bytes],
                 kd3: Union[str, bytes],
                 kd4: Union[str, bytes]) -> bytes:
    if isinstance(kd1, str): kd1 = kd1.encode("utf-8")
    if isinstance(kd2, str): kd2 = kd2.encode("utf-8")
    if isinstance(kd3, str): kd3 = kd3.encode("utf-8")
    if isinstance(kd4, str): kd4 = kd4.encode("utf-8")
    h1, h2, h3, h4 = _byte_hash(kd1), _byte_hash(kd2), _byte_hash(kd3), _byte_hash(kd4)
    s0, s1, s2, s3 = _feistel_transform(h1, h2, h3, h4)
    return _final_mix(s0, s1, s2, s3)


class NetSecSession:
    def __init__(self, fixed_uuid: Optional[str] = None):
        if fixed_uuid:
            raw_uuid = fixed_uuid.replace("-", "")
        else:
            raw_uuid = str(uuid.uuid4()).replace("-", "")
        printable_pool = [chr(i) for i in range(0x21, 0x7E)]
        random_suffix = "".join(random.choice(printable_pool) for _ in range(16))
        candidate_pool = raw_uuid + random_suffix
        pos = 0
        segments = []
        for _ in range(4):
            seg_len = random.randint(8, 12)
            if pos + seg_len <= len(candidate_pool):
                segments.append(candidate_pool[pos:pos + seg_len])
                pos += seg_len
            else:
                segments.append(candidate_pool[pos:])
                pos = len(candidate_pool)
        while len(segments) < 4:
            segments.append("1234567890")
        self.keyDataOne = segments[0]
        self.keyDataTwo = segments[1]
        self.keyDataThree = segments[2]
        self.keyDataFour = segments[3]
        self.response_aes_key = response_kdf(
            self.keyDataOne, self.keyDataTwo, self.keyDataThree, self.keyDataFour
        )

    def get_key_data_dict(self) -> Dict[str, str]:
        return {
            "keyDataOne": self.keyDataOne,
            "keyDataTwo": self.keyDataTwo,
            "keyDataThree": self.keyDataThree,
            "keyDataFour": self.keyDataFour,
        }


class NetSecCrypto:
    def __init__(self,
                 request_rsa_key_b64: str = REQUEST_RSA_PUBKEY_PKCS1_B64,
                 response_rsa_key_b64: str = RESPONSE_VERIFY_PUBKEY_SPKI_B64):
        req_der = base64.b64decode(request_rsa_key_b64)
        self.request_rsa_key = RSA.import_key(req_der)
        self.request_rsa_cipher = PKCS1_v1_5.new(self.request_rsa_key)
        resp_der = base64.b64decode(response_rsa_key_b64)
        self.response_rsa_key = RSA.import_key(resp_der)

    def encrypt_request(self,
                        caller_plaintext: Union[str, bytes, dict, list],
                        session: NetSecSession,
                        timestamp_sec: Optional[int] = None) -> Dict[str, str]:
        if isinstance(caller_plaintext, (dict, list)):
            caller_bytes = json.dumps(caller_plaintext, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        elif isinstance(caller_plaintext, str):
            caller_bytes = caller_plaintext.encode("utf-8")
        else:
            caller_bytes = caller_plaintext
        b64_data = base64.b64encode(caller_bytes).decode("ascii")
        if timestamp_sec is None:
            timestamp_sec = int(time.time())
        inner_dict = collections.OrderedDict([
            ("data", b64_data),
            ("keyDataFour", session.keyDataFour),
            ("keyDataOne", session.keyDataOne),
            ("keyDataThree", session.keyDataThree),
            ("keyDataTwo", session.keyDataTwo),
            ("platform", 2),
            ("timeStamp", timestamp_sec),
        ])
        inner_json = json.dumps(inner_dict, separators=(",", ":"), ensure_ascii=False) + chr(10)
        inner_bytes = inner_json.encode("utf-8")
        h = hashlib.md5(inner_bytes).hexdigest().lower()
        printable_pool = [chr(i) for i in range(0x21, 0x7E)]
        req_aes_key = "".join(random.choice(printable_pool) for _ in range(16)).encode("ascii")
        zero_iv = bytes(16)
        aes_cipher = AES.new(req_aes_key, AES.MODE_CBC, iv=zero_iv)
        ciphertext = aes_cipher.encrypt(pad(inner_bytes, 16))
        d = base64.b64encode(ciphertext).decode("ascii")
        rsa_cipher = PKCS1_v1_5.new(self.request_rsa_key)
        enc_key = rsa_cipher.encrypt(req_aes_key)
        k = base64.b64encode(enc_key).decode("ascii")
        return {
            "d": d,
            "h": h,
            "k": k,
            "p": "101",
            "t": "0"
        }

    def decrypt_response(self,
                         wire_response: Union[str, dict],
                         session: NetSecSession,
                         verify_sig: bool = True) -> str:
        if isinstance(wire_response, str):
            res_obj = json.loads(wire_response)
        else:
            res_obj = wire_response
        v = res_obj.get("v")
        if v != 101 and str(v) != "101":
            raise ValueError(f"Unsupported response version: {v}, expected 101")
        r_b64 = res_obj["r"]
        s_b64 = res_obj["s"]
        cipher_bytes = base64.b64decode(r_b64)
        zero_iv = bytes(16)
        aes_cipher = AES.new(session.response_aes_key, AES.MODE_CBC, iv=zero_iv)
        padded_plain = aes_cipher.decrypt(cipher_bytes)
        try:
            inner_plain_bytes = unpad(padded_plain, 16)
        except ValueError:
            inner_plain_bytes = padded_plain
        if verify_sig:
            digest_hex = hashlib.md5(inner_plain_bytes).hexdigest().lower().encode("ascii")
            sig_bytes = base64.b64decode(s_b64)
            block_size = (self.response_rsa_key.n.bit_length() + 7) // 8
            if len(sig_bytes) != block_size:
                raise ValueError(
                    f"Invalid response signature length: {len(sig_bytes)}, expected {block_size}"
                )
            sig_int = int.from_bytes(sig_bytes, "big")
            recovered_int = pow(sig_int, self.response_rsa_key.e, self.response_rsa_key.n)
            recovered_bytes = recovered_int.to_bytes(block_size, "big")
            sep_idx = recovered_bytes.find(bytes([0]), 2)
            valid_padding = (
                recovered_bytes.startswith(b"\x00\x01")
                and sep_idx >= 10
                and all(value == 0xFF for value in recovered_bytes[2:sep_idx])
            )
            if not valid_padding:
                raise ValueError("Invalid PKCS#1 v1.5 response signature padding")
            recovered_digest = recovered_bytes[sep_idx + 1:]
            if recovered_digest.lower() != digest_hex.lower():
                raise ValueError(
                    f"Signature mismatch: recovered={recovered_digest!r} vs expected={digest_hex!r}"
                )
        inner_obj = json.loads(inner_plain_bytes.decode("utf-8"))
        data_b64 = inner_obj.get("data", "")
        business_bytes = base64.b64decode(data_b64)
        return business_bytes.decode("utf-8")

    def simulate_server_encrypt(self,
                                business_obj: Union[str, dict, list],
                                session: NetSecSession) -> Dict[str, Union[str, int]]:
        if isinstance(business_obj, (dict, list)):
            business_str = json.dumps(business_obj, separators=(",", ":"), ensure_ascii=False)
        else:
            business_str = str(business_obj)
        inner_obj = {"data": base64.b64encode(business_str.encode("utf-8")).decode("ascii")}
        inner_bytes = json.dumps(inner_obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        aes_cipher = AES.new(session.response_aes_key, AES.MODE_CBC, iv=bytes(16))
        cipher_bytes = aes_cipher.encrypt(pad(inner_bytes, 16))
        return {
            "r": base64.b64encode(cipher_bytes).decode("ascii"),
            "s": "MOCK_SERVER_SIGNATURE_PLACEHOLDER",
            "v": 101
        }


