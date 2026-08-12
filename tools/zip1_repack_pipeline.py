#!/usr/bin/env python3
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "reverse-analysis" / "zip-1-target"
RAW = WORK / "raw"
DECODED = WORK / "decoded-base-1-full"
INJECT_SRC = WORK / "inject-src" / "org" / "nebula" / "horizon" / "composeai" / "ctf" / "RechargeActivity.java"
HOMER_WEB_SRC = WORK / "inject-src" / "org" / "nebula" / "horizon" / "composeai" / "ctf" / "HomerWebActivity.java"
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
HOMER_WEB_ACTIVITY = "org.nebula.horizon.composeai.ctf.HomerWebActivity"
HOMER_WEB_URL = "https://patcher.villainy.top/app/"
EXPECTED_SIGNER_SHA256 = "429b4165d958750c1fa90289c23b6d9b6d45ff915b535c5b1fbc72d52d93f320"
DEFAULT_LOCAL_SERVER_URL = "http://10.0.2.2:8000/"
DEFAULT_SERVER_NODES_SMALI = DECODED / "smali_classes5" / "org" / "nebula" / "horizon" / "composeai" / "core" / "common" / "constants" / "DefaultServerNodes.smali"
PAYMENT_RETURN_URL_SMALI = DECODED / "smali_classes5" / "org" / "nebula" / "horizon" / "composeai" / "PayViewModel$toPay$1.smali"
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
ORIGINAL_PAYMENT_RETURN_URL = "https://aifuck.cc/explore/apps?ranking=overall_rank"


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


HOMER_WEB_JAVA = r'''package org.nebula.horizon.composeai.ctf;

import android.Manifest;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.view.Gravity;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.PermissionRequest;
import android.webkit.SslErrorHandler;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.net.http.SslError;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;
import java.io.OutputStream;
import android.util.Base64;

/** The only user-facing entry point: the current Homer web application. */
public class HomerWebActivity extends Activity {
    private static final String APP_URL = "https://patcher.villainy.top/app/";
    private static final String APP_HOST = "patcher.villainy.top";
    private static final int FILE_CHOOSER_REQUEST = 4101;
    private static final int MEDIA_PERMISSION_REQUEST = 4102;
    private static final int CREATE_FILE_REQUEST = 4103;
    private static final long MAX_BLOB_DOWNLOAD_BYTES = 64L * 1024L * 1024L;

    private WebView webView;
    private View errorView;
    private ValueCallback<Uri[]> fileCallback;
    private PermissionRequest pendingPermissionRequest;
    private byte[] pendingDownloadBytes;
    private String pendingDownloadMime;
    private boolean mainFrameFailed;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.WHITE);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
        setTitle("惑梦（Homer）");
        setContentView(buildContent());
        configureWebView();
        if (savedInstanceState == null) {
            webView.loadUrl(APP_URL);
        } else {
            if (webView.restoreState(savedInstanceState) == null) webView.loadUrl(APP_URL);
        }
    }

    private View buildContent() {
        FrameLayout root = new FrameLayout(this);
        webView = new WebView(this);
        root.addView(webView, new FrameLayout.LayoutParams(-1, -1));

        LinearLayout retry = new LinearLayout(this);
        retry.setOrientation(LinearLayout.VERTICAL);
        retry.setGravity(Gravity.CENTER);
        retry.setPadding(dp(28), dp(28), dp(28), dp(28));
        retry.setBackgroundColor(Color.WHITE);
        TextView title = new TextView(this);
        title.setText("惑梦暂时无法连接");
        title.setTextColor(Color.rgb(35, 35, 42));
        title.setTextSize(20f);
        title.setGravity(Gravity.CENTER);
        retry.addView(title, new LinearLayout.LayoutParams(-1, -2));
        TextView hint = new TextView(this);
        hint.setText("请检查网络后重试。聊天、角色和积分需要在线服务。\n不会在此处显示登录凭据或接口密钥。");
        hint.setTextColor(Color.rgb(95, 95, 105));
        hint.setTextSize(14f);
        hint.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams hintParams = new LinearLayout.LayoutParams(-1, -2);
        hintParams.setMargins(0, dp(10), 0, dp(18));
        retry.addView(hint, hintParams);
        Button button = new Button(this);
        button.setText("重新加载");
        button.setAllCaps(false);
        button.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View view) {
                hideError();
                webView.loadUrl(APP_URL);
            }
        });
        retry.addView(button, new LinearLayout.LayoutParams(-1, dp(48)));
        errorView = retry;
        errorView.setVisibility(View.GONE);
        root.addView(errorView, new FrameLayout.LayoutParams(-1, -1));
        return root;
    }

    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setUserAgentString(settings.getUserAgentString() + " HomerAPK/20260812");
        CookieManager cookies = CookieManager.getInstance();
        cookies.setAcceptCookie(true);
        cookies.setAcceptThirdPartyCookies(webView, false);
        WebView.setWebContentsDebuggingEnabled(false);
        webView.setBackgroundColor(Color.WHITE);
        webView.setWebViewClient(new HomerWebViewClient());
        webView.setWebChromeClient(new HomerChromeClient());
        webView.setDownloadListener(new HomerDownloadListener());
        webView.setOverScrollMode(View.OVER_SCROLL_NEVER);
    }

    private final class HomerWebViewClient extends WebViewClient {
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            return handleNavigation(request == null ? null : request.getUrl());
        }

        @Override
        public boolean shouldOverrideUrlLoading(WebView view, String url) {
            return handleNavigation(url == null ? null : Uri.parse(url));
        }

        private boolean handleNavigation(Uri uri) {
            if (uri == null) return true;
            String scheme = uri.getScheme() == null ? "" : uri.getScheme().toLowerCase();
            String host = uri.getHost() == null ? "" : uri.getHost().toLowerCase();
            if ("https".equals(scheme) && APP_HOST.equals(host)) return false;
            if ("https".equals(scheme) && !APP_HOST.equals(host)) {
                openExternal(uri);
                return true;
            }
            if ("about".equals(scheme) && "blank".equals(uri.getSchemeSpecificPart())) return false;
            return true;
        }

        @Override
        public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
            mainFrameFailed = false;
            hideError();
            cancelPendingPermission();
            super.onPageStarted(view, url, favicon);
        }

        @Override
        public void onPageFinished(WebView view, String url) {
            if (!mainFrameFailed) hideError();
            CookieManager.getInstance().flush();
            super.onPageFinished(view, url);
        }

        @Override
        public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
            if (request == null || request.isForMainFrame()) {
                mainFrameFailed = true;
                showError();
            }
            super.onReceivedError(view, request, error);
        }

        @Override
        public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {
            if (request != null && request.isForMainFrame() && response != null && response.getStatusCode() >= 400) {
                mainFrameFailed = true;
                showError();
            }
            super.onReceivedHttpError(view, request, response);
        }

        @Override
        public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
            handler.cancel();
            mainFrameFailed = true;
            showError();
        }

    }

    private final class HomerChromeClient extends WebChromeClient {
        @Override
        public boolean onJsPrompt(WebView view, String url, String message, String defaultValue, android.webkit.JsPromptResult result) {
            if (url != null && url.startsWith("https://" + APP_HOST + "/") && message != null && message.startsWith("HOMER_SAVE_BLOB:")) {
                try {
                    String filename = message.substring("HOMER_SAVE_BLOB:".length());
                    int comma = defaultValue == null ? -1 : defaultValue.indexOf(',');
                    if (comma <= 5) throw new IllegalArgumentException("invalid data URL");
                    String metadata = defaultValue.substring(5, comma);
                    pendingDownloadMime = metadata.split(";")[0];
                    String payload = defaultValue.substring(comma + 1);
                    if (payload.length() > MAX_BLOB_DOWNLOAD_BYTES * 2L) throw new IllegalArgumentException("download too large");
                    if (metadata.contains(";base64")) pendingDownloadBytes = Base64.decode(payload, Base64.DEFAULT);
                    else pendingDownloadBytes = Uri.decode(payload).getBytes("UTF-8");
                    if (pendingDownloadBytes.length > MAX_BLOB_DOWNLOAD_BYTES) throw new IllegalArgumentException("download too large");
                    Intent create = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                    create.addCategory(Intent.CATEGORY_OPENABLE);
                    create.setType(pendingDownloadMime == null || pendingDownloadMime.length() == 0 ? "application/octet-stream" : pendingDownloadMime);
                    create.putExtra(Intent.EXTRA_TITLE, filename.length() == 0 ? "homer-download" : filename);
                    startActivityForResult(create, CREATE_FILE_REQUEST);
                    result.confirm("");
                } catch (Exception e) {
                    pendingDownloadBytes = null;
                    pendingDownloadMime = null;
                    result.cancel();
                }
                return true;
            }
            return super.onJsPrompt(view, url, message, defaultValue, result);
        }

        @Override
        public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
            if (fileCallback != null) fileCallback.onReceiveValue(null);
            fileCallback = callback;
            Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("*/*");
            intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, false);
            intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[] {
                    "application/json", "text/plain",
                    "image/png", "image/jpeg", "image/webp", "image/gif",
                    "audio/mpeg", "video/mp4", "video/webm",
                    "application/zip", "application/x-zip-compressed", "application/octet-stream"
            });
            try {
                startActivityForResult(intent, FILE_CHOOSER_REQUEST);
            } catch (ActivityNotFoundException e) {
                fileCallback = null;
                callback.onReceiveValue(null);
                showError();
            }
            return true;
        }

        @Override
        public void onPermissionRequest(final PermissionRequest request) {
            runOnUiThread(new Runnable() {
                @Override public void run() {
                    if (request == null || request.getOrigin() == null
                            || !"https".equalsIgnoreCase(request.getOrigin().getScheme())
                            || !APP_HOST.equalsIgnoreCase(request.getOrigin().getHost())) {
                        request.deny();
                        return;
                    }
                    List<String> needed = new ArrayList<String>();
                    boolean hasAllowedResource = false;
                    for (String resource : request.getResources()) {
                        if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resource)) {
                            hasAllowedResource = true;
                            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                                needed.add(Manifest.permission.RECORD_AUDIO);
                            }
                        } else if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(resource)) {
                            hasAllowedResource = true;
                            if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
                                needed.add(Manifest.permission.CAMERA);
                            }
                        } else {
                            request.deny();
                            return;
                        }
                    }
                    if (!hasAllowedResource) {
                        request.deny();
                    } else if (needed.isEmpty()) {
                        request.grant(request.getResources());
                    } else {
                        if (pendingPermissionRequest != null) {
                            request.deny();
                            return;
                        }
                        pendingPermissionRequest = request;
                        requestPermissions(needed.toArray(new String[needed.size()]), MEDIA_PERMISSION_REQUEST);
                    }
                }
            });
        }

        @Override
        public boolean onConsoleMessage(android.webkit.ConsoleMessage message) {
            return true;
        }
    }

    private final class HomerDownloadListener implements DownloadListener {
        @Override
        public void onDownloadStart(String url, String userAgent, String contentDisposition, String mimetype, long contentLength) {
            if (url != null && url.startsWith("blob:")) {
                String name = URLUtil.guessFileName(APP_URL, contentDisposition, mimetype);
                webView.evaluateJavascript("(function(){try{var u=" + jsQuote(url) + ";fetch(u).then(function(r){return r.blob()}).then(function(b){if(b.size>67108864)return;var q=new FileReader();q.onloadend=function(){prompt('HOMER_SAVE_BLOB:'+" + jsQuote(name) + ",q.result)};q.readAsDataURL(b)}).catch(function(){})}catch(e){}})();", null);
                return;
            }
            Uri downloadUri = url == null ? null : Uri.parse(url);
            if (downloadUri == null || !"https".equalsIgnoreCase(downloadUri.getScheme())) return;
            try {
                DownloadManager.Request request = new DownloadManager.Request(downloadUri);
                request.setMimeType(mimetype);
                request.addRequestHeader("User-Agent", userAgent);
                String cookie = CookieManager.getInstance().getCookie(url);
                if (cookie != null) request.addRequestHeader("Cookie", cookie);
                request.setTitle(URLUtil.guessFileName(url, contentDisposition, mimetype));
                request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                request.setDestinationInExternalFilesDir(HomerWebActivity.this, Environment.DIRECTORY_DOWNLOADS, URLUtil.guessFileName(url, contentDisposition, mimetype));
                ((DownloadManager) getSystemService(DOWNLOAD_SERVICE)).enqueue(request);
            } catch (Exception ignored) {
                openExternal(Uri.parse(url));
            }
        }
    }

    private String jsQuote(String value) {
        if (value == null) return "\"\"";
        return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r") + "\"";
    }

    private void openExternal(Uri uri) {
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, uri);
            startActivity(intent);
        } catch (Exception ignored) {
            // Do not expose URL/cookie details in UI or logs.
        }
    }

    private void showError() { if (errorView != null) errorView.setVisibility(View.VISIBLE); }
    private void hideError() { if (errorView != null) errorView.setVisibility(View.GONE); }
    private void cancelPendingPermission() {
        if (pendingPermissionRequest != null) {
            try { pendingPermissionRequest.deny(); } catch (Exception ignored) { }
            pendingPermissionRequest = null;
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != MEDIA_PERMISSION_REQUEST || pendingPermissionRequest == null) return;
        boolean granted = grantResults.length > 0;
        for (int result : grantResults) if (result != PackageManager.PERMISSION_GRANTED) granted = false;
        try {
            if (granted) pendingPermissionRequest.grant(pendingPermissionRequest.getResources());
            else pendingPermissionRequest.deny();
        } catch (Exception ignored) { }
        pendingPermissionRequest = null;
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == CREATE_FILE_REQUEST) {
            if (resultCode == RESULT_OK && data != null && data.getData() != null && pendingDownloadBytes != null) {
                try {
                    OutputStream out = getContentResolver().openOutputStream(data.getData());
                    if (out != null) {
                        out.write(pendingDownloadBytes);
                        out.close();
                    }
                } catch (Exception ignored) { }
            }
            pendingDownloadBytes = null;
            pendingDownloadMime = null;
            return;
        }
        if (requestCode != FILE_CHOOSER_REQUEST || fileCallback == null) return;
        Uri[] result = null;
        if (resultCode == RESULT_OK && data != null && data.getData() != null) result = new Uri[] { data.getData() };
        fileCallback.onReceiveValue(result);
        fileCallback = null;
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        webView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    private int dp(int value) { return (int) (value * getResources().getDisplayMetrics().density + 0.5f); }
}
'''


def log(message: str) -> None:
    print(f"[zip1-repack] {message}", flush=True)


def run(cmd, cwd=ROOT, check=True, echo_output=True):
    printable_parts = []
    redact_next = False
    for item in cmd:
        value = str(item)
        if redact_next:
            printable_parts.append("<redacted>")
            redact_next = False
            continue
        printable_parts.append(value)
        if value in {"--ks-pass", "--key-pass", "--storepass", "--store-pass"}:
            redact_next = True
    printable = " ".join(printable_parts)
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
    if p.stdout and echo_output:
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


def powershell_path_literal(path: Path) -> str:
    return windows_long_path(path).replace("'", "''")


def delete_directory_long_path(path: Path, *, required: bool = True) -> bool:
    if not path.exists():
        return True
    command = "[System.IO.Directory]::Delete('{0}', $true)".format(powershell_path_literal(path))
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    removed = not path.exists()
    if not removed and required:
        raise RuntimeError(f"failed to delete directory via long-path .NET API: {path}; exit={result.returncode}")
    return removed


def remove_work_tree(path: Path) -> None:
    resolved = path.resolve()
    work_root = WORK.resolve()
    if resolved == work_root or work_root not in resolved.parents:
        raise RuntimeError(f"refusing to delete outside work tree: {resolved}")
    if not path.exists():
        return
    quarantine = STAGE / f"discard-decoded-{os.getpid()}"
    if quarantine.exists():
        delete_directory_long_path(quarantine)
    try:
        os.replace(windows_long_path(resolved), windows_long_path(quarantine))
    except OSError:
        command = "[System.IO.Directory]::Move('{0}', '{1}')".format(
            powershell_path_literal(resolved),
            powershell_path_literal(quarantine),
        )
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    if path.exists():
        delete_directory_long_path(path)
    if path.exists():
        raise RuntimeError(f"failed to delete decoded work tree: {resolved}")
    if quarantine.exists() and not delete_directory_long_path(quarantine, required=False):
        log(f"warning: decoded work tree remains quarantined at {quarantine}")


def remove_directory_via_junction(path: Path, alias_name: str) -> None:
    resolved = path.resolve()
    decoded_root = DECODED.resolve()
    if resolved == decoded_root or decoded_root not in resolved.parents:
        raise RuntimeError(f"refusing to delete outside decoded tree: {resolved}")
    if not path.exists():
        return
    quarantine = STAGE / f"discard-{alias_name}-{os.getpid()}"
    stage_root = STAGE.resolve()
    quarantine_resolved = quarantine.resolve(strict=False)
    if stage_root not in quarantine_resolved.parents:
        raise RuntimeError(f"refusing to use quarantine outside stage root: {quarantine_resolved}")
    if quarantine.exists():
        delete_directory_long_path(quarantine)
    moved = False
    try:
        os.replace(windows_long_path(resolved), windows_long_path(quarantine))
        moved = True
    except OSError:
        command = "[System.IO.Directory]::Move('{0}', '{1}')".format(
            powershell_path_literal(resolved),
            powershell_path_literal(quarantine),
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        moved = result.returncode == 0 and not path.exists()
    if not moved and path.exists():
        delete_directory_long_path(path)
    if path.exists():
        raise RuntimeError(f"failed to remove legacy payload: {path}")
    if quarantine.exists() and not delete_directory_long_path(quarantine, required=False):
        log(f"warning: quarantined legacy directory remains outside decoded tree: {quarantine}")


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


def patch_payment_return_url(server_url: str | None) -> None:
    if not server_url:
        return
    target_url = normalize_base_url(server_url).rstrip("/") + "/app/"
    smali = PAYMENT_RETURN_URL_SMALI
    if not smali.exists():
        raise FileNotFoundError(f"payment return URL smali not found: {smali}")
    text = smali.read_text(encoding="utf-8")
    candidates = [ORIGINAL_PAYMENT_RETURN_URL]
    candidates.extend(base.rstrip("/") + "/app/" for base in KNOWN_PATCHED_SERVER_URLS)
    replaced = 0
    for candidate in dict.fromkeys(candidates):
        if candidate == target_url:
            continue
        count = text.count(candidate)
        if count:
            replaced += count
            text = text.replace(candidate, target_url)
    if replaced == 0 and target_url not in text:
        raise RuntimeError("payment return URL patch did not find the original, previous, or target URL")
    smali.write_text(text, encoding="utf-8")
    if ORIGINAL_PAYMENT_RETURN_URL in text:
        raise RuntimeError("payment return URL patch incomplete")
    log(f"patched payment return URL to {target_url}; replacements={replaced}")


def patch_network_security_config(server_url: str | None, web_mode: bool = True) -> None:
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
    if web_mode:
        if domain_config is not None:
            root.remove(domain_config)
            ET.indent(tree, space="    ")
            tree.write(NETWORK_SECURITY_CONFIG, encoding="utf-8", xml_declaration=True)
            log("removed legacy cleartext domain policy for Homer WebView")
        else:
            log("legacy cleartext domain policy already absent")
        return
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


def patch_webview_security_config() -> None:
    if not NETWORK_SECURITY_CONFIG.exists():
        return
    tree = ET.parse(NETWORK_SECURITY_CONFIG)
    root = tree.getroot()
    changed = False
    for domain_config in list(root.findall("domain-config")):
        if domain_config.attrib.get("cleartextTrafficPermitted") == "true":
            root.remove(domain_config)
            changed = True
    for base in root.findall("base-config"):
        anchors = base.find("trust-anchors")
        if anchors is None:
            continue
        for certificate in list(anchors.findall("certificates")):
            if certificate.attrib.get("src") == "user":
                anchors.remove(certificate)
                changed = True
    if changed:
        ET.indent(tree, space="    ")
        tree.write(NETWORK_SECURITY_CONFIG, encoding="utf-8", xml_declaration=True)
        log("hardened WebView network security config to HTTPS/system trust only")
    else:
        log("WebView network security config already hardened")


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
        if path.name == "strings.xml" and path.parent.name in {"values", "values-en"}:
            text = re.sub(r'(<string\s+name="app_name">)(.*?)(</string>)', rf'\g<1>{app_name}\g<3>', text, count=1)
        if not content_parity:
            text = text.replace("欢迎来到AI风月", f"欢迎来到{app_name}")
            text = text.replace("AI风月 本地服务器", f"{app_name} 本地服务器")
            text = text.replace("AI风月 CTF APK server binding", f"{app_name} CTF APK server binding")
        if text != original:
            path.write_text(text, encoding="utf-8")
            log(f"patched branding in {path.relative_to(ROOT)}")


def patch_web_version() -> None:
    apktool_yml = DECODED / "apktool.yml"
    text = apktool_yml.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^\s*versionCode:\s*\S+", "  versionCode: 261", text, count=1)
    text = re.sub(r"(?m)^\s*versionName:\s*\S+", "  versionName: 1.12.21", text, count=1)
    apktool_yml.write_text(text, encoding="utf-8")
    log("patched APK version to 1.12.21 (261)")


def strip_legacy_native_payload() -> None:
    removed = []
    legacy_names = [
        path.name
        for path in DECODED.iterdir()
        if path.name == "smali" or re.fullmatch(r"smali_classes\d+", path.name)
    ]
    legacy_names.extend(["assets", "unknown", "lib", "build"])
    for index, name in enumerate(dict.fromkeys(legacy_names)):
        target = DECODED / name
        if target.exists():
            if target.is_dir():
                remove_directory_via_junction(target, f"legacy-{index}")
            else:
                target.unlink()
            removed.append(name)
    manifest = DECODED / "AndroidManifest.xml"
    manifest_text = manifest.read_text(encoding="utf-8")
    manifest_text = re.sub(r'\sandroid:name="org\.nebula\.horizon\.composeai\.ComposeAIApp"', "", manifest_text, count=1)
    app_match = re.search(r'(?P<open><application\b[^>]*>)(?P<body>.*?)(?P<close></application>)', manifest_text, re.DOTALL)
    if not app_match:
        raise RuntimeError("application block not found while stripping legacy manifest components")
    body = "\n" + _homer_launcher_block() + "    "
    manifest_text = manifest_text[:app_match.start()] + app_match.group("open") + body + app_match.group("close") + manifest_text[app_match.end():]
    manifest.write_text(manifest_text, encoding="utf-8")
    (DECODED / "apktool.yml").write_text(
        """version: 3.0.2
apkFileName: base (1).apk
usesFramework:
  ids:
  - 1
sdkInfo:
  minSdkVersion: 24
  targetSdkVersion: 35
versionInfo:
  versionCode: 261
  versionName: 1.12.21
resourcesInfo:
  packageId: 127
doNotCompress:
- arsc
- png
""",
        encoding="utf-8",
    )
    log("removed legacy Compose/webapp/native payload: " + ", ".join(removed))


def write_minimal_homer_resources() -> None:
    res_root = DECODED / "res"
    icon_files = []
    for density in ["mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"]:
        source = res_root / f"mipmap-{density}" / "logo.png"
        if source.exists():
            icon_files.append((density, source.read_bytes()))
    if res_root.exists():
        remove_directory_via_junction(res_root, "legacy-res")
    values = res_root / "values"
    values.mkdir(parents=True, exist_ok=True)
    for density, data in icon_files:
        target = res_root / f"mipmap-{density}" / "logo.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (values / "styles.xml").write_text(
        '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="Theme.Homer" parent="@android:style/Theme.Material.Light.NoActionBar">
        <item name="android:fontFamily">sans</item>
        <item name="android:windowActionModeOverlay">true</item>
        <item name="android:windowLightStatusBar">true</item>
        <item name="android:navigationBarColor">#FFFFFF</item>
        <item name="android:statusBarColor">#FFFFFF</item>
        <item name="android:colorAccent">#8F1F45</item>
    </style>
</resources>
''',
        encoding="utf-8",
    )
    (values / "strings.xml").write_text(
        '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">惑梦（Homer）</string>
</resources>
''',
        encoding="utf-8",
    )
    NETWORK_SECURITY_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    NETWORK_SECURITY_CONFIG.write_text(
        '''<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors>
            <certificates src="system"/>
        </trust-anchors>
    </base-config>
</network-security-config>
''',
        encoding="utf-8",
    )
    manifest = DECODED / "AndroidManifest.xml"
    manifest_text = manifest.read_text(encoding="utf-8")
    manifest_text = re.sub(r'\s*<queries>.*?</queries>', "", manifest_text, flags=re.DOTALL)
    permissions = [
        '<uses-permission android:name="android.permission.INTERNET"/>',
        '<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>',
        '<uses-permission android:name="android.permission.CAMERA"/>',
        '<uses-permission android:name="android.permission.RECORD_AUDIO"/>',
    ]
    manifest_text = re.sub(r'\s*<uses-permission\b[^>]*/>', "", manifest_text)
    manifest_text = re.sub(r'\s*<permission\b[^>]*/>', "", manifest_text)
    manifest_text = re.sub(r'\s*<uses-feature\b[^>]*/>', "", manifest_text)
    manifest_text = manifest_text.replace(
        '    <application',
        '\n'.join('    ' + item for item in permissions)
        + '\n    <uses-feature android:name="android.hardware.camera" android:required="false"/>'
        + '\n    <uses-feature android:name="android.hardware.microphone" android:required="false"/>'
        + '\n    <application',
        1,
    )
    manifest_text = manifest_text.replace('android:theme="@style/Theme.ComposeAI"', 'android:theme="@style/Theme.Homer"')
    manifest_text = re.sub(r'android:allowBackup="[^"]*"', 'android:allowBackup="false"', manifest_text, count=1)
    manifest_text = re.sub(r'\sandroid:appComponentFactory="[^"]*"', "", manifest_text, count=1)
    manifest_text = re.sub(r'\sandroid:fullBackupContent="[^"]*"', "", manifest_text, count=1)
    manifest_text = re.sub(r'\sandroid:extractNativeLibs="[^"]*"', "", manifest_text, count=1)
    manifest.write_text(manifest_text, encoding="utf-8")
    log("wrote minimal Homer resources and platform-only theme")


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
    HOMER_WEB_SRC.write_text(HOMER_WEB_JAVA, encoding="utf-8")
    log(f"wrote injection sources: {INJECT_SRC.name}, {HOMER_WEB_SRC.name}")


def _remove_launcher_filter(activity_block: str) -> str:
    pattern = re.compile(
        r"\s*<intent-filter>\s*"
        r"(?:(?!</intent-filter>).)*?<action\s+android:name=\"android\.intent\.action\.MAIN\"\s*/>"
        r"(?:(?!</intent-filter>).)*?<category\s+android:name=\"android\.intent\.category\.LAUNCHER\"\s*/>"
        r"(?:(?!</intent-filter>).)*?</intent-filter>",
        re.DOTALL,
    )
    return pattern.sub("", activity_block)


def _patch_activity_block(text: str, activity_name: str, exported: str | None = None, enabled: str | None = None) -> tuple[str, bool]:
    pattern = re.compile(
        rf"(?P<open>\s*<activity\b[^>]*android:name=\"{re.escape(activity_name)}\"[^>]*>)(?P<body>.*?)(?P<close>\s*</activity>)",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return text, False
    opening = match.group("open")
    if exported is not None:
        opening = re.sub(r'\sandroid:exported="[^"]*"', f' android:exported="{exported}"', opening, count=1)
        if 'android:exported=' not in opening:
            opening = opening[:-1] + f' android:exported="{exported}">'
    if enabled is not None:
        if re.search(r'\sandroid:enabled="[^"]*"', opening):
            opening = re.sub(r'\sandroid:enabled="[^"]*"', f' android:enabled="{enabled}"', opening, count=1)
        else:
            opening = opening[:-1] + f' android:enabled="{enabled}">'
    body = _remove_launcher_filter(match.group("body"))
    replacement = opening + body + match.group("close")
    return text[:match.start()] + replacement + text[match.end():], True


def _remove_activity_block(text: str, activity_name: str) -> tuple[str, bool]:
    pattern = re.compile(
        rf"\s*<activity\b[^>]*android:name=\"{re.escape(activity_name)}\"[^>]*(?:/>|>.*?</activity>)",
        re.DOTALL,
    )
    updated, count = pattern.subn("", text, count=1)
    return updated, bool(count)


def _homer_launcher_block() -> str:
    return f'''        <activity android:configChanges="keyboardHidden|orientation|screenLayout|screenSize|uiMode" android:exported="true" android:label="@string/app_name" android:name="{HOMER_WEB_ACTIVITY}" android:screenOrientation="unspecified" android:theme="@style/Theme.Homer" android:windowSoftInputMode="adjustResize">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
'''


def patch_manifest(web_mode: bool = True) -> None:
    manifest = DECODED / "AndroidManifest.xml"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace(' android:dataExtractionRules="@xml/data_extraction_rules"', "")
    text = text.replace(' android:enableOnBackInvokedCallback="true"', "")
    if web_mode:
        if 'android.permission.RECORD_AUDIO' not in text:
            text = text.replace('    <uses-permission android:name="android.permission.CAMERA"/>', '    <uses-permission android:name="android.permission.CAMERA"/>\n    <uses-permission android:name="android.permission.RECORD_AUDIO"/>', 1)
        text = text.replace('android:label="@string/app_name"', 'android:label="@string/app_name"')
        text = re.sub(r'\sandroid:usesCleartextTraffic="[^"]*"', ' android:usesCleartextTraffic="false"', text, count=1)
        text, main_found = _remove_activity_block(text, MAIN_ACTIVITY)
        text, recharge_found = _remove_activity_block(text, RECHARGE_ACTIVITY)
        text, _ = _remove_activity_block(text, HOMER_WEB_ACTIVITY)
        marker = '        <provider android:authorities="org.nebula.horizon.composeai.fileprovider"'
        if marker in text:
            text = text.replace(marker, _homer_launcher_block() + marker, 1)
        elif '    </application>' in text:
            text = text.replace('    </application>', _homer_launcher_block() + '    </application>', 1)
        else:
            raise RuntimeError("manifest application insertion marker not found")
        manifest.write_text(text, encoding="utf-8")
        log(f"manifest configured for HomerWebActivity; main_found={main_found}; recharge_found={recharge_found}")
        return
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


def compile_injection(sdk: Path, build_tools: Path, web_mode: bool = True) -> None:
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
    sources = [HOMER_WEB_SRC] if web_mode else [INJECT_SRC]
    run([str(java_home / "bin" / "javac.exe"), "-encoding", "UTF-8", "-source", "8", "-target", "8", "-bootclasspath", str(android_jar), "-d", str(INJECT_CLASSES)] + [str(source) for source in sources])
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


def inject_extra_dex(unsigned: Path, web_mode: bool = True) -> Path:
    injected = STAGE / ("homer-web-repacked-unaligned.apk" if web_mode else "ai-fengyue-repacked-with-recharge-unaligned.apk")
    if injected.exists():
        injected.unlink()
    with zipfile.ZipFile(unsigned, "r") as zin, zipfile.ZipFile(injected, "w") as zout:
        for info in zin.infolist():
            name = info.filename
            if name.startswith("META-INF/") and name.upper().endswith((".RSA", ".DSA", ".EC", ".SF", ".MF")):
                continue
            if web_mode and re.fullmatch(r"classes(?:\d+)?\.dex", name):
                continue
            if not web_mode and name == "classes6.dex":
                continue
            zout.writestr(info, zin.read(name))
        dex_name = "classes.dex" if web_mode else "classes6.dex"
        dex_info = zipfile.ZipInfo(dex_name)
        dex_info.compress_type = zipfile.ZIP_STORED
        dex_info.external_attr = 0o644 << 16
        zout.writestr(dex_info, INJECT_DEX.read_bytes())
    log(f"added injection dex as {dex_name} ({INJECT_DEX.stat().st_size} bytes)")
    shutil.copy2(injected, OUT / injected.name)
    return injected


def ensure_keystore(java_home: Path) -> Path:
    keystore = STAGE / "zip1-repack.keystore"
    if keystore.exists():
        return keystore
    legacy_keystore = OUT / keystore.name
    if legacy_keystore.exists():
        shutil.copy2(legacy_keystore, keystore)
        return keystore
    raise FileNotFoundError("existing APK signing keystore not found; refusing to create a different upgrade signer")


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
    signature = run([str(build_tools / "apksigner.bat"), "verify", "--verbose", "--print-certs", str(signed)])
    match = re.search(r"Signer #1 certificate SHA-256 digest:\s*([0-9a-fA-F]+)", signature.stdout)
    if not match or match.group(1).lower() != EXPECTED_SIGNER_SHA256:
        observed = match.group(1).lower() if match else "missing"
        raise RuntimeError(f"unexpected APK signer certificate: {observed}")
    run([str(build_tools / "zipalign.exe"), "-c", "-p", "-v", "4", str(signed)])
    out_signed = OUT / signed.name
    shutil.copy2(aligned, OUT / aligned.name)
    shutil.copy2(signed, out_signed)
    return out_signed


def adb_verify(sdk: Path, apk: Path, clear_data: bool = False) -> str:
    adb = sdk / "platform-tools" / "adb.exe"
    if not adb.exists():
        log("adb not found; skipping runtime verification")
        return "skipped: adb was not found"
    devices = run([str(adb), "devices", "-l"], check=False)
    lines = [
        line
        for line in devices.stdout.splitlines()
        if len(line.split()) >= 2 and line.split()[1] == "device"
    ]
    if not lines:
        log("no adb device connected; skipping install/start verification")
        return "skipped: no connected adb device"
    run([str(adb), "install", "-r", str(apk)])
    if clear_data:
        run([str(adb), "shell", "pm", "clear", PACKAGE], check=False)
    run([str(adb), "logcat", "-c"], check=False)
    launch = run([str(adb), "shell", "am", "start", "-W", "-n", f"{PACKAGE}/{HOMER_WEB_ACTIVITY}"], check=False)
    if launch.returncode != 0 or "Status: ok" not in launch.stdout:
        raise RuntimeError("ADB install succeeded but HomerWebActivity did not report a successful launch")
    time.sleep(5)
    screenshot = OUT / "homer-web-start.png"
    with screenshot.open("wb") as f:
        p = subprocess.run([str(adb), "exec-out", "screencap", "-p"], stdout=f)
        log(f"screenshot capture exit={p.returncode}: {screenshot}")
    activity = run([str(adb), "shell", "dumpsys", "activity", "activities"], check=False, echo_output=False)
    if not re.search(r"topResumedActivity=.*(?:\.ctf\.HomerWebActivity|" + re.escape(HOMER_WEB_ACTIVITY) + r")", activity.stdout):
        raise RuntimeError("HomerWebActivity launched but was not confirmed as the foreground Activity")
    pid = run([str(adb), "shell", "pidof", PACKAGE], check=False, echo_output=False).stdout.strip()
    if not pid:
        raise RuntimeError("Homer process was not alive after launch")
    runtime_log = OUT / "homer-web-logcat.txt"
    logcat = run([str(adb), "logcat", "-d", "-v", "time"], check=False, echo_output=False)
    runtime_log.write_text(logcat.stdout, encoding="utf-8")
    if re.search(r"FATAL EXCEPTION.*?(?:\n.*?){0,8}Process:\s*" + re.escape(PACKAGE), logcat.stdout, re.DOTALL):
        raise RuntimeError("Homer process logged a fatal exception after launch")
    return (
        f"completed on {len(lines)} connected adb device(s); install succeeded; cold launch status ok; "
        f"foreground Activity and live process confirmed; screenshot={screenshot.name}; logcat={runtime_log.name}"
    )


def write_report(apk: Path, source_apk: Path, server_url: str | None, runtime_verification: str, web_mode: bool = True) -> Path:
    report = OUT / "final-report.md"
    if web_mode:
        modification = rf"""- The injected `HomerWebActivity` is the only code payload in primary `classes.dex` and loads `{HOMER_WEB_URL}`.
- Legacy Compose dex, native libraries, bundled webapp/assets, and old launcher components are removed.
- WebView enables JavaScript/DOM storage/cookies, file selection, downloads, safe external navigation, and retry/error handling.
- The production shell is bound to the HTTPS Homer Web app; no legacy native server-node code remains.
- Cleartext domain policy is removed for the HTTPS Homer build."""
        verification_apk = "homer-web-apk-signed.apk"
        launcher = HOMER_WEB_ACTIVITY
    else:
        modification = rf"""- The historical `RechargeActivity` injection is packaged as `classes6.dex`.
- Existing native application dex/resources are retained for compatibility testing.
- When `--server-url` is used, legacy native server nodes and the payment return URL are patched to that backend."""
        verification_apk = apk.name
        launcher = RECHARGE_ACTIVITY
    text = rf"""# 惑梦 Android APK Repack Report

## Result

- Target: `base (1).apk`
- Package: `{PACKAGE}`
- Launcher: `{launcher}`
- Output APK: `{apk}`
- Output SHA-256: `{sha256(apk)}`
- Source APK SHA-256: `{sha256(source_apk)}`
- Bound server URL: `{server_url or "not patched; original node list preserved"}`

## Modification

{modification}

## Verification Commands

```powershell
D:\\Anconda3\\python.exe .\\tools\\zip1_repack_pipeline.py
D:\\Anconda3\\python.exe .\\tools\\zip1_repack_pipeline.py --server-url https://patcher.villainy.top/
python .\\tools\\ai_fengyue_local_server.py --host 0.0.0.0 --port 8000
.\tools\zip1_repack_pipeline.ps1 -Install
E:\\android\\Sdk\\build-tools\\36.1.0\\apksigner.bat verify --verbose --print-certs .\\output\\zip-1-repack\\{verification_apk}
E:\\android\\Sdk\\build-tools\\36.1.0\\zipalign.exe -c -p -v 4 .\\output\\zip-1-repack\\{verification_apk}
E:\\android\\Sdk\\platform-tools\\adb.exe install -r .\\output\\zip-1-repack\\{verification_apk}
E:\\android\\Sdk\\platform-tools\\adb.exe shell pm clear {PACKAGE}
E:\\android\\Sdk\\platform-tools\\adb.exe shell am start -n {PACKAGE}/{launcher}
```

## Runtime Verification

- Status: `{runtime_verification}`.
- The report does not infer installation or launch success from a successful build.
- Run with `--install` while an adb device is connected to perform installation and Activity launch checks.

## Delivery

- Deliver the signed APK together with an independent hash/signature verification summary.
- Do not include the signing keystore or its password in the public delivery package.
"""
    report.write_text(text, encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-decode", action="store_true", help="delete and recreate apktool decode directory")
    parser.add_argument("--install", action="store_true", help="install and launch on the first connected adb device")
    parser.add_argument("--server-url", default=None, help=f"replace built-in server nodes, for emulator use {DEFAULT_LOCAL_SERVER_URL}")
    parser.add_argument("--clear-data", action="store_true", help="clear app data after install so persisted selected_node_url is reset")
    parser.add_argument("--legacy-recharge", action="store_true", help="build the historical native recharge injection instead of the Homer WebView shell")
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

        web_mode = not args.legacy_recharge
        source_apk = extract_zip_if_needed()
        legacy_decode_missing = not web_mode and not DEFAULT_SERVER_NODES_SMALI.exists()
        ensure_decoded(apktool, source_apk, args.force_decode or legacy_decode_missing)
        if web_mode:
            requested_web_url = normalize_base_url(args.server_url) if args.server_url else "https://patcher.villainy.top/"
            if requested_web_url != "https://patcher.villainy.top/":
                raise ValueError("Homer WebView shell is fixed to https://patcher.villainy.top/; use --legacy-recharge for native server URL patching")
            patched_server_url = requested_web_url
        else:
            patched_server_url = patch_server_nodes(args.server_url)
        if not web_mode:
            patch_payment_return_url(patched_server_url)
        patch_network_security_config(patched_server_url, web_mode=web_mode)
        if web_mode:
            patch_webview_security_config()
        if not web_mode:
            patch_node_test_latency(patched_server_url)
        patch_branding("惑梦（Homer）" if web_mode else "AI星月", content_parity=args.functional_parity)
        if web_mode:
            patch_web_version()
        if args.xingyue_assets and not web_mode:
            run([str(java_home / "bin" / "java.exe"), "-version"], check=False)
            run([str(Path(sys.executable)), str(ROOT / "tools" / "patch_ai_xingyue_icon.py")])
            run([str(Path(sys.executable)), str(ROOT / "tools" / "patch_ai_xingyue_welcome.py")])
        if web_mode:
            run([
                str(Path(sys.executable)),
                str(ROOT / "tools" / "patch_ai_xingyue_icon.py"),
                "--icon",
                str(ROOT / "frontend" / "assets" / "img" / "logo-512.png"),
            ])
        ensure_injection_source()
        patch_manifest(web_mode=web_mode)
        if web_mode:
            strip_legacy_native_payload()
            write_minimal_homer_resources()
        compile_injection(sdk, build_tools, web_mode=web_mode)
        unsigned = build_unsigned(apktool)
        unaligned = inject_extra_dex(unsigned, web_mode=web_mode)
        keystore = ensure_keystore(java_home)
        if web_mode and patched_server_url and "patcher.villainy.top" in patched_server_url:
            output_stem = "homer-web-apk-signed"
        elif patched_server_url and "patcher.villainy.top" in patched_server_url:
            output_stem = "ai-xingyue-patcher-signed" if args.xingyue_assets else ("ai-xingyue-parity-signed" if args.functional_parity else "ai-xingyue-patcher-signed")
        elif patched_server_url and "villainy.top" in patched_server_url:
            output_stem = "ai-fengyue-villainy-signed"
        else:
            output_stem = "ai-fengyue-localserver-signed" if patched_server_url else "ai-fengyue-recharge-signed"
        signed = align_and_sign(build_tools, unaligned, keystore, output_stem)
        runtime_verification = "not requested; static build only"
        if args.install:
            runtime_verification = adb_verify(sdk, signed, clear_data=args.clear_data or bool(patched_server_url))
        report = write_report(signed, source_apk, patched_server_url, runtime_verification, web_mode=web_mode)
        log(f"done: {signed}")
        log(f"report: {report}")
        return 0
    except Exception as exc:
        log(f"failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
