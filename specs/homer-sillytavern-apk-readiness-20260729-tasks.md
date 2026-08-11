# 惑梦 SillyTavern APK 打包前优化 Tasks

日期：2026-07-29
最终本地验收：2026-08-02

| ID | 任务 | 状态 | 验证/备注 |
|---|---|---|---|
| HSA1 | 审计交接包、共同基线和当前主干差异 | Done | 源包 `E:\obs录制\惑梦-Homer-外部导入与角色卡兼容阶段备份-20260801.zip`，SHA-256 `D759B34DD40C77AE28FFC01B6957414CA4C4AE2F20CD5AB48CF64DEBC2BDBABC`；以当前 `main` 为合并目标，未整包覆盖主干。源包文件名和文本内容均未发现 `st-yuzi-phone`。 |
| HSA2 | 创建 requirements/design/tasks | Done | 本组三份 SPEC 已按真实实现持续更新；`specs/README.md` 已登记入口。 |
| HSA3 | 引入精简 SillyTavern 1.18.0 runtime 和离线启动工具 | Done | 固定上游 `1.18.0`/`51ad27f`；新增离线启动、代理、种子数据和验收工具；Git 排除 `node_modules`、data、output、Cookie、log、token 和 secret。 |
| HSA4 | 合并 dialogue-session、身份桥、角色/消息同步和固定模型桥 | Done | 原版 ST E2E 完成身份进入、V3 未知字段往返、卡片脚本、真实本地模型生成和云端消息同步；保留现有模型/运行时安全边界。 |
| HSA5 | 消除 SillyTavern 首屏闪露 | Done | 网站启动器和 runtime 双层 gate 均由 bridge ready 驱动揭示；浏览器断言未暴露 ST 品牌、设置树、角色管理、默认通知或内部端口，桌面/移动 console/page/network error 均为 0。 |
| HSA6 | 统一对话页视觉 | Done | 惑梦暖纸/暖黑/深玫红主题覆盖 ST 外壳、消息、输入区、弹窗和操作条；Chromium `1440×900`、`390×844` 无横向溢出。 |
| HSA6A | 实现 `自动注入.txt` 关键词侧栏 | Done | clean-room 侧栏覆盖 `【状态栏】`、`【角色开始】`、`【Live】`；浏览器真实点击证明发送前按序补词、刷新恢复、跨会话不泄漏，移动端面板无溢出。 |
| HSA7 | 为每条消息绑定回溯、续写、重写和 swipe 操作 | Done | E2E 校验每个 action bar 的 `messageIndex` 与消息 `mesid` 一致；完成逐消息续写、全局续写、重生成、next/swipe 和无刷新实时回溯，云端同步一致。 |
| HSA8 | 新对话动作同步 Homer 日志 | Done | `_verify_homer_apk_readiness_backend.py` 验证事件白名单、所有权、幂等；日志仅含动作元数据，不含 Prompt、回复正文或秘密。 |
| HSA9 | 后台补齐扩展/脚本导入管理 | Done | 管理员扩展 ZIP 导入/列表/启停/删除及 Prompt/Regex 导入能力已接入；普通用户扩展变更返回 403。固定 runtime 枚举四个公共扩展，均 `auto_update=false`。 |
| HSA10 | 用户列表显示注册时间和成功充值金额 | Done | 后端只聚合 `payment_orders.status='paid'`；夹具结果 `paid_money_cents=1300`，待支付和旧测试额度未计入。后台桌面/移动显示注册时间 `2026-08-02 03:26:15` 与 `¥13.00`，无溢出和浏览器错误。 |
| HSA11 | 静态、后端与 SillyTavern 自测 | Done | `python -m compileall -q tools`、前端/bridge/Yuzi bundle `node --check`、`git diff --check` 通过；webpack lock/runtime 均为 `5.105.4`；Card Experience Schema 4/4、Card Stage、Conversation Database、SillyTavern Runtime 自测全部通过；临时 SQLite `quick_check=ok`。 |
| HSA12 | Chromium 桌面/移动端到端验收 | Done | `_e2e_original_sillytavern_browser.py`、`_e2e_sillytavern_runtime.py`、`_verify_homer_admin_users_browser.py` 全部通过；RoleplayHub 23 条 Regex、1 个 UI 模板、5 个媒体项，iframe sandbox 精确为 `allow-scripts`。 |
| HSA13 | 更新 AGENTS 错误记忆与任务结果 | Done | 已记录中文路径 Junction、离线模型 stub 和 webpack 版本锁三项稳定经验；未写入密钥或临时日志。 |
| HSA14 | 聚焦 Git 提交并推送 | Done | 主实现提交 `fae520b`（`feat: integrate Homer SillyTavern runtime`）已推送到 `origin/main`；用户 `Tavo_主题效果_14G5y(1).thm` 保持未跟踪、未修改、未提交。 |
| HSA15 | 补齐 TavernHelper 卡内脚本查看、编辑、导入、导出和无损持久化 | Done | 专用字段 `tavern_helper_scripts`；最多 100 条/4 MiB；显式提交需高级创作权限；基础编辑不覆盖旧脚本；JSON/PNG/ST 导出无损；锁定投影同时脱敏 `extensions.tavern_helper.scripts` 正文。后端与浏览器夹具均通过。 |
| HSA16 | 补齐生产 dialogue runtime、systemd、Nginx 和部署工具 | Done | 部署工具已实现安全包、源码/数据分离、专用用户、loopback `8091`、同源 `/module/dialogue/`、旧路径/根相对资源重定向、cookie path、独立 frame policy、webpack `5.105.4` 校验与失败回滚；本地布局/归档验证通过。 |
| HSA17 | 完成本地静态、后端、runtime 和桌面/移动浏览器回归 | Done | `py_compile`、`node --check`、`git diff --check`、4 项卡体验自测、对话数据库/ST runtime 自测、TavernHelper 后端/浏览器、后端 readiness、原版 ST 与 Homer runtime Chromium E2E 均通过；桌面/390px 无溢出、console/page/network error 为 0，固定四扩展和 RoleplayHub sandbox 均通过。 |
| HSA18 | 备份并部署生产，完成安全、许可和回滚验收 | Done | 2026-08-08 生产 runtime 已原子切换到 `/opt/homer-dialogue-runtime/releases/20260808-182614`；backend/dialogue/Nginx active，8008/8091 仅 loopback，webpack `5.105.4`，内外 Homer health 与 dialogue `/csrf-token` 均为 200，`CONTENT_MODE=local_only`。最终真实登录 Chromium 在桌面和 390px 均退出加载层、显示 5 条目标会话消息，runtime 为 `homer-runtime-ready` 且无 pending，RoleplayHub sandbox 精确为 `allow-scripts`，page/console/network error 均为 0；release 启动后 CSRF 403 为 0。 |
| HSA19 | 更新项目记忆、聚焦提交并推送 | Done | 生产卡死修复、回归测试、部署器守卫、SPEC 和两条稳定错误记忆已提交为 `fa9067a`（`fix: stabilize Homer dialogue runtime startup`）并推送 `origin/main`；用户 `.thm`、运行数据、截图、token、Cookie、secrets 和临时清理脚本均未提交。 |
| HSA20 | 下线平台级许可/源码入口并阻止旧 URL 回退 | Done | 2026-08-12 删除共享侧栏“许可”、信息中心许可卡片和 `frontend/app/open-source.html`；前端归档 86 文件且不含该页面，部署器会删除远端残留并校验精确 Nginx 404。线上文件不存在、旧 URL=404、`layout.js` 无旧 href、`info.html` 无许可文案；backend/dialogue/Nginx active，8008 health、8091 `/csrf-token`、公网 health 和 `CONTENT_MODE=local_only` 通过。真实 Chromium 1440×900 与 390×844 均无许可文本/旧链接、无横向溢出，console/page error=0。 |
| HSA21 | 清理生产历史备份并固化最近一组保留策略 | Done | `/opt/ai-fengyue-backend/backups/` 删除 55 个历史项、43,103,877,141 bytes；最终仅保留当前 SQLite + 前端源码归档，磁盘可用空间约 41.8 GB。部署器在全部生产验收后将托管 DB/前端备份各裁剪到 1；本地自测、`py_compile`、`git diff --check` 和最终线上完整性/健康检查通过。 |

## 固定公共扩展

| 扩展 | 固定版本 | 来源/策略 |
|---|---|---|
| `js-slash-runner` | `4.8.19` | 固定发布快照，管理员控制，关闭自动更新。 |
| `ST-Prompt-Template` | `1.17.6.8` | 固定源码快照，管理员控制，关闭自动更新。 |
| `st-yuzi-phone` | `1.4.2` | 官方仓库 `yuzi83/st-yuzi-phone` 提交 `00ddd047f81164e9a20abb6870dc54a72c328672` 的发布文件；源交接包缺失，已补齐并关闭自动更新。 |
| `SillyTavern-MemoryBooks` | `8.2.2` | 用户交接包快照，管理员控制，关闭自动更新。 |

## 当前范围决定

- 不恢复角色卡版本选择。
- 本轮在完整本地回归后部署生产内部 dialogue runtime；仍不打 APK。
- 充值金额定义为成功在线支付金额；兑换码、积分调整和免费额度不计现金充值。
- RoleplayHub 与角色卡脚本继续在无 `allow-same-origin` 的隔离 iframe 内运行；普通用户无任意扩展安装权限。
- 平台级“许可/开源许可与源码”不向普通用户展示，旧 `/app/open-source.html` 固定返回 404；角色卡/社区自身的开源属性与内部第三方许可证文件不受影响。此产品决定不代表第三方许可义务已经解除。

## 验收产物

- 本地运行数据与截图：`output/sillytavern-e2e/`（不提交 Git）。
- 进程登记：`output/sillytavern-e2e/runtime/original-sillytavern-processes.json`；验收结束后已按 PID 和命令特征精确停止新旧两套测试栈，`18080/18081/18082/18091` 均无监听。
- 原版 ST 浏览器结果包含：真实生成、逐消息动作、实时回溯、扩展设置持久化、关键词侧栏、普通用户 403、桌面/移动布局。
- 2026-08-06 本地收尾：许可页真实 Chromium 桌面/390px 通过；TavernHelper 锁定投影补充确认 `extensions.tavern_helper.scripts` 不含正文；重新启动隔离栈后，原版 ST 与 Homer runtime 两套 Chromium E2E 均通过，四个端口验收后已按登记 PID 停止。
- 2026-08-08 生产卡死修复：`/module/dialogue/` 下的根相对 API/CSRF 请求统一进入 cookie-scoped 模块路径，核心 ESM 只保留单一 mounted URL；MacroEngine、SlashCommandParser/power-user、extension prompt 常量和 TTS provider 的启动循环改为依赖无关状态桥、常量下沉与惰性读取。生产桌面/390px 对《黎明之契2.71》真实存档验证 5 条消息可见，加载器隐藏、iframe opacity=1、无启动循环/CSRF/资源失败。
- 2026-08-12 平台许可入口下线：桌面截图 `output/playwright/license-removal-desktop.png`、移动截图 `output/playwright/license-removal-mobile.png`；侧栏工具链接精确为 `创作/历史/收藏`，手机底栏为 `探索/群聊/创作/历史对话/我的`。本次重试发现备份目录占满磁盘，仅清理失败产生的 `20260812-015441` 不完整 SQLite backup/journal，保留 `20260812-015059` 有效恢复点；当时磁盘约 413 MB 可用，历史备份保留待办随后由 HSA21 完成。
- 2026-08-12 历史备份收敛：先验证 live 与 `20260812-015059` 恢复库 `quick_check=ok`、旧前端 tar 可读，再删除备份目录直属历史项并生成当前恢复集。最终仅有 `ai_fengyue-current-20260811-183028.sqlite3`（1,776,779,264 bytes）和 `frontend-source-current-20260811-183028.tgz`（1,955,764 bytes，130 entries）；删除 55 项共 43,103,877,141 bytes，可用空间为 41,801,490,432 bytes。SQLite 临时 `-wal/-shm` 已在确认 WAL 为 0 后清理，前端归档排除 `media-cache/download`。
- 收尾清理：两条无消息诊断会话及其 16 条会话表镜像、2 条 runtime profile 已在单事务中精确删除；root-only 定向恢复库为 `/opt/ai-fengyue-backend/data/backups/diagnostic-conversations-before-20260808-103812.sqlite3`（mode 600），恢复库和 live SQLite 均 `quick_check=ok`。
