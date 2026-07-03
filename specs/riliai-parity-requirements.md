# AI星月 Web 对齐 RiliaiChat 功能需求

## 目标

- 将 `https://patcher.villainy.top/app` 从基础角色聊天 Web 客户端升级为类似 `https://riliaichat.com/` 的角色聊天产品体验。
- 功能结构对齐参考站公开可见的角色探索、工作坊、历史、收藏、图片聊天、奖励、日志、充值和信息中心入口。
- 所有数据、账号、积分、角色卡、封面、会话和模型 API 继续对齐 AI星月 APK 与 `patcher.villainy.top` 后端，不使用参考站品牌、文案或素材。

## 用户

- 普通用户：浏览角色、按榜单/分类/排序/无图模式筛选，搜索角色，进入详情和聊天，收藏角色，查看历史会话，创建和管理自己的角色卡，查看奖励/日志/积分充值入口。
- 管理员：继续通过已有后台管理模型 API 和官方角色卡；本需求不改后台主流程。

## 范围

- 前端主要在 `frontend/app/` 内新增和改造页面。
- 后端主要在 `tools/ai_fengyue_local_server.py` 内补齐轻量 API。
- 登录/注册视觉保持现有 AI星月风格和流程。
- 充值仍跳转现有 `dashboard.html`，不重复实现支付页。
- 图片聊天先实现 AI星月同库入口和历史/发送占位能力；如果后续有真实图片模型 API，再接入真实图片生成/识别。

## 功能对齐项

- Home / Explore：角色发现流，包含搜索、榜单切换 Daily/Weekly/Monthly/Overall、分类、排序 Random/Popular/Latest/Updated、Pictureless 无图模式。
- Workshop：创作中心，聚合创建角色、我的角色、官方/用户角色管理入口。
- Histories：历史对话列表，点击继续聊天。
- Favorites：收藏角色列表，角色详情和探索页可收藏/取消收藏。
- Image Chat：图片聊天入口，支持上传/选择图片、输入提示词、保存请求日志，当前使用本地占位回复。
- Rewards：奖励中心，展示签到/积分奖励入口。
- Logs：用户请求日志，展示近期聊天/图片聊天/充值/签到等本地事件。
- Deposit：充值入口，跳转现有充值页。
- Info Center App：信息中心，展示账号共享、APK 下载、当前本地内容库状态。

## 验收标准

- `/app/` 默认进入新的 AI星月 Home/Explore，而不是只有跳转或空页。
- `/app/explore.html` 具有参考站级别的筛选入口：榜单、分类、排序、Pictureless、搜索、收藏按钮。
- `/app/workshop.html`、`/app/histories.html`、`/app/favorites.html`、`/app/image-chat.html`、`/app/rewards.html`、`/app/logs.html`、`/app/info.html` 页面可访问且使用同一侧栏/移动底栏。
- 收藏接口可真实持久化：收藏后在 Favorites 可见，取消后消失。
- Histories 使用真实会话数据，能跳回 `/app/chat.html` 继续对话。
- Logs 使用后端真实请求/事件日志，至少能看到最近 Web 聊天或图片聊天事件。
- Image Chat 能提交文本和可选图片，并返回占位回复，记录到日志。
- 线上部署后真实验证页面 HTTP 200、核心 API 成功、移动和桌面截图无明显遮挡/溢出。

## 非目标

- 不复制 riliaichat 的品牌、受保护文案、图像或专有样式。
- 不重写 APK。
- 不实现完整真实图像模型能力，除非管理员后续提供对应模型 API。
