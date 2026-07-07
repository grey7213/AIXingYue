# AI星月 Web 对齐 RiliaiChat 任务

| ID | 任务 | 状态 | 验证 |
|----|------|------|------|
| RP1 | 补齐功能对齐需求与设计 SPEC | Done | `riliai-parity-requirements.md`、`riliai-parity-design.md`、本任务表 |
| RP2 | 增加后端收藏、日志、奖励、图片聊天、home stats API | Done | `D:\Anconda3\python.exe -m py_compile .\tools\ai_fengyue_local_server.py .\tools\deploy_ai_fengyue_villainy.py`；线上注册/登录/奖励/图片聊天/日志 API 成功 |
| RP3 | 增强探索接口支持 tag/sort/rank/pictureless 参数 | Done | `/go/api/explore/search?page=1&page_size=3&sort=popular` 返回 3 条；`pictureless=1` 返回无图卡且 `cover/icon` 为空 |
| RP4 | 建立共享 App Shell 导航与页面组件样式 | Done | 2026-06-18 全部 `/app/*.html` 使用 `data-app-sidebar` / `data-app-bottom-nav`；旧 `chat/create/my-apps/me/character` 已接入 `injectLayout()` |
| RP5 | 改造 Home/Explore 为参考站同类发现体验 | Done | `/app/` 与 `/app/explore.html` 有搜索、Daily/Weekly/Monthly/Overall、Random/Popular/Latest/Updated、Pictureless、分类、收藏按钮 |
| RP6 | 新增 Workshop/Histories/Favorites/Image Chat/Rewards/Logs/Info 页面 | Done | `/app/workshop.html`、`histories.html`、`favorites.html`、`image-chat.html`、`rewards.html`、`logs.html`、`info.html` 均 HTTP 200 |
| RP7 | 部署到 `patcher.villainy.top` | Done | `D:\Anconda3\python.exe .\tools\deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot` 成功；`ai-fengyue-backend.service` 和 `nginx` active；`/health` OK；`CONTENT_MODE=local_only` |
| RP8 | 线上 API 和浏览器截图验收 | Done | API 摘要：本地库 `apps.total=451`、探索 3 条、Pictureless 3 条；浏览器截图见 `output\riliai-parity-final-explore-desktop.png`、`output\riliai-parity-final-home-mobile.png`、`output\riliai-parity-final-chat-desktop.png` |
| RP9 | 优化 `/app/` 首页首屏加载 | Done | 2026-06-29 列表接口改为轻量卡片、首页并发加载、去掉 Tailwind CDN、Alpine 本地化、预加载默认第一页和模块依赖；线上浏览器首张卡约 `1795ms`，列表约 `10.9KB`，无 console/page error |
| RP10 | 图片聊天接入真实图片模型 | Done | `/console/api/web/image-chat` 从占位日志改为可调用后台图片模型配置；后台可维护 Base URL、模型名、API Key、尺寸、返回格式和超时，返回 URL/base64 图片并展示在 `/app/image-chat.html`。线上真实图片生成返回 `mode=image_model`、`model=gpt-image-2`、有图片 URL 且文件存在。 |
| RP11 | 纯净发现区、收藏入口和创作者运营面板 | Done | 2026-07-07 默认发现页和榜单进入纯净区，搜索/全库可主动扩展；聊天页补收藏入口；创作工坊展示定期比赛和创作者排行榜；玩家可给角色加私有标签并在历史/收藏中展示。线上 Playwright 移动端验证通过，公开 API 验证 `zone=clean` 与 `zone=all` 总数不同且比赛接口返回“本期创作者比赛”。 |

## 2026-07-05 图片聊天真实图片模型

- 后台“模型配置”新增图片模型配置，支持启用状态、显示名称、Base URL、端点路径、模型名、尺寸、返回格式、图片数量、超时、质量参数和 API Key；管理员读取时只返回 Key 状态/预览，普通用户接口不暴露图片模型和 Key。
- `/console/api/web/image-chat` 已改为在图片模型配置完整时调用 OpenAI-compatible `/images/generations`；支持 provider 返回 `url`、`b64_json`、`base64`、`data_url`，base64 会保存到 `/media-cache/generated/` 后返回可访问 URL。
- 线上 CelestiAI 模型探测后选择 `gpt-image-2` 作为默认图片模型；`gpt-image-1` 对当前 token 无访问权限，因此没有作为默认值。
- 验证：本地 `verify_image_memory_local.py` 通过图片保存和路径调用断言；线上 `verify_image_memory_remote.py` 确认后台图片模型已启用、Key 脱敏且公开模型列表无 Key；`verify_real_image_chat_remote.py` 返回 `status=200`、`ok=true`、`mode=image_model`、`model=gpt-image-2`、`has_image_url=true`、`image_file_exists=true`；浏览器 `verify_image_memory_browser.py` 确认图片聊天页和后台面板无 console/page error，截图 `output/playwright/image-chat-model-20260705.png`。

## 2026-06-18 验收记录

- 页面 HTTP：`/app/`、`workshop`、`histories`、`favorites`、`image-chat`、`rewards`、`logs`、`info`、`explore`、`chat`、`create`、`my-apps`、`me`、`character` 全部返回 `200 text/html; charset=utf-8`。
- API：一次性账号验证了注册前登录失败、邮件码发送成功、错误验证码注册失败、正确验证码注册成功、登录成功、每日奖励成功、图片聊天成功、日志写入成功。
- 服务：远端 `systemctl is-active ai-fengyue-backend.service nginx` 均为 `active`，`curl http://127.0.0.1:8008/health` 为 `OK`。
- 浏览器：桌面端 Home/Explore 显示统一侧栏；移动端 Home 显示底部 Home/Chat/Create/Favs/Me；旧页面 `chat/create/my-apps/me/character` 清空浏览器错误后逐页打开无新增 JS 错误。
- 修复：`my-apps.html` 编辑弹窗从 `x-show="editing"` 改为 `template x-if="editing"`，避免 `editing=null` 时 Alpine 求值 `editing.name` 等字段。

## 2026-06-29 首页加载优化记录

- 后端 `/go/api/explore/search` 首页列表改用 `list_local_apps(..., lightweight=True)` 和 `local_app_to_list_card()`，只返回 id、名称、简介、封面、标签、状态、计数和时间等列表字段，不返回 `opening_statement`、`pre_prompt`、`world_info`、`regex_scripts`、`extensions`、`alternate_greetings` 等详情重字段。
- 前端 `/app/` 的 `explore.js` 将站点配置、用户资料/积分/统计、角色列表并发加载；默认第一页 page size 从 20 降为 12，并用 `total` 判断 `hasMore`。
- 首页去掉 `https://cdn.tailwindcss.com`，补齐所需本地 CSS 工具类；Alpine 3.14.1 固定为 `/app/assets/vendor/alpine-3.14.1.min.js`，首页不再依赖 jsdelivr。
- 首页 `<head>` 预加载默认第一页、Alpine、本地模块依赖；`api.exploreSearch()` 对公开探索接口不再发送无用 Authorization 头，便于浏览器复用预加载。
- 验证：`node --check frontend\app\assets\js\explore.js` 和 `node --check frontend\app\assets\js\app-core.js` 通过；`D:\Anconda3\python.exe -m py_compile tools\ai_fengyue_local_server.py output\verify_home_fast_browser.py` 通过；线上 `/app/` HTML 无 Tailwind/jsdelivr 外链，包含本地 Alpine、fetch preload、modulepreload 和 `home-fast4`。
- 线上浏览器验证：`D:\Anconda3\python.exe .\output\verify_home_fast_browser.py` 返回 `domcontentloaded_ms=1708`、`first_card_ms=1795`、`card_count=12`、`explore_payloads[0].bytes=10902`、`first_has_heavy_fields=false`、`console_error_count=0`、`page_error_count=0`；截图 `output\playwright\home-fast-live.png`。
- 部署验证：`ai-fengyue-backend.service` 与 `nginx` 均 active，公网 `/health` 返回 `OK`，`CONTENT_MODE=local_only`。

## 剩余说明

- 角色库内容来自现有 AI星月本地数据库，部分卡片文案带成人向内容；本次没有清洗或替换既有角色数据。
