# RP Hub 互动卡与官推卡池设计（2026-07-16）

## RP Hub 沙箱兼容

- 在 `chat.js` 的 HTML 清理器中增加严格外部资源白名单：
  - Vue：将卡内 `unpkg.com/vue@3/.../vue.global.prod.js` 固定重写到受控版本。
  - Font Awesome：仅保留卡片当前使用的 cdnjs 6.5.0 CSS。
  - BGM：仅允许 `https://raw.githubusercontent.com/...` 的 MP3/OGG/WAV/M4A。
- CSP 只为上述固定来源增加 `script-src/style-src/font-src/media-src`，`connect-src` 继续为 `none`。
- 将卡内 `window.parent.document/window.parent.localStorage/window.parent` 重写到现有 `__xySTTop` 安全代理；代理的 document/storage 都指向 iframe 自身。
- 安全代理补齐 `addEventListener/removeEventListener`，使悬浮播放器的 resize/cleanup 逻辑在 iframe 内运行。
- 不给 iframe 增加 `allow-same-origin`，不把作者脚本插入主聊天 DOM。

## 官推卡池

- `local_apps` 新增 `official_recommended integer not null default 0`，启动时轻量补列并建立筛选索引。
- 详情卡、轻量卡均返回 `official_recommended`；用户角色 CRUD 不接受该字段，管理员 create/update 可维护。
- `Store.list_local_apps()` 增加可选官推过滤；新增 `list_official_recommendations(limit, seed)`，只查询 `is_public=1 AND status='published' AND official_recommended=1`。
- `/go/api/explore/search` 第 1 页响应增加 `featured_apps` 与 `featured_pool_count`；使用请求 seed 随机排序。
- 管理后台角色列表增加官推状态筛选、徽标和快速加入/移出按钮，编辑弹窗也可设置。
- Explore 页面保存独立 `featuredCardsPool`，官推区优先使用服务端池，普通推荐排除官推 ID；池为空时沿用旧回退。

## 兼容与回滚

- 新列默认 0，不改变现有角色顺序和可见性。
- 官推池为空时首页行为与现状一致。
- 外部资源白名单不匹配时维持旧安全处理：删除外链并阻止网络。
