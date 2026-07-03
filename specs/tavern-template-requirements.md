# AI星月 Tavern Template / 酒馆助手兼容需求

Updated: 2026-07-01

## 目标

- 在 AI星月 Web 后端补齐常见 SillyTavern Prompt Template / 酒馆助手式提示词模板能力。
- 让角色设定、Prompt Manager、世界书、开场白、长期记忆、快捷回复、用户输入、历史消息和模型回复都能使用同一套模板处理链。
- 支持“全局效果”类用法：世界书特殊条目可在生成前插入到消息开头、结尾或指定位置，且可用条件判断控制是否生效。

## 范围

- 支持受限模板语法：`<% if (...) { %>`、`<% } else { %>`、`<% for (...) { %>`、`<%- expr %>`、`<%= expr %>`、`print()`、`getvar()`、`setvar()`。
- 支持基础酒馆助手/Prompt Template 世界书标记：`[GENERATE:BEFORE]`、`[GENERATE:AFTER]`、`[GENERATE:n:BEFORE/AFTER]`、`[GENERATE:REGEX:...]`、`@@generate_before`、`@@generate_after`、`@@if ...`、基础 `@INJECT ...`。
- 继续补齐三个 SillyTavern 插件的常用安全子集：
  - 酒馆助手：保留角色卡 `TavernHelper_scripts` / `extensions.regex_scripts` 到平台 Regex；支持安全 HTML/CSS/JS 渲染 iframe；提供常用变量函数别名。
  - Prompt Template：补齐 `getLocalVar/getGlobalVar`、`incvar/decvar/delvar/insvar`、`injectPrompt/getPromptsInjected`、`getwi/getchar` 等只读或受限写接口。
  - Prompt Template Syntax：补齐常见 JS 表达式写法，如 `??`、字符串/数组基础方法、`for` 循环变体、`switch/case`。
- 支持 `[RENDER:BEFORE]`、`[RENDER:AFTER]`、`@@render_before`、`@@render_after` 在模型回复保存前做受限渲染注入；HTML/Tavo 类内容仍交给前端 sandbox iframe。
- 支持 `[InitialVariables]` / `@@initial_variables` 作为会话变量初始种子，默认只填充缺失变量，避免每轮生成覆盖已变化状态。
- 模板变量按当前用户隔离，并支持全局、角色、会话三类作用域。
- 模型回复如果包含模板语法，需要在保存和展示前处理，避免把控制代码直接显示给用户。

## 非目标

- 不把 SillyTavern 第三方扩展原样安装到 AI星月服务器。
- 不在服务器执行任意 JavaScript、网络请求、文件读写或访问环境变量。
- 不开放普通用户 BYOK 或任意服务器脚本能力。
- 不重打 APK。

## 验收标准

- 本地模板函数验证覆盖：条件、循环、变量读写、世界书 GENERATE 注入、`@INJECT` 插入、回复后 `setvar`。
- 本地补充验证覆盖：变量别名/增减/删除/插入、`injectPrompt`、`getwi/getchar`、`[InitialVariables]`、`[RENDER:*]`、`@INJECT target/index/at`、`switch`、常用字符串方法。
- Web 聊天流式、阻塞、重生成、swipe、群聊、开场白均复用模板处理链。
- 部署后服务和 Nginx active，公网 `/health` 返回 `OK`，`CONTENT_MODE=local_only` 保持不变。
- 线上临时用户/角色 E2E 验证模板变量持久化、Prompt payload 注入、回复后清理和管理端 Gemini 模型真实可用，测试数据清理为 0。
