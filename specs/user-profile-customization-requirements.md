# 用户资料自定义 Requirements

## 目标

- 让用户在 Web `/app/me.html` 的“我的”界面自行设置展示 ID 和头像。
- 保持真实 `users.id` 主键稳定，不允许前端修改内部 ID。
- 资料保存后，个人卡、侧边栏用户卡和后续 profile API 都能返回最新展示资料。

## 范围

- Web 用户资料：展示 ID、头像 URL、头像上传。
- 后端持久化：在 `users` 表新增轻量字段并迁移现有数据库。
- API：新增 Web profile 保存和头像上传接口。

## 验收标准

- 用户可以输入 3-32 位展示 ID，允许字母、数字、下划线、短横线，且同一展示 ID 不能被其他用户占用。
- 用户可以上传 PNG/JPEG/WebP/GIF/AVIF 头像，服务端保存到 `/media-cache/profile/` 并返回公开 URL。
- 用户也可以保存合法的 `http(s)` 或 `/media-cache/profile/` 头像 URL。
- `/console/api/account/profile` 保留真实 `id`，同时返回 `display_id`、`public_id`、`avatar_url`。
- `/app/me.html` 显示头像图片和展示 ID 编辑控件；真实内部 ID 只读展示。

## 非目标

- 不修改 APK。
- 不迁移或重写历史用户 ID、token、会话、角色卡、积分等关联数据。
- 不做头像裁剪、图片压缩或第三方对象存储。
