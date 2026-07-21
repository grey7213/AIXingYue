# 惑梦开放式聊天扩展运行时设计

## 总体架构

```text
角色卡 / UI 模板 / 已安装扩展
              │ HTML/CSS/JS + manifest
              ▼
     Open Chat Runtime iframe
              │ state / intent postMessage
              ▼
        chat.js Host Controller
              │ 现有 API/SSE
              ▼
   惑梦后端、积分、SQLite、模型节点
```

## 数据结构

`card_experience.chat_shell`：

- `enabled`：是否启用整页界面。
- `name`、`version`：界面标识。
- `html`、`css`、`javascript`：运行时资源。
- `permissions`：声明需要的能力；v1 仅接受平台白名单。
- `fallback`：异常时回退 `default`。

后端只做大小、类型和已知权限归一化；内容通过角色卡 V2 扩展字段 `homer_card_experience` 无损往返。实际代码只在隔离运行时内执行。

## 浏览器运行时

- 新模块 `frontend/app/assets/js/open-chat-runtime.mjs`。
- 单个 iframe 固定覆盖聊天区域；切换角色/锁定版本时重新挂载，普通消息变化只推送 state patch。
- `sandbox="allow-scripts"`，不使用 `allow-same-origin`。
- iframe CSP 默认禁止 connect/frame/form/object；图片、字体和媒体仅允许 data/blob/公开 HTTPS 素材。
- 自定义内容以 Base64/JSON 配置传入 bootstrap，避免 `</script>` 或完整文档破坏宿主 srcdoc。
- 暴露 `window.HomerChat` 以及常用酒馆助手别名：读取消息、发送文本、执行受支持 slash 命令、订阅状态。

已实现的 clean-room 兼容面：

- `window.HomerChat`：状态订阅、发送、续写、重生成、Swipe、编辑、删除、回溯、加载旧消息、TTS、草稿、停止生成、退出和打开原生设置。
- `window.TavernHelper`：`getChatMessages`、消息增删改、变量、宏、事件、`generate/generateRaw` 与停止生成的第一阶段兼容。
- `window.SillyTavern.getContext()`：提供当前聊天镜像、角色/用户名称、事件源和常用事件名。
- 全局别名：`triggerSlash`、`executeSlashCommands`、`eventOn/eventOnce/eventEmit`、变量与宏函数。

此实现只复刻公开 API 行为，不复制 JS-Slash-Runner 源码或构建产物。JS-Slash-Runner 4.8.19 仍深度依赖 SillyTavern 内部模块、同源父 DOM 和服务端扩展接口，并且其 AFPL v9 对商业分发有限制。

## 通信协议

父页面 → iframe：

- `runtime.init`：角色、界面配置、capabilities、channel。
- `state.replace`：完整会话/消息快照。
- `state.patch`：流式消息、生成阶段和 swipe 更新。

iframe → 父页面：

- `runtime.ready`、`runtime.error`。
- `intent.send`、`intent.continue`、`intent.regenerate`。
- `intent.swipe`、`intent.edit`、`intent.delete`、`intent.rollback`。
- `intent.loadOlder`、`intent.tts`、`intent.openSettings`、`intent.exit`。

父页面忽略 iframe 传来的 user_id、积分、模型配置和任意 URL，只使用当前已加载会话和消息对象执行现有方法。

## 接入点

- `card-experience-schema.mjs`：归一化 `chat_shell`。
- `card_experience_extension.py`：服务端归一化和保存。
- `chat.js`：保留现有 controller，新增 mount/sync/intent adapter。
- `chat.html`：新增运行时根节点和父页面安全退出按钮；Open Shell 活跃时隐藏默认消息/输入区。
- Tavo 插件 runtime contributions 后续扩展 `chatShells/actions`，复用同一 host API。

## 扩展包接入

已安装的 `.tpg` 插件可声明 `contributes.chatShells`，每项使用包内文件路径：

```json
{
  "contributes": {
    "chatShells": [{
      "id": "dream-ui",
      "label": "Dream UI",
      "html": "shell/index.html",
      "css": "shell/style.css",
      "javascript": "shell/main.js",
      "permissions": ["read_state", "send", "continue", "exit"],
      "priority": 30
    }]
  }
}
```

管理员启用插件后，角色卡自身没有启用 `chat_shell` 时使用最高优先级的插件 Shell；角色卡自带 Shell 始终优先。包内文件仍在 opaque-origin iframe 中执行，`actions.js` 不会因此进入父页面。

## 降级策略

- 未声明 `chat_shell.enabled`：保持当前默认/Tavo 渲染。
- iframe 3 秒未 ready、脚本异常或用户退出：销毁 iframe并恢复默认 UI。
- 切换会话、退出登录和页面卸载：销毁旧 channel，旧 iframe 消息全部失效。

## 验证

- Node 语法检查、Python 编译和 schema 单元测试。
- Playwright 使用测试 Chat Shell 验证桌面/移动端、自定义气泡、发送及所有 intent。
- 安全断言：无 same-origin、父 DOM/localStorage 不可读、伪造 channel/消息 ID 被拒。
- 旧 Tavo sandbox、续写、回溯、swipe 和普通默认聊天回归。

本地真实 Chromium 已验证自定义整页 UI、所有 Host intents、390×844/1440×960 无溢出、安全边界、伪造 channel、手动退出和异常回退。截图位于 `output/playwright/open-chat-runtime-mobile.png` 与 `output/playwright/open-chat-runtime-desktop.png`。
