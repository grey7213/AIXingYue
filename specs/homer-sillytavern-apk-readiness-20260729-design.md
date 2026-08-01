# 惑梦 SillyTavern APK 打包前优化 Design

日期：2026-07-29

## 合并策略

- 合并基线：当前 Git `main`/HEAD。
- 参考实现：`output/homer-handoff-20260731/`，其工作大致从历史提交 `7f67f7c` 分叉。
- 可整体引入：去除运行数据和依赖后的 `sillytavern-runtime/` 固定源码快照。
- 必须定向移植：`tools/ai_fengyue_local_server.py`、`frontend/admin.html`、`frontend/assets/js/admin-app.js`、共享 API 和部署/离线启动工具。
- 入口替换：`frontend/app/chat.html` 与 `frontend/app/assets/js/chat.js` 改为轻量 Homer 启动器，不保留旧静态聊天作为主线。
- 源包审计：`E:\obs录制\惑梦-Homer-外部导入与角色卡兼容阶段备份-20260801.zip` 不含 `st-yuzi-phone` 的目录名或文本引用；固定 runtime 从唯一官方仓库补入 manifest `1.4.2` 的发布 bundle，并锁定提交 `00ddd047f81164e9a20abb6870dc54a72c328672`。

## 页面与状态流

```text
/app/chat.html
  -> 验证 Homer 登录与 app_id/conversation_id
  -> 保持 Homer 首屏遮罩
  -> 获取 dialogue-session
  -> 跳转/嵌入受控 SillyTavern runtime
  -> homer-bridge 导入角色、恢复消息/运行时状态
  -> bridge 发出 homer:runtime-ready
  -> 原子移除 runtime 预加载遮罩并显示对话
```

加载失败时不揭示底层 UI，启动器显示错误态和安全导航。

## SillyTavern bridge

### 云同步

- `dialogue-session` 返回短期桥令牌、固定模型桥、角色原始快照、会话消息和运行时配置。
- bridge 将 Homer 消息映射到 ST `chat`，在消息事件后批量同步。
- 同步接口继续以 Homer 会话所有权和版本为准；本地 ST 文件只作镜像。

### 日志事件

- 新增受限接口 `POST /console/api/web/dialogue/events`。
- 请求字段：`event_id`、`event_type`、`app_id`、`conversation_id`、可选 `message_id/message_index`、`result`。
- 服务端白名单映射为用户可读中文日志；拒绝未知类型、跨用户会话和超长字段。
- 新表/唯一键保存已接收 `event_id`，或复用现有幂等事件存储，保证重复请求只写一条 `user_logs`。

### 逐消息动作

- bridge 使用事件委托和 MutationObserver，为当前 `#chat .mes` 增加 Homer action bar。
- 目标优先使用 `message.extra.homer_message_id/homer_sync_id`，其次使用当前 DOM `mesid` 并在动作执行时重新解析。
- 回溯：截断目标消息之后的消息，再走原生保存/事件/同步。
- 续写：选中目标 assistant 消息，调用 ST continuation 生成。
- 重写：回到目标 assistant 消息并调用原生 swipe/regenerate。
- swipe：调用原生左右切换；无已有 swipe 时右切生成新 swipe。
- 动作完成后安排云同步和日志；生成中的按钮禁用。

## UI 主题与首屏

- 在 `homer-bridge/style.css` 中定义 `--homer-*` 语义变量并覆盖 ST 外壳、顶部栏、消息区、输入区、抽屉、弹窗和逐消息按钮。
- 使用 `html.homer-runtime-pending` 隐藏所有 ST 主内容，只显示 `#homer-runtime-loader`。
- loader 的关闭条件是 bridge 完成身份、角色、聊天、运行时设置和连接配置；不依赖任意固定延迟。
- 无 JavaScript 时保留可读错误；减少动效时停用非必要过渡。

## 关键词注入侧栏

- `homer-bridge/keyword-injector.js` clean-room 实现 `自动注入.txt` 的三个固定 token：`【状态栏】`、`【角色开始】`、`【Live】`。
- 选择状态与启用状态按 Homer 会话保存；发送前走 SillyTavern 输入/发送链路补词，不监听任意 `[class*=send]`，避免误触。
- 面板使用 Homer 主题、键盘/ARIA 语义和移动端宽度约束，不执行用户文本中的内联事件属性。

## 扩展管理

- 复用交接实现的 `sillytavern_extensions` 注册表与受管扩展目录。
- ZIP 校验：固定最大上传/展开大小、最大文件数、拒绝绝对路径/盘符/NUL/`..`、只读 manifest 声明入口。
- 管理员 API：列表、导入、启停、删除；用户 runtime API 只返回已启用扩展和受控资源。
- 后台“对话扩展”页接入现有管理导航；保留全局 Prompt/Regex 导入页面。

## 用户充值聚合

后台用户列表 SQL 使用相关子查询或聚合 CTE：

```sql
select u.*,
       coalesce(sum(case when p.status='paid' then p.money_cents else 0 end), 0)
         as paid_money_cents
from users u
left join payment_orders p on p.user_id=u.id
...
group by u.id
```

搜索和分页先按用户过滤，再聚合；返回 `created_at` 和 `paid_money_cents`，前端分别格式化为本地时间和两位小数人民币。

## 主要文件

- `sillytavern-runtime/**`
- `frontend/app/chat.html`
- `frontend/app/assets/js/chat.js`
- `frontend/app/assets/css/chat.css`（若启动器需要独立样式）
- `sillytavern-runtime/public/scripts/extensions/homer-bridge/index.js`
- `sillytavern-runtime/public/scripts/extensions/homer-bridge/style.css`
- `sillytavern-runtime/public/index.html`
- `sillytavern-runtime/public/css/loader.css`
- `tools/ai_fengyue_local_server.py`
- `frontend/admin.html`
- `frontend/assets/js/admin-app.js`
- `frontend/assets/js/api.js`
- 离线启动、部署和验证脚本

## 验证方案

1. 静态：`py_compile`、`node --check`、`git diff --check`。
2. SillyTavern：上游 selftests + Homer runtime/会话/卡片自测。
3. 后端：临时 SQLite 覆盖权限、ZIP 安全、事件幂等/脱敏、支付金额聚合。
4. 浏览器：本地三服务启动，桌面/移动检查首屏视频/截图、逐消息动作、RoleplayHub sandbox、后台列表和扩展导入。
5. 产物：本轮隔离运行数据、浏览器截图和进程登记统一放在 `output/sillytavern-e2e/`；通用页面回归仍可放在 `output/playwright/`，两者均不提交 Git。
