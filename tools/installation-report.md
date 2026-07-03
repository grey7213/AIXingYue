# 工具安装报告

## ✅ 安装成功

### apktool v3.0.2
- **位置**: `E:\酒馆开发\tools\apktool\apktool.bat`
- **Smali版本**: 3.0.9-dev
- **Baksmali版本**: 3.0.9-dev
- **状态**: ✅ 完全可用

**验证输出**:
```
Apktool 3.0.2
```

## ⚠️ 部分可用

### jadx v1.5.5
- **位置**: `E:\酒馆开发\tools\jadx\bin\jadx.bat`
- **GUI位置**: `E:\酒馆开发\tools\jadx\bin\jadx-gui.bat`
- **状态**: ⚠️ 需要Java 11+

**问题**:
```
UnsupportedClassVersionError: class file version 55.0
```

**原因**: 
- jadx编译时使用Java 11（class file version 55.0）
- 当前系统Java版本：1.8.0_112（class file version 52.0）
- 版本不匹配

**解决方案**:
1. **安装Java 11+** (推荐)
   - 下载: https://adoptium.net/temurin/releases/
   - 选择: JDK 11 或 JDK 17 LTS
   
2. **使用apktool + Smali分析** (当前可行)
   - apktool输出Smali代码（忠实反映字节码）
   - 虽然可读性略低，但更精确
   - 足够完成大部分分析任务

## 工具能力对比

| 功能 | apktool | jadx |
|------|---------|------|
| **解包APK** | ✅ | ✅ |
| **AndroidManifest解析** | ✅ | ✅ |
| **资源提取** | ✅ | ✅ |
| **代码格式** | Smali | Java |
| **可读性** | 中 | 高 |
| **精确度** | 高 | 中 |
| **重新打包** | ✅ | ❌ |
| **当前可用性** | ✅ | ❌ (需Java 11+) |

## 当前策略

### 阶段1: 使用apktool进行完整分析 ✅
1. 解包两个APK
2. 分析AndroidManifest.xml
3. 提取资源文件
4. 阅读Smali代码（核心逻辑）

### 阶段2: 升级Java并使用jadx（可选）
- 如果Smali代码难以理解，再升级Java版本
- 使用jadx获得更易读的Java代码

## Smali代码示例

虽然Smali不如Java直观，但经过学习也可以理解：

**Java代码**:
```java
public String getUserName() {
    return this.userName;
}
```

**对应的Smali代码**:
```smali
.method public getUserName()Ljava/lang/String;
    .locals 1
    iget-object v0, p0, Lcom/example/User;->userName:Ljava/lang/String;
    return-object v0
.end method
```

**解读**:
- `.method` - 方法定义
- `public` - 访问修饰符
- `()Ljava/lang/String;` - 返回String类型
- `iget-object` - 获取对象字段
- `v0` - 局部变量0
- `p0` - 参数0 (this)
- `return-object` - 返回对象

## 下一步行动

✅ **立即开始**: 使用apktool解包和分析APK  
📝 **后续可选**: 安装Java 11并使用jadx获得Java代码视图

---

*报告生成时间: 2026-06-14*
