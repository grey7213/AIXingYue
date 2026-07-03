# AI星月 Tavern Template / 酒馆助手兼容任务

Updated: 2026-07-01

| ID | 任务 | 状态 | 验证 |
|----|------|------|------|
| TT1 | 补齐需求/设计/任务 SPEC | Done | 本文件与 requirements/design |
| TT2 | 新增受限模板解释器与变量表 | Done | `py_compile`；`output/verify_tavern_template_local.py` |
| TT3 | 将系统提示、世界书、Prompt Manager、记忆、开场白、历史和输入接入模板处理 | Done | 本地 payload 断言；线上假上游 payload 断言 |
| TT4 | 支持 GENERATE / @INJECT / @@if 世界书注入 | Done | 本地/线上均验证 `[GENERATE:BEFORE]`、`[GENERATE:REGEX]`、`@INJECT pos=0` |
| TT5 | 回复后模板处理 + 正则脚本顺序修正 | Done | 回复 `<% setvar %>Hello SECRET` 处理为 `Hello 星月`，变量持久化为 10 |
| TT6 | 前端提示文案与 cache-buster 更新 | Done | `node --check`；线上 create 页 `create.js?v=20260701-template`；Playwright 无错误 |
| TT7 | 部署并线上验证 | Done | service/nginx active；公网 `/health` OK；`CONTENT_MODE=local_only`；线上临时数据清理为 0 |
| TT8 | 按用户明确的三个插件补齐安全兼容层 | Done | 本地和线上假上游 E2E 验证变量别名、`injectPrompt/getPromptsInjected`、`getwi/getchar`、`[InitialVariables]`、`[RENDER:*]`、`@INJECT target/index/at`、TavernHelper regex 导入 |
| TT9 | 管理端 Gemini 模型真实端到端验证 | Done | 公开模型列表 7 个启用 Gemini 选项且无 key；线上临时用户逐个验证 7 个 Gemini model_id 均 `message_end=true` 且回复命中哨兵，积分 `5000 -> 4650`，临时数据清理为 0 |

## 本轮记录

- 2026-07-01 用户要求把 JS Slash Runner / 酒馆助手文档中的能力和截图里的 Prompt Template 语法加入 AI星月，并应用全局效果。
- 2026-07-01 已上线受限 EJS-like Prompt Template：支持 `<% if %>`、`<% for %>`、`<%- expr %>`、`getvar/setvar`，变量按用户隔离并分 global/app/conversation 作用域。
- 2026-07-01 已接入系统提示、Prompt Manager、世界书、记忆、开场白、历史、用户输入、阻塞/流式回复、重生成、swipe 和群聊回复链路；模型回复先执行模板再执行 Regex。
- 2026-07-01 世界书全局效果支持 `@@if`、`[GENERATE:BEFORE]`、`[GENERATE:AFTER]`、`[GENERATE:n:BEFORE/AFTER]`、`[GENERATE:REGEX:...]`、`@@generate_before/after` 和基础 `@INJECT pos=...,role=...`。
- 2026-07-01 本地验证：`D:\Anconda3\python.exe -m py_compile tools\ai_fengyue_local_server.py output\verify_tavern_template_local.py output\verify_tavern_template_remote.py output\verify_create_template_browser.py` 通过；`D:\Anconda3\python.exe output\verify_tavern_template_local.py` 返回 `template_payload=true`、`world_injections=true`、`reply_postprocess=true`、`affinity=10`；`node --check frontend\app\assets\js\create.js frontend\app\assets\js\chat.js frontend\app\assets\js\app-core.js` 通过。
- 2026-07-01 线上验证：部署后 `ai-fengyue-backend.service`、`nginx` active，公网 `/health` OK，`CONTENT_MODE=local_only`；远程 E2E 返回 `remote_template_payload=true`、`remote_world_injections=true`、`remote_reply=Hello 星月`、`remote_affinity=10`、`points_after=4950`，临时 users/apps/conversations/messages/template_variables 清理均为 0。
- 2026-07-01 浏览器验收：`D:\Anconda3\python.exe output\verify_create_template_browser.py` 返回 `has_prompt_template_text=true`、`has_generate_text=true`、`console_error_count=0`、`page_error_count=0`，截图 `output\playwright\create-template-live.png`。
- 2026-07-01 用户进一步明确本轮要覆盖三个 SillyTavern 插件：酒馆助手、提示词模板、提示词模板语法，并要求用管理端可用的 Gemini 模型验证。补齐范围记录在 `requirements.md` 和 `design.md`。
- 2026-07-01 已按插件文档补齐安全兼容层：常用变量函数别名、增减/删除/插入变量、`injectPrompt/getPromptsInjected`、`getwi/getchar`、`[InitialVariables]`、`[RENDER:BEFORE/AFTER]`、`@INJECT target/index/at`、`??`、三元表达式、`for <=`、`switch/case`、字符串/数组基础方法；导入层会把 `extensions.regex_scripts` 和 `extensions.TavernHelper_scripts` 提升为平台 Regex。
- 2026-07-01 本地验证：`D:\Anconda3\python.exe -m py_compile tools\ai_fengyue_local_server.py output\verify_tavern_template_local.py output\verify_tavern_template_remote.py output\verify_gemini_template_remote.py output\verify_create_template_browser.py` 通过；`D:\Anconda3\python.exe output\verify_tavern_template_local.py` 返回 `template_payload=true`、`world_injections=true`、`reply_postprocess=true`、`affinity=10`、`counter=2`、`global_seen=yes`、`imported_regex=2`。
- 2026-07-01 线上部署验证：`ai-fengyue-backend.service` 与 `nginx` 均 active，公网 `/health` OK，`CONTENT_MODE=local_only`。线上假上游 E2E 返回 `remote_reply=渲染前 10\n\nHello 星月\n\n渲染后 2`、`remote_counter=2`、`remote_global_seen=yes`、`points_after=4950`，临时数据清理为 0。
- 2026-07-01 线上真实 Gemini 验证：公开 `/console/api/web/model-presets` 返回 7 个启用 Gemini 模型且无 API Key；`output/verify_gemini_template_remote.py` 验证默认 `celestiai-gemini-25-pro::gemini-2.5-pro-cli` 成功；`output/verify_all_gemini_models_remote.py` 逐个验证 7 个 Gemini model_id 均 `message_end=true` 且回复命中哨兵，积分 `5000 -> 4650`，临时 users/apps/conversations/messages 清理均为 0。
