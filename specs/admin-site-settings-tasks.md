# AI星月后台运营配置任务

| ID | 任务 | 状态 | 验证 |
|----|------|------|------|
| ASS1 | 建立后台运营配置 SPEC | Done | requirements/design/tasks |
| ASS2 | 后端实现 `site_settings` 默认值、读写 API | Done | `py_compile`；本地/线上 API 读写验证 |
| ASS3 | 奖励/购买接口接入运营配置 | Done | 每日积分、任务、套餐、购买链接从配置返回 |
| ASS4 | 后台新增“运营配置”可视化表单 | Done | `/admin.html` 运营配置 Tab 渲染并加载表单值 |
| ASS5 | 官网首页读取公开配置 | Done | 首页文案/按钮链接由公开配置替换 |
| ASS6 | App Shell 读取公开公告 | Done | `/app` 页面可显示/隐藏后台公告 |
| ASS7 | 部署和线上验证 | Done | 服务 active、`/health` OK、Playwright 截图 |
| ASS8 | 扩展官网功能卡片、下载信息、FAQ 和 App 信息中心配置 | Done | API、首页、信息中心、后台表单和截图验证 |
| ASS9 | 扩展登录/用户中心/导航/空态运营配置 | Done | API、登录页、App 导航、用户中心、我的页、工坊、图片聊天、后台表单和截图验证 |
| ASS10 | 扩展角色详情/聊天/角色编辑器/群聊运营配置 | Done | 本地 API、线上页面、后台表单、配置恢复和健康检查通过 |
| ASS11 | 扩展 App 首页/探索、我的角色、用户中心/我的页交互文案 | Done | 本地 API、线上页面、后台表单、配置恢复和健康检查通过 |
| ASS12 | 扩展登录页、奖励页和 App Shell 剩余普通用户文案 | Done | 本地 API、线上页面、后台表单、配置恢复和健康检查通过 |
| ASS13 | 补齐审计剩余普通用户可见文案 | Done | 本地 API、线上 API、真实浏览器页面、后台表单、配置恢复和健康检查通过 |

## 验证记录

- 2026-06-26 本地语法检查：
  - `D:\Anconda3\python.exe -m py_compile .\tools\ai_fengyue_local_server.py`
  - `node --check .\frontend\assets\js\admin-app.js`
  - `node --check .\frontend\assets\js\site-settings.js`
  - `node --check .\frontend\app\assets\js\layout.js`
  - `node --check .\frontend\app\assets\js\hub-pages.js`
- 2026-06-26 本地 API 验证：
  - `D:\Anconda3\python.exe .\output\verify_site_settings_local.py`
  - 结果：公开配置可读；管理员保存可生效；奖励接口返回 `daily.points=13`；旧 `dailyapppoints` 首次发放 `points_added=13`；重复新版签到返回 `points_added=0`；购买链接返回测试 URL。
- 2026-06-26 线上部署：
  - `D:\Anconda3\python.exe .\tools\deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot`
  - `ai-fengyue-backend.service` active，`nginx` active，`/health` 返回 `OK`，`CONTENT_MODE=local_only`。
- 2026-06-26 线上临时配置验证：
  - `D:\Anconda3\python.exe .\output\verify_site_settings_remote.py set-test`
  - 临时写入公告、首页标题、`daily_points=17`、购买链接和套餐，API 均返回测试值。
  - `D:\Anconda3\python.exe .\output\verify_site_settings_browser.py`
  - 结果：App 公告、奖励页动态按钮 `领取 +17`、后台运营配置 Tab 全部渲染；浏览器 console/page error 均为 0。
  - 截图：`output\playwright\admin-site-settings-home.png`、`output\playwright\app-announcement-site-settings.png`、`output\playwright\rewards-site-settings.png`、`output\playwright\admin-site-settings.png`。
- 2026-06-26 线上恢复确认：
  - `D:\Anconda3\python.exe .\output\verify_site_settings_remote.py restore`
  - 恢复后公开配置为：`hero_title=让想象·照进二次元`、`announcement_enabled=false`、`daily_points=10`、`aifadian_url=""`。
- 2026-06-26 第二批运营配置扩展：
  - 新增可配置内容：官网“核心功能”标题/说明/功能卡片、下载信息卡、安装提示、FAQ 标题/问题/回答、App 信息中心标题/按钮/主文案/统计标签。
  - `D:\Anconda3\python.exe .\output\verify_site_settings_local.py` 验证新增字段可由管理员保存并从公开 API 返回。
  - 线上 `set-test` 验证返回：`feature_card_title=运营功能卡`、`download_fact_value=v-ops`、`faq_question=运营配置问题？`、`info_topbar_title=运营信息中心`。
  - `D:\Anconda3\python.exe .\output\verify_site_settings_browser.py` 验证首页功能卡/下载信息/FAQ、App 公告、奖励页、信息中心和后台表单全部渲染；浏览器 `console_error_count=0`、`page_error_count=0`。
  - 新截图：`output\playwright\home-expanded-site-settings.png`、`output\playwright\info-site-settings.png`，并刷新 `admin-site-settings.png`、`app-announcement-site-settings.png`、`rewards-site-settings.png`。
  - 恢复后公开配置摘要：`hero_title=让想象·照进二次元`、`announcement_enabled=false`、`daily_points=10`、`features_title=核心功能`、`faq_title=常见问题`、`info_topbar_title=信息中心`、`aifadian_url=""`。
- 2026-06-26 第三批运营配置扩展：
  - 新增可配置内容：登录/注册页文案、用户中心余额/签到/API 说明、“我的”页人设/模型连接器说明、桌面/移动 App 导航标签、探索/收藏/历史/我的角色/操作记录/兑换记录/工坊/图片聊天空状态和占位文案、购买卡标题/说明/按钮/兑换码占位。
  - 本地验证：
    - `D:\Anconda3\python.exe -m py_compile .\tools\ai_fengyue_local_server.py`
    - `node --check` 通过：`admin-app.js`、`layout.js`、`hub-pages.js`、`login.js`、`dashboard-app.js`、`me.js`、`explore.js`、`my-apps.js`、`character.js`、`chat.js`、`create.js`、`group-chat.js`。
    - `D:\Anconda3\python.exe .\output\verify_site_settings_local.py` 返回：`nav_home_label=本地首页`、`auth_login_button=本地进入`、`dashboard_balance_title=本地余额标题`、`account_persona_title=本地人设标题`、`deposit_title=本地购买标题`、`explore_empty=本地探索空态`。
  - 线上部署：
    - `D:\Anconda3\python.exe .\tools\deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot`
    - `ai-fengyue-backend.service` active，`nginx` active，公网 `/health` 返回 `OK`，`CONTENT_MODE=local_only`。
  - 线上临时配置验证：
    - `D:\Anconda3\python.exe .\output\verify_site_settings_remote.py set-test` 返回：`nav_home_label=运营首页`、`auth_login_button=运营进入`、`dashboard_balance_title=运营余额标题`、`account_persona_title=运营人设标题`、`deposit_title=运营购买标题`、`explore_empty=运营探索空态`。
    - `D:\Anconda3\python.exe .\output\verify_site_settings_browser.py` 返回：`login_copy_ok=true`、`app_nav_ok=true`、`dashboard_copy_ok=true`、`me_copy_ok=true`、`workshop_copy_ok=true`、`image_copy_ok=true`、`admin_values_ok=true`、`console_error_count=0`、`page_error_count=0`。
    - 新截图：`output\playwright\login-site-settings.png`、`dashboard-site-settings.png`、`me-site-settings.png`、`workshop-site-settings.png`、`image-chat-site-settings.png`，并刷新首页、公告、奖励、信息中心和后台运营配置截图。
  - 线上恢复确认：
    - `D:\Anconda3\python.exe .\output\verify_site_settings_remote.py restore`
    - 恢复后：`announcement_enabled=false`、`hero_title=让想象·照进二次元`、`daily_points=10`；公开配置包含第三批默认字段，`aifadian_url=""`。
- 2026-06-26 第四批运营配置扩展：
  - 新增可配置内容：角色详情页标题/按钮/徽标/空态、聊天页会话列表/记忆抽屉/消息操作/输入框/确认提示、角色编辑器工具栏/基础字段/提示词/Prompt Manager/世界书/高级提示词/默认模型/语音和分享占位、群聊页列表/创建面板/输入框/toast/确认提示。
  - 本地验证：
    - `D:\Anconda3\python.exe -m py_compile .\tools\ai_fengyue_local_server.py .\output\verify_site_settings_local.py .\output\verify_site_settings_remote.py .\output\verify_site_settings_browser.py`
    - `node --check` 通过：`admin-app.js`、`character.js`、`chat.js`、`create.js`、`group-chat.js`。
    - `D:\Anconda3\python.exe .\output\verify_site_settings_local.py` 返回：`character_page_title=本地角色详情`、`chat_memory_title=本地记忆面板`、`creator_tip_text=本地编辑器提示`、`group_chat_title=本地群聊`。
  - 线上部署：
    - `D:\Anconda3\python.exe .\tools\deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot`
    - 部署过程中 `ai-fengyue-backend.service` active，Nginx 配置测试通过，公网 `/health` 返回 `OK`。
  - 线上临时配置验证：
    - `D:\Anconda3\python.exe .\output\verify_site_settings_remote.py set-test` 返回：`character_page_title=运营角色详情`、`chat_memory_title=运营记忆面板`、`creator_tip_text=运营编辑器提示`、`group_chat_title=运营群聊`。
    - `D:\Anconda3\python.exe .\output\verify_site_settings_browser.py` 返回：`character_copy_ok=true`、`chat_copy_ok=true`、`create_copy_ok=true`、`group_chat_copy_ok=true`、`admin_values_ok=true`、`console_error_count=0`、`page_error_count=0`。
    - 新截图：`output\playwright\character-site-settings.png`、`chat-site-settings.png`、`create-site-settings.png`、`group-chat-site-settings.png`，并刷新 `admin-site-settings.png` 等运营配置截图。
  - 线上恢复和健康检查：
    - `D:\Anconda3\python.exe .\output\verify_site_settings_remote.py restore`
    - 恢复后：`announcement_enabled=false`、`hero_title=让想象·照进二次元`、`daily_points=10`。
    - `ai-fengyue-backend.service` active，`nginx` active，内网和公网 `/health` 均 `OK`，`CONTENT_MODE=local_only`。
- 2026-06-26 第五批运营配置扩展：
  - 新增可配置内容：App 首页/探索标题、搜索占位、分类/榜单/排序标签、无图模式、卡片作者/名称/简介兜底、加载/到底提示；我的角色页标题、新建按钮、卡片按钮、编辑弹窗字段和保存/删除提示；用户中心登录/注册字段标签/占位、兑换/签到/退出 toast；我的页人设字段、模型连接器输入占位、协议名、按钮和保存提示。
  - 本地验证：
    - `D:\Anconda3\python.exe -m py_compile .\tools\ai_fengyue_local_server.py .\output\verify_site_settings_local.py .\output\verify_site_settings_remote.py .\output\verify_site_settings_browser.py`
    - `node --check` 通过：`admin-app.js`、`explore.js`、`my-apps.js`、`dashboard-app.js`、`me.js`、`hub-pages.js`。
    - `D:\Anconda3\python.exe .\output\verify_site_settings_local.py` 返回：`app_home_title=本地 App 首页`、`app_home_category_all=本地全部`、`auth_email_label=本地邮箱`、`dashboard_redeem_empty=本地请输入兑换码`、`account_persona_name_label=本地人设名`、`my_apps_topbar_title=本地我的角色`。
  - 线上部署：
    - `D:\Anconda3\python.exe .\tools\deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot`
    - 部署过程中 `ai-fengyue-backend.service` active，Nginx 配置测试通过，内网和公网 `/health` 均返回 `OK`。
  - 线上临时配置验证：
    - `D:\Anconda3\python.exe .\output\verify_site_settings_remote.py set-test` 返回：`app_home_title=运营 App 首页`、`app_home_category_all=运营全部`、`auth_email_label=运营邮箱`、`dashboard_redeem_empty=运营请输入兑换码`、`account_persona_name_label=运营人设名`、`my_apps_topbar_title=运营我的角色`。
    - `D:\Anconda3\python.exe .\output\verify_site_settings_browser.py` 返回：`app_home_copy_ok=true`、`dashboard_auth_copy_ok=true`、`me_copy_ok=true`、`my_apps_copy_ok=true`、`admin_values_ok=true`、`console_error_count=0`、`page_error_count=0`。
    - 新截图：`output\playwright\my-apps-site-settings.png`，并刷新 `app-announcement-site-settings.png`、`dashboard-site-settings.png`、`me-site-settings.png`、`rewards-site-settings.png`、`admin-site-settings.png` 等运营配置截图。
  - 线上恢复和健康检查：
    - `D:\Anconda3\python.exe .\output\verify_site_settings_remote.py restore`
    - 恢复后：`announcement_enabled=false`、`hero_title=让想象·照进二次元`、`daily_points=10`。
    - `ai-fengyue-backend.service` active，`nginx` active，内网和公网 `/health` 均 `OK`，`CONTENT_MODE=local_only`。
- 2026-06-26 第六批运营配置扩展：
  - 新增可配置内容：`/app/login.html` 字段标签/输入占位/toast；App Shell 用户卡 title、兜底昵称和积分后缀；奖励页顶部标题、Credits 眉标、余额说明、额度后缀、套餐区标题、购买按钮兜底、奖励前缀、领取按钮模板、已领取文案、任务状态、兑换记录标题/说明/刷新按钮；Hub 页顶部标题和收藏/历史/工坊/日志等剩余兜底文案复用已有运营配置。
  - 本地验证：
    - `D:\Anconda3\python.exe -m py_compile .\tools\ai_fengyue_local_server.py .\output\verify_site_settings_local.py .\output\verify_site_settings_remote.py .\output\verify_site_settings_browser.py`
    - `node --check` 通过：`admin-app.js`、`layout.js`、`hub-pages.js`、`login.js`、`explore.js`、`my-apps.js`、`dashboard-app.js`、`me.js`、`character.js`、`chat.js`、`create.js`、`group-chat.js`。
    - `D:\Anconda3\python.exe .\output\verify_site_settings_local.py` 返回：`app_shell_points_suffix=本地积分`、`rewards_page_title=本地 Credits`、`rewards_redemptions_title=本地兑换记录`。
  - 线上部署：
    - `D:\Anconda3\python.exe .\tools\deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot`
    - 部署过程中 `ai-fengyue-backend.service` active，Nginx 配置测试通过，内网和公网 `/health` 均返回 `OK`，服务日志显示 `content mode: local_only`。
  - 线上临时配置验证：
    - `D:\Anconda3\python.exe .\output\verify_site_settings_remote.py set-test` 返回：`app_shell_points_suffix=运营积分`、`rewards_page_title=运营 Credits`、`rewards_redemptions_title=运营兑换记录`。
    - `D:\Anconda3\python.exe .\output\verify_site_settings_browser.py` 返回：`login_copy_ok=true`、`app_nav_ok=true`、`rewards_page_copy_ok=true`、`admin_values_ok=true`、`console_error_count=0`、`page_error_count=0`。
    - 期间修复 `layout.js` 属性转义问题：`JSON.stringify()` 结果插入双引号 HTML 属性前需要 `escapeHtml()`，否则 Alpine 报 `Unexpected token '}'`。
  - 线上恢复和健康检查：
    - `D:\Anconda3\python.exe .\output\verify_site_settings_remote.py restore`
    - 恢复后：`announcement_enabled=false`、`hero_title=让想象·照进二次元`、`daily_points=10`。
    - `ai-fengyue-backend.service` active，`nginx` active，内网和公网 `/health` 均 `OK`，`CONTENT_MODE=local_only`。
- 2026-06-26 第七批运营配置补漏：
  - 新增可配置内容：图片聊天回复标题、聊天无会话空态连接词、Prompt Manager 注入位置下拉选项、角色编辑器读取角色失败提示。
  - 本地验证：
    - `D:\Anconda3\python.exe -m py_compile .\tools\ai_fengyue_local_server.py .\output\verify_site_settings_local.py .\output\verify_site_settings_remote.py .\output\verify_site_settings_browser.py`
    - `node --check .\frontend\assets\js\admin-app.js` 和 `node --check .\frontend\app\assets\js\create.js`
    - `D:\Anconda3\python.exe .\output\verify_site_settings_local.py` 返回：`chat_no_conversations_prefix=本地去`、`creator_prompt_position_system_before=本地 System 前`、`creator_load_existing_failed=本地读取角色失败`、`image_reply_title=本地图片回复标题`。
  - 线上部署：
    - `D:\Anconda3\python.exe .\tools\deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot`
    - 部署过程中 `ai-fengyue-backend.service` active，Nginx 配置测试通过，内网和公网 `/health` 均返回 `OK`，服务日志显示 `content mode: local_only`。
  - 线上临时配置验证：
    - `D:\Anconda3\python.exe .\output\verify_site_settings_remote.py set-test` 返回：`chat_no_conversations_prefix=运营去往`、`creator_prompt_position_system_before=运营 System 前`、`creator_load_existing_failed=运营读取角色失败`、`image_reply_title=运营图片回复标题`。
    - `D:\Anconda3\python.exe .\output\verify_site_settings_browser.py` 返回：`image_copy_ok=true`、`create_copy_ok=true`、`admin_values_ok=true`、`console_error_count=0`、`page_error_count=0`。
    - 图片聊天页验证会发送一次临时图片提示词请求以渲染回复标题；该操作只写操作日志，不改配置或积分。
  - 线上恢复和健康检查：
    - `D:\Anconda3\python.exe .\output\verify_site_settings_remote.py restore`
    - 恢复后：`announcement_enabled=false`、`hero_title=让想象·照进二次元`、`daily_points=10`、`image_reply_title=图片回复`、`no_conversations_prefix=去`。
    - `ai-fengyue-backend.service` active，`nginx` active，内网和公网 `/health` 均 `OK`，`CONTENT_MODE=local_only`。

## 剩余风险 / 下一步

- 本轮只支持纯文本和受限 URL，不支持富文本、图片上传或服务器级配置面板。
- 当前爱发电链接仍为空，管理员后续可在后台“运营配置”里填入正式购买链接。
- ASS10/ASS11 已覆盖聊天页抽屉/记忆/快捷回复、创建页高级配置、角色详情页、群聊页、App 首页/探索、我的角色、用户中心/我的页字段和交互 toast。管理后台自身的固定操作文案仍作为后台工具文案保留。
- ASS12 已覆盖 `/app/login.html` 字段/toast、奖励页 Credits/套餐/兑换记录/任务状态文案，以及 App Shell 用户卡兜底和积分后缀。管理后台自身的固定操作文案仍作为后台工具文案保留。
- ASS13 审计范围只处理普通用户页面的剩余小漏点；浏览器 `<title>`、无 JS 静态 fallback 和后台工具自身操作文案不作为本轮运营配置目标。
- 2026-06-26 审计后普通用户主要页面的运营可配置项已覆盖到当前 SPEC 范围；后续若新增页面或新功能，需要同步把新增普通用户可见文案纳入 `site_settings`。
