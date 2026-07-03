# AI星月上游内容迁移任务

| ID | 任务 | 状态 | 验证 |
|----|------|------|------|
| CM1 | 梳理当前代理上游的内容接口 | Done | 已定位 `proxy_json()` 和核心路由 |
| CM2 | 补充迁移需求和设计 SPEC | Done | `content-migration-*.md` |
| CM3 | 在后端增加 `content_cache` 表和本地缓存读取 | Done | `python3 -m py_compile`；`admin/api/content-cache/stats` |
| CM4 | 编写上游内容同步/估算脚本 | Done | `tools/sync_aifun_content.py` |
| CM5 | 服务器备份后部署后端和脚本 | Done | 备份 `20260616-083844`；systemd active；`/health` OK |
| CM6 | 首次同步核心内容 JSON 到服务器 SQLite | Done | 服务器 `content_cache` 约 95 条，JSON 原始体量约 3.19 MB |
| CM7 | 估算媒体资源存储空间 | Done | 识别媒体/外链 URL 986 条；已 HEAD 样本 28 条约 29.68 MB |
| CM8 | 验证本地库可替代上游返回核心接口 | Done | 临时 `CONTENT_MODE=local_only` 返回 `自定义人生`，无 upstream proxy failure |
| CM9 | 镜像当前内容媒体到服务器 | Done | `/var/www/ai-fengyue-frontend/media-cache/m` 962 个文件，约 270 MB |
| CM10 | 重写内容缓存里的媒体 URL | Done | 探索页和推荐帖返回 `https://patcher.villainy.top/media-cache/m/...`，旧 `aifun.wiki`/`catai.wiki` 计数为 0 |
| CM11 | 正式后端切换为本地模式 | Done | `/opt/ai-fengyue-backend/ai-fengyue.env` 设置 `CONTENT_MODE=local_only`，服务日志确认 |
| CM12 | 重新打包并发布当前可跑通的 AI星月 APK | Done | `ai-xingyue-patcher-signed.apk` 已上传并在线校验 SHA-256 `c4113f12725e2ce4f5060bbd65f4287791e540410b52a501bf6aef5185124e26` |
| CM13 | 上游角色继续本地化并补全角色管理 | Done | `local_apps`、`/console/api/web/my-apps`、`/media-cache/`、创建/编辑/删除/上传封面/聊天均已本地烟测和线上验证 |
| CM14 | 扩大上游角色同步覆盖并验证本地探索总量 | Done | `sync_upstream_content.py` 同步到上游角色 449；探索页总数 451；媒体文件 1622 个约 364M |
| CM15 | 增强角色同步脚本的重试和报告能力 | Done | `--timeout`、`--retries`、`--retry-sleep`、`--report` 已加入并上传服务器 |
| CM16 | 低频续跑第 14 页并生成同步报告 | Done | 2026-06-18 单页续跑 `--start-page 14 --pages 1 --timeout 30 --retries 1 --retry-sleep 20 --force --no-detail --report ...`；报告显示 page 14 非合法 JSON，`processed=0`、`total_upstream_in_db=449` |

## 当前结论

账号、验证码、积分、充值、上游内容缓存、上游角色本地化、后台官方角色卡和自建角色管理都已经在 `patcher.villainy.top` 后端数据库中。后端当前保持 `CONTENT_MODE=local_only`，探索页会优先返回本地库；我的角色页、创建页、聊天页、封面上传和封面回读已完成线上验证。

当前识别到的媒体资源已镜像到 `https://patcher.villainy.top/media-cache/...`，新同步的上游封面和用户上传封面都可直接访问。2026-06-18 扩大同步后，远端 SQLite 中 `local_apps` 为 `upstream=449`、`user=2`，探索页返回总数 `451`；`media-cache` 约 `1622` 个文件、`364M`。继续向第 14 页以后同步时上游返回超时/429。2026-06-18 后续单页低频复验已生成 `/opt/ai-fengyue-backend/data/sync-upstream-report.json`，第 14 页仍失败，错误为 `Expecting value: line 1 column 1 (char 0)`，未新增角色。后续应低频增量重跑，避免触发限流。

后续低频增量同步建议命令：

```powershell
ssh -i 'C:\Users\86180\.ssh\villainy_backup_ed25519' root@45.207.192.148 "python3 /opt/ai-fengyue-backend/sync_upstream_content.py --db /opt/ai-fengyue-backend/data/ai_fengyue.sqlite3 --media-dir /var/www/ai-fengyue-frontend/media-cache --public-base https://patcher.villainy.top --start-page 14 --pages 10 --timeout 45 --retries 2 --retry-sleep 30 --force --no-detail --report /opt/ai-fengyue-backend/data/sync-upstream-report.json"
```

交互式 SSH 容易在多页长同步时被本地超时中断，导致脚本尚未写出报告。若只是确认上游是否恢复，优先用单页短跑：

```powershell
ssh -i 'C:\Users\86180\.ssh\villainy_backup_ed25519' root@45.207.192.148 "python3 /opt/ai-fengyue-backend/sync_upstream_content.py --db /opt/ai-fengyue-backend/data/ai_fengyue.sqlite3 --media-dir /var/www/ai-fengyue-frontend/media-cache --public-base https://patcher.villainy.top --start-page 14 --pages 1 --timeout 30 --retries 1 --retry-sleep 20 --force --no-detail --report /opt/ai-fengyue-backend/data/sync-upstream-report.json"
```

