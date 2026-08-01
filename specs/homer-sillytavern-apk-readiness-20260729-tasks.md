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

## 固定公共扩展

| 扩展 | 固定版本 | 来源/策略 |
|---|---|---|
| `js-slash-runner` | `4.8.19` | 固定发布快照，管理员控制，关闭自动更新。 |
| `ST-Prompt-Template` | `1.17.6.8` | 固定源码快照，管理员控制，关闭自动更新。 |
| `st-yuzi-phone` | `1.4.2` | 官方仓库 `yuzi83/st-yuzi-phone` 提交 `00ddd047f81164e9a20abb6870dc54a72c328672` 的发布文件；源交接包缺失，已补齐并关闭自动更新。 |
| `SillyTavern-MemoryBooks` | `8.2.2` | 用户交接包快照，管理员控制，关闭自动更新。 |

## 当前范围决定

- 不恢复角色卡版本选择。
- 不部署生产，不打 APK；当前状态为“本地真实验收通过，可进入 APK 打包下一步”。
- 充值金额定义为成功在线支付金额；兑换码、积分调整和免费额度不计现金充值。
- RoleplayHub 与角色卡脚本继续在无 `allow-same-origin` 的隔离 iframe 内运行；普通用户无任意扩展安装权限。

## 验收产物

- 本地运行数据与截图：`output/sillytavern-e2e/`（不提交 Git）。
- 进程登记：`output/sillytavern-e2e/runtime/original-sillytavern-processes.json`；验收结束后已按 PID 和命令特征精确停止新旧两套测试栈，`18080/18081/18082/18091` 均无监听。
- 原版 ST 浏览器结果包含：真实生成、逐消息动作、实时回溯、扩展设置持久化、关键词侧栏、普通用户 403、桌面/移动布局。
