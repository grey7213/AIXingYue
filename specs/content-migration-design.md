# AI星月上游内容迁移设计

## 当前状态

`tools/ai_fengyue_local_server.py` 已托管账号、验证码、积分、充值等业务数据，但内容接口仍通过 `proxy_json()` 从 `https://aifun.wiki/` 读取后再做品牌替换。

主要代理范围：

- `console/api/installed-apps`
- `console/api/used-installed-apps`
- `go/api/gallery/list`
- `console/api/apps/*`
- `go/api/apps/*`
- `announcements` / `announcement`
- `console/api/v1/activities/gift-packs`
- `console/api/activity/*`
- `console/api/workspaces/sidebar_notice`
- `console/api/app_site/list`
- `console/api/emojis`
- `go/api/posts/recommended`
- `go/api/explore/*`
- `model-list` / `model`
- 兜底的 `go/*`、`console/*`

## 数据结构

新增 SQLite 表：

- `content_cache`
  - `cache_key`: `METHOD path?normalized_query`
  - `method`: 请求方法，当前主要为 `GET`
  - `path`: 接口路径，不带开头 `/`
  - `query`: 原始 query
  - `status`: 上游 HTTP 状态
  - `response_json`: 已品牌替换后的 JSON 文本
  - `raw_bytes`: 响应字节数
  - `source_url`: 原始上游 URL
  - `fetched_at`: 抓取时间
  - `updated_at`: 更新时间

## 读取策略

- `CONTENT_MODE=cache_first`：`proxy_json()` 先查 `content_cache`，命中则返回；未命中继续回源，成功后写入缓存。
- `CONTENT_MODE=local_only`：`proxy_json()` 只查 `content_cache`，未命中返回现有 fallback，用于验证完全脱离上游。

## 同步策略

新增 `tools/sync_aifun_content.py`：

- 支持写入服务器同一个 SQLite DB。
- 按固定核心端点分页抓取。
- 支持从 `request_log` 读取历史 APK 实际访问过的 `GET /go/*`、`GET /console/*` 接口并同步。
- 扫描 JSON 中的 `http/https` URL，汇总媒体 URL。
- 可选对媒体 URL 做 `HEAD`，估算可下载大小。

## 存储估算

- JSON 缓存通常是 MB 级，主要取决于 app/帖子分页数量。
- 媒体资源可能是 GB 级，需根据 URL 清单和 `HEAD Content-Length` 估算。
- SQLite 可直接承担 JSON 缓存；媒体建议后续落到 `/var/www/ai-fengyue-frontend/media-cache/` 或对象存储，再把 URL 改写到 `patcher.villainy.top`。
