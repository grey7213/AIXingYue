# 用户资料自定义 Tasks

- [x] 明确展示 ID 与真实内部 ID 分离，避免破坏现有账号关联。
- [x] 后端新增 `display_id/avatar_url` 字段、保存接口和头像上传接口。
- [x] 前端“我的”页增加展示 ID 与头像编辑控件。
- [x] 侧边栏用户卡读取自定义头像。
- [x] 本地语法/API 验证。
- [x] 部署到 `patcher.villainy.top` 并做线上 API/浏览器验证。
- [x] 记录最终验证结果和剩余风险。

## Verification 2026-06-26

- Local syntax: `D:\Anconda3\python.exe -m py_compile .\tools\ai_fengyue_local_server.py` passed.
- Local JS syntax: `node --check` passed for `me.js`, `app-core.js`, and `layout.js`.
- Local API: `D:\Anconda3\python.exe .\output\verify_profile_customization_local.py` returned `internal_id_unchanged=true`, `display_id_saved=true`, `avatar_saved=true`, `duplicate_rejected=true`, `avatar_file_exists=true`.
- Remote API: `D:\Anconda3\python.exe .\output\verify_profile_customization_remote.py` returned `internal_id_unchanged=true`, `display_id_saved=true`, `avatar_saved=true`, `duplicate_rejected=true`, and cleaned 2 temp users plus 1 uploaded temp avatar file.
- Browser: Playwright opened `https://patcher.villainy.top/app/me.html`, saved `browser_user_01` plus avatar URL, read profile back successfully, confirmed sidebar avatar image rendered, and reported 0 console errors. Screenshot: `E:\酒馆开发\profile-customization-me.png`.
- Health: `ai-fengyue-backend.service` and `nginx` are active, `/health` returns `OK`, live env remains `CONTENT_MODE=local_only`, and `GET /media-cache/profile/default-avatar.png` returns `200 image/png`.

## Residual Risk

- The real internal user ID remains immutable and is still shown as read-only for support/debug use.
- Avatar upload stores the original image bytes without cropping or compression.
