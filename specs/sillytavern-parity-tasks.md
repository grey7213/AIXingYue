# AI星月 SillyTavern 能力补齐任务

Updated: 2026-07-02

| ID | 任务 | 状态 | 验证 |
|----|------|------|------|
| ST0 | 修复每日签到无限领取积分 | Done | 线上临时用户验证：初始 `1000`；第一次 `/console/api/ctf/dailyapppoints` `points_added=10` 且余额 `1010`；第二次旧接口 `points_added=0`；第三次 `/console/api/web/rewards/daily` `points_added=0`；奖励状态 `claimed=true` |
| ST1 | 流式输出基础能力 | Done | 线上 `/console/api/web/chat/stream` 返回 SSE：`start=true`、`delta_events=3`、`message_end=true`；线上 `chat.js` 已调用 `sendChatStream()` |
| ST2 | 真模型端 `stream:true` 透传 | Done | 本地假上游验证 payload `stream=true`、模型名 `gpt-real`、chunks `["你","好"]`；线上临时假上游验证 `upstream_called=true`、`upstream_stream_true=true`、`upstream_model=gpt-stream-real`、`delta_events=3`、`reply_saved=true`；临时用户/角色/消息清理后计数为 0 |
| ST3 | Prompt Manager | Done | 线上远程验证：创建角色返回 `detail_prompt_blocks=3`；`system_before/system_after/post_history` 均注入；上游 payload `stream=true`、模型 `gpt-prompt-real`；SSE 有 `message_end` |
| ST4 | 高级世界书 | Done | 本地与线上导入后端验证：优先级顺序、`probability=0` 排除、二级关键词命中、`post_history` 注入、`depth` 插入、递归扫描均为 true；线上创建页包含二级关键词/插入深度/递归扫描字段 |
| ST5 | 角色卡 V2/PNG 全兼容 | Done | 线上 API E2E：PNG `card_file` 导入成功，`export-png` 返回 PNG data URL；反解析后 `creator/extensions`、二级关键词、depth position、`probability=0`、recursive 均保留 |
| ST6 | 群聊 | Done | 线上 API E2E：创建 2 角色群、用户发言后角色 A 自动回复、指定角色 B 回复、详情/列表可见、删除成功；截图 `output/playwright/group-chat-st6.png` 验证页面渲染 |
| ST7 | 用户 BYOK/多供应商连接器 | Disabled | 2026-06-29 按运营要求关闭普通用户自定义 API 接入；用户页移除连接器，创建页只选站点模型，后端默认拒绝保存用户模型并让旧 `user:*` 引用回落站点模型 |
| ST8 | 长期记忆与自动摘要 | Done | 本地 payload 验证 `summary_injected=true`、`memory_injected=true`；线上 E2E：记忆保存、摘要保存、假上游收到 `model=gpt-st8-real` 且 `stream=true`，payload 含 `【对话摘要】` 和 `【长期记忆】`，SSE `delta_count=2`，最终回复 `ST8 OK`，`auto_summary_created=true`；截图 `output/playwright/chat-memory-st8.png` 无浏览器错误 |
| ST9 | 媒体与扩展能力 | Done | 线上 E2E：Quick Reply/Regex 字段保存回读成功；假上游收到 `model=gpt-st9-real` 且 `stream=true`；Regex 将流式回复 `Hello SECRET` 处理为 `Hello 星月`，前端 delta 和最终保存回复均无 `SECRET`；截图 `create-extensions-st9.png`、`chat-media-extensions-st9.png` 无浏览器错误，语音输入/朗读/快捷回复按钮存在 |
| ST10 | Tavo/高级 HTML 可视化渲染兼容 | Done | 2026-06-29 `/app/chat.html` 已新增受限 iframe 渲染层：fenced/raw HTML 只进入 `iframe sandbox="allow-scripts"` 的 `srcdoc`，不加 `allow-same-origin`；`srcdoc` 注入 CSP 禁止网络连接、子 frame、object、form 和外部脚本；主聊天 DOM 不插入卡内 `<script>`。本地浏览器验证截图 `output/playwright/chat-tavo-sandbox-local.png` |
| ST11 | 聊天加载占位和 XML 状态面板格式化 | Done | 2026-06-29 修复流式回复时“空白 assistant 气泡 + 独立加载气泡”重复显示；正在生成时只保留一个 assistant loading 气泡并隐藏操作条；`<battle_status_panel>` 等 XML 状态面板渲染为中文状态卡。线上验证 `verify_chat_panel_fix_browser.py` 通过 |
| ST12 | first_mes 多开头拆分为 SillyTavern alternate greetings/swipes | Done | 2026-06-29 后端导入和新对话启动都会识别 `## U1/U2`、`## P1/P2`、`## Opening 1`、`## 开场1` 等多开头 Markdown 段落；首条 assistant 只显示第一个开头，其余进入同一消息的 `swipes`。线上存量修复备份 `/opt/ai-fengyue-backend/data/ai_fengyue.sqlite3.bak-silly-openings-20260629-154616`，角色卡字段已修复，旧会话首条 assistant 开场命中 2 条并拆为 swipe；远程 API 验证 `swipe_count=4`、`first_has_u2=false`、`next_swipe_has_u2=true`，临时数据清理为 0 |
| ST13 | Prompt Template / 酒馆助手全局效果 | Done | 2026-07-01 新增受限 EJS-like 模板解释器和 `template_variables`，支持 `<% if %>`、`<% for %>`、`<%- expr %>`、`getvar/setvar`；系统提示、Prompt Manager、世界书、记忆、开场白、历史、输入、回复后处理、重生成、swipe 和群聊均接入；世界书支持 `@@if`、`[GENERATE:*]` 和基础 `@INJECT`。线上 E2E 返回 `remote_template_payload=true`、`remote_world_injections=true`、`remote_reply=Hello 星月`、`remote_affinity=10`，临时数据清理为 0 |
| ST14 | 三个插件明确补齐：酒馆助手、提示词模板、提示词模板语法 | Done | 2026-07-01 按插件文档补齐安全子集：变量别名/增减/删除/插入、`injectPrompt/getPromptsInjected`、`getwi/getchar`、`[InitialVariables]`、`[RENDER:*]`、`@INJECT target/index/at`、JS 常见表达式、TavernHelper Regex 导入提升；线上假上游 E2E 与 7 个真实 Gemini model_id 全量 E2E 均通过 |
| ST15 | `角色卡下载.zip` 全量可用角色卡导入 | Done | 2026-07-01 按用户要求不做题材筛选；3,304 个 PNG/JSON 候选中 2,695 个有 metadata，2,137 个可用角色卡导入为公开官方卡，558 个空壳/配置类与 609 个无 metadata 文件未导入；970 张保留并提升 Regex/TavernHelper 脚本，2,027 个封面上传；线上验证 `expected_found=2137`、`empty_imported=0`、样本详情/封面/流式聊天通过，总官方卡数 2,255 |
| ST16 | 正则后最终回复格式规范 | Done | 2026-07-02 后端在 Prompt Template / `[RENDER:*]` / Regex 之后清洗最终可见回复，移除英文过程标题、JSON 包裹和推理标签；流式解析丢弃 `reasoning_content`；前端 assistant 历史同样清洗。线上假上游 E2E 和浏览器验证通过 |
| ST17 | Tavo 高级渲染设置与 TavoJS 兼容桥 | Done | 2026-07-02 `/app/chat.html` 新增高级渲染设置；支持 HTML/CSS 渲染开关、JavaScript `disabled/auto/script/code-block` 模式、TavoJS 执行确认和 LaTeX/AsciiMath 轻量显示；TavoJS 兼容桥只存在于 sandbox iframe 内。线上验证 `sandbox_has_same_origin=false`、`tavo_bridge_ok=true`、`raw_script_ran=false`、`fenced_script_ran=true`、console/page error 为 0 |
| ST18 | HTML 代码注入器片段兼容 | Done | 2026-07-02 修复片段开头 `<style>/<script>` 被 DOMParser 移入 head 后早于 `.mes_text` 执行的问题；iframe 内提供 `#chat/.mes/.mes_text/.message-content` 兼容目标；线上验证 `injector_ran=true`、`unclosed_fence_ran=true`、`event_only_ran=true`，安全沙箱仍无 same-origin |

## 2026-07-01 角色卡下载包导入

- Source archive: `E:\xd高级动效\角色卡下载.zip`; AES password `123`.
- Local artifacts:
  - `output\role-card-download-import\import-bundle.json`
  - `output\role-card-download-import\import-summary.json`
  - `output\role-card-download-import\covers.tar.gz`
  - `output\prepare_role_card_download_import.py`
  - `output\import_role_card_download_remote.py`
  - `output\verify_role_card_download_remote.py`
- Import policy: no topic filtering; only skip files without recognizable Character Card metadata and parsed payloads that are empty shells or script/config/workflow-only.
- Results: 2,137 imported public/admin cards, 970 with non-empty promoted `regex_scripts`, 2,119 preserving `extensions`, 2,036 with world info, and 1,013 with alternate greetings.
- Remote DB backup before import: `/opt/ai-fengyue-backend/data/ai_fengyue.sqlite3.bak-role-card-download-20260701-140213`.
- Verification: remote Python E2E returned `expected_found=2137`, `public_found=2137`, `empty_imported=0`, sample detail OK, sample cover HTTP 200, streaming chat `message_end=true`, `chat_delta_count=24`, points `5000 -> 4950`, temporary user cleanup 0. Service and Nginx remained active, public `/health` returned OK, and `/go/api/explore/search` reported total 2,255 with lightweight payload.

## 2026-07-02 正则后回复格式规范

- 现象：实际聊天中，部分 Gemini/导入角色卡回复会出现英文过程标题（如 `Processing Initial Inputs` / `Narrative Flow`）和 JSON 包裹；带 Regex/TavernHelper 的角色尤其容易把这些脏结构作为最终可见内容渲染出来。
- 修复：`tools/ai_fengyue_local_server.py` 的系统提示明确禁止推理/计划/JSON/英文过程标题；流式解析不再把上游 `reasoning_content` 当正文；`process_model_reply()` 在 Prompt Template、世界书 `[RENDER:*]` 和角色 Regex 全部执行后，再调用 `normalize_visible_chat_reply()` 只保留最终可见回复。
- 前端兼容：`frontend/app/assets/js/chat.js` 对 assistant 历史消息执行同一展示级清洗，用户消息不清洗；`frontend/app/chat.html` 引用 `chat.js?v=20260702-reply-format`。
- 验证：本地 `output/verify_reply_format_local.py` 覆盖英文过程标题、JSON/fenced JSON、Regex 后清洗、状态块/HTML 保留和 `reasoning_content` 丢弃；线上 `/tmp/verify_reply_format_remote.py` 临时假上游返回 `reasoning_content + fenced JSON`，最终 delta 和数据库保存均为 `你好 星月`，临时用户/角色/消息清理为 0；浏览器 `output/verify_reply_format_browser.py` 返回 `bubble_text=你好，星月。`、console/page error 为 0，截图 `output/playwright/chat-reply-format-live.png`。

## 2026-07-02 Tavo 高级渲染设置

- 修复：`frontend/app/chat.html` 新增“高级渲染”工具面板，包含高级渲染开关、JavaScript 支持模式、TavoJS 操作确认和公式渲染开关；`frontend/app/assets/js/chat.js` 将设置持久化到本地浏览器。
- TavoJS 兼容桥：iframe 内提供 `window.TavoJS` / `window.tavo` / `window.Tavo`，支持本地 `getVar/setVar/getState/setState/on/emit/resize/notify/confirm` 等有限能力。桥接不暴露主页面 DOM、localStorage、token、平台 API、同源权限或网络访问。
- 安全边界：高级内容仍进入 `iframe srcdoc`；确认后脚本 iframe 只给 `sandbox="allow-scripts"`，不加 `allow-same-origin`；禁用脚本时 iframe `sandbox=""` 且 `script-src 'none'`；CSP 继续禁止 `connect/frame/object/form` 和外部脚本/资源。
- 公式显示：不引入外部 CDN，支持 `\(...\)`、`$$...$$`、```math/latex/asciimath``` 的轻量安全显示。
- 验证：本地和线上 `output/verify_tavo_advanced_render_browser.py` 均通过，关键结果为 `default_confirm_paused=true`、`settings_persisted=true`、`tavo_bridge_ok=true`、`tavo_bridge_value=7`、`sandbox_has_same_origin=false`、`parent_can_read_frame=false`、`disabled_srcdoc_has_script=false`、`raw_script_ran=false`、`fenced_script_ran=true`、`formula_inline=true`、console/page error 为 0；旧 `output/verify_tavo_sandbox_browser.py` 线上回归也通过。

## 2026-07-02 HTML 代码注入器兼容修复

- 现象：高级渲染开关已开启，但部分 HTML 代码注入器没有可见效果，尤其是片段以 `<style>` 或 `<script>` 开头，并在脚本里查找 `.mes_text`、`#chat` 等 SillyTavern 消息目标时。
- 原因：浏览器 `DOMParser.parseFromString(..., 'text/html')` 会把片段开头的 `<style>/<script>` 自动移动到 iframe `<head>`；这些脚本在 body 和 `.mes_text` 兼容目标创建前运行，目标为空。另有部分模型输出 ` ```html injector ` 或未闭合最终 code fence，旧检测没有稳定识别。
- 修复：非完整 HTML 片段的 parsed head 内容会放回 iframe body 兼容容器内执行；iframe body 内提供 `#chat`、`.mes`、`.mes_text`、`.message-content`、`.tavo-content` 等目标；HTML fence 语言取首个 token，最后一个未闭合 fence 也会被解析；`script` 模式允许事件属性和 `javascript:` 可执行片段，但仍只在 `sandbox="allow-scripts"` 且无 `allow-same-origin` 的 iframe 中运行。
- 验证：本地和线上 `output/verify_tavo_advanced_render_browser.py` 返回 `injector_ran=true`、`injector_text_has_result=true`、`unclosed_fence_ran=true`、`event_only_ran=true`，同时 `sandbox_has_same_origin=false`、`parent_can_read_frame=false`、`main_script_count=0`；线上 `output/verify_tavo_sandbox_browser.py` 旧沙箱回归通过。

## 2026-06-26 验证摘要

- 本地：`D:\Anconda3\python.exe -m py_compile .\tools\ai_fengyue_local_server.py` 通过。
- 本地：`node --check` 校验 `app-core.js`、`chat.js`、`me.js`、`dashboard-app.js` 通过。
- 本地：`D:\Anconda3\python.exe .\output\verify_provider_protocol_local.py` 验证 OpenAI 阻塞/流式返回 `OPENAI OK/OPENAI STREAM`，Anthropic 阻塞/流式返回 `ANTHROPIC OK/ANTHROPIC STREAM`，Anthropic 请求命中 `/messages` 且使用 `x-api-key`/`anthropic-version`，用户连接器 `protocol=anthropic` 可保存，后台多模型预设展开为 2 个模型且第二模型还原为 `gpt-b`。
- 部署：`D:\Anconda3\python.exe .\tools\deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot` 成功。
- 线上：`ai-fengyue-backend.service`、`nginx` 均 active，`/health` 返回 OK。
- 2026-06-26 ST2：部署后 `https://patcher.villainy.top/console/api/web/model-presets` 恢复原预设 `default/gpt-4o-mini`；`CONTENT_MODE=local_only`；远程临时真流式验证通过并已清理。
- 2026-06-26 ST3：修正验证脚本先保存 persona 后，远程 Prompt Manager 验证通过：3 个提示词块保存回读，system 前置、system 后置、历史后块均进入 OpenAI-compatible payload，真流式请求和 SSE 结束事件正常。
- 2026-06-26 ST4：高级世界书上线。`D:\Anconda3\python.exe .\output\verify_advanced_world_info.py` 本地通过；远程 `SERVER_PATH=/opt/ai-fengyue-backend/ai_fengyue_local_server.py python3 /tmp/verify_advanced_world_info.py` 通过；部署后 `ai-fengyue-backend.service`、`nginx` active，`/health` OK，`CONTENT_MODE=local_only`。
- 2026-06-26 ST5：PNG 角色卡导入/导出上线。`verify_card_png_metadata.py` 本地与远程函数级 round-trip 通过；`verify_card_png_api_remote.py` 通过线上 API E2E，临时用户上传 PNG metadata 角色卡、导出 PNG、反解析 metadata 后关键字段保留，测试数据已清理。
- 2026-06-26 ST6：群聊上线。`verify_group_chat_remote.py` 通过线上 API E2E，返回 `created_members=2`、`send_message_count=2`、`manual_message_count=3`、`has_role_a=true`、`has_role_b=true`、`deleted=true`；`/app/group-chat.html` 和 `group-chat.js` 已在线；Playwright/Chrome 截图 `output/playwright/group-chat-st6.png` 显示群聊入口、创建面板和角色列表正常渲染。
- 2026-06-26 ST7：用户 BYOK 上线。`verify_user_byok_remote.py` 通过线上 E2E，返回 `preset_saved=true`、`api_key_redacted=true`、`app_model=user:codex-byok`、`upstream_model=gpt-user-real`、`upstream_auth_user_key=true`、`reply=BYOK OK`；修复阻塞 OpenAI response `choices[0].message.content` 解析；`check_byok_cleanup.py` 确认临时用户/角色/preset 均为 0；Playwright/Chrome 截图 `output/playwright/me-byok-st7.png` 显示“我的模型连接器”正常渲染。
- 2026-06-26 ST7 补强：模型连接器和管理员预设新增 `protocol=openai|anthropic`；OpenAI-compatible 调 `/chat/completions`，Anthropic-compatible 调 `/messages` 并使用 `x-api-key`/`anthropic-version`。本地 `output/verify_provider_protocol_local.py` 验证 OpenAI/Anthropic 阻塞与流式均通过；线上 `verify_provider_protocol_remote.py` 验证真实后端通过用户 BYOK 调用远程假 Anthropic 上游，返回 `REMOTE ANTHROPIC`，`path_ok/auth_ok/model_ok/stream_true/system_top_level` 均为 true。Playwright 截图 `output/playwright/me-provider-protocol.png` 验证“添加 Anthropic/Claude”后供应商和协议下拉显示正确且无 console error。
- 2026-06-29 ST7 状态调整：普通用户 BYOK 不再作为产品入口开放。保留管理员多模型/多协议预设能力；用户侧 `/console/api/web/provider-templates` 返回空列表，`/console/api/web/user-model-presets` GET 返回空/disabled，POST 返回 403。历史角色中的 `llm_model=user:*` 不再触发用户 Key 调用，会回落到站点默认模型。
- 2026-06-26 ST8：长期记忆与自动摘要上线。新增 `chat_memories`、`conversation_summaries`，新增 `/console/api/web/memories` 与 `/console/api/web/conversations/{id}/summary`；`build_user_llm_request()` 会把 `【对话摘要】` 和命中的 `【长期记忆】` 插入 OpenAI-compatible messages。本地 `verify_st8_memory_local.py` 返回 `summary_injected=true`、`memory_injected=true`、`system_context_count=3`；线上 `verify_st8_memory_remote.py` 返回 `memory_saved=true`、`summary_saved=true`、`upstream_stream=true`、`summary_injected=true`、`memory_injected=true`、`delta_count=2`、`reply=ST8 OK`、`auto_summary_created=true`；Playwright/Chrome 截图 `output/playwright/chat-memory-st8.png` 显示聊天页记忆抽屉正常渲染且浏览器错误为 0。
- 2026-06-26 ST9：媒体与扩展上线。角色卡 `extra_settings` 支持 `quick_replies` 和 `regex_scripts`；创建页“高级提示词”可编辑快捷回复和 Regex，聊天页渲染 Quick Reply 按钮，assistant 消息支持浏览器朗读，输入框支持浏览器语音输入，图片聊天维持占位记录接口。线上 `verify_st9_extensions_remote.py` 返回 `quick_reply_roundtrip=true`、`regex_roundtrip=true`、`upstream_model=gpt-st9-real`、`upstream_stream=true`、`regex_reply=Hello 星月`、`regex_delta_text=Hello 星月`、`secret_removed=true`；截图 `output/playwright/create-extensions-st9.png`、`output/playwright/chat-media-extensions-st9.png` 验证 UI 渲染，浏览器错误为 0。

## 2026-06-29 Tavo 高级渲染样本卡实测

- 样本卡来源：用户提供的 PNG 角色卡，解析结果保存在 `output\sillytavern-tavo-check\card-summary.json` 和 `output\sillytavern-tavo-check\card-metadata.json`；不在文档中复写卡片正文。
- 临时 SillyTavern：`E:\_codex_tmp\sttavo\SillyTavern`，Node `22.17.1`，监听 `http://127.0.0.1:8000/`。因 Windows 中文路径会导致启动异常，实际运行在 ASCII 临时目录。
- 依赖修复：npm 临时安装的 `webpack@5.108.1` 会导致 `/lib.js` 构建失败；锁定 `webpack@5.105.4` 后 SillyTavern 正常启动。
- 角色卡事实：`extensions.regex_scripts` 共 7 条，包括双语对话、状态栏美化、开局可视化；内置 `character_book` 可由 SillyTavern 导入为世界书。
- 实测结果：SillyTavern 选择角色后弹出内置 regex 确认，点击确定后 regex 生效；随后导入内置 worldbook；回到聊天区后，开场消息被 `开局可视化` 规则替换为大型 HTML/CSS/JS 代码块。
- 关键差异：vanilla SillyTavern 1.18.0 没有 Tavo/高级 HTML 执行扩展，聊天区只显示语法高亮代码块。用户截图里的全屏背景、菜单、状态栏等 Tavo 效果依赖额外高级渲染能力，而不是普通 SillyTavern regex 本身。
- 证据截图：
  - `output\sillytavern-tavo-check\st-card-selected.png`
  - `output\sillytavern-tavo-check\st-regex-enabled-editor.png`
  - `output\sillytavern-tavo-check\st-worldbook-imported.png`
  - `output\sillytavern-tavo-check\st-after-worldbook-close.png`
- 后续实现建议：AI星月可以先支持安全 HTML/CSS 预览和 `<StatusBlock>`/`ruby`/`details` 等静态结构；涉及 `<script>` 的卡内 TavoJS 必须走隔离 iframe、CSP/sandbox、用户确认和能力白名单，避免任意卡片脚本直接接触主页面、账号 token、localStorage 或平台 API。

## 2026-06-29 Tavo/Sandbox 实现记录

- 前端 `frontend/app/assets/js/chat.js` 会检测 triple-backtick HTML/Tavo/SVG/XML 代码块，以及 raw `<html>/<head>/<body>/<style>/<script>/<details>/<svg>/<div>` 等高级 HTML 片段；普通文本仍安全转义，`<StatusBlock>` 仍格式化为中文状态卡。
- 高级 HTML 使用 `iframe srcdoc` 渲染，sandbox 只给 `allow-scripts`，不允许 same-origin、表单、弹窗或主页面 DOM 访问；父页面只接收 iframe 的高度 postMessage，按 260-860px 边界调整 iframe 高度。
- `srcdoc` 会移除外部 `<script src>`、`link[rel]`、`iframe/object/embed/base`、meta refresh/CSP、外部 `src/href/action/srcset/ping/integrity`，并强制 CSP：`default-src 'none'`、`connect-src 'none'`、`frame-src 'none'`、`object-src 'none'`、`form-action 'none'`，只保留 data/blob 媒体和内联样式/脚本。
- 为长内容体验，普通超长文本折叠为“展开完整内容”，高级源码只展示片段；消息列表默认加载最新 80 条，顶部按钮按 `before` 分页加载更早消息。
- 本地验证：`D:\Anconda3\python.exe .\output\verify_tavo_sandbox_browser.py` 返回 `hasIframe=true`、`sandboxHasSameOrigin=false`、`mainScriptCount=0`、`srcdocHasCsp=true`、`externalScriptRemoved=true`、`externalImageRemoved=true`、`parentCanReadFrame=false`、`scriptPostMessageReceived=true`、`hasLongTextCollapse=true`、`console_error_count=0`、`page_error_count=0`；`D:\Anconda3\python.exe .\output\verify_message_pagination_local.py` 验证消息分页返回最新窗口并保持升序。
- 线上验证：部署后 `https://patcher.villainy.top/app/chat.html` 引用 `chat.js?v=20260629-tavo-sandbox`；线上 `chat.js` 包含 `sandbox="allow-scripts"`、`connect-src 'none'`、无 `allow-same-origin`、长文本折叠和 `loadOlderMessages`。`VERIFY_BASE_URL=https://patcher.villainy.top D:\Anconda3\python.exe .\output\verify_tavo_sandbox_browser.py` 返回 sandbox/CSP/主 DOM 脚本数/长文本折叠检查全通过，截图 `output\playwright\chat-tavo-sandbox-live.png`；远程临时数据验证 `/console/api/web/conversations/{id}/messages?limit=5&before=...` 返回最新和更早窗口正确，清理后临时 users/conversations/messages 均为 0。

## 2026-06-29 聊天状态面板与加载占位修复

- 现象：流式回复开始时前端已经插入一条空 assistant 占位消息，但模板底部又用 `x-if="replying"` 额外渲染一个加载气泡，导致移动端看起来像“上面空白气泡 + 下面加载中”；空占位消息还会露出编辑、朗读、删除等操作条。
- 修复：`frontend/app/chat.html` 删除独立 `replying` 加载气泡；`frontend/app/assets/js/chat.js` 增加 `rowClass()` 和 `bubbleClass()`，assistant 占位消息在 `_typing && !content` 时直接加 `is-loading`；生成过程中隐藏消息操作条。
- 格式优化：`frontend/app/assets/js/chat.js` 新增 `<battle_status_panel>` / `*_status_panel` 解析，把 `<protagonist>`、`<opponent>`、`<affection>` 这类子块转成中文状态卡，不再在聊天中显示 raw XML 标签。
- 验证：`node --check frontend/app/assets/js/chat.js` 通过；`D:\Anconda3\python.exe -m py_compile output/verify_chat_panel_fix_browser.py tools/ai_fengyue_local_server.py` 通过；线上 `D:\Anconda3\python.exe .\output\verify_chat_panel_fix_browser.py` 返回 `assistantBubbles=1`、`loadingBubbles=1`、`visibleActions=0`、`panelCount=1`、`rawTagVisible=false`、`console_error_count=0`、`page_error_count=0`，截图 `output/playwright/chat-panel-fix-live.png`。

## 2026-06-29 first_mes 多开头拆分

- 现象：部分 SillyTavern 角色卡把多个 `## U1/U2/U3/U4` 或 `## P1/P2/...` 开场塞进同一个 `first_mes`，AI星月之前会把它们作为一条长开场全部显示在聊天首屏。
- 修复：`tools/ai_fengyue_local_server.py` 新增 `split_silly_first_mes_greetings()`、`merge_alternate_greetings()` 和 `chat_greetings_from_card()`；导入角色卡时把第一个段落写入 `opening_statement`，其余段落写入 `alternate_greetings`，开场前说明保留到 `creator_notes`；新对话启动时也会动态拆分存量 packed `opening_statement`，生成同一 assistant 消息的 `swipes`。
- 存量数据：线上脚本 `output/normalize_silly_openings_remote.py` 上传到 `/tmp/` 后执行，使用 SQLite backup API 先备份，再修复匹配卡和旧会话首条 assistant 开场消息。最终备份为 `/opt/ai-fengyue-backend/data/ai_fengyue.sqlite3.bak-silly-openings-20260629-154616`；此前角色卡字段已更新 1 张 `admin-rczip-9721d5969c2effd819af`，补强后扫描 10 条旧会话首条 assistant 消息，更新 2 条，每条拆成 12 个 swipe。
- 验证：`D:\Anconda3\python.exe .\output\verify_silly_opening_split_local.py` 通过；线上 `/tmp/verify_silly_opening_split_remote.py` 通过真实 `/console/api/web/cards/import`、`/conversations/start`、`/messages/{id}/swipe`，返回 `initial_message_count=1`、`swipe_count=4`、`first_has_u2=false`、`next_swipe_has_u2=true`，临时 users/apps/messages 均为 0；服务/Nginx active，公网 `/health` 为 OK，`CONTENT_MODE=local_only`。
