# 酒馆功能补全 — Tasks

配套 requirements/design。完成标记 OK。

## 后端（tools/ai_fengyue_local_server.py）

- OK T1 schema 迁移：ensure_user_persona_columns（users.persona_name/desc）、ensure_messages_columns（messages.swipes/swipe_index）；已在 init 调用链注册。
- OK T2 apply_macros(text,char,user) + 在系统提示/开场白/世界书/示例对话统一应用。
- OK T3 扩展 normalize_user_app_extras + normalize_world_info：personality/scenario/mes_example/post_history_instructions/alternate_greetings/world_info/creator_notes/character_version。
- OK T4 扩展 local_app_to_card：展开上述字段。
- OK T5 重写 call_user_llm 系统提示组装（build_system_prompt + select_world_info + persona，移除开场白）；新增 regenerate_reply_for_app。
- OK T6 Store：get_message/get_last_message/update_message_content/append_swipe/set_swipe/delete_message/delete_conversation/get_persona/set_persona；append_message 支持 swipes；list_messages 输出 swipes/swipe_index。
- OK T7 端点：conversations/start、regenerate、messages/<id>/{swipe,edit,delete}、conversations/<id>/delete、persona(GET/POST)。
- OK T8 端点：cards/import、my-apps/<id>/export；silly_card_to_app / app_to_silly_card。
- OK T9 路由顺序自检（新路由均在 loose / catch-all 前）。

## 前端

- OK T10 app-core.js 新增 11 个方法（startConversation/regenerate/swipeMessage/editMessage/deleteMessage/deleteConversation/getPersona/setPersona/importCard/exportCard）。
- OK T11 create.html/create.js：性格/场景/示例对话字段 + 备用开场白组 + 世界书组 + 高级提示词组 + 导入/导出按钮；三处序列化同步。
- OK T12 chat.html/chat.js：开场白首条、消息操作条（重生成/编辑/删除）、swipe、打字机、新建/删除会话。
- OK T13 me.html/me.js：我的人设卡片。

## 验证

- OK T14 本地 py_compile 通过；4 个 JS node --check 通过；Store 逻辑 smoke 全过；真实 HTTP e2e（8077 端口，import/persona/start/swipe/regenerate/edit/delete/export 全过）。
- OK T15 部署成功（backend 重启 + nginx reload + /health OK）；线上冒烟：persona 200、model-presets 200、create/chat/me 页 200；生产 DB 迁移已落地。
- OK T16 浏览器实测（grey 账号）：人设卡片渲染+保存；编辑器全部新字段渲染（0 console error）；导入 V2 卡成功；chat 开场白首条+persona宏、swipe 1/2 与 2/2、发送+打字机、重新生成 1/1 变 2/2；测试卡+会话已清理。
- OK T17 已更新 skill：current-state.md 决策日志（2026-06-19）、backend-api.md 端点表。本文件已回填。

## 验证结果

全部通过。关键证据：
- 后端：python -m py_compile OK；temp DB Store smoke 全 assert 通过（世界书关键词命中、constant 注入、宏无泄漏、persona 注入）。
- HTTP e2e（本地 8077）：导入->persona->start(开场白带 2 swipes)->swipe->chat->regenerate(swipes=2)->swipe prev->edit->list->export(spec=chara_card_v2, 含 character_book)->delete msg/conv->列表归零，输出 E2E ALL OK。
- 生产浏览器：开场白持有 persona 名（user 宏替换为星语者）；swipe 到备用开场白；发送消息->打字机回复；重新生成 1/1 变 2/2。0 console error。

残留风险 / 后续项：
1. 真 SSE token 流未做 —— 当前是前端打字机模拟。要真流式需 call_user_llm 流式 + handler flush + Nginx 关 proxy_buffering。
2. 生产 LLM key 未配 —— 浏览器实测时角色卡走 build_chat_reply 模板兜底（采样/世界书/persona 链路已在本地 LLM-less 路径验证；接入真实 key 后即生效）。
3. world_info / mes_example token 膨胀 —— 已各自限长（世界书 4000 字、示例对话 12000 字）。
4. 导入封面 —— 仅取 V2 avatar 的 URL，不解析 PNG 内嵌 chara 数据（tEXt chunk）。
5. CONTENT_MODE 在生产 env 仍是 local_only —— 与本次无关，沿用现状。

## 2026-06-22 复核

结论：按本 SPEC 范围，酒馆核心功能已完整实现并在线可用。

本次重新验证的证据：
- 本地语法：`D:\Anconda3\python.exe -m py_compile .\tools\ai_fengyue_local_server.py` 通过；`node --check` 对 `app-core.js`、`chat.js`、`create.js`、`me.js` 全部通过。
- 线上健康：`ai-fengyue-backend.service`、`nginx` 均为 `active`；内网 `/health` 和公网 `https://patcher.villainy.top/health` 返回 `OK`；生产 env 仍为 `CONTENT_MODE=local_only`。
- 线上页面：`/app/chat.html`、`/app/create.html`、`/app/me.html` HTTP 200；下载后的页面/JS 静态包含编辑器深度字段、备用开场白、世界书、人设、swipe、重新生成、新建/删除会话与打字机逻辑。
- 线上 API E2E：一次性账号完成注册登录、导入 SillyTavern V2 角色卡、保存 persona、启动会话并生成首条开场白、宏替换、备用开场白 swipe、发送消息、重新生成并追加 swipe、编辑消息、导出 V2 JSON、删除消息、删除会话、删除测试角色。输出 `ONLINE_TAVERN_E2E_OK`，测试卡与会话已清理。

复核限制：
- 本次尝试用 `npx --package playwright` 做新浏览器截图时包解析/下载超时，未生成新的 2026-06-22 截图；仍保留 2026-06-19 的浏览器截图证据，且本次用线上页面内容与完整 API E2E 补强验证。
