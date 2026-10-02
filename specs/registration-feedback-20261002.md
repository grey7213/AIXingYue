# 已注册邮箱再次注册的明确反馈

## 需求与原因

已有邮箱点击获取注册验证码时，必须明确提示“该邮箱已注册，请直接登录；忘记密码可找回”，不能出现发送成功或倒计时。直接提交重复注册也须给出相同提示。新邮箱继续正常发送和注册。

真实原因：`/console/api/register/email` 对已存在账号返回 HTTP 200 / accepted，但不调用邮件服务；前端据此显示成功并启动倒计时。重复注册接口的提示是英文，前端仅有短暂 toast，容易错过。

## 实现

- 后端两个注册入口统一返回 HTTP 409，保留现有 failure/message/msg/data 兼容结构，并增加 `error_code=email_already_registered`。已注册邮箱不生成验证码、不发送邮件、不增加账号或积分。
- 以用户明确要求为准，注册流程明确反馈邮箱已注册；密码找回流程保持现状。
- 登录页新增持久注册错误提示，已注册时显示“去登录 / 找回密码”，沿用当前表单样式并携带已填写邮箱。修改邮箱清除旧反馈及倒计时，忽略旧邮箱的迟到请求结果。
- 注册验证码按钮防重复点击；只在 API 成功后显示发送提示和倒计时。更新登录 JS URL 版本。
- APK 既有共享 API 客户端能读取 HTTP 错误 message，服务端修复直接生效；新增表单内引导属于新版网页资源。本次不因服务器错误提示修复强制发布新 APK。

## 任务与验收

- [x] 定位后端假成功响应及前端反馈入口。
- [x] 修复并验证已注册、大小写/空格邮箱、重复提交、新邮箱发送/冷却、邮件失败和重复注册竞态。
- [x] 真实浏览器验证桌面/390px：提示可见且持久、失败无倒计时、登录/找回密码携带邮箱、换邮箱能恢复、新邮箱成功。
- [x] 备份后定向部署，核对哈希及服务健康；线上已有邮箱验证不外发邮件、不变更账号。
- [x] 记录证据、提交并推送。

证据放 `output/registration-feedback-20261002/`，不得外发测试邮件或记录真实邮箱、密钥和验证码。本机本轮 `adb devices -l` 无连接设备，APK 实机 UI 验收未执行。

## 验证结果

- `D:\Anconda3\python.exe tools/_selftest_registration_feedback.py`：6 项通过；真实注册 route + 临时验证码 SQLite，邮件发送 mock，覆盖已有邮箱归一化、重复提交、新邮箱发送/冷却、发信失败、注册竞态及成功会话设置。
- Playwright Chromium：1440px 与 390px 各 6 场景，共 12 项通过，page error 为 0；真实页面/API 客户端调用本地真实后端 route，账号夹具与邮件传输隔离。提示在 toast 消失后仍可见，无横向溢出，登录/找回邮箱正确，旧邮箱迟到响应不影响新邮箱，网络失败可重试。已有账号拒绝提交时会清除残留倒计时。
- 已查看 `register-existing-1440.png` 与 `register-existing-390.png`。Python 编译、JS 语法检查、diff whitespace 检查通过。
- 线上三个原文件与修改前 HEAD 一致；部署前备份并逐一 cmp 核对，root-only 目录 `/root/homer-register-feedback-before-20261002/`。恢复时按原路径/权限回写对应文件并重启 backend。
- 生产内部和公网的 `register/email`、`register` 共 4 次实际请求均为 HTTP 409 / `email_already_registered`，中文提示正确。只使用服务器内部选取的既有邮箱，未外发邮件；验证码行数以及该账号密码/积分均未改变，未输出邮箱或账号信息。
- 后端与网页文件线上/本地 SHA-256 一致；登录页使用 `login.js?v=20261002-register-feedback-v2`。backend/dialogue/Nginx active，内外 `/health` 均 OK。明细在本任务 `production-verification.json`。
- APK 本轮未重打包：旧资源已有的 ApiError/message 处理能消费服务端错误；本次新增网页持久提示需要新网页资源，未宣称旧 APK 已具备该新增 UI。若后续发 APK，纳入本次 login.html/login.js 更新并补设备验收。
