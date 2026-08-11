# 惑梦 SillyTavern APK 打包前优化 Requirements

日期：2026-07-29

## 目标

基于 `E:\obs录制\惑梦-Homer-外部导入与角色卡兼容阶段备份-20260801.zip` 中的原版 SillyTavern 1.18.0 对话架构，将交接分支安全合并回当前主干，使 Web/App WebView 具备稳定、统一、可审计的对话体验，并把已通过本地验收的内部对话模块部署到生产。源包 SHA-256 为 `D759B34DD40C77AE28FFC01B6957414CA4C4AE2F20CD5AB48CF64DEBC2BDBABC`。

## 用户与范围

- 普通用户：进入角色对话、使用逐消息操作、查看自己的操作日志。
- 管理员：导入和管理已审计的 SillyTavern 扩展包，查看用户注册与实际充值汇总。
- 本轮修改 Web 前端、SillyTavern runtime、Python 后端、部署工具和验证脚本，并在完整本地回归后部署生产。
- 本轮不重建 APK、不恢复旧“角色卡版本选择”入口。

## 功能要求

1. 对话首屏
   - 从 `/app/chat.html` 到 SillyTavern 完成水合前始终显示惑梦加载层。
   - 不得短暂露出 SillyTavern 默认首页、齿轮动画、角色列表、空聊天或图形初始化过程。
   - 成功后只做一次平滑揭示；失败时提供重试、历史会话和返回探索入口。

2. 日志同步
   - SillyTavern 内的发送、续写、重写/重生成、下回续、编辑、删除、回溯/swipe 等用户动作同步到 Homer `user_logs`。
   - 日志只保存动作类型、角色/会话/消息标识和必要结果，不保存提示词、回复正文、Cookie、Token 或模型密钥。
   - 同一次浏览器事件必须有幂等键，避免事件监听和云同步重复记账。

3. 后台扩展与脚本导入
   - 管理员可导入标准 SillyTavern UI 扩展 ZIP，校验 `manifest.json`、路径、文件数量和展开体积；导入后默认停用。
   - 管理员可查看、启停、删除扩展；普通用户不得安装、更新、启停或删除扩展。
   - 后台同时保留现有全局 Prompt JSON 和 Regex ZIP 导入能力，不回退为旧 TAVO 插件主线。
   - 卡内 TavernHelper/未知扩展字段继续通过角色卡原始快照无损保存，不向普通用户开放任意脚本安装入口。
   - 固定 runtime 包含用户列出的四个公共扩展：`js-slash-runner`、`ST-Prompt-Template`、`st-yuzi-phone`、`SillyTavern-MemoryBooks`。其中源包缺少 `st-yuzi-phone`，按其唯一官方仓库 `yuzi83/st-yuzi-phone` 的固定提交 `00ddd047f81164e9a20abb6870dc54a72c328672`、manifest `1.4.2` 补入发布文件。

4. 对话 UI
   - 对话页使用惑梦现有暖纸、深玫红、暖黑语义变量，与探索、角色详情和 App Shell 风格一致。
   - 桌面 1440×900 和移动 390×844 可用，无横向溢出、遮挡、不可读文本或 SillyTavern 品牌残留。
   - 不破坏原版 SillyTavern 消息生成、Regex、世界书、TavernHelper、RoleplayHub 隔离 iframe 和模型桥。

5. 逐消息操作
   - 每条适用的 assistant 消息拥有就地操作入口，而不是只有全局操作坞。
   - 至少覆盖：回溯到该消息、从该消息续写、重写/重生成该消息、切换前后 swipe；仅在语义适用时显示。
   - 操作必须以被点击消息的稳定标识或当前索引为目标；执行前校验当前会话，防止切换会话后的陈旧点击。
   - 继续使用 SillyTavern 原生编辑/删除/swipe/生成链路，Homer 负责计费、日志和云同步。

6. 关键词注入侧栏
   - `E:\obs录制\自动注入.txt` 的“状态栏/预设角色/直播”关键词选择、发送前自动补入、开关、清空和预览能力以 Homer 原生扩展实现。
   - 设置按当前会话保存，不向父页面注入不受控 `onerror` 脚本，也不依赖旧 UniApp textarea 选择器。

7. 后台用户管理
   - 用户列表显示注册时间。
   - 用户列表显示累计实际充值金额，按成功支付订单 `payment_orders.status='paid'` 的 `money_cents` 聚合。
   - 不把管理员积分调整、免费积分、每日奖励、兑换码或旧测试充值额度误算为现金充值。
   - 搜索、分页和管理员权限控制保持有效。

8. TavernHelper 卡内脚本创作能力
   - 高级创作者可在制卡/编辑页查看、编辑、复制、导入和导出 `extensions.tavern_helper.scripts`。
   - 前端使用专用字段 `tavern_helper_scripts`，不得把整份 `extensions` 作为普通用户可编辑字段回传。
   - 最多 100 条脚本，总 JSON UTF-8 大小不超过 4 MiB；超限必须明确报错，不得静默截断。
   - 显式提交（包括清空）要求高级创作权限；无权限用户只看到已有脚本数量和锁定说明，普通基础编辑不得覆盖或丢失原脚本。
   - 保存时仅合并 `extensions.tavern_helper.scripts`，保留 `tavern_helper` 及其他 extension 的未知字段；JSON/PNG/SillyTavern 导出必须无损带回已编辑脚本。

9. 生产内部对话模块
   - SillyTavern runtime 源码部署到 `/opt/homer-dialogue-runtime`，运行数据部署到 `/var/lib/homer-dialogue`，以专用 `homer-dialogue` 用户运行。
   - systemd 仅监听 `127.0.0.1:8091`，通过 `HOMER_BACKEND_BASE_URL=http://127.0.0.1:8008` 与 Homer 后端通信。
   - Nginx 对外只暴露同源 `/module/dialogue/`；旧 `/dialogue-core/` 仅兼容重定向，运行时根相对资源/API 统一重定向到模块前缀。
   - 顶层直接访问内部 runtime 时返回 `/app/chat.html`；只有带受控嵌入标记的 iframe 可加载。
   - dialogue 响应单独允许 `frame-ancestors 'self'`，站点其他页面继续保持现有防嵌入策略。
   - 安装依赖只使用 `npm ci --omit=dev --no-audit --no-fund`，部署后 webpack 必须仍为 `5.105.4`。

## 架构与安全约束

- 当前主干为合并目标，禁止直接覆盖后端、后台或前端文件；以交接分支的共同基线做定向移植。
- Homer SQLite 是账号、会话、消息、积分和日志主数据；SillyTavern 文件目录是可重建镜像。
- 普通用户 BYOK 保持关闭；模型 Key 只在服务端。
- RoleplayHub HTML 继续使用无 `allow-same-origin` 的 sandbox iframe和随机通道令牌。
- SillyTavern Node 端口只允许受控代理访问，不作为无认证公网服务直接暴露。
- 2026-08-12 产品决定取代此前的用户可见许可页要求：平台导航、信息页不展示“许可/开源许可与源码”或源码仓库入口，`/app/open-source.html` 必须不存在并返回 404。
- `sillytavern-runtime/LICENSE` 与第三方许可证文件、来源和风险记录仍需保留在源码/内部文档中；不得因隐藏页面而宣称 AGPL、AFPL 或其他第三方许可义务已经消失或项目已经取得闭源授权。
- 保留当前主干的模型自动发现/探测、会话运行时配置、社区/版本/Spine/Open Chat Runtime 及 7 月下旬渲染修复。

## 验收标准

- Python、Node 静态检查通过；SillyTavern 自测通过。
- 后端测试证明扩展导入权限、日志幂等与脱敏、用户注册时间和充值聚合正确。
- 真实 Chromium 在 1440×900 与 390×844 验证：首屏无 ST 闪露、逐消息操作有效、对话 UI 无横向溢出，console/page error 为 0。
- 四个固定公共扩展均能被 runtime 枚举；离线验收不得因扩展产生外部网络请求。
- TavernHelper 脚本 API 覆盖创建、读取、更新、清空、JSON/PNG 导出、未知 extension 字段保留、权限拒绝和 100 条/4 MiB 边界。
- 生产验收证明 8091 只绑定 loopback，`/module/dialogue/` 可嵌入、顶层访问会回到站内聊天，桌面/390px 真实登录无首屏闪露且 RoleplayHub sandbox 无 `allow-same-origin`。
- 生产 backend/runtime/Nginx 均 active，内外 health 正常，`CONTENT_MODE=local_only` 不变；部署前配置与数据有时间戳备份和可执行回滚路径。
- Git 工作树只包含本任务文件和用户原有未跟踪 `.thm`；后者不被修改或提交。

## 非目标

- 不在本轮恢复角色卡历史版本选择。
- 不迁移历史接口路径、数据库名、APK 包名或服务名。
- 不允许普通用户安装任意第三方扩展或把卡内脚本放入父页面同源 DOM。
- 不以编译通过代替浏览器验收，也不在未验证前部署；本轮始终不打 APK。
