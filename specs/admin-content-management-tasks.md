# AI星月后台内容管理任务

| ID | 任务 | 状态 | 验证 |
|----|------|------|------|
| ACM1 | 建立后台内容管理 SPEC | Done | 本文件及 requirements/design |
| ACM2 | 后端支持管理员导入角色卡 | Done | 本地/线上 `POST /admin/api/apps/import` 成功 |
| ACM3 | 后端允许管理员编辑/删除任意来源角色 | Done | 本地/线上 update/delete 验证成功 |
| ACM4 | 前端后台增加 JSON 导入入口 | Done | `output/playwright/admin-content-import-dialog.png` |
| ACM5 | 前端后台增加快捷上下架/公开管理 | Done | 角色卡 Tab 显示编辑、公开/私有、发布/下架、删除操作 |
| ACM6 | 部署到线上 | Done | deploy helper 成功；服务 active；`/admin.html` 200 |
| ACM7 | 线上端到端验证 | Done | 导入、编辑、列表、删除测试角色均成功，测试数据已清理 |
| ACM8 | 后端支持管理员批量编辑角色卡标签/简介/设定/世界书 | Done | 本地和线上 `bulk-update` API 验证通过 |
| ACM9 | 前端后台增加角色卡勾选和批量编辑弹窗 | Done | `output/playwright/admin-bulk-edit-live.png` |
| ACM10 | 批量编辑部署和线上端到端验证 | Done | deploy helper 成功；服务 active；`CONTENT_MODE=local_only` |
| ACM11 | 后台角色列表改为轻量列表并按需拉完整详情 | Done | 浏览器验证 15 秒内完成，console/page error 为 0 |

## 2026-06-19 验证记录

- 本地编译：`D:\Anconda3\python.exe -m py_compile .\tools\ai_fengyue_local_server.py` 通过。
- 本地 API：临时服务 `127.0.0.1:8021` 验证导入 2 张角色、编辑其中一张为草稿/私有、列表搜索、删除清理成功。
- 线上部署：`D:\Anconda3\python.exe .\tools\deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot` 成功，`ai-fengyue-backend.service` active，`/health` 返回 `OK`。
- 线上 API：导入 `线上后台导入验证` 角色，编辑为 `draft`/私有，列表搜索命中，删除后再次搜索为 0。
- 浏览器：`agent-browser` 验证 `/admin.html` 角色卡 Tab 有 `导入 JSON`、`发布角色卡`；导入弹窗有上传/粘贴入口和提交按钮。
- 截图：
  - `output/playwright/admin-content-apps.png`
  - `output/playwright/admin-content-import-dialog.png`

## 2026-07-02 批量编辑验证记录

- 本地编译：`D:\Anconda3\python.exe -m py_compile .\tools\ai_fengyue_local_server.py .\output\verify_admin_bulk_edit_local.py .\output\verify_admin_bulk_edit_remote.py .\output\verify_admin_bulk_edit_browser.py` 通过。
- 前端语法：`node --check .\frontend\assets\js\admin-app.js` 和 `node --check .\frontend\assets\js\api.js` 通过。
- 本地数据行为：`D:\Anconda3\python.exe .\output\verify_admin_bulk_edit_local.py` 返回标签追加/移除/替换、简介/设定覆盖、世界书追加/合并/替换、未选中对照卡不变均为 `true`。
- 线上 API：`/admin/api/apps/bulk-update` 通过临时角色端到端验证，返回 `updated=2`、`not_found_ok=true`、`world_append_merge_replace_ok=true`，临时角色已清理。
- 浏览器：`D:\Anconda3\python.exe .\output\verify_admin_bulk_edit_browser.py` 返回批量按钮/弹窗/标签/简介/世界书控件均可见，`console_error_count=0`、`page_error_count=0`。
- 截图：`output/playwright/admin-bulk-edit-live.png`。
- 线上健康：`ai-fengyue-backend.service` 和 `nginx` 均为 `active`，公网 `/health` 返回 `OK`，`CONTENT_MODE=local_only`。
