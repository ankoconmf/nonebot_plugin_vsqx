from pathlib import Path

# 插件数据目录（token 持久化、临时下载文件）
PLUGIN_DIR = Path(__file__).parent
DATA_FILE = PLUGIN_DIR / "vsqx_data.json"
DOWNLOAD_DIR = PLUGIN_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# 站点地址
BASE_URL = "https://www.vsqx.top"
COVER_BASE = "https://vsqx-cover.vsqx.top"
ASSETS_BASE = "https://vsqx-assets.vsqx.top"

# 通用请求头
COMMON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Origin": BASE_URL,
    "Referer": BASE_URL + "/",
}

# 登录使用的 RSA 公钥（从站点前端 app.js 中提取，RSA-OAEP 加密密码）
LOGIN_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAo83J1IOC2DcICFTDJA5w
Dn12Vt0Fl09hHN2ZPk2o2rud8po3LiDIs2HzJgnCjZoDbUC8yl3nwJw8/N+3mOC6
5PLwK8AxNrESO4IiVd3cyf+GFnJbcRMEB1/UYpC7r7UFvckW19SXiZzqjmg6w32N
W8OSGOxKBo9aDP/wkKTOveasVRfy4YTxNNeyq4jVroCRqgd05ca4UtW5Yk/eCAvO
0QfP5sRPm9C9RmzL/1xdePeKn5GNjQNe2D0AaELYOlQNtnLR51Gvjxyi8gD1Wy/w
WmZ914FT+pR5iSr/zIoMhtRH3vBCYddBEJ52nLKFy6jK/uPr+hrDot6rdlVZnH9Q
TQIDAQAB
-----END PUBLIC KEY-----"""

# 每次搜索最多展示的结果条数
MAX_RESULTS = 10

# 搜索会话有效期（秒），超时后发送序号不再触发下载
SESSION_TTL = 300
