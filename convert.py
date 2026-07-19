import asyncio
from pathlib import Path

from nonebot.log import logger
from nonebot_plugin_htmlrender import get_browser

from .config import DOWNLOAD_DIR

UTAFORMATIX_URL = "https://sdercolin.github.io/utaformatix3"

# 导出格式表：key = 页面格式卡标题（用于点击），name = 展示名，desc = 说明
EXPORT_FORMATS: list[dict] = [
    {"key": "Vsqx", "name": "VSQX", "desc": "VOCALOID4 工程"},
    {"key": "Vpr", "name": "VPR", "desc": "VOCALOID5 工程"},
    {"key": "Vsq", "name": "VSQ", "desc": "VOCALOID2 工程"},
    {"key": "Mid (VOCALOID)", "name": "MID (VOCALOID)", "desc": "VOCALOID1 工程"},
    {"key": "Mid (Standard)", "name": "MID (Standard)", "desc": "标准 MIDI 文件"},
    {"key": "Ust", "name": "UST", "desc": "UTAU 工程"},
    {"key": "Ustx", "name": "USTX", "desc": "OpenUtau 工程"},
    {"key": "Ccs", "name": "CCS", "desc": "CeVIO 工程"},
    {"key": "MusicXml", "name": "MusicXML", "desc": "MusicXML 2.0（CeVIO 标准）"},
    {"key": "Svp", "name": "SVP", "desc": "Synthesizer V Studio 工程"},
    {"key": "S5p", "name": "S5P", "desc": "Synthesizer V 工程"},
    {"key": "Dv", "name": "DV", "desc": "DeepVocal 工程"},
    {"key": "Tssln", "name": "TSSLN", "desc": "VoiSona 工程"},
    {"key": "UfData", "name": "UfData", "desc": "UtaFormatix 数据格式（v1）"},
]


async def convert_project(input_path: Path, fmt_key: str) -> Path:
    """用 utaformatix3 网页把 input_path 转换为 fmt_key 指定格式，返回导出文件（zip）路径。

    fmt_key 为 EXPORT_FORMATS 里的 key（即页面格式卡标题）。
    整个流程跑在无头浏览器里，失败会抛异常。
    """
    browser = await get_browser()
    ctx = await browser.new_context(accept_downloads=True)
    page = await ctx.new_page()
    try:
        await page.goto(UTAFORMATIX_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2000)

        # 1. 上传工程文件
        async with page.expect_file_chooser(timeout=15000) as fc_info:
            await page.click(".file-drop-target")
        fc = await fc_info.value
        await fc.set_files(str(input_path))

        # 若有导入警告弹窗（如缺节拍记号），尝试关闭 / 继续
        await _dismiss_dialog(page)

        # 2. 选择输出格式：等待格式卡出现（工程解析可能较慢），再点击
        fmt_card = page.get_by_text(fmt_key, exact=True).first
        await fmt_card.wait_for(timeout=30000)
        await fmt_card.click()

        # 3. 设置页 → 下一步（使用默认设置）
        next_btn = page.get_by_role("button", name="下一步")
        try:
            await next_btn.wait_for(timeout=10000)
            await next_btn.click()
        except Exception:
            # 极少数格式可能没有设置页，忽略
            pass

        # 4. 导出并抓取下载：等导出按钮出现再点
        export_btn = page.get_by_role("button", name="导出")
        await export_btn.wait_for(timeout=15000)
        async with page.expect_download(timeout=60000) as dl_info:
            await export_btn.click()
        download = await dl_info.value

        out_name = download.suggested_filename or f"{input_path.stem}_{fmt_key}.zip"
        out_path = DOWNLOAD_DIR / out_name
        await download.save_as(str(out_path))
        logger.info(f"utaformatix 转换完成: {out_path}")
        return out_path
    finally:
        await ctx.close()


async def _dismiss_dialog(page) -> None:
    """尝试关闭导入过程中的警告对话框（若存在）。"""
    for label in ("确定", "确认", "OK", "继续", "知道了"):
        try:
            btn = page.get_by_role("button", name=label)
            if await btn.count() > 0:
                await btn.first.click(timeout=1500)
                await page.wait_for_timeout(500)
                return
        except Exception:
            continue
