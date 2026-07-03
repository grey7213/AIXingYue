# AI星月 Tavern Template / 酒馆助手兼容设计

Updated: 2026-07-01

## 设计原则

- AI星月是公网服务，模板执行必须是受限解释器，不执行任意 JS。
- 保持现有单文件 Python 后端和 Alpine 前端结构。
- 所有已有 `apply_macros()` 调用逐步收敛到 `render_tavern_template()`，保留 `{{char}}`、`{{user}}`、`<BOT>`、`<USER>` 兼容。

## 数据结构

新增 SQLite 表：

```sql
template_variables(
  user_id text not null,
  scope text not null,
  scope_id text not null,
  name text not null,
  value_json text,
  updated_at integer not null,
  primary key(user_id, scope, scope_id, name)
)
```

作用域：

- `global`：用户级全局变量，`scope_id=''`。
- `app`：用户在某个角色上的变量，`scope_id=app_id`。
- `conversation`：某个会话变量，`scope_id=conversation_id` 或群聊 id。

## 模板处理链

1. 先做原有宏替换：`{{char}}` / `{{name}}` / `{{user}}` / `<BOT>` / `<USER>`。
2. 如果文本包含 `<%`，走受限 EJS-like 编译器。
3. 模板上下文提供：
   - `variables`：conversation > app > global 合并后的变量。
   - `global_variables`、`character_variables`、`chat_variables`。
   - `char`、`user`、`app`、`message`、`context`。
   - `getvar(path, options)`、`setvar(path, value, options)`、`print()`。
   - 变量函数别名：`getLocalVar/getGlobalVar/getMessageVar`、`setLocalVar/setGlobalVar/setMessageVar`、`incvar/decvar/delvar/insvar` 及对应作用域别名。
   - 只读内容函数：`getwi/getWorldInfo` 从当前角色世界书取条目内容；`getchar/getChara` 返回当前角色或同名可访问角色的精简定义。
   - Prompt slot 函数：`injectPrompt(key, prompt, order)`、`getPromptsInjected(key)`、`hasPromptsInjected(key)` 在同一次生成上下文内传递片段。
4. 模型回复处理在正则脚本前执行，再保存最终文本。

## 世界书特殊注入

- `@@if <expr>`：表达式为 false 时跳过该条目。
- `[GENERATE:BEFORE]` / `@@generate_before`：插入 prompt 消息开头。
- `[GENERATE:AFTER]` / `@@generate_after`：插入 prompt 消息结尾。
- `[GENERATE:n:BEFORE/AFTER]`：插入指定消息前/后。
- `[GENERATE:REGEX:pattern]`：命中任一消息内容时插入对应消息前。
- `@INJECT pos=...,role=...`、`target=...`、`regex=...`：生成独立消息插入。
- `[RENDER:BEFORE]` / `@@render_before`：在模型回复前插入渲染内容。
- `[RENDER:AFTER]` / `@@render_after`：在模型回复后插入渲染内容。
- `[InitialVariables]` / `@@initial_variables`：把 JSON 对象作为当前会话变量初始种子，只写入缺失顶层变量。

## 导入与渲染兼容

- 角色卡导入时继续保留 `extensions` 原文。
- `extensions.regex_scripts` 和 `extensions.TavernHelper_scripts` 会规范化为平台顶层 `regex_scripts`，聊天链路统一执行。
- 酒馆助手/Tavo 类 HTML/CSS/JS 不进入主 DOM，继续由 `/app/chat.html` 的 sandbox iframe 渲染，服务器只负责模板和 Regex 处理。

## 安全限制

- 只允许白名单 Python AST 节点和函数。
- 禁止 import、函数/类定义、lambda、while、try、with、属性名以下划线开头、未知函数调用。
- `execute`、网络请求、文件读写、任意浏览器/服务器 API 访问不实现；模板里出现这些能力时不会获得主站权限。
- 模板输出和变量大小裁剪，避免单条角色卡撑爆 prompt。
- 模板异常不会阻断聊天，只记录简短日志并保留原文去除控制副作用。

## 前端

- 创建页提示文案补充模板语法说明，避免用户以为只能 `{{char}}/{{user}}`。
- 现有 Tavo iframe 渲染继续负责可视化 HTML，不与服务器模板执行混用。
