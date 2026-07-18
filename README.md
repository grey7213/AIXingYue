# 惑梦（Homer）开发工作区

当前正式开发主线是 Web 平台与后端，线上地址为 `https://patcher.villainy.top/`。历史 APK 文件名、服务名、数据库名和部分接口仍保留 AI星月/AI风月旧技术命名以维持兼容。

## 从这里开始

1. 先读 `AGENTS.md`：当前架构、部署规则、已验证踩坑与关键模块。
2. 再读 `specs/README.md`：活动 SPEC、运维 runbook 和历史文档入口。
3. Web 前端位于 `frontend/`，主后端位于 `tools/ai_fengyue_local_server.py`。

## 当前主要模块

- `frontend/app/`：用户 Web App、创作中心、聊天、角色卡、农场与账户页面。
- `frontend/admin.html`、`frontend/assets/js/admin-app.js`：管理后台。
- `tools/ai_fengyue_local_server.py`：生产后端与 SQLite 业务逻辑。
- `tools/deploy_ai_fengyue_villainy.py`：前后端部署工具。
- `specs/`：需求、设计、任务和 runbook；请从 `specs/README.md` 导航。
- `output/`：被 Git 忽略的验证截图、trace、临时脚本、审计解包和历史构建产物。
- `reverse-analysis/`：APK 逆向产物，默认不参与 Web 开发。

## 常用验证

```powershell
node --check frontend/app/assets/js/chat.js
D:\Anconda3\python.exe -m py_compile tools/ai_fengyue_local_server.py
curl.exe -k -sS https://patcher.villainy.top/health
```

前端 UI 改动还必须用真实浏览器检查桌面与移动端，不能只以语法或构建通过为完成标准。

## 部署

Web/backend 变更使用：

```powershell
D:\Anconda3\python.exe .\tools\deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot
```

部署前做服务器时间戳备份；部署后检查 backend/Nginx、内外 `/health`、`CONTENT_MODE=local_only` 和 SQLite `quick_check`。

## 历史资料

2026-06 初期 APK 学习、交付和完成报告已归档到 `docs/archive/2026-06-apk-foundation/`。它们保留用于追溯，不再作为当前项目入口。
