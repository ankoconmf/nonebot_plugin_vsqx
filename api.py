import base64
import json
from typing import Any, Optional

import httpx
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA

from .config import (
    BASE_URL,
    COMMON_HEADERS,
    COVER_BASE,
    ASSETS_BASE,
    DATA_FILE,
    LOGIN_PUBLIC_KEY,
)


def _encrypt_password(password: str) -> str:
    """使用站点 RSA 公钥加密密码（RSA-OAEP，与前端 node publicEncrypt 一致）。"""
    key = RSA.import_key(LOGIN_PUBLIC_KEY)
    cipher = PKCS1_OAEP.new(key)  # 默认 SHA-1，对应 RSA_PKCS1_OAEP_PADDING
    return base64.b64encode(cipher.encrypt(password.encode("utf-8"))).decode()


def load_token() -> Optional[str]:
    """从本地数据文件读取登录 token。"""
    if not DATA_FILE.exists():
        return None
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return data.get("token") or None
    except Exception:
        return None


def save_token(token: str, username: str = "") -> None:
    """持久化 token 到本地数据文件。"""
    DATA_FILE.write_text(
        json.dumps({"token": token, "username": username}, ensure_ascii=False),
        encoding="utf-8",
    )


def cover_url(item: dict) -> str:
    """根据项目数据还原封面图 URL（对应前端 cover_src 逻辑）。"""
    vocaloid_type = item.get("vocaloid_type")
    vocaloid_2019 = item.get("vocaloid_2019")
    pic_exist = item.get("pic_exist")
    vsqx_uid = item.get("vsqx_uid")
    synthesizer_type = item.get("synthesizer_type")

    if vocaloid_type is not None:
        if vocaloid_type == 2019:
            return f"{ASSETS_BASE}/vocaloid_bar/{vocaloid_2019}.jpg"
        return f"{ASSETS_BASE}/vocaloid_bar/vocaloid_{vocaloid_type}.jpg"
    if pic_exist == 1:
        # 有自定义封面：使用 vsqx_uid（时间戳）
        return f"{COVER_BASE}/{vsqx_uid}.jpg"
    # 兜底：按合成器类型的默认封面
    return f"{COVER_BASE}/{synthesizer_type}.jpg"


def project_type(item: dict) -> str:
    """根据 synthesizer_type 返回工程类型名（对应前端映射）。"""
    t = item.get("synthesizer_type")
    if t == 1:
        return "Vocaloid 工程"
    if t == 2:
        name = item.get("synthesizer_name") or "其他"
        return f"{name} 工程"
    if t == 3:
        return "MIDI 工程"
    if t == 4:
        return "插件/工具"
    return "未知类型"


async def search_projects(keyword: str, page: int = 1) -> tuple[list[dict], int]:
    """搜索工程，返回 (结果列表, 总数)。"""
    payload = {
        "search_text": keyword,
        "currPageIndex": page,
        "language": 0,
        "singer": 0,
        "level": 0,
        "music_exist": False,
        "order_by_hot": False,
        "order_by_recent_hot": False,
        "synthesizer": 0,
        "synthesizer_name": 0,
    }
    headers = {**COMMON_HEADERS, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{BASE_URL}/api/app/new_project_list", json=payload, headers=headers
        )
        data = resp.json()
    if not data.get("success"):
        return [], 0
    return data.get("data") or [], data.get("total") or 0


async def login(username: str, password: str) -> tuple[bool, str]:
    """登录 vsqx.top，成功返回 (True, token)，失败返回 (False, 错误信息)。"""
    enc = _encrypt_password(password)
    payload = {"username": username, "enc_password": enc}
    headers = {**COMMON_HEADERS, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{BASE_URL}/api/login", json=payload, headers=headers
        )
        data = resp.json()
    if data.get("success"):
        token = data.get("token", "")
        save_token(token, username)
        return True, token
    return False, data.get("message") or "登录失败"


async def get_download_url(music_id: int, token: str) -> tuple[Optional[str], str]:
    """获取工程下载直链，返回 (url, 错误信息)。"""
    payload = {"vn": int(music_id)}
    headers = {**COMMON_HEADERS, "Content-Type": "application/json", "token": token}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{BASE_URL}/api/app/download_project", json=payload, headers=headers
        )
        data = resp.json()
    if data.get("success"):
        return data.get("data"), ""
    return None, data.get("message") or "下载失败（可能未登录或 token 已失效）"


async def fetch_bytes(url: str, timeout: float = 15) -> Optional[bytes]:
    """下载任意 URL 的二进制内容（用于封面图）。"""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=COMMON_HEADERS)
            if resp.status_code == 200:
                return resp.content
    except Exception:
        pass
    return None
