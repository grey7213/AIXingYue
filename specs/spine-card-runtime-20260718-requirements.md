# Spine 卡片与交互桥接需求（2026-07-18）

## 目标

- 修复完整 HTML 开场卡调用 `window.triggerSlash()` 时无法把角色设定发送到当前会话的问题。
- 完整资源包识别 Spine 骨骼、atlas 和纹理文件，不把它们误当普通立绘或未知文件静默丢弃。
- 在不削弱 iframe sandbox/CSP、素材所有权和上传校验的前提下，为后续 Spine 渲染保存完整资源组信息。

## 验收

- `黎明之契2.71` 点击“踏上旅程”后产生一次真实用户消息，不再显示“未提供发送接口”。
- 发送事件只接受当前页面的 `iframe.tavo-frame`，限制消息长度，生成中不重复发送。
- `.json/.skel + .atlas + png/webp` Spine 文件组可被资源包解析、上传并原样关联；缺少骨骼、atlas 或纹理时明确报错。
- 旧 JSON/PNG、立绘、背景、BGM 和 Tavo sandbox 回归通过。
