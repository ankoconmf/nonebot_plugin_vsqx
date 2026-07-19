import asyncio
import base64
from pathlib import Path

from nonebot_plugin_htmlrender import template_to_pic

from .api import cover_url, fetch_bytes, project_type

TEMPLATE_DIR = Path(__file__).parent / "templates"

# 封面加载失败时的占位图（浅灰 + 音符），内嵌 SVG data URI
_PLACEHOLDER = (
    "data:image/svg+xml;base64,"
    + base64.b64encode(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="88" height="88">'
        b'<rect width="88" height="88" rx="14" fill="#e0e4ec"/>'
        b'<text x="44" y="58" font-size="40" fill="#aab0bd" '
        b'text-anchor="middle" font-family="sans-serif">&#9835;</text></svg>'
    ).decode()
)


async def _cover_data_uri(item: dict) -> str:
    """下载封面并转为 base64 data URI，失败则用占位图。"""
    raw = await fetch_bytes(cover_url(item), timeout=10)
    if not raw:
        return _PLACEHOLDER
    b64 = base64.b64encode(raw).decode()
    return f"data:image/jpeg;base64,{b64}"


async def render_results(keyword: str, items: list[dict], total: int) -> bytes:
    """用 htmlrender 渲染搜索结果图，返回 PNG 字节。"""
    covers = await asyncio.gather(*(_cover_data_uri(it) for it in items))
    view_items = []
    for it, cover in zip(items, covers):
        view_items.append(
            {
                "music_name": it.get("music_name") or "(无标题)",
                "p_name": it.get("p_name") or "未知",
                "ptype": project_type(it),
                "download_num": it.get("download_num", 0),
                "click_num": it.get("click_num", 0),
                "tag": it.get("tag") or "",
                "cover": cover,
            }
        )

    return await template_to_pic(
        template_path=str(TEMPLATE_DIR),
        template_name="search.html",
        templates={"keyword": keyword, "items": view_items, "total": total},
        type="png",
        device_scale_factor=2,
    )


async def render_formats(filename: str, formats: list[dict]) -> bytes:
    """渲染输出格式选择列表图，返回 PNG 字节。"""
    return await template_to_pic(
        template_path=str(TEMPLATE_DIR),
        template_name="formats.html",
        templates={"filename": filename, "formats": formats},
        type="png",
        device_scale_factor=2,
    )


async def render_help(cmds: list[dict]) -> bytes:
    """渲染指令帮助图，返回 PNG 字节。"""
    return await template_to_pic(
        template_path=str(TEMPLATE_DIR),
        template_name="help.html",
        templates={"cmds": cmds},
        type="png",
        device_scale_factor=2,
    )
