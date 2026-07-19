# nonebot_plugin_vsqx

基于 [NoneBot2](https://nonebot.dev/) 的 QQ 机器人插件：在群内搜索、下载 [vsqx.top](https://www.vsqx.top/project) 的歌声合成工程，并可调用 [UtaFormatix](https://sdercolin.github.io/utaformatix3) 做工程格式转换。

## 功能

- **搜索工程**：从 vsqx.top 按名字搜索，返回带序号的结果图
- **下载工程**：发送序号即可获取工程详情页链接并下载文件到群
- **格式转换**：把工程文件在 VSQX / VPR / VSQ / MID / UST / USTX / CCS / MusicXML / SVP / S5P / DV / TSSLN / UfData 等 14 种格式间互转
- **图片渲染**：搜索结果、格式列表、帮助均以美观图片呈现（htmlrender）

## 指令

| 指令 | 说明 |
|------|------|
| `#搜索工程 名字` | 搜索工程，例：`#搜索工程 初音` |
| `序号` | 搜索后发送对应序号，下载该工程 |
| `#工程转换` | 发起格式转换：随后发送工程文件 → 选目标格式序号 |
| `#vsqx登录 账号 密码` | 登录 vsqx.top 获取下载权限（**仅超级管理员，需私聊**） |
| `#工程帮助` | 显示指令帮助图 |

## 依赖

- `nonebot2` + `nonebot-adapter-onebot`（OneBot V11）
- `nonebot-plugin-htmlrender`（图片渲染，需 Playwright + Chromium）
- `httpx`（网络请求）
- `pycryptodome`（登录密码 RSA 加密）

安装 Playwright 浏览器：

```bash
playwright install chromium
```

## 使用说明

1. 将本插件目录放入 NoneBot 项目的插件目录并加载
2. 由超级管理员**私聊** bot 发送 `#vsqx登录 账号 密码` 完成登录（凭证保存在本地 `vsqx_data.json`，已被 `.gitignore` 排除）
3. 群内即可 `#搜索工程`、发序号下载、`#工程转换`

## 说明

- 工程转换基于 UtaFormatix 网页版，通过无头浏览器自动化完成，转换结果为 zip
- 接收群文件依赖 OneBot V11 的 `get_group_file_url` API，不同实现（go-cqhttp / NapCat / Lagrange）均支持

## 致谢

- [vsqx.top](https://www.vsqx.top/) — vsqx 工程配布平台
- [UtaFormatix3](https://github.com/sdercolin/utaformatix3) by [@sdercolin](https://github.com/sdercolin) — 工程格式转换（Apache-2.0）
