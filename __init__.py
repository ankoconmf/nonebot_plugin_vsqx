import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from nonebot import on_command, on_message, on_notice, on_regex, require

require("nonebot_plugin_htmlrender")
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    GroupUploadNoticeEvent,
    MessageEvent,
    MessageSegment,
    PrivateMessageEvent,
)
from nonebot.log import logger
from nonebot.permission import SUPERUSER
from nonebot.rule import Rule

from . import api
from .config import BASE_URL, COMMON_HEADERS, DOWNLOAD_DIR, MAX_RESULTS, SESSION_TTL
from .convert import EXPORT_FORMATS, convert_project
from .render import render_formats, render_help, render_results

# 搜索会话：key = 群号/用户id，value = {"time": ts, "keyword": str, "items": list}
_sessions: dict[int, dict[str, Any]] = {}


def _session_key(event: MessageEvent) -> int:
    gid = getattr(event, "group_id", None)
    return gid if gid is not None else event.user_id


def _clean_filename(name: str) -> str:
    """去除 Windows 非法字符。"""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "vsqx_project"


# ========== 搜索工程 ==========
search_matcher = on_regex(r"^#搜索工程\s+(.+)$", priority=5, block=True)


@search_matcher.handle()
async def handle_search(bot: Bot, event: MessageEvent):
    text = event.get_plaintext().strip()
    m = re.match(r"^#搜索工程\s+(.+)$", text)
    if not m:
        return
    keyword = m.group(1).strip()
    if not keyword:
        await search_matcher.finish("请输入要搜索的工程名，例如：#搜索工程 初音")

    try:
        items, total = await api.search_projects(keyword)
    except Exception as e:
        logger.error(f"vsqx 搜索失败: {e}")
        await search_matcher.finish("搜索出错了，请稍后再试~")

    if not items:
        await search_matcher.finish(f"没有找到与「{keyword}」相关的工程~")

    items = items[:MAX_RESULTS]
    _sessions[_session_key(event)] = {
        "time": time.time(),
        "keyword": keyword,
        "items": items,
    }

    try:
        img = await render_results(keyword, items, total)
    except Exception as e:
        logger.error(f"vsqx 渲染失败: {e}")
        await search_matcher.finish("结果渲染失败，请稍后再试~")

    await search_matcher.finish(MessageSegment.image(img))


# ========== 序号选择下载 ==========
def _has_active_session(event: MessageEvent) -> bool:
    text = event.get_plaintext().strip()
    if not text.isdigit():
        return False
    sess = _sessions.get(_session_key(event))
    if not sess:
        return False
    if time.time() - sess["time"] > SESSION_TTL:
        _sessions.pop(_session_key(event), None)
        return False
    return True


number_matcher = on_message(rule=Rule(_has_active_session), priority=10, block=True)


@number_matcher.handle()
async def handle_number(bot: Bot, event: MessageEvent):
    key = _session_key(event)
    sess = _sessions.get(key)
    if not sess:
        return
    idx = int(event.get_plaintext().strip())
    items = sess["items"]
    if idx < 1 or idx > len(items):
        await number_matcher.finish(f"序号超出范围，请发送 1~{len(items)} 之间的数字。")

    item = items[idx - 1]
    music_id = item["music_id"]
    music_name = item.get("music_name") or str(music_id)

    token = api.load_token()
    if not token:
        await number_matcher.finish(
            "尚未登录 vsqx.top，无法下载。请超级管理员私聊发送：#vsqx登录 账号 密码"
        )
        return

    url, err = await api.get_download_url(music_id, token)
    if not url:
        await number_matcher.finish(f"获取下载链接失败：{err}")
        return

    # 先发送“开始下载”、工程名和工程详情页链接
    project_link = f"{BASE_URL}/project/vn{music_id}"
    await number_matcher.send(f"开始下载「{music_name}」\n{project_link}")

    # 流式下载到本地
    try:
        file_path = await _download_to_disk(url, music_name)
    except Exception as e:
        logger.error(f"vsqx 下载文件失败: {e}")
        await number_matcher.finish("下载文件失败，请稍后再试~")
        return

    # 上传到 QQ
    try:
        if isinstance(event, GroupMessageEvent):
            await bot.call_api(
                "upload_group_file",
                group_id=event.group_id,
                file=str(file_path),
                name=file_path.name,
            )
        else:
            await bot.call_api(
                "upload_private_file",
                user_id=event.user_id,
                file=str(file_path),
                name=file_path.name,
            )
    except Exception as e:
        logger.error(f"vsqx 上传文件失败: {e}")
        await number_matcher.finish(f"文件已下载但上传失败：{e}")


async def _download_to_disk(url: str, fallback_name: str) -> Path:
    """流式下载 URL 到本地下载目录，返回文件路径。"""
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        async with client.stream("GET", url, headers=COMMON_HEADERS) as resp:
            resp.raise_for_status()
            filename = _filename_from_response(resp, url, fallback_name)
            file_path = DOWNLOAD_DIR / _clean_filename(filename)
            with open(file_path, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    f.write(chunk)
    return file_path


def _filename_from_response(resp: httpx.Response, url: str, fallback: str) -> str:
    # 优先从 Content-Disposition 取文件名
    cd = resp.headers.get("content-disposition", "")
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
    if m:
        return unquote(m.group(1))
    # 其次从 URL 路径取
    path = urlparse(url).path
    base = unquote(Path(path).name)
    if base and "." in base:
        return base
    # 兜底：用工程名 + 常见后缀
    return f"{fallback}.zip"


# ========== 超级管理员登录 ==========
login_matcher = on_command(
    "vsqx登录",
    aliases={"#vsqx登录"},
    permission=SUPERUSER,
    priority=4,
    block=True,
)


@login_matcher.handle()
async def handle_login(bot: Bot, event: MessageEvent):
    # 仅允许私聊，避免账号密码在群内泄露
    if not isinstance(event, PrivateMessageEvent):
        await login_matcher.finish("请私聊我发送该命令，避免账号密码泄露~")

    args = event.get_plaintext().strip()
    # 去掉命令头
    args = re.sub(r"^#?vsqx登录\s*", "", args).strip()
    parts = args.split()
    if len(parts) < 2:
        await login_matcher.finish("格式：#vsqx登录 账号 密码")

    username, password = parts[0], parts[1]
    try:
        ok, result = await api.login(username, password)
    except Exception as e:
        logger.error(f"vsqx 登录异常: {e}")
        await login_matcher.finish("登录请求出错，请稍后再试~")

    if ok:
        await login_matcher.finish("登录成功，已保存凭证，现在可以下载工程了~")
    else:
        await login_matcher.finish(f"登录失败：{result}")


# ========== 工程格式转换 ==========
# 转换会话：key = "group_id:user_id"，value = {stage, time, file_path, filename}
_convert_sessions: dict[str, dict] = {}


def _convert_key(group_id: int, user_id: int) -> str:
    return f"{group_id}:{user_id}"


convert_matcher = on_regex(r"^#工程转换$", priority=5, block=True)


@convert_matcher.handle()
async def handle_convert_start(bot: Bot, event: MessageEvent):
    if not isinstance(event, GroupMessageEvent):
        await convert_matcher.finish("请在群内使用该功能~")
        return
    key = _convert_key(event.group_id, event.user_id)
    _convert_sessions[key] = {"stage": "wait_file", "time": time.time()}
    await convert_matcher.finish(
        "请发送要转换的工程文件（支持 VSQX/VPR/VSQ/MID/UST/USTX/CCS/"
        "MUSICXML/SVP/S5P/DV/PPSF/TSSLN/UFDATA）"
    )


# 群文件上传：仅当发送者处于“等待文件”阶段时处理
async def _waiting_file(event: GroupUploadNoticeEvent) -> bool:
    key = _convert_key(event.group_id, event.user_id)
    sess = _convert_sessions.get(key)
    if not sess or sess.get("stage") != "wait_file":
        return False
    if time.time() - sess["time"] > SESSION_TTL:
        _convert_sessions.pop(key, None)
        return False
    return True


file_matcher = on_notice(rule=Rule(_waiting_file), priority=5, block=True)


@file_matcher.handle()
async def handle_file_received(bot: Bot, event: GroupUploadNoticeEvent):
    key = _convert_key(event.group_id, event.user_id)
    filename = event.file.name

    # 取文件下载直链
    try:
        info = await bot.call_api(
            "get_group_file_url",
            group_id=event.group_id,
            file_id=event.file.id,
            busid=event.file.busid,
        )
        url = info.get("url")
    except Exception as e:
        logger.error(f"获取群文件直链失败: {e}")
        await file_matcher.finish("获取文件失败，请重试~")
        return
    if not url:
        await file_matcher.finish("获取文件下载地址失败，请重试~")
        return

    # 下载到本地
    try:
        file_path = DOWNLOAD_DIR / _clean_filename(filename)
        raw = await api.fetch_bytes(url, timeout=60)
        if not raw:
            raise RuntimeError("空文件")
        file_path.write_bytes(raw)
    except Exception as e:
        logger.error(f"下载群文件失败: {e}")
        await file_matcher.finish("下载文件失败，请重试~")
        return

    _convert_sessions[key] = {
        "stage": "wait_format",
        "time": time.time(),
        "file_path": file_path,
        "filename": filename,
    }

    # 渲染输出格式列表
    try:
        img = await render_formats(filename, EXPORT_FORMATS)
    except Exception as e:
        logger.error(f"渲染格式列表失败: {e}")
        await file_matcher.finish("渲染格式列表失败，请稍后再试~")
        return

    await file_matcher.finish(MessageSegment.image(img))


# 转换序号选择：仅当处于“等待格式”阶段且消息为纯数字
def _waiting_format(event: MessageEvent) -> bool:
    if not isinstance(event, GroupMessageEvent):
        return False
    if not event.get_plaintext().strip().isdigit():
        return False
    key = _convert_key(event.group_id, event.user_id)
    sess = _convert_sessions.get(key)
    if not sess or sess.get("stage") != "wait_format":
        return False
    if time.time() - sess["time"] > SESSION_TTL:
        _convert_sessions.pop(key, None)
        return False
    return True


# 优先级高于搜索下载序号，避免冲突
convert_num_matcher = on_message(rule=Rule(_waiting_format), priority=9, block=True)


@convert_num_matcher.handle()
async def handle_convert_number(bot: Bot, event: GroupMessageEvent):
    key = _convert_key(event.group_id, event.user_id)
    sess = _convert_sessions.get(key)
    if not sess:
        return
    idx = int(event.get_plaintext().strip())
    if idx < 1 or idx > len(EXPORT_FORMATS):
        await convert_num_matcher.finish(
            f"序号超出范围，请发送 1~{len(EXPORT_FORMATS)} 之间的数字。"
        )
        return

    fmt = EXPORT_FORMATS[idx - 1]
    file_path: Path = sess["file_path"]
    await convert_num_matcher.send(f"正在转换为 {fmt['name']}，请稍候（约需 20 秒）…")

    try:
        out_path = await convert_project(file_path, fmt["key"])
    except Exception as e:
        logger.error(f"vsqx 工程转换失败: {e}")
        await convert_num_matcher.finish("转换失败，可能是文件格式不受支持或站点异常~")
        return

    # 转换完成，清理会话并上传结果
    _convert_sessions.pop(key, None)
    try:
        await bot.call_api(
            "upload_group_file",
            group_id=event.group_id,
            file=str(out_path),
            name=out_path.name,
        )
    except Exception as e:
        logger.error(f"上传转换结果失败: {e}")
        await convert_num_matcher.finish(f"转换完成但上传失败：{e}")


# ========== 指令帮助 ==========
HELP_COMMANDS: list[dict[str, str]] = [
    {
        "cmd": "#搜索工程 <span class='arg'>名字</span>",
        "desc": "从 vsqx.top 搜索工程，返回带序号的结果图。例：#搜索工程 初音",
    },
    {
        "cmd": "<span class='arg'>序号</span>",
        "desc": "搜索后发送对应序号，获取该工程的详情页链接并下载工程文件到群。",
    },
    {
        "cmd": "#工程转换",
        "desc": "发起格式转换：随后发送工程文件，选择目标格式即可转换（基于 UtaFormatix，支持 VSQX/UST/USTX/MIDI/SVP 等 14 种格式）。",
    },
    {
        "cmd": "#vsqx登录 <span class='arg'>账号 密码</span>",
        "desc": "登录 vsqx.top 以获取下载权限，凭证会被保存复用。",
        "badge": "仅超管 · 私聊",
    },
    {
        "cmd": "#工程帮助",
        "desc": "显示本指令说明图。",
    },
]

help_matcher = on_regex(r"^#工程帮助$", priority=5, block=True)


@help_matcher.handle()
async def handle_help(bot: Bot, event: MessageEvent):
    try:
        img = await render_help(HELP_COMMANDS)
    except Exception as e:
        logger.error(f"渲染帮助图失败: {e}")
        await help_matcher.finish("帮助图渲染失败，请稍后再试~")
        return
    await help_matcher.finish(MessageSegment.image(img))
