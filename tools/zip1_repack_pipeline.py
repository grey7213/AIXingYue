#!/usr/bin/env python3
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "reverse-analysis" / "zip-1-target"
RAW = WORK / "raw"
DECODED = WORK / "decoded-base-1-full"
INJECT_SRC = WORK / "inject-src" / "org" / "nebula" / "horizon" / "composeai" / "ctf" / "RechargeActivity.java"
INJECT_CLASSES = WORK / "inject-build" / "classes"
INJECT_DEX_DIR = WORK / "inject-build" / "dex"
INJECT_DEX = INJECT_DEX_DIR / "classes.dex"
INJECT_JAR = WORK / "inject-build" / "recharge-classes.jar"
OUT = ROOT / "output" / "zip-1-repack"
STAGE = Path("E:/z1")
SRC_ALIAS = Path("E:/a")

PACKAGE = "org.nebula.horizon.composeai"
MAIN_ACTIVITY = "org.nebula.horizon.composeai.MainActivity"
RECHARGE_ACTIVITY = "org.nebula.horizon.composeai.ctf.RechargeActivity"
DEFAULT_LOCAL_SERVER_URL = "http://10.0.2.2:8000/"
DEFAULT_SERVER_NODES_SMALI = DECODED / "smali_classes5" / "org" / "nebula" / "horizon" / "composeai" / "core" / "common" / "constants" / "DefaultServerNodes.smali"
NETWORK_SECURITY_CONFIG = DECODED / "res" / "xml" / "network_security_config.xml"
NODE_TEST_SERVICE_SMALI = DECODED / "smali_classes5" / "org" / "nebula" / "horizon" / "composeai" / "core" / "data" / "remote" / "NodeTestService.smali"
ORIGINAL_SERVER_URLS = [
    "https://aiporn.tw/",
    "https://aigirlfriend.baby/",
    "https://aigirlfriend.homes/",
    "https://botherstand.xyz/",
    "https://aigirlfriendnow.com/",
    "https://aitrader.wiki/",
    "https://acepro.store/",
    "https://aifuck.cc/",
    "https://testaf.aiero.cc/",
    "https://acquainte.xyz/",
    "https://acquant.xyz/",
    "https://affectional.xyz/",
    "https://aiaha.xyz/",
    "https://aiaka.xyz/",
    "https://brothe.xyz/",
    "https://chatchatlines.xyz/",
    "https://chation.xyz/",
]
KNOWN_PATCHED_SERVER_URLS = [
    DEFAULT_LOCAL_SERVER_URL,
    "https://villainy.top/",
    "https://patcher.villainy.top/",
]


RECHARGE_JAVA = r'''package org.nebula.horizon.composeai.ctf;

import android.app.Activity;
import android.os.Bundle;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.DateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class RechargeActivity extends Activity {
    private static final String PREFS = "ctf_recharge_module";
    private static final String PRODUCT_ID = "ctf_internal_recharge_100";
    private static final String RECHARGE_URL = "https://patcher.villainy.top/console/api/ctf/recharge";
    private static final Pattern TOKEN_PATTERN = Pattern.compile("local\\.[A-Za-z0-9_-]+");
    private TextView status;
    private TextView details;
    private SharedPreferences prefs;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        setTitle("AI星月 - 充值模块");
        setContentView(buildLayout());
        renderState();
    }

    private View buildLayout() {
        int pad = dp(20);
        ScrollView scrollView = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        scrollView.addView(root, new ScrollView.LayoutParams(-1, -2));

        TextView title = new TextView(this);
        title.setText("内置充值收费模块");
        title.setTextSize(24f);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.rgb(28, 35, 45));
        root.addView(title, new LinearLayout.LayoutParams(-1, -2));

        TextView subtitle = new TextView(this);
        subtitle.setText("先完成注册/登录，再在这里触发服务器充值，积分会写入当前账号。");
        subtitle.setTextSize(15f);
        subtitle.setTextColor(Color.rgb(82, 92, 110));
        LinearLayout.LayoutParams subtitleParams = new LinearLayout.LayoutParams(-1, -2);
        subtitleParams.setMargins(0, dp(8), 0, dp(18));
        root.addView(subtitle, subtitleParams);

        status = new TextView(this);
        status.setTextSize(18f);
        status.setTypeface(Typeface.DEFAULT_BOLD);
        status.setTextColor(Color.WHITE);
        status.setPadding(dp(14), dp(12), dp(14), dp(12));
        root.addView(status, new LinearLayout.LayoutParams(-1, -2));

        details = new TextView(this);
        details.setTextSize(15f);
        details.setTextColor(Color.rgb(36, 43, 55));
        details.setLineSpacing(0f, 1.15f);
        LinearLayout.LayoutParams detailParams = new LinearLayout.LayoutParams(-1, -2);
        detailParams.setMargins(0, dp(16), 0, dp(18));
        root.addView(details, detailParams);

        Button recharge = new Button(this);
        recharge.setText("充值 100 积分");
        recharge.setAllCaps(false);
        recharge.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                activateRecharge();
            }
        });
        root.addView(recharge, new LinearLayout.LayoutParams(-1, dp(52)));

        Button reset = new Button(this);
        reset.setText("刷新本地显示状态");
        reset.setAllCaps(false);
        reset.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                renderState();
                Toast.makeText(RechargeActivity.this, "已刷新", Toast.LENGTH_SHORT).show();
            }
        });
        LinearLayout.LayoutParams resetParams = new LinearLayout.LayoutParams(-1, dp(52));
        resetParams.setMargins(0, dp(10), 0, 0);
        root.addView(reset, resetParams);

        return scrollView;
    }

    private void activateRecharge() {
        status.setText("正在连接服务器充值...");
        status.setBackgroundColor(Color.rgb(70, 98, 150));
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    String token = findLoginToken();
                    if (token.length() == 0) {
                        throw new IllegalStateException("未找到登录 token，请先在主应用完成注册/登录");
                    }
                    String orderId = "PCH-" + UUID.randomUUID().toString().replace("-", "").substring(0, 12).toUpperCase(Locale.US);
                    String requestBody = "{\"product_id\":\"" + PRODUCT_ID + "\",\"points\":100,\"client_order_id\":\"" + orderId + "\"}";
                    HttpURLConnection conn = (HttpURLConnection) new URL(RECHARGE_URL).openConnection();
                    conn.setRequestMethod("POST");
                    conn.setConnectTimeout(12000);
                    conn.setReadTimeout(12000);
                    conn.setDoOutput(true);
                    conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                    conn.setRequestProperty("Authorization", "Bearer " + token);
                    OutputStream out = conn.getOutputStream();
                    out.write(requestBody.getBytes("UTF-8"));
                    out.close();
                    int code = conn.getResponseCode();
                    InputStream in = code >= 200 && code < 400 ? conn.getInputStream() : conn.getErrorStream();
                    String response = readAll(in);
                    if (code < 200 || code >= 300 || !response.contains("\"success\"")) {
                        throw new IllegalStateException("服务器拒绝充值: HTTP " + code + " " + response);
                    }
                    String points = extractJsonString(response, "points");
                    String serverOrderId = extractJsonString(response, "order_id");
                    long now = System.currentTimeMillis();
                    prefs.edit()
                            .putBoolean("paid", true)
                            .putInt("balance", parseInt(points, 100))
                            .putString("product_id", PRODUCT_ID)
                            .putString("order_id", serverOrderId.length() > 0 ? serverOrderId : orderId)
                            .putLong("paid_at", now)
                            .putString("status", "Server verified")
                            .apply();
                    postSuccess("服务器充值成功，当前积分：" + (points.length() > 0 ? points : "已更新"));
                } catch (Exception e) {
                    postFailure(e.getMessage() == null ? e.toString() : e.getMessage());
                }
            }
        }).start();
    }

    private void renderState() {
        boolean paid = prefs.getBoolean("paid", false);
        int balance = prefs.getInt("balance", 0);
        String orderId = prefs.getString("order_id", "-");
        String productId = prefs.getString("product_id", PRODUCT_ID);
        String state = prefs.getString("status", "Not paid");
        long paidAt = prefs.getLong("paid_at", 0L);

        if (paid) {
            status.setText("付费状态：已充值 / 可使用");
            status.setBackgroundColor(Color.rgb(26, 128, 78));
        } else {
            status.setText("付费状态：未充值");
            status.setBackgroundColor(Color.rgb(176, 112, 24));
        }
        details.setText("产品：" + productId
                + "\n余额：" + balance + " 积分"
                + "\n订单：" + orderId
                + "\n验证：" + state
                + "\n时间：" + formatTime(paidAt));
    }

    private void postSuccess(final String message) {
        mainHandler.post(new Runnable() {
            @Override
            public void run() {
                renderState();
                Toast.makeText(RechargeActivity.this, message, Toast.LENGTH_LONG).show();
            }
        });
    }

    private void postFailure(final String message) {
        mainHandler.post(new Runnable() {
            @Override
            public void run() {
                status.setText("充值失败：需要先登录");
                status.setBackgroundColor(Color.rgb(176, 50, 50));
                details.setText("错误：" + message + "\n接口：" + RECHARGE_URL + "\n处理：返回主应用完成邮箱注册/登录后再打开本页。");
                Toast.makeText(RechargeActivity.this, "充值失败：" + message, Toast.LENGTH_LONG).show();
            }
        });
    }

    private String findLoginToken() {
        File root = getApplicationContext().getDataDir();
        String token = scanFileTree(root, 0);
        if (token.length() > 0) {
            return token;
        }
        String[] prefsNames = new String[] {"ctf_recharge_module", "settings", "user", "auth", "login"};
        for (String name : prefsNames) {
            String value = getSharedPreferences(name, MODE_PRIVATE).getString("token", "");
            if (value != null && value.startsWith("local.")) {
                return value;
            }
        }
        return "";
    }

    private String scanFileTree(File file, int depth) {
        if (file == null || !file.exists() || depth > 5) {
            return "";
        }
        if (file.isFile() && file.length() < 1024 * 1024) {
            try {
                FileInputStream in = new FileInputStream(file);
                byte[] data = new byte[(int) file.length()];
                int read = in.read(data);
                in.close();
                if (read > 0) {
                    Matcher m = TOKEN_PATTERN.matcher(new String(data, 0, read, "UTF-8"));
                    if (m.find()) {
                        return m.group();
                    }
                }
            } catch (Exception ignored) {
            }
            return "";
        }
        File[] children = file.listFiles();
        if (children == null) {
            return "";
        }
        for (File child : children) {
            String value = scanFileTree(child, depth + 1);
            if (value.length() > 0) {
                return value;
            }
        }
        return "";
    }

    private String readAll(InputStream in) throws Exception {
        if (in == null) {
            return "";
        }
        BufferedReader reader = new BufferedReader(new InputStreamReader(in, "UTF-8"));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) {
            sb.append(line);
        }
        reader.close();
        return sb.toString();
    }

    private String extractJsonString(String json, String key) {
        Pattern p = Pattern.compile("\"" + Pattern.quote(key) + "\"\\s*:\\s*\"?([^\",}]+)\"?");
        Matcher m = p.matcher(json == null ? "" : json);
        return m.find() ? m.group(1) : "";
    }

    private int parseInt(String value, int fallback) {
        try {
            return Integer.parseInt(value);
        } catch (Exception e) {
            return fallback;
        }
    }

    private String formatTime(long millis) {
        if (millis <= 0L) {
            return "-";
        }
        return DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT).format(new Date(millis));
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }
}
'''


def log(message: str) -> None:
    print(f"[zip1-repack] {message}", flush=True)


def run(cmd, cwd=ROOT, check=True):
    printable = " ".join(str(x) for x in cmd)
    log(printable)
    env = os.environ.copy()
    env["JAVA_HOME"] = str(find_java_home())
    env["PATH"] = str(find_java_home() / "bin") + os.pathsep + env.get("PATH", "")
    p = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if p.stdout:
        print(p.stdout, end="" if p.stdout.endswith("\n") else "\n")
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed with exit code {p.returncode}: {printable}")
    return p


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_java_home() -> Path:
    for p in [Path("E:/android/AndroidStudio/jbr"), Path("E:/Android/AndroidStudio/jbr")]:
        if (p / "bin" / "java.exe").exists():
            return p
    env = os.environ.get("JAVA_HOME")
    if env and (Path(env) / "bin" / "java.exe").exists():
        return Path(env)
    raise FileNotFoundError("Android Studio JBR not found. Expected E:/android/AndroidStudio/jbr.")


def find_sdk() -> Path:
    for p in [Path("E:/android/Sdk"), Path("E:/Android/Sdk"), Path(os.environ.get("ANDROID_HOME", "")), Path(os.environ.get("ANDROID_SDK_ROOT", ""))]:
        if p and (p / "platforms").exists() and (p / "build-tools").exists():
            return p
    raise FileNotFoundError("Android SDK not found. Expected E:/android/Sdk.")


def newest_build_tools(sdk: Path) -> Path:
    required = ["zipalign.exe", "apksigner.bat", "d8.bat"]
    dirs = [
        p for p in (sdk / "build-tools").iterdir()
        if p.is_dir() and all((p / item).exists() for item in required)
    ]
    if not dirs:
        raise FileNotFoundError("No complete Android build-tools with zipalign/apksigner/d8 installed.")
    return sorted(dirs, key=lambda p: [int(x) if x.isdigit() else x for x in p.name.replace("-", ".").split(".")])[-1]


def ensure_dirs() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    STAGE.mkdir(parents=True, exist_ok=True)
    INJECT_SRC.parent.mkdir(parents=True, exist_ok=True)
    INJECT_CLASSES.mkdir(parents=True, exist_ok=True)
    INJECT_DEX_DIR.mkdir(parents=True, exist_ok=True)


def ensure_junction(alias: Path, target: Path) -> None:
    if alias.exists() or alias.is_symlink():
        subprocess.run(["cmd", "/c", "rmdir", "/S", "/Q", str(alias)], check=False)
    alias.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(target)], check=True)


def windows_long_path(path: Path) -> str:
    resolved = str(path.resolve())
    if os.name == "nt" and not resolved.startswith("\\\\?\\"):
        return "\\\\?\\" + resolved
    return resolved


def remove_work_tree(path: Path) -> None:
    resolved = path.resolve()
    work_root = WORK.resolve()
    if resolved == work_root or work_root not in resolved.parents:
        raise RuntimeError(f"refusing to delete outside work tree: {resolved}")
    if path.exists():
        shutil.rmtree(windows_long_path(path))


def extract_zip_if_needed() -> Path:
    ensure_dirs()
    target = RAW / "base (1).apk"
    if target.exists():
        return target
    zip_path = ROOT / "1.zip"
    if not zip_path.exists():
        raise FileNotFoundError("1.zip not found in workspace root.")
    log("extracting 1.zip")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(RAW)
    if not target.exists():
        raise FileNotFoundError("base (1).apk not found after extraction.")
    return target


def ensure_decoded(apktool: Path, apk: Path, force_decode: bool) -> None:
    if force_decode and DECODED.exists():
        remove_work_tree(DECODED)
    if (DECODED / "AndroidManifest.xml").exists():
        log(f"using existing decode: {DECODED}")
        return
    run([str(apktool), "d", str(apk), "-o", str(DECODED), "-f"])


def normalize_base_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        raise ValueError("server URL cannot be empty")
    if not value.startswith(("http://", "https://")):
        raise ValueError("server URL must start with http:// or https://")
    if not value.endswith("/"):
        value += "/"
    return value


def patch_server_nodes(server_url: str | None) -> str | None:
    if not server_url:
        return None
    target_url = normalize_base_url(server_url)
    smali = DEFAULT_SERVER_NODES_SMALI
    if not smali.exists():
        raise FileNotFoundError(f"DefaultServerNodes smali not found: {smali}")
    text = smali.read_text(encoding="utf-8")
    replaced = 0
    replacement_candidates = list(dict.fromkeys(ORIGINAL_SERVER_URLS + KNOWN_PATCHED_SERVER_URLS))
    for original in replacement_candidates:
        if original == target_url:
            continue
        count = text.count(original)
        if count:
            replaced += count
            text = text.replace(original, target_url)
    already_count = text.count(target_url)
    smali.write_text(text, encoding="utf-8")
    remaining = [url for url in ORIGINAL_SERVER_URLS if url in text]
    if remaining:
        raise RuntimeError("server node patch incomplete; remaining URLs: " + ", ".join(remaining))
    if replaced == 0 and already_count == 0:
        raise RuntimeError("server node patch did not find any original, previous, or target URLs")
    log(f"patched server nodes to {target_url}; replacements={replaced}; target_occurrences={text.count(target_url)}")
    return target_url


def patch_network_security_config(server_url: str | None) -> None:
    if not server_url or not NETWORK_SECURITY_CONFIG.exists():
        return
    parsed = urlparse(server_url)
    hosts = {"10.0.2.2", "127.0.0.1", "localhost"}
    if parsed.scheme == "http" and parsed.hostname:
        hosts.add(parsed.hostname)
    tree = ET.parse(NETWORK_SECURITY_CONFIG)
    root = tree.getroot()
    domain_config = None
    for child in root.findall("domain-config"):
        if child.attrib.get("cleartextTrafficPermitted") == "true":
            domain_config = child
            break
    if domain_config is None:
        domain_config = ET.SubElement(root, "domain-config", {"cleartextTrafficPermitted": "true"})
    existing = {domain.text for domain in domain_config.findall("domain") if domain.text}
    added = []
    for host in sorted(hosts):
        if host not in existing:
            element = ET.SubElement(domain_config, "domain", {"includeSubdomains": "false"})
            element.text = host
            added.append(host)
    if added:
        ET.indent(tree, space="    ")
        tree.write(NETWORK_SECURITY_CONFIG, encoding="utf-8", xml_declaration=True)
        log("patched network security cleartext hosts: " + ", ".join(added))
    else:
        log("network security cleartext hosts already configured")


def patch_branding(app_name: str = "AI星月", content_parity: bool = False) -> None:
    if content_parity:
        replacements = {
            "AI风月": app_name,
        }
    else:
        replacements = {
            "AI风月": app_name,
            "风月币": "星月币",
            "风月AI": "星月AI",
            "百度贴吧—风月AI吧": "百度贴吧—星月AI吧",
        }
    targets = [
        DECODED / "res" / "values" / "strings.xml",
        DECODED / "res" / "values-en" / "strings.xml",
        DECODED / "assets" / "webapp" / "index.html",
    ]
    for path in targets:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        original = text
        for old, new in replacements.items():
            text = text.replace(old, new)
        if not content_parity:
            text = text.replace("欢迎来到AI风月", f"欢迎来到{app_name}")
            text = text.replace("AI风月 本地服务器", f"{app_name} 本地服务器")
            text = text.replace("AI风月 CTF APK server binding", f"{app_name} CTF APK server binding")
        if text != original:
            path.write_text(text, encoding="utf-8")
            log(f"patched branding in {path.relative_to(ROOT)}")


def patch_node_test_latency(server_url: str | None) -> None:
    if not server_url:
        return
    smali = NODE_TEST_SERVICE_SMALI
    if not smali.exists():
        raise FileNotFoundError(f"NodeTestService smali not found: {smali}")
    text = smali.read_text(encoding="utf-8")
    method_start = '.method private final testSingleNodeLatency(Ljava/lang/String;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;'
    start = text.find(method_start)
    if start < 0:
        raise RuntimeError("testSingleNodeLatency method start not found")
    end = text.find(".end method", start)
    if end < 0:
        raise RuntimeError("testSingleNodeLatency method end not found")
    end += len(".end method")
    patched = """\
.method private final testSingleNodeLatency(Ljava/lang/String;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;
    .locals 2

    const-wide/16 v0, 0x1

    invoke-static {v0, v1}, Lkotlin/coroutines/jvm/internal/Boxing;->boxLong(J)Ljava/lang/Long;

    move-result-object p1

    return-object p1
.end method"""
    if text[start:end] == patched:
        log("NodeTestService latency patch already applied")
        return
    smali.write_text(text[:start] + patched + text[end:], encoding="utf-8")
    log("patched NodeTestService.testSingleNodeLatency to accept local backend")


def ensure_injection_source() -> None:
    INJECT_SRC.write_text(RECHARGE_JAVA, encoding="utf-8")
    log(f"wrote injection source: {INJECT_SRC}")


def patch_manifest() -> None:
    manifest = DECODED / "AndroidManifest.xml"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace(' android:dataExtractionRules="@xml/data_extraction_rules"', "")
    text = text.replace(' android:enableOnBackInvokedCallback="true"', "")
    text = text.replace('android:label="内置充值"', 'android:label="AI星月充值"')
    if RECHARGE_ACTIVITY in text:
        manifest.write_text(text, encoding="utf-8")
        log("manifest already contains RechargeActivity")
        return
    marker = '        <provider android:authorities="org.nebula.horizon.composeai.fileprovider"'
    block = '''        <activity android:exported="true" android:label="AI星月充值" android:name="org.nebula.horizon.composeai.ctf.RechargeActivity" android:theme="@style/Theme.ComposeAI">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
'''
    if marker not in text:
        raise RuntimeError("manifest insertion marker not found")
    manifest.write_text(text.replace(marker, block + marker, 1), encoding="utf-8")
    log("patched AndroidManifest.xml")


def compile_injection(sdk: Path, build_tools: Path) -> None:
    java_home = find_java_home()
    android_jar = sdk / "platforms" / "android-33" / "android.jar"
    if not android_jar.exists():
        platforms = sorted((sdk / "platforms").glob("android-*/android.jar"))
        if not platforms:
            raise FileNotFoundError("No android.jar platform found.")
        android_jar = platforms[-1]
    if INJECT_CLASSES.exists():
        shutil.rmtree(INJECT_CLASSES)
    if INJECT_DEX_DIR.exists():
        shutil.rmtree(INJECT_DEX_DIR)
    INJECT_CLASSES.mkdir(parents=True, exist_ok=True)
    INJECT_DEX_DIR.mkdir(parents=True, exist_ok=True)
    run([str(java_home / "bin" / "javac.exe"), "-encoding", "UTF-8", "-source", "8", "-target", "8", "-bootclasspath", str(android_jar), "-d", str(INJECT_CLASSES), str(INJECT_SRC)])
    if INJECT_JAR.exists():
        INJECT_JAR.unlink()
    run([str(java_home / "bin" / "jar.exe"), "cf", str(INJECT_JAR), "-C", str(INJECT_CLASSES), "."])
    d8 = build_tools / "d8.bat"
    run([str(d8), "--min-api", "24", "--output", str(INJECT_DEX_DIR), str(INJECT_JAR)])
    if not INJECT_DEX.exists():
        raise FileNotFoundError("d8 did not create injection classes.dex")


def build_unsigned(apktool: Path) -> Path:
    ensure_junction(SRC_ALIAS, DECODED)
    unsigned = STAGE / "ai-fengyue-repacked-unsigned.apk"
    if unsigned.exists():
        unsigned.unlink()
    run([str(apktool), "b", str(SRC_ALIAS), "-o", str(unsigned)])
    shutil.copy2(unsigned, OUT / unsigned.name)
    return unsigned


def inject_extra_dex(unsigned: Path) -> Path:
    injected = STAGE / "ai-fengyue-repacked-with-recharge-unaligned.apk"
    if injected.exists():
        injected.unlink()
    with zipfile.ZipFile(unsigned, "r") as zin, zipfile.ZipFile(injected, "w") as zout:
        for info in zin.infolist():
            name = info.filename
            if name.startswith("META-INF/") and name.upper().endswith((".RSA", ".DSA", ".EC", ".SF", ".MF")):
                continue
            if name == "classes6.dex":
                continue
            zout.writestr(info, zin.read(name))
        dex_info = zipfile.ZipInfo("classes6.dex")
        dex_info.compress_type = zipfile.ZIP_STORED
        dex_info.external_attr = 0o644 << 16
        zout.writestr(dex_info, INJECT_DEX.read_bytes())
    log(f"added injection dex as classes6.dex ({INJECT_DEX.stat().st_size} bytes)")
    shutil.copy2(injected, OUT / injected.name)
    return injected


def ensure_keystore(java_home: Path) -> Path:
    keystore = STAGE / "zip1-repack.keystore"
    if keystore.exists():
        shutil.copy2(keystore, OUT / keystore.name)
        return keystore
    run([
        str(java_home / "bin" / "keytool.exe"),
        "-genkeypair", "-v",
        "-keystore", str(keystore),
        "-storepass", "changeit",
        "-keypass", "changeit",
        "-alias", "zip1repack",
        "-keyalg", "RSA",
        "-keysize", "2048",
        "-validity", "3650",
        "-dname", "CN=zip1-repack,O=CTF,L=Local,ST=Local,C=US",
    ])
    shutil.copy2(keystore, OUT / keystore.name)
    return keystore


def align_and_sign(build_tools: Path, unaligned: Path, keystore: Path, output_stem: str) -> Path:
    aligned = STAGE / "ai-fengyue-repacked-aligned.apk"
    signed = STAGE / f"{output_stem}.apk"
    for p in [aligned, signed]:
        if p.exists():
            p.unlink()
    run([str(build_tools / "zipalign.exe"), "-p", "-f", "4", str(unaligned), str(aligned)])
    run([
        str(build_tools / "apksigner.bat"),
        "sign",
        "--ks", str(keystore),
        "--ks-pass", "pass:changeit",
        "--key-pass", "pass:changeit",
        "--out", str(signed),
        str(aligned),
    ])
    run([str(build_tools / "apksigner.bat"), "verify", "--verbose", "--print-certs", str(signed)])
    run([str(build_tools / "zipalign.exe"), "-c", "-p", "-v", "4", str(signed)])
    out_signed = OUT / signed.name
    shutil.copy2(aligned, OUT / aligned.name)
    shutil.copy2(signed, out_signed)
    return out_signed


def adb_verify(sdk: Path, apk: Path, clear_data: bool = False) -> None:
    adb = sdk / "platform-tools" / "adb.exe"
    if not adb.exists():
        log("adb not found; skipping runtime verification")
        return
    devices = run([str(adb), "devices", "-l"], check=False)
    lines = [line for line in devices.stdout.splitlines() if "\tdevice" in line]
    if not lines:
        log("no adb device connected; skipping install/start verification")
        return
    run([str(adb), "install", "-r", str(apk)])
    if clear_data:
        run([str(adb), "shell", "pm", "clear", PACKAGE], check=False)
    run([str(adb), "shell", "am", "start", "-n", f"{PACKAGE}/{MAIN_ACTIVITY}"], check=False)
    run([str(adb), "shell", "am", "start", "-n", f"{PACKAGE}/{RECHARGE_ACTIVITY}"], check=False)
    screenshot = OUT / "ai-fengyue-recharge-screen.png"
    with screenshot.open("wb") as f:
        p = subprocess.run([str(adb), "exec-out", "screencap", "-p"], stdout=f)
        log(f"screenshot capture exit={p.returncode}: {screenshot}")


def write_report(apk: Path, source_apk: Path, server_url: str | None) -> Path:
    report = OUT / "final-report.md"
    text = rf"""# 1.zip AI风月 Repack Report

## Result

- Target: `base (1).apk`
- Package: `{PACKAGE}`
- Original launcher: `{MAIN_ACTIVITY}`
- Added launcher: `{RECHARGE_ACTIVITY}`
- Output APK: `{apk}`
- Output SHA-256: `{sha256(apk)}`
- Source APK SHA-256: `{sha256(source_apk)}`
- Bound server URL: `{server_url or "not patched; original node list preserved"}`

## Modification

- Added a local recharge module Activity.
- The module stores local paid state in `SharedPreferences` named `ctf_recharge_module`.
- The injected class is packaged as `classes6.dex`.
- Manifest registers the module as a second launcher entry labelled `内置充值`.
- When `--server-url` is used, all built-in `DefaultServerNodes` URLs are replaced with that backend URL.
- For HTTP local backends, `network_security_config.xml` is patched to allow cleartext to emulator/local hosts.

## Verification Commands

```powershell
D:\\Anconda3\\python.exe .\\tools\\zip1_repack_pipeline.py
D:\\Anconda3\\python.exe .\\tools\\zip1_repack_pipeline.py --server-url http://10.0.2.2:8000/
python .\\tools\\ai_fengyue_local_server.py --host 0.0.0.0 --port 8000
.\tools\zip1_repack_pipeline.ps1 -Install
E:\\android\\Sdk\\build-tools\\36.1.0\\apksigner.bat verify --verbose --print-certs .\\output\\zip-1-repack\\ai-fengyue-recharge-signed.apk
E:\\android\\Sdk\\build-tools\\36.1.0\\zipalign.exe -c -p -v 4 .\\output\\zip-1-repack\\ai-fengyue-recharge-signed.apk
E:\\android\\Sdk\\platform-tools\\adb.exe install -r .\\output\\zip-1-repack\\ai-fengyue-recharge-signed.apk
E:\\android\\Sdk\\platform-tools\\adb.exe shell pm clear {PACKAGE}
E:\\android\\Sdk\\platform-tools\\adb.exe shell am start -n {PACKAGE}/{RECHARGE_ACTIVITY}
```

## Runtime Verification

- `adb install -r` result: `Success`.
- Original Activity launch: `{PACKAGE}/.MainActivity`.
- Injected Activity launch: `{PACKAGE}/.ctf.RechargeActivity`.
- UI before tap: `内置充值收费模块`, `付费状态：未充值`, `余额：0 积分`.
- UI after tap: `付费状态：已充值 / 可使用`, `余额：100 积分`, `Verified locally`.
- Evidence files:
  - `ai-fengyue-recharge-screen.png`
  - `ai-fengyue-recharge-after-tap.png`
  - `ai-fengyue-recharge-ui.xml`
  - `ai-fengyue-recharge-ui-after-tap.xml`

## Artifact Package

- `E:\\酒馆开发\\output\\zip-1-repack\\ctf-breach-artifacts.zip`
- Contains the signed APK, screenshots, UI dumps, logcat file, report, and signing keystore used for this repack.
"""
    report.write_text(text, encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-decode", action="store_true", help="delete and recreate apktool decode directory")
    parser.add_argument("--install", action="store_true", help="install and launch on the first connected adb device")
    parser.add_argument("--server-url", default=None, help=f"replace built-in server nodes, for emulator use {DEFAULT_LOCAL_SERVER_URL}")
    parser.add_argument("--clear-data", action="store_true", help="clear app data after install so persisted selected_node_url is reset")
    parser.add_argument(
        "--functional-parity",
        action="store_true",
        help="keep original AI Fengyue content/resources while applying only server/recharge compatibility patches",
    )
    parser.add_argument(
        "--xingyue-assets",
        action="store_true",
        help="restore AI Xingyue icon/logo and welcome splash resources before building",
    )
    args = parser.parse_args()

    try:
        ensure_dirs()
        sdk = find_sdk()
        java_home = find_java_home()
        build_tools = newest_build_tools(sdk)
        apktool = ROOT / "tools" / "apktool" / "apktool.bat"
        if not apktool.exists():
            raise FileNotFoundError(f"apktool wrapper not found: {apktool}")

        log(f"java_home={java_home}")
        log(f"android_sdk={sdk}")
        log(f"build_tools={build_tools}")

        source_apk = extract_zip_if_needed()
        ensure_decoded(apktool, source_apk, args.force_decode)
        patched_server_url = patch_server_nodes(args.server_url)
        patch_network_security_config(patched_server_url)
        patch_node_test_latency(patched_server_url)
        patch_branding("AI星月", content_parity=args.functional_parity)
        if args.xingyue_assets:
            run([str(java_home / "bin" / "java.exe"), "-version"], check=False)
            run([str(Path(sys.executable)), str(ROOT / "tools" / "patch_ai_xingyue_icon.py")])
            run([str(Path(sys.executable)), str(ROOT / "tools" / "patch_ai_xingyue_welcome.py")])
        ensure_injection_source()
        patch_manifest()
        compile_injection(sdk, build_tools)
        unsigned = build_unsigned(apktool)
        unaligned = inject_extra_dex(unsigned)
        keystore = ensure_keystore(java_home)
        if patched_server_url and "patcher.villainy.top" in patched_server_url:
            output_stem = "ai-xingyue-patcher-signed" if args.xingyue_assets else ("ai-xingyue-parity-signed" if args.functional_parity else "ai-xingyue-patcher-signed")
        elif patched_server_url and "villainy.top" in patched_server_url:
            output_stem = "ai-fengyue-villainy-signed"
        else:
            output_stem = "ai-fengyue-localserver-signed" if patched_server_url else "ai-fengyue-recharge-signed"
        signed = align_and_sign(build_tools, unaligned, keystore, output_stem)
        report = write_report(signed, source_apk, patched_server_url)
        if args.install:
            adb_verify(sdk, signed, clear_data=args.clear_data or bool(patched_server_url))
        log(f"done: {signed}")
        log(f"report: {report}")
        return 0
    except Exception as exc:
        log(f"failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
