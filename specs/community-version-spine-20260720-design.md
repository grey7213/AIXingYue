# 惑梦社区工坊、不可变版本与 Spine 稳定化设计（2026-07-20）

## 数据模型

- `community_works` 保存社区作品的可索引投影：类型、作者、名称、简介、公开/开源状态和 `current_version_id`。
- `content_versions` 统一保存 `character/mod/ui_template/preset` 不可变快照：实体 ID、版本号、版本名、作者介绍、内容哈希、快照和发布时间。
- `local_apps.current_version_id` 指向角色当前公开版本。
- `conversations.version_id` 必须固定到属于 `app_id` 的角色版本。
- `conversation_mods` 保存有序 JSON：`[{work_id, version_id}]`。
- `contest_entries` 保存赛事、角色、报名版本和报名时间；投票只引用有效参赛记录。
- `content_version_assets` 保存版本对卡片媒体的引用，清理素材前必须确认没有版本引用。
- `card_extra_flags` 保存开源、赛事报名、已应用预设和 UI 模板引用。

## 发布事务

1. `BEGIN IMMEDIATE` 并重新读取实体与权限。
2. 规范化提交 payload，生成完整快照与稳定 SHA-256。
3. 写入下一版本号；版本名必填，作者介绍显式保存。
4. 更新实体投影与 `current_version_id`。
5. 写入媒体引用；角色报名赛事时写入绑定本版本的 `contest_entries`。
6. 提交；任一步失败整体回滚。

初次创建与导入也走同一发布函数生成 `v1`。旧库存角色在首次需要版本时惰性生成基线 `v1`，不在服务启动路径全库迁移。

## 运行时解析

- 会话创建时未显式选版本，则解析当前 `current_version_id`；旧库存卡先生成基线版本。
- 所有 send、stream、continue、regenerate、swipe/new-swipe 通过 `(app_id, conversation.version_id)` 读取快照。
- Mod 仅能选择用户自有或已收藏的社区 `mod`，保存时锁定其当前版本。
- 世界书合并直接使用数组顺序：保留反扒条目第一，追加 Mod 版本条目，再追加角色版本条目；不依赖极端 priority 值。

## 前端

- 交接 ZIP 的历史菜单、社区页、新建弹窗、双列 Mod 选择作为 UI 基础。
- UI 模板演示使用受限 `srcdoc`：`sandbox="allow-scripts"`、无 same-origin，CSP 禁止 connect/frame/form/object 和外部资源。
- 角色详情加载版本列表，开始游玩前始终弹出版本选择（仅一个版本时可显示默认选中并一键确认）。
- 创作编辑保存改为“发布新版本”，提交版本名、作者介绍和完整表单 payload；不再先调用原地 update。

## Spine

- 上传仍使用单个 `.spine.zip` asset；服务端安全解压到独立目录并生成 `spine.json`。
- 服务端从 skeleton JSON 或二进制头读取 Spine 导出版本，解析 atlas 页面名并校验纹理齐全，清单记录精确 runtime 版本。
- 前端 `SpinePortraitLayer` 分离 `_renderLayer()` 方法和 `_renderState` 状态，使用递增 generation token 防止旧异步加载覆盖新素材。
- 使用本地固定 4.2 runtime；增加 `ResizeObserver`、visibility pause/resume、context lost 状态和逐素材失败缓存。
- 失败回退到第一张纹理；切换到其他合法素材仍可重新尝试。

## 部署

- 仅部署正式源码与已确认许可证的 runtime 文件；排除交接包 output、数据库和临时文件。
- 部署前备份后端、前端、Nginx 和 SQLite；部署后轮询 health、检查 Nginx、`CONTENT_MODE`、数据库 `quick_check` 和静态 MIME。
