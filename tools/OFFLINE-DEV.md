# Homer Windows 离线调试

离线调试器只监听本机回环地址：

- 前端和同源 API 入口：`http://127.0.0.1:8080/`
- Python 后端：`http://127.0.0.1:8000/`
- 同页对话入口：`http://127.0.0.1:8080/module/dialogue/`
- SillyTavern 内部端口：`http://127.0.0.1:8091/`（只供本机代理访问，不作为用户入口）
- 登录页：`http://127.0.0.1:8080/app/login.html`
- 管理后台：`http://127.0.0.1:8080/admin.html`

`start` 会同时启动后端、网站代理和内部 SillyTavern 运行时。用户始终从 8080
登录和选择角色；打开 `/app/chat.html` 后，网站在同页 iframe 中加载
`/module/dialogue/`，地址栏不会进入 8091。

第一次启动会按 `package-lock.json` 自动执行 `npm ci --omit=dev`，安装日志位于
`output\offline-dev\logs\sillytavern-install.*.log`；后续启动会直接复用依赖。

如果项目或运行数据路径包含中文，启动器会在 `%LOCALAPPDATA%\HomerOfflineDev\`
下建立指向真实源码和 `output\offline-dev` 的 ASCII 目录联接，并用 Node 的
symlink 保留参数启动内部运行时。真实源码和数据仍只保存在项目目录；这是为了规避
SillyTavern/Node 在 Windows 中文真实路径下可能触发的 `0xC0000409` 原生退出。

## 一键使用

双击 `tools\Homer-Offline.cmd`，或在 PowerShell 中运行：

```powershell
.\tools\Homer-Offline.ps1 start
.\tools\Homer-Offline.ps1 status
.\tools\Homer-Offline.ps1 stop
.\tools\Homer-Offline.ps1 reset
```

CMD 入口也接受动作参数：

```bat
tools\Homer-Offline.cmd start
tools\Homer-Offline.cmd status
tools\Homer-Offline.cmd stop
tools\Homer-Offline.cmd reset
```

`start` 默认打开登录页。自动化或不希望打开浏览器时使用：

```powershell
.\tools\Homer-Offline.ps1 start -NoBrowser
```

需要机器可读状态时使用：

```powershell
.\tools\Homer-Offline.ps1 status -Json
```

## 数据和管理员

所有可变内容均位于 `output\offline-dev\`：

- `data\`：独立 SQLite、媒体文件；
- `sillytavern-data\`：各 Homer 用户隔离的 SillyTavern 可重建运行时镜像；
- `logs\`：后端和代理的 stdout/stderr；
- `runtime\processes.json`：仅本项目子进程的 PID 记录；
- `runtime\auth-token-secret.txt`：随机本地 Cookie 签名密钥；
- `runtime\credentials.json`：随机生成的本地管理员邮箱和密码。

启动器不会把管理员密码打印到终端或日志。需要登录时，由本机开发者直接查看
`runtime\credentials.json`。请勿把这个运行目录打包、提交或发给他人；项目的
`.gitignore` 已忽略整个 `output\`。

`reset` 会先验证并停止本项目进程，然后删除整个 `output\offline-dev`，重新生成
数据库、密钥和管理员凭据。它不会操作原交接快照中的 SQLite。

## 安全边界

- 不会使用 `Get-Process python | Stop-Process`；停止前必须同时匹配 PID 记录和命令行。
- 8000、8080 或 8091 被其他程序占用时直接报错，不会结束占用程序。
- 子进程会清除宿主环境中的 LLM、OpenAI、SMTP、Resend、支付、代理等配置。
- 内容模式固定为 `offline`，支付、APK 下载、BYOK 和外部邮件默认关闭。
- 本地网站代理对 8080 页面下发离线 CSP。站点 API、导航、表单和 iframe 保持同源；
  为兼容 RoleplayHub 卡片与已安装公共扩展，仅对脚本、样式、字体、媒体和连接开放
  固定来源白名单（jsDelivr/Fastly、`raw.githubusercontent.com`、Google Fonts、
  GitLab、Thumbsnap、Catbox）。图片预览可加载 HTTPS 图床，但不会因此获得脚本或
  API 权限。未列入白名单的远程代码和连接仍会被拦截。
- 8091 是内部卡片兼容运行时。卡内声明的远程 TavernHelper/MVU
  资源仍需要能访问对应来源；网络不可用时，角色基础对话可打开，但相应卡内 UI
  会按上游行为加载失败。
- Alpine 和本地 Tailwind 浏览器运行时需要动态表达式，因此仅在这个回环地址调试
  CSP 中保留 `unsafe-eval`；外部来源仅限上述兼容白名单，生产 HTML/CSP 不会被修改。
- API 与静态站点保持同源；HttpOnly Cookie 可在普通 HTTP 本地调试。
- SSE 不会整段缓冲，聊天流可逐块透传。

## 故障定位

先运行：

```powershell
.\tools\Homer-Offline.ps1 status
```

如果启动失败，查看：

- `output\offline-dev\logs\backend.err.log`
- `output\offline-dev\logs\proxy.err.log`
- `output\offline-dev\logs\sillytavern.err.log`

正常状态应同时满足：后端、代理和 SillyTavern 进程均为 `running`，三项
health 均为 `OK`。
