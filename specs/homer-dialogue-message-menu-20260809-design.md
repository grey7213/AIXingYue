# 惑梦对话消息长按菜单 Design

日期：2026-08-09

## Prior art 与复用结论

1. 只读交接包 `对话界面UI原型-开发交接包-网站弹窗视觉统一-20260809.zip` 已提供 `520ms` 长按、桌面右键、白色浅粉菜单与遮罩关闭行为；复用其交互节奏和视觉语言，不复制原型的模拟聊天状态机。
2. 固定上游 SillyTavern 1.18.0 已提供消息编辑、生成、Swipe、保存和事件生命周期；Homer bridge 继续调用这些原生能力，不另造聊天状态仓库。
3. 上游 `addLongPressEvent()` 仅处理 touch 且任意移动即取消。本轮用 Pointer Events 实现 `12px` 位移阈值，并补右键和键盘入口，以适配桌面与移动端同一代码路径。

## DOM 与状态

- 常驻消息 DOM 保留，但 Homer CSS 在普通状态隐藏：
  - `.ch_name`、`.mes_buttons`、`.extraMesButtons`；
  - `.homer-message-actions`；
  - `.swipe_left`、`.swipeRightBlock`、`.swipe_right`、`.swipes-counter`。
- 编辑状态通过 `.mes:has(.edit_textarea)` 临时恢复 `.ch_name` 容器，只显示 `.mes_edit_done` 和 `.mes_edit_cancel`。
- bridge 的消息 MutationObserver 不再创建操作条，只为非系统消息补菜单目标 class、`tabindex`、`aria-haspopup`、`data-message-index` 和稳定消息 ID。

菜单使用单个可复用 `<dialog id="homer-message-menu-dialog">`：

```text
dialog
  header: 用户输入/角色回复 + 候选 x/y + 关闭
  action grid: 按消息角色生成按钮
```

- `<dialog>` 进入浏览器 top layer，避免被卡片浮层或 SillyTavern stacking context 遮挡。
- 桌面打开后测量实际尺寸，根据目标 `.mes_text/.mes_block` 矩形放在上方或下方并钳制到视口。
- `max-width:640px` 时改为左右安全边距固定、底部 safe-area 弹层。

## 目标绑定

打开菜单时保存：

```text
messageIndex
messageId = homer_message_id || homer_sync_id || fallback
isUser
```

执行前：

1. 先检查原索引处消息的稳定 ID 是否仍匹配。
2. 不匹配时在当前 `context.chat` 中按稳定 ID 查找。
3. 仍找不到则提示“目标消息已经变化”，不执行任何动作。

这样 MutationObserver 重绘、删除前文或云同步导致索引变化时，菜单不会错误作用于最后一条消息。

## 动作映射

| 菜单动作 | 实现 |
|---|---|
| 复制 | 复制当前 `message.mes`，成功后显示 Homer notice |
| 编辑 | 直接调用 SillyTavern 导出的 `messageEdit(messageIndex)`，复用原生 textarea/save/cancel 和 MESSAGE_EDITED 同步；不依赖已被视觉隐藏的 `.mes_edit` 按钮 |
| 回溯 | 调用现有云端 `/messages/:id/rollback`，再原位裁剪 `context.chat` 并重绘 |
| 删除 | 调用 `/messages/:id/delete`，只移除目标消息并同步本地镜像 |
| 续写/重写/下回 | 复用 `runAction(type,{messageIndex})`；较早消息先确认并移除后续时间线 |
| 上一/下一候选 | 复用 `context.swipe.left/right()`；较早消息先确认并移除后续时间线 |

确认弹窗统一复用 Homer `homer-sheet-dialog` 视觉，不再调用浏览器原生 `window.confirm()`。

## 事件与日志

- Pointer long press：`pointerdown` 启动 `520ms` timer；位移超过 `12px`、`pointerup/cancel` 清理；触发后阻止紧随的 click。
- `contextmenu` 直接打开菜单并阻止浏览器菜单。
- `ContextMenu` 或 `Shift+F10` 从聚焦消息打开。
- 删除/回溯在本地数组变更前记录准确目标事件 ID；重绘时静音原生重复 MESSAGE_DELETED 日志，避免错记下一条消息。
- MESSAGE_SENT/EDITED/DELETED/SWIPED 与 DOM MutationObserver 继续刷新菜单绑定。

## 验证设计

- 静态断言：旧操作条创建函数和 rollback 顶部按钮注入不存在；CSS 对常驻控件提供确定性隐藏。
- E2E 桌面：检查常驻控件不可见；长按用户消息后确认菜单 `mesid`，进入准确消息编辑再取消；右键角色回复执行 regenerate/continue/next 和 Swipe。
- E2E 移动：真实 `520ms` pointer hold 打开底部弹层，测量左右/底部边界并截图。
- 第二会话：从消息长按菜单执行云端 rollback，断言 iframe/宿主页不重载且云端消息实时归零。

## 实现后校正

- 真实 Chromium 首轮回归证明：对隐藏 `.mes_edit` 元素调用 `HTMLElement.click()` 在当前嵌入生命周期中不能稳定打开编辑器；改为调用同一上游模块公开的 `messageEdit()` 后，目标用户消息编辑器稳定打开，仍完全沿用原生保存、取消和事件链。
- 删除和回溯进入临时同步抑制状态时保存旧 `suppressSync`，结束后恢复旧值，避免未来从其他受控批处理调用时错误解除外层同步锁。
