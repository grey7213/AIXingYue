# 角色卡正则渲染与舞台协议 v2

## 目标

在不接管网站发送、生成、云存档、实时回溯和账号体系的前提下，让角色卡决定当前会话的视觉舞台，并完整保留 SillyTavern 生态的 Regex、TavernHelper/卡内脚本和 HTML 互动能力。实现必须依据卡内结构字段和标准脚本能力检测，禁止按卡名、角色 ID 或文件名写特例。

## 四层执行顺序

1. **标准生态层**：原生 SillyTavern Regex、世界书、预设、QuickReply、TavernHelper/卡内 JS 按原有事件周期运行。
2. **平台兼容层**：RoleplayHub 等已知结构只做字段转换、变量桥和受控 iframe 执行，不重写角色内容。
3. **声明式舞台层**：读取 Character Card `data.extensions.homer_card_experience` 与 `homer_media_assets`，应用当前卡的布局、气泡、输入栏、背景、视频、立绘、BGM、侧栏、弹窗和场景切换。
4. **结构化组件层**：从最终消息中的 `homer-ui` JSON 代码块建立地图、物品、关系、技能树或状态面板。点击、下钻、搜索和筛选仅修改浏览器 DOM，不调用模型。

四层可以共存。舞台切换只作用于当前角色卡；消息里的组件数据随消息保存，因此刷新可重建、实时回溯会立即移除对应组件。

## 标准卡内字段

```json
{
  "data": {
    "extensions": {
      "homer_card_experience": {
        "version": 2,
        "stage": {
          "enabled": true,
          "layout": "split",
          "chat_width": 58,
          "background_asset_id": "asset-bg",
          "portrait_asset_id": "asset-char",
          "accent_color": "#d7b878",
          "user_bubble_color": "#5b4635",
          "assistant_bubble_color": "#211d19",
          "text_color": "#fff8ed",
          "bubble_radius": 18,
          "font_scale": 1,
          "input_style": "floating"
        },
        "structured_components": {
          "enabled": true,
          "map": true,
          "inventory": true,
          "relationship": true,
          "skill_tree": true,
          "status": true
        },
        "bgm": {},
        "ui_rules": [],
        "sidebars": [],
        "galgame": {}
      },
      "homer_media_assets": []
    }
  }
}
```

`layout` 支持 `standard`、`landscape`、`split`、`visual_novel`。背景素材沿用 `background` 类型，通过真实 MIME 区分图片和 MP4/WebM，避免破坏既有数据库枚举。

## AI 结构化输出语法

作者在角色提示或世界书中要求模型输出 Markdown fenced code block，语言固定为 `homer-ui`，内容是 JSON：

````markdown
```homer-ui
{
  "type": "map",
  "title": "世界地图",
  "root": {
    "id": "world",
    "name": "大陆",
    "description": "当前可探索区域",
    "image": "/media/example.webp",
    "children": [
      {"id": "north", "name": "北境", "x": 31, "y": 28, "children": []}
    ]
  }
}
```
````

支持的 `type`：

- `map`：`root` 为递归区域树；节点支持 `name/description/image/x/y/children/prompt`。
- `inventory`：`items[]` 支持 `name/description/icon/category/quantity/rarity`。
- `relationship`：`center` 与 `nodes[]`，节点支持 `name/relation/description`。
- `skill_tree`：`skills[]` 支持 `name/description/tier/unlocked`。
- `status`：`items[]` 支持 `name/value/max/description`。

原始 JSON 代码块在成功解析后从可见消息中隐藏，替换为声明式组件。无效 JSON、未知组件或超过限额的数据保留为普通代码块，便于作者排错。

## 安全与隐私边界

- 结构化组件只使用 `textContent` 和白名单属性构建 DOM，不执行 JSON 内的 HTML 或 JavaScript。
- 图片/媒体只接受站内绝对路径、HTTPS 和白名单 data image；组件不能主动发起 API 请求。
- 单块最大 100KB、每条消息最多 12 块、列表最大 200 项、地图最大 8 层。
- 卡内可执行 JS 继续在既有批准扩展或受控 iframe/TavernHelper 环境运行，不借结构化组件绕过权限。
- 世界书正文不进入舞台层。侧栏只展示创作者明确填写的公开 HTML；世界书关联仅用于内部场景 ID 和媒体绑定。
- 删除/回溯消息后组件随当前 DOM 立即消失；不会要求刷新页面，也不会把组件状态写到其他角色或新会话。

## 验收标准

- 普通 ST 卡、复杂 Regex/脚本卡与 RoleplayHub 卡现有回归不退化。
- 卡切换后舞台类、背景、音频与悬浮组件完全卸载，无跨卡残留。
- `homer-ui` 地图能按层级下钻和面包屑返回；其他四类组件具备本地交互。
- 结构化组件不会产生模型请求；刷新可按消息重建；回溯无需刷新。
- 工坊可视化配置舞台、图片/视频背景、立绘、BGM、侧栏和五类组件开关。
- 1440×900 与 390×844 无横向溢出，控制台、页面和意外网络错误为 0。
