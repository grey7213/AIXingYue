# AI星月多模型预设任务

| ID | 任务 | 状态 | 验证 |
|----|------|------|------|
| MMP1 | 建立多模型预设 SPEC | Done | requirements/design/tasks |
| MMP2 | 后端支持多模型预设存储和旧配置兼容 | Done | 本地/线上 `GET/POST /admin/api/llm-settings` |
| MMP3 | 后端聊天按角色选择的预设调用 | Done | `effective_llm_settings(app)` 按 `llm_model` 匹配预设 ID/模型名 |
| MMP4 | 用户端暴露启用预设列表 | Done | `/console/api/web/model-presets` 仅返回启用预设且不含 Key |
| MMP5 | 后台模型配置 UI 改为多预设 | Done | `output/playwright/admin-model-presets.png` |
| MMP6 | 用户创建角色改为预设下拉选择 | Done | `output/playwright/create-model-select.png` |
| MMP7 | 部署线上并验证 | Done | 服务 active、页面/API 正常 |

## 2026-06-19 验证记录

- 本地编译：`D:\Anconda3\python.exe -m py_compile .\tools\ai_fengyue_local_server.py` 通过。
- 前端语法：`node --check frontend/assets/js/admin-app.js`、`node --check frontend/app/assets/js/create.js`、`node --check frontend/app/assets/js/app-core.js` 通过。
- 本地 API：临时服务 `127.0.0.1:8022` 保存 3 个模型预设，其中 2 个启用；用户端只返回启用预设且不包含密钥；创建角色保存 `llm_model=quality`。
- 线上 API：读取现有旧配置后添加临时测试预设，用户端可见且不泄露 Key；随后移除测试预设并恢复为原预设数量。
- 线上部署：`D:\Anconda3\python.exe .\tools\deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot` 成功。
- 浏览器：后台模型配置显示“添加模型预设”和预设卡片；用户创建角色页显示模型下拉。
