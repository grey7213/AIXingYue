# 安卓逆向工程学习项目 - 技术设计文档

## 系统架构

```
酒馆开发/
├── specs/                      # 项目规范文档
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md
├── tools/                      # 逆向工程工具
│   ├── apktool/
│   ├── jadx/
│   └── dex2jar/
├── reverse-analysis/           # 分析工作区
│   ├── base-apk/              # 第一个APK分析
│   │   ├── decompiled/        # 反编译源码
│   │   ├── unpacked/          # 解包资源
│   │   ├── analysis-report.md # 分析报告
│   │   └── findings/          # 关键发现
│   └── base-1-apk/            # 第二个APK分析
│       ├── decompiled/
│       ├── unpacked/
│       ├── analysis-report.md
│       └── findings/
├── learning-notes/             # 学习笔记
│   ├── apk-structure.md
│   ├── decompilation-techniques.md
│   ├── architecture-patterns.md
│   └── security-mechanisms.md
└── base.apk / base (1).apk    # 原始APK文件
```

## 技术方案

### 1. APK解包流程

```
APK文件 → apktool decode → 解包目录
                           ├── AndroidManifest.xml (可读XML)
                           ├── res/ (资源文件)
                           ├── smali/ (Smali字节码)
                           ├── lib/ (原生库)
                           └── assets/ (资产文件)
```

**工具选择**：apktool v2.9.0+
- 优势：完整保留资源结构，支持重新打包
- 输出：Smali字节码（低级但精确）

### 2. 代码反编译流程

```
APK文件 → jadx → 反编译源码目录
                 ├── sources/ (Java/Kotlin源码)
                 ├── resources/ (资源文件)
                 └── 导航索引
```

**工具选择**：jadx-gui v1.5.0+
- 优势：直接生成可读的Java代码，UI友好
- 输出：高级语言代码，便于理解业务逻辑

**备用方案**：dex2jar + jd-gui
```
classes.dex → d2j-dex2jar → classes.jar → jd-gui → Java源码
```

### 3. 分析工作流

#### Phase 1: 初步侦察
```python
1. 获取APK基本信息
   - 包名
   - 版本号
   - 最小/目标SDK版本
   - 权限列表
   - 签名信息

2. 评估应用规模
   - DEX文件数量和大小
   - 原生库架构支持（armeabi-v7a, arm64-v8a等）
   - 资源文件数量
   - 是否有代码混淆
```

#### Phase 2: 结构分析
```python
1. Manifest深度分析
   - 四大组件清单（Activity/Service/BroadcastReceiver/ContentProvider）
   - 入口Activity识别
   - 权限使用场景
   - 自定义权限定义

2. 资源文件分析
   - 布局文件（layout/）理解UI结构
   - 字符串资源（strings.xml）理解功能模块
   - 网络配置（network_security_config.xml）
   - 主题和样式
```

#### Phase 3: 代码分析
```python
1. 包结构梳理
   project.package/
   ├── ui/              # UI层
   ├── data/            # 数据层
   ├── domain/          # 业务逻辑层
   ├── network/         # 网络层
   ├── database/        # 数据库层
   └── utils/           # 工具类

2. 关键类识别
   - Application子类（全局初始化）
   - MainActivity（入口点）
   - 网络请求类（API定义）
   - 数据模型类（业务实体）
   - 加密/安全相关类

3. 架构模式识别
   - MVVM: ViewModel + LiveData + DataBinding
   - MVC: Controller直接操作Model和View
   - Clean Architecture: 分层依赖注入
   - Repository Pattern: 数据抽象层
```

#### Phase 4: 内核功能分析
```python
1. 启动流程追踪
   Application.onCreate() 
   → 初始化组件（DI/网络/数据库）
   → MainActivity.onCreate()
   → 首屏渲染

2. 核心业务逻辑
   - 用户认证流程
   - 数据同步机制
   - 核心算法实现
   - 状态管理方案

3. 技术栈识别
   - 网络库：Retrofit/OkHttp/Volley
   - 图片加载：Glide/Picasso/Coil
   - 数据库：Room/SQLite/Realm
   - 依赖注入：Dagger/Hilt/Koin
   - 异步处理：Coroutines/RxJava/AsyncTask
```

#### Phase 5: 安全分析
```python
1. 代码混淆评估
   - ProGuard/R8规则分析
   - 关键类/方法是否保留可读性

2. 数据保护
   - SharedPreferences加密
   - 数据库加密（SQLCipher）
   - 网络通信加密（SSL Pinning）

3. 防护措施
   - Root检测
   - 模拟器检测
   - 调试器检测
   - 完整性校验
```

### 4. 原生库逆向（可选）

如果APK包含关键的.so文件：

```
lib/arm64-v8a/libnative.so → Ghidra/IDA Pro → ARM汇编分析
                                              → 识别JNI函数
                                              → 提取关键算法
```

**工具**：Ghidra（免费开源）或IDA Pro
**难度**：高，需要汇编和C/C++基础

## 技术选型理由

| 工具 | 用途 | 选择理由 |
|------|------|---------|
| apktool | APK解包 | 开源稳定，社区活跃，支持最新Android版本 |
| jadx | 反编译 | 直接输出Java代码，UI友好，反混淆能力强 |
| dex2jar | 备用反编译 | 传统方案，兼容性好，配合jd-gui使用 |
| AXMLPrinter2 | XML解析 | 轻量级，单一功能精准 |

## 数据流图

```
APK文件输入
    ↓
[基础信息提取] → APK元数据JSON
    ↓
[解包] → 资源文件 + Smali代码
    ↓
[反编译] → Java源码
    ↓
[静态分析] → 代码结构图 + 依赖关系
    ↓
[功能分析] → 业务逻辑流程图
    ↓
[学习总结] → Markdown文档 + 思维导图
```

## 输出物清单

1. **APK基础信息报告** (`apk-info.json`)
2. **代码结构分析** (`code-structure.md`)
3. **架构模式识别** (`architecture-analysis.md`)
4. **核心功能说明** (`core-features.md`)
5. **技术栈清单** (`tech-stack.md`)
6. **安全机制分析** (`security-analysis.md`)
7. **学习笔记** (`learning-notes/`)
8. **可借鉴的代码片段** (`findings/code-snippets/`)

## 风险和约束

### 技术风险
- **代码混淆严重**：可能导致反编译代码可读性差
  - 缓解：使用多种工具交叉验证，结合Smali分析
- **原生代码占比高**：Java层只是壳
  - 缓解：使用Ghidra分析.so文件，或聚焦Java层架构学习
- **加壳保护**：APK使用了加固服务（360加固/梆梆加固）
  - 缓解：尝试脱壳工具，或选择未加固的APK学习

### 法律约束
- 仅用于个人学习，不公开传播反编译代码
- 不修改应用用于非法目的
- 遵守软件许可协议

### 工具约束
- Windows环境需要安装Java JDK 11+
- 部分工具需要Python环境
- 大型APK反编译可能需要8GB+内存

## 性能考虑

- **大APK处理**：base.apk (75MB) 反编译可能需要5-10分钟
- **内存占用**：jadx-gui建议分配4GB堆内存（-Xmx4g）
- **存储空间**：每个APK解包后约为原大小的2-3倍

## 后续扩展

学习完成后可以进一步探索：
- 动态调试（Frida/Xposed）
- 流量抓包分析（Charles/Wireshark）
- 自动化逆向脚本开发
- 编写安全加固方案
