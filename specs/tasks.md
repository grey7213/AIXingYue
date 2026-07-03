# 安卓逆向工程学习项目 - 任务分解

## 当前 CTF 授权验证任务（2026-06-14）

| ID | 任务名称 | 状态 | 验证方式 |
|----|---------|------|----------|
| CTF-1 | 读取项目规则、现有 SPEC、逆向报告 | ✅ 已完成 | 已读取 `specs/*`、README、base-apk/base-1-apk 报告 |
| CTF-2 | 真实工具链发现 | ✅ 已完成 | apktool 3.0.2；Android SDK build-tools 33.0.2；adb 可运行；JADX 因 Java 8 失败 |
| CTF-3 | 运行环境控制权限检查 | ✅ 已完成 | `adb devices -l` 无设备，无法证明 root/管理员运行时控制 |
| CTF-4 | 静态完整性/反篡改边界定位 | ✅ 已完成 | `StubApp.smali`、`libjiagu*.so`、`.jgapp`、v2/v3 签名已定位 |
| CTF-5 | 生成本地篡改-重打包-签名脚本 | ✅ 已完成 | `tools\ctf-apk-control-audit.ps1` |
| CTF-6 | 执行脚本并生成报告 | ✅ 已完成 | 已生成 `reverse-analysis\ctf-control-audit\audit-report.md`，本地 build/align/sign/verify 成功 |
| CTF-7 | adb 动态安装/启动验证 | ⏸️ 阻塞 | 已启动 `sdk_gphone64_x86_64` 模拟器；root 失败且 APK 为 ARM-only，ABI 不匹配 |
| CTF-8 | Python 全流程边界脚本 | ✅ 已完成 | `D:\Anconda3\python.exe .\tools\ctf_breach_pipeline.py --apk .\base.apk --package com.flai.flai --activity com.flai.flai.MainActivity` 默认动态失败返回非 0；`--skip-dynamic` 静态/商店模拟返回 0 |
| CTF-9 | 产物打包 | ✅ 已完成 | `output\ctf-breach-artifacts.zip`，包含重签名 APK、Frida hook、静态分析 JSON、报告、日志 |

### CTF 验证结果摘要

- 本地文件级控制：已确认，可以修改解包副本并生成重签名 APK。
- root/管理员运行时控制：未确认；当前 `sdk_gphone64_x86_64` Google Play USER 镜像返回 `adbd cannot run as root in production builds`，`su: inaccessible or not found`。
- 关键完整性/反篡改：静态边界定位到 `com.stub.StubApp`、`assets/libjiagu*.so`、`assets/.jgapp` 和 v2/v3 APK 签名；动态绕过未验证。
- 签名打包链：最小篡改后的 `reverse-analysis\ctf-control-audit\mutated-signed.apk` 通过 v2/v3 签名验证，但证书 SHA-256 变为 `c65db194b19986fc2e5465a785108d115c4d4e6691bdabdb6dee91cefda1f542`，不能冒充原始证书 `ecb0084ee691d4665c7546ed3f11cc3056663bccf7ccc0b2cf1128c2979785dc`。
- Python 全流程脚本生成两个不同证书的 APK，均通过 `zipalign -c -p -v 4` 和 APK Signature Scheme v2/v3 验证；私有 HTTP store 下载 hash 与 manifest 一致。
- 动态安装阻塞原因：设备 ABI 为 `x86_64`，目标 APK native ABI 为 `arm64-v8a, armeabi-v7a`，脚本现在会在安装前判定不兼容，避免误报。
- 可复跑脚本：`tools\ctf-apk-control-audit.ps1`、`tools\ctf_breach_pipeline.py`。
- 详细边界报告：`reverse-analysis\base-apk\protection-boundary-audit.md`。

## 任务概览

| ID | 任务名称 | 优先级 | 预计时间 | 状态 |
|----|---------|--------|---------|------|
| T1 | 环境准备和工具安装 | P0 | 1h | 🔄 进行中 |
| T2 | APK基础信息提取 | P0 | 30min | ⏸️ 待开始 |
| T3 | APK解包和资源提取 | P0 | 1h | ⏸️ 待开始 |
| T4 | 代码反编译 | P0 | 1h | ⏸️ 待开始 |
| T5 | AndroidManifest深度分析 | P1 | 1h | ⏸️ 待开始 |
| T6 | 代码结构分析 | P1 | 2h | ⏸️ 待开始 |
| T7 | 架构模式识别 | P1 | 2h | ⏸️ 待开始 |
| T8 | 核心功能分析 | P0 | 3h | ⏸️ 待开始 |
| T9 | 技术栈识别 | P1 | 1h | ⏸️ 待开始 |
| T10 | 安全机制分析 | P2 | 2h | ⏸️ 待开始 |
| T11 | 学习总结和文档输出 | P0 | 2h | ⏸️ 待开始 |

---

## T1: 环境准备和工具安装 ⏱️ 1h

### 目标
搭建完整的安卓逆向工程工具链

### 子任务

#### T1.1 检查Java环境
```powershell
java -version  # 需要 JDK 11+
```

**验收**: 输出Java版本 >= 11

#### T1.2 下载和配置 apktool
- 下载地址: https://github.com/iBotPeaches/Apktool/releases
- 文件: apktool_2.9.3.jar
- 放置位置: `E:\酒馆开发\tools\apktool\`
- 创建启动脚本: `apktool.bat`

**验收**: 运行 `apktool.bat` 显示帮助信息

#### T1.3 下载和配置 jadx
- 下载地址: https://github.com/skylot/jadx/releases
- 文件: jadx-1.5.0.zip
- 解压位置: `E:\酒馆开发\tools\jadx\`

**验收**: 运行 `jadx-gui.bat` 启动GUI

#### T1.4 准备备用工具 dex2jar（可选）
- 下载地址: https://github.com/pxb1988/dex2jar/releases
- 解压位置: `E:\酒馆开发\tools\dex2jar\`

---

## T2: APK基础信息提取 ⏱️ 30min

### 目标
获取两个APK的元数据和基本信息

### 分析维度

#### 对 base.apk (75MB)
```powershell
# 1. 基础信息
apktool d -o temp_info base.apk --no-src --no-res

# 2. 提取信息
- 包名
- 版本号和版本名
- 最小SDK版本
- 目标SDK版本
- 权限列表
- 四大组件清单
- 应用入口Activity

# 3. 签名信息
apksigner verify -v --print-certs base.apk
```

#### 对 base (1).apk (44MB)
执行相同分析

### 输出物
- `reverse-analysis/base-apk/apk-info.json`
- `reverse-analysis/base-1-apk/apk-info.json`

**验收**: JSON包含完整元数据，包名/版本/权限清晰

---

## T3: APK解包和资源提取 ⏱️ 1h

### 目标
完整解包APK，提取所有资源文件和Smali代码

### 执行步骤

#### 解包 base.apk
```powershell
apktool d base.apk -o reverse-analysis/base-apk/unpacked
```

#### 解包 base (1).apk
```powershell
apktool d "base (1).apk" -o reverse-analysis/base-1-apk/unpacked
```

### 检查项
- ✅ AndroidManifest.xml 可读（非二进制）
- ✅ res/ 目录完整
- ✅ smali/ 目录存在
- ✅ lib/ 目录（原生库，如果有）
- ✅ assets/ 目录（资产文件）

### 输出物
- 完整解包目录
- 资源文件清单 `resources-list.txt`

**验收**: 可以用文本编辑器打开AndroidManifest.xml

---

## T4: 代码反编译 ⏱️ 1h

### 目标
将DEX字节码反编译为可读的Java源代码

### 方案A: 使用 jadx（主要方案）

#### 命令行方式
```powershell
jadx base.apk -d reverse-analysis/base-apk/decompiled
jadx "base (1).apk" -d reverse-analysis/base-1-apk/decompiled
```

#### GUI方式
```powershell
# 启动jadx-gui
tools\jadx\bin\jadx-gui.bat

# 手动操作:
1. File -> Open -> 选择 base.apk
2. 等待反编译完成
3. File -> Save All -> 选择输出目录
```

### 方案B: 使用 dex2jar + jd-gui（备用）
```powershell
d2j-dex2jar base.apk -o base.jar
# 使用 jd-gui 打开 base.jar
```

### 输出物
- `reverse-analysis/base-apk/decompiled/sources/` - Java源码
- `reverse-analysis/base-apk/decompiled/resources/` - 资源

**验收**: 
- 反编译成功，无致命错误
- 可以看到Java类文件
- 包结构清晰

---

## T5: AndroidManifest深度分析 ⏱️ 1h

### 目标
理解应用的组件结构和权限模型

### 分析内容

#### 1. 应用元信息
- package（包名）
- android:versionCode / versionName
- android:minSdkVersion / targetSdkVersion
- android:label（应用名称）
- android:icon（应用图标）

#### 2. 权限分析
```xml
<uses-permission android:name="..." />
```
分类：
- 网络权限（INTERNET, ACCESS_NETWORK_STATE）
- 存储权限（READ/WRITE_EXTERNAL_STORAGE）
- 位置权限（ACCESS_FINE_LOCATION）
- 相机/录音（CAMERA, RECORD_AUDIO）
- 危险权限（需运行时申请）

#### 3. 四大组件清单

##### Activity（界面）
- 入口Activity（带MAIN和LAUNCHER intent-filter）
- 其他Activity列表
- exported属性（是否允许外部调用）

##### Service（服务）
- 前台服务
- 后台服务
- exported属性

##### BroadcastReceiver（广播接收器）
- 静态注册的接收器
- intent-filter（监听的广播类型）

##### ContentProvider（内容提供者）
- authorities（URI授权）
- exported和permission

#### 4. Intent Filter分析
- 深度链接（Deep Link）
- URL Scheme
- 自定义Action

### 输出物
- `reverse-analysis/base-apk/manifest-analysis.md`

**验收**: 
- 列出所有组件
- 标注入口Activity
- 权限用途说明

---

## T6: 代码结构分析 ⏱️ 2h

### 目标
梳理代码包结构，识别核心模块

### 分析步骤

#### 1. 包结构扫描
```
com.example.app/
├── ui/              # UI层
│   ├── activity/
│   ├── fragment/
│   ├── adapter/
│   └── widget/
├── data/            # 数据层
│   ├── model/
│   ├── repository/
│   └── source/
├── domain/          # 业务逻辑
│   ├── usecase/
│   └── entity/
├── network/         # 网络层
│   ├── api/
│   ├── request/
│   └── response/
├── database/        # 数据库
│   ├── dao/
│   └── entity/
└── utils/           # 工具类
```

#### 2. 关键类识别

##### Application子类
```java
public class MyApplication extends Application {
    @Override
    public void onCreate() {
        // 全局初始化逻辑
    }
}
```

##### 入口Activity
```java
public class MainActivity extends AppCompatActivity {
    // 主界面逻辑
}
```

##### 网络请求接口
```java
public interface ApiService {
    @GET("endpoint")
    Call<Response> getData();
}
```

##### 数据模型
```java
public class User {
    private String id;
    private String name;
    // ...
}
```

#### 3. 类统计
- 总类数量
- 每个包的类数量
- 平均类大小

### 输出物
- `reverse-analysis/base-apk/code-structure.md`
- 包结构树形图
- 关键类清单

**验收**: 
- 包结构图完整
- 识别出至少5个关键类

---

## T7: 架构模式识别 ⏱️ 2h

### 目标
识别应用使用的架构模式和设计模式

### 识别维度

#### 1. 整体架构模式

##### MVVM (Model-View-ViewModel)
特征：
- 使用 ViewModel 类
- LiveData / StateFlow 数据流
- DataBinding / ViewBinding

```java
public class UserViewModel extends ViewModel {
    private MutableLiveData<User> userLiveData;
    
    public LiveData<User> getUser() {
        return userLiveData;
    }
}
```

##### MVP (Model-View-Presenter)
特征：
- Presenter 类作为中介
- View 接口定义
- Contract 接口

##### MVC (Model-View-Controller)
特征：
- Activity/Fragment 直接操作 Model
- 没有明确的 ViewModel 层

##### Clean Architecture
特征：
- domain/ 独立业务逻辑层
- UseCase 类
- Repository 接口
- 依赖注入

#### 2. 设计模式识别

- **单例模式**: getInstance()
- **工厂模式**: Factory类
- **观察者模式**: Listener/Callback
- **策略模式**: Strategy接口
- **适配器模式**: Adapter类
- **建造者模式**: Builder类

#### 3. Repository Pattern
```java
public class UserRepository {
    private UserApiService apiService;
    private UserDao userDao;
    
    public LiveData<User> getUser(String id) {
        // 先从本地数据库获取
        // 然后从网络更新
    }
}
```

### 输出物
- `reverse-analysis/base-apk/architecture-analysis.md`

**验收**: 
- 明确指出使用的架构模式
- 附带代码证据

---

## T8: 核心功能分析 ⏱️ 3h

### 目标
深入分析应用的核心业务逻辑和技术实现

### 分析内容

#### 1. 启动流程追踪
```
AndroidManifest -> Application.onCreate()
    ↓
初始化组件（网络/数据库/DI容器）
    ↓
MainActivity.onCreate()
    ↓
加载首页数据
    ↓
渲染UI
```

#### 2. 核心业务功能识别

通过以下线索：
- Activity/Fragment 名称
- strings.xml 中的功能描述
- 网络API端点
- 数据库表结构

示例功能：
- 用户认证（登录/注册）
- 数据列表展示
- 详情页查看
- 数据提交/更新
- 文件上传/下载

#### 3. 数据流分析

##### 网络请求流
```
UI事件触发
    ↓
ViewModel / Presenter
    ↓
UseCase (可选)
    ↓
Repository
    ↓
NetworkDataSource
    ↓
ApiService (Retrofit/OkHttp)
    ↓
服务器
```

##### 数据持久化流
```
业务数据
    ↓
Repository
    ↓
LocalDataSource
    ↓
DAO (Room) / SQLiteDatabase
    ↓
本地数据库文件
```

#### 4. 状态管理

- LiveData / StateFlow
- SharedPreferences
- 内存缓存
- 事件总线（EventBus / LiveEventBus）

#### 5. 关键算法提取

示例：
- 加密算法（AES/RSA）
- 签名算法（MD5/SHA256）
- 数据压缩
- 自定义业务算法

### 输出物
- `reverse-analysis/base-apk/core-features.md`
- 业务流程图
- 关键代码片段

**验收**: 
- 列出至少3个核心功能
- 每个功能附带流程说明

---

## T9: 技术栈识别 ⏱️ 1h

### 目标
识别应用使用的第三方库和框架

### 识别方法

#### 1. 导入语句分析
```java
import retrofit2.http.GET;           // Retrofit 网络库
import com.google.gson.Gson;          // Gson JSON解析
import androidx.lifecycle.ViewModel;  // Android Jetpack
import kotlinx.coroutines.*;          // Kotlin 协程
```

#### 2. 依赖库检测

扫描常见包名：
- `retrofit2.*` - Retrofit
- `okhttp3.*` - OkHttp
- `com.squareup.picasso.*` - Picasso
- `com.bumptech.glide.*` - Glide
- `io.coil.*` - Coil
- `androidx.room.*` - Room
- `com.google.dagger.*` - Dagger
- `org.koin.*` - Koin
- `io.reactivex.*` - RxJava
- `kotlinx.coroutines.*` - Kotlin Coroutines

#### 3. 原生库分析
```
lib/
├── armeabi-v7a/
│   └── libnative.so    # 32位ARM
├── arm64-v8a/
│   └── libnative.so    # 64位ARM
├── x86/
└── x86_64/
```

### 输出物
- `reverse-analysis/base-apk/tech-stack.md`

技术栈清单模板：
```markdown
## 网络层
- Retrofit 2.9.0
- OkHttp 4.10.0

## 图片加载
- Glide 4.14.0

## 数据库
- Room 2.5.0

## 依赖注入
- Hilt 2.44

## 异步处理
- Kotlin Coroutines
```

**验收**: 识别出至少5个主要依赖库

---

## T10: 安全机制分析 ⏱️ 2h

### 目标
分析应用的安全保护措施和潜在风险点

### 分析维度

#### 1. 代码混淆评估

**未混淆特征**:
- 类名清晰可读（UserActivity, LoginViewModel）
- 方法名语义明确（getUserInfo(), login()）

**已混淆特征**:
```java
public class a {
    public void b(String c) {
        // ...
    }
}
```

#### 2. 网络安全

##### SSL Pinning检测
查找：
```java
CertificatePinner certificatePinner = new CertificatePinner.Builder()
    .add("api.example.com", "sha256/...")
    .build();
```

##### 网络安全配置
检查 `res/xml/network_security_config.xml`:
```xml
<network-security-config>
    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">api.example.com</domain>
    </domain-config>
</network-security-config>
```

#### 3. 数据保护

##### SharedPreferences加密
```java
EncryptedSharedPreferences.create(...)
```

##### 数据库加密
```java
SQLCipherUtils.encrypt(...)
```

##### 敏感数据处理
- 密钥硬编码检查
- Token存储方式
- 用户密码处理

#### 4. 防护措施

##### Root检测
```java
public boolean isDeviceRooted() {
    // 检查 su 命令
    // 检查 Magisk/SuperSU
}
```

##### 模拟器检测
```java
public boolean isEmulator() {
    // 检查 Build 属性
    // 检查特定文件
}
```

##### 调试检测
```java
if (BuildConfig.DEBUG || isDebuggerConnected()) {
    // 防调试逻辑
}
```

##### 签名校验
```java
public boolean verifySignature() {
    // 检查APK签名
}
```

### 输出物
- `reverse-analysis/base-apk/security-analysis.md`

**验收**: 
- 明确说明是否混淆
- 列出发现的安全措施

---

## T11: 学习总结和文档输出 ⏱️ 2h

### 目标
整理分析成果，提炼学习要点

### 输出内容

#### 1. 综合分析报告
`reverse-analysis/base-apk/analysis-report.md`

结构：
```markdown
# APK逆向分析报告

## 1. 应用概述
- 包名
- 版本信息
- 应用类型

## 2. 技术架构
- 架构模式
- 技术栈

## 3. 核心功能
- 功能清单
- 实现方式

## 4. 安全分析
- 保护措施
- 潜在风险

## 5. 学习要点
- 可借鉴的设计
- 技术亮点
```

#### 2. 学习笔记
`learning-notes/`

- `apk-structure.md` - APK文件格式
- `decompilation-techniques.md` - 反编译技术
- `architecture-patterns.md` - 架构模式
- `security-mechanisms.md` - 安全机制

#### 3. 代码片段库
`reverse-analysis/base-apk/findings/code-snippets/`

提取值得学习的代码：
- 优雅的架构实现
- 高效的算法
- 安全的加密方案
- 性能优化技巧

#### 4. 思维导图（可选）
使用Markdown或Mermaid绘制：
- 应用结构图
- 数据流图
- 组件关系图

### 输出物清单

✅ 所有分析报告完成  
✅ 学习笔记整理完毕  
✅ 代码片段归档  
✅ 文档结构清晰  

**验收**: 
- 报告完整且可读
- 包含实际代码示例
- 突出学习价值

---

## 验证检查清单

### 环境验证
- [ ] Java JDK 11+ 已安装
- [ ] apktool 可正常运行
- [ ] jadx 可正常运行

### 数据验证
- [ ] 两个APK都成功解包
- [ ] 两个APK都成功反编译
- [ ] AndroidManifest.xml 可读

### 分析验证
- [ ] APK基础信息完整
- [ ] 代码结构清晰
- [ ] 架构模式已识别
- [ ] 核心功能已分析
- [ ] 技术栈已列出
- [ ] 安全机制已评估

### 文档验证
- [ ] 所有报告生成
- [ ] 学习笔记完成
- [ ] 代码片段提取

---

## 风险和阻塞项

### 已知风险
1. **代码混淆严重** → 影响可读性
   - 缓解：使用Smali辅助分析
2. **应用加固** → 无法直接反编译
   - 缓解：尝试脱壳工具或选择其他APK
3. **原生代码为主** → Java层分析价值有限
   - 缓解：学习Ghidra进行.so分析

### 依赖项
- 所有任务依赖 T1（环境准备）
- T5-T10 依赖 T3-T4（解包和反编译）
- T11 依赖所有分析任务

---

## 完成标准

项目完成当且仅当：
1. ✅ 两个APK完整分析
2. ✅ 所有11个任务标记为"✅ 已完成"
3. ✅ 生成至少10个分析文档
4. ✅ 提取至少20个值得学习的技术要点
5. ✅ 学习笔记结构化整理

---

## 下一步行动

当前待执行：**T1 - 环境准备和工具安装**

立即开始：检查Java环境并下载必要工具
