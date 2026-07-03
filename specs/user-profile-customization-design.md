# 用户资料自定义 Design

## 后端

- `users` 新增字段：
  - `display_id text`
  - `avatar_url text`
- 增加 `Store.ensure_user_profile_columns()`，随服务启动自动补列。
- 增加 `Store.update_user_profile(user_id, display_id, avatar_url)`：
  - `display_id` 为空表示清除展示 ID。
  - 非空展示 ID 使用正则 `^[A-Za-z0-9_-]{3,32}$`。
  - 展示 ID 做大小写无关唯一校验，排除当前用户。
  - `avatar_url` 为空表示恢复默认头像。
  - 头像 URL 只接受 `http://`、`https://` 或 `/media-cache/profile/`、`/media-cache/avatar/`。
- `profile_json()` 保留真实 `id`，新增 `display_id/public_id/custom_id`，并让 `avatar/avatar_url` 使用用户头像或默认头像。
- 新增接口：
  - `POST /console/api/web/profile`
  - `POST /console/api/web/profile/avatar`
- 头像上传复用 `decode_data_url()`，写入 `MEDIA_DIR/profile`，返回公开 URL。

## 前端

- `app-core.js` 新增 `updateProfile()` 和 `uploadAvatar()`。
- `me.js` 新增 `profileForm`、保存状态、上传状态、文件转 data URL。
- `me.html` 的个人卡改为真实头像预览、展示 ID 输入、头像 URL 输入、上传按钮、保存按钮。
- `layout.js` 侧栏用户卡优先显示 `user.avatar_url/user.avatar`，否则回退首字母。

## 验证

- 本地语法检查：Python `py_compile`，JS `node --check`。
- 本地 API 验证：展示 ID 唯一性、头像上传、真实 ID 不变。
- 部署后线上 API 和浏览器验证 `/app/me.html`。
