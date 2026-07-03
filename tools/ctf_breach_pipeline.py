#!/usr/bin/env python3
"""
CTF APK breach and publishing-boundary audit pipeline.

This script is intentionally self-contained and conservative about claims:
it automates environment checks, APK rebuild/signing variants, static
protection analysis, optional emulator/device testing, Frida hook deployment,
private-store simulation, reporting, and artifact packaging.
"""

from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import lzma
import os
import platform
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
WORK = OUTPUT / "work"
HOOKS = OUTPUT / "frida"
LOGS = OUTPUT / "logs"
REPORT = OUTPUT / "final-audit-report.md"
ARTIFACT_ZIP = OUTPUT / "ctf-breach-artifacts.zip"


@dataclass
class Step:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Ctx:
    apk: Path
    package: str
    activity: str
    sdk: Path | None
    adb: Path | None = None
    emulator: Path | None = None
    apksigner: Path | None = None
    zipalign: Path | None = None
    keytool: Path | None = None
    apktool: Path | None = None
    python: Path = Path(sys.executable)
    java_home: Path | None = None
    sdk_candidates: list[Path] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)


def log(msg: str) -> None:
    OUTPUT.mkdir(exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with (LOGS / "pipeline.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd: list[str | Path], timeout: int = 120, allow_fail: bool = True, cwd: Path | None = None) -> tuple[int, str]:
    printable = " ".join(str(x) for x in cmd)
    log(f"$ {printable}")
    try:
        p = subprocess.run(
            [str(x) for x in cmd],
            cwd=str(cwd or ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            errors="replace",
        )
        out = p.stdout.strip()
        if out:
            log(out[-4000:])
        if p.returncode != 0 and not allow_fail:
            raise RuntimeError(f"command failed: {printable}\n{out}")
        return p.returncode, out
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") + "\nTIMEOUT"
        log(out[-4000:])
        if not allow_fail:
            raise
        return 124, out


def run_with_env(
    cmd: list[str | Path],
    env_extra: dict[str, str],
    timeout: int = 120,
    allow_fail: bool = True,
    cwd: Path | None = None,
    input_text: str | None = None,
) -> tuple[int, str]:
    printable = " ".join(str(x) for x in cmd)
    log(f"$ {printable}")
    env = os.environ.copy()
    env.update(env_extra)
    try:
        p = subprocess.run(
            [str(x) for x in cmd],
            cwd=str(cwd or ROOT),
            env=env,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            errors="replace",
        )
        out = p.stdout.strip()
        if out:
            log(out[-4000:])
        if p.returncode != 0 and not allow_fail:
            raise RuntimeError(f"command failed: {printable}\n{out}")
        return p.returncode, out
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") + "\nTIMEOUT"
        log(out[-4000:])
        if not allow_fail:
            raise
        return 124, out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def apk_native_abis(apk: Path) -> list[str]:
    if not apk.exists():
        return []
    abis: set[str] = set()
    with zipfile.ZipFile(apk, "r") as z:
        for name in z.namelist():
            m = re.match(r"lib/([^/]+)/[^/]+\.so$", name)
            if m:
                abis.add(m.group(1))
    return sorted(abis)


def abi_compatible(device_abi: str, apk_abis: list[str]) -> bool:
    if not apk_abis:
        return True
    device_abi = device_abi.strip()
    if device_abi in apk_abis:
        return True
    # 64-bit Android devices can normally run matching 32-bit userland libs.
    if device_abi == "arm64-v8a" and "armeabi-v7a" in apk_abis:
        return True
    if device_abi == "x86_64" and "x86" in apk_abis:
        return True
    return False


def which(name: str) -> Path | None:
    p = shutil.which(name)
    return Path(p) if p else None


def android_sdk_candidates() -> list[Path]:
    candidates = [
        os.environ.get("ANDROID_SDK_ROOT"),
        os.environ.get("ANDROID_HOME"),
        str(ROOT / "android-sdk"),
        r"E:\android\Sdk" if platform.system() == "Windows" else None,
        str(Path.home() / "AppData" / "Local" / "Android" / "Sdk") if platform.system() == "Windows" else None,
        str(Path.home() / "Library" / "Android" / "sdk") if platform.system() == "Darwin" else None,
        str(Path.home() / "Android" / "Sdk"),
    ]
    out: list[Path] = []
    for c in candidates:
        if c:
            p = Path(c)
            if p.exists() and p not in out:
                out.append(p)
    return out


def find_android_sdk() -> Path | None:
    candidates = android_sdk_candidates()
    for p in candidates:
        if (p / "platform-tools").exists() or (p / "build-tools").exists() or (p / "emulator").exists():
            return p
    return None


def sdk_exe_name(exe: str) -> str:
    if platform.system() != "Windows":
        return exe
    if exe in {"apksigner", "sdkmanager", "avdmanager"}:
        return exe + ".bat"
    return exe + ".exe"


def runnable_file(path: Path | None) -> Path | None:
    if path and path.exists() and path.is_file():
        return path
    return None


def find_sdk_binary(ctx: Ctx, rel_parts: list[str], exe: str) -> Path | None:
    names = [sdk_exe_name(exe), exe]
    for sdk in ctx.sdk_candidates:
        for n in names:
            p = sdk.joinpath(*rel_parts, n)
            if runnable_file(p):
                return p
    return None


def find_build_tool(ctx: Ctx, exe: str) -> Path | None:
    direct = which(exe)
    if direct:
        return direct
    names = [sdk_exe_name(exe), exe]
    for sdk in ctx.sdk_candidates:
        bt = sdk / "build-tools"
        if bt.exists():
            for d in sorted([p for p in bt.iterdir() if p.is_dir()], reverse=True):
                for n in names:
                    p = d / n
                    if runnable_file(p):
                        return p
    return None


def find_java_home() -> Path | None:
    candidates = [
        os.environ.get("JAVA_HOME"),
        r"E:\android\AndroidStudio\jbr" if platform.system() == "Windows" else None,
        str(Path.home() / ".jdks" / "openjdk-23.0.1") if platform.system() == "Windows" else None,
        r"C:\Program Files\Android\Android Studio\jbr" if platform.system() == "Windows" else None,
    ]
    for c in candidates:
        if c:
            p = Path(c)
            if (p / "bin" / ("java.exe" if platform.system() == "Windows" else "java")).exists():
                return p
    return None


def find_tools(ctx: Ctx) -> None:
    ctx.sdk_candidates = android_sdk_candidates()
    if ctx.sdk and ctx.sdk not in ctx.sdk_candidates:
        ctx.sdk_candidates.insert(0, ctx.sdk)
    ctx.java_home = find_java_home()
    ctx.adb = which("adb") or find_sdk_binary(ctx, ["platform-tools"], "adb")
    ctx.emulator = which("emulator") or find_sdk_binary(ctx, ["emulator"], "emulator")
    ctx.apksigner = find_build_tool(ctx, "apksigner")
    ctx.zipalign = find_build_tool(ctx, "zipalign")
    java_keytool = ctx.java_home / "bin" / ("keytool.exe" if platform.system() == "Windows" else "keytool") if ctx.java_home else None
    ctx.keytool = runnable_file(java_keytool) or which("keytool")
    ctx.apktool = ROOT / "tools" / "apktool" / ("apktool.bat" if platform.system() == "Windows" else "apktool")
    if not ctx.apktool.exists():
        ctx.apktool = which("apktool")
    ctx.evidence["sdk_candidates"] = [str(p) for p in ctx.sdk_candidates]
    ctx.evidence["java_home"] = str(ctx.java_home) if ctx.java_home else None
    ctx.evidence["tools"] = {k: str(getattr(ctx, k)) for k in ["adb", "emulator", "apksigner", "zipalign", "keytool", "apktool"]}
    missing = [k for k in ["adb", "emulator", "apksigner", "zipalign", "keytool", "apktool"] if not getattr(ctx, k)]
    ctx.steps.append(Step("tool discovery", not missing, "missing: " + ", ".join(missing) if missing else "all required host tools found"))


def sdkmanager_path(sdk: Path) -> Path | None:
    for rel in [
        ("cmdline-tools", "latest", "bin"),
        ("cmdline-tools", "bin"),
    ]:
        p = sdk.joinpath(*rel, sdk_exe_name("sdkmanager"))
        if runnable_file(p):
            return p
    return None


def ensure_workspace_cmdline_tools(ctx: Ctx) -> bool:
    sdk = ROOT / "android-sdk"
    latest = sdk / "cmdline-tools" / "latest"
    manager = latest / "bin" / sdk_exe_name("sdkmanager")
    if runnable_file(manager):
        return True
    cache = sdk / ".cache"
    cache.mkdir(parents=True, exist_ok=True)
    url = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
    zip_path = cache / "commandlinetools-win-latest.zip"
    if not zip_path.exists() or zip_path.stat().st_size < 150_000_000:
        curl = which("curl.exe") or which("curl")
        if not curl:
            ctx.evidence["workspace_sdk_install"] = "curl missing; cannot download commandline-tools"
            return False
        code, out = run([curl, "-L", "-C", "-", "--retry", "5", "--retry-delay", "3", "-o", zip_path, url], timeout=1800)
        if code != 0:
            ctx.evidence["workspace_sdk_install"] = f"commandline-tools download failed: {out[-1000:]}"
            return False
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            bad = z.testzip()
            if bad:
                ctx.evidence["workspace_sdk_install"] = f"commandline-tools zip corrupt at {bad}"
                return False
            tmp = sdk / ".cmdline-tools-extract"
            if tmp.exists():
                shutil.rmtree(tmp)
            z.extractall(tmp)
            if latest.exists():
                shutil.rmtree(latest)
            latest.mkdir(parents=True, exist_ok=True)
            extracted = tmp / "cmdline-tools"
            for child in extracted.iterdir():
                shutil.move(str(child), str(latest / child.name))
            shutil.rmtree(tmp, ignore_errors=True)
    except Exception as e:
        ctx.evidence["workspace_sdk_install"] = f"commandline-tools extract failed: {e}"
        return False
    return runnable_file(manager) is not None


def ensure_android_runtime_tools(ctx: Ctx) -> None:
    if ctx.adb and ctx.emulator:
        ctx.steps.append(Step("android runtime tool install", True, "adb/emulator already available"))
        return
    sdk = ROOT / "android-sdk"
    sdk.mkdir(exist_ok=True)
    if not ctx.java_home:
        ctx.steps.append(Step("android runtime tool install", False, "JDK 17+ missing for sdkmanager"))
        return
    if not ensure_workspace_cmdline_tools(ctx):
        ctx.steps.append(Step("android runtime tool install", False, str(ctx.evidence.get("workspace_sdk_install", "cmdline-tools unavailable"))))
        return
    manager = sdkmanager_path(sdk)
    if not manager:
        ctx.steps.append(Step("android runtime tool install", False, "sdkmanager missing after commandline-tools setup"))
        return
    env = {
        "JAVA_HOME": str(ctx.java_home),
        "ANDROID_SDK_ROOT": str(sdk),
        "ANDROID_HOME": str(sdk),
        "PATH": str(ctx.java_home / "bin") + os.pathsep + os.environ.get("PATH", ""),
    }
    run_with_env([manager, "--sdk_root=" + str(sdk), "--licenses"], env, timeout=300, input_text=("y\n" * 100))
    packages = [
        "platform-tools",
        "emulator",
        "platforms;android-33",
        "build-tools;33.0.2",
        "system-images;android-33;google_apis;arm64-v8a",
    ]
    code, out = run_with_env([manager, "--sdk_root=" + str(sdk), "--install", *packages, "--channel=0"], env, timeout=1800, input_text=("y\n" * 50))
    ctx.evidence["workspace_sdk_install"] = {"returncode": code, "output_tail": out[-2000:]}
    ctx.sdk_candidates.insert(0, sdk)
    ctx.adb = which("adb") or find_sdk_binary(ctx, ["platform-tools"], "adb")
    ctx.emulator = which("emulator") or find_sdk_binary(ctx, ["emulator"], "emulator")
    if not ctx.apksigner:
        ctx.apksigner = find_build_tool(ctx, "apksigner")
    if not ctx.zipalign:
        ctx.zipalign = find_build_tool(ctx, "zipalign")
    ok = bool(ctx.adb and ctx.emulator)
    detail = "workspace SDK runtime tools available" if ok else f"adb={ctx.adb}, emulator={ctx.emulator}, install_rc={code}"
    ctx.steps.append(Step("android runtime tool install", ok, detail))


def ensure_python_packages(ctx: Ctx) -> None:
    packages = ["frida-tools", "objection", "capstone", "requests"]
    missing = []
    import importlib.util
    module_map = {"frida-tools": "frida_tools", "objection": "objection", "capstone": "capstone", "requests": "requests"}
    for pkg in packages:
        if importlib.util.find_spec(module_map[pkg]) is None:
            missing.append(pkg)
    if missing:
        run([ctx.python, "-m", "pip", "install", "--upgrade", *missing], timeout=600, allow_fail=True)
    still_missing = [pkg for pkg in packages if importlib.util.find_spec(module_map[pkg]) is None]
    ctx.steps.append(Step("python dependency install", not still_missing, "missing: " + ", ".join(still_missing) if still_missing else "frida-tools/objection/capstone available"))


def make_manual_avd(ctx: Ctx, name: str = "Pixel_6_API_33_CTF") -> Path | None:
    if not ctx.sdk:
        return None
    image = ctx.sdk / "system-images" / "android-33" / "google_apis_playstore" / "x86_64"
    if not image.exists():
        ctx.steps.append(Step("manual AVD create", False, f"missing image {image}"))
        return None
    avd_root = Path.home() / ".android" / "avd"
    avd_dir = avd_root / f"{name}.avd"
    avd_root.mkdir(parents=True, exist_ok=True)
    avd_dir.mkdir(parents=True, exist_ok=True)
    (avd_root / f"{name}.ini").write_text(f"avd.ini.encoding=UTF-8\npath={avd_dir}\npath.rel=avd/{name}.avd\ntarget=android-33\n", encoding="utf-8")
    config = f"""
AvdId={name}
PlayStore.enabled=true
abi.type=x86_64
avd.ini.displayname=Pixel 6 API 33 CTF
disk.dataPartition.size=8G
hw.accelerometer=yes
hw.audioInput=yes
hw.battery=yes
hw.camera.back=emulated
hw.camera.front=emulated
hw.cpu.arch=x86_64
hw.device.manufacturer=Google
hw.device.name=pixel_6
hw.gpu.enabled=yes
hw.gpu.mode=auto
hw.keyboard=yes
hw.lcd.density=420
hw.lcd.height=2400
hw.lcd.width=1080
hw.ramSize=4096
image.sysdir.1=system-images/android-33/google_apis_playstore/x86_64/
runtime.network.latency=none
runtime.network.speed=full
sdcard.size=512M
tag.display=Google Play
tag.id=google_apis_playstore
target=android-33
vm.heapSize=512
"""
    (avd_dir / "config.ini").write_text(textwrap.dedent(config).strip() + "\n", encoding="utf-8")
    ctx.steps.append(Step("manual AVD create", True, str(avd_dir)))
    return avd_dir


def adb_devices(ctx: Ctx) -> list[str]:
    if not ctx.adb:
        return []
    _, out = run([ctx.adb, "devices", "-l"], timeout=30)
    devices = []
    for line in out.splitlines():
        if "\tdevice" in line or re.search(r"\sdevice\s", line):
            if not line.startswith("List of"):
                devices.append(line.split()[0])
    ctx.evidence["adb_devices"] = out
    return devices


def start_emulator_if_needed(ctx: Ctx) -> bool:
    if adb_devices(ctx):
        ctx.steps.append(Step("device available", True, "existing adb device found"))
        return True
    if not ctx.emulator:
        ctx.steps.append(Step("emulator start", False, "emulator executable missing"))
        return False
    name = "Pixel_6_API_33_CTF"
    make_manual_avd(ctx, name)
    cmd = [ctx.emulator, "-avd", name, "-no-window", "-no-audio", "-no-snapshot", "-writable-system", "-gpu", "swiftshader_indirect"]
    log("starting emulator in background")
    subprocess.Popen([str(x) for x in cmd], cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 420
    while time.time() < deadline:
        if adb_devices(ctx):
            if ctx.adb:
                run([ctx.adb, "wait-for-device"], timeout=60)
                code, boot = run([ctx.adb, "shell", "getprop", "sys.boot_completed"], timeout=20)
                if "1" in boot:
                    ctx.steps.append(Step("emulator start", True, "boot_completed=1"))
                    return True
        time.sleep(10)
    ctx.steps.append(Step("emulator start", False, "timeout waiting for boot"))
    return False


def try_root(ctx: Ctx) -> bool:
    if not ctx.adb:
        ctx.steps.append(Step("root check", False, "adb missing"))
        return False
    run([ctx.adb, "root"], timeout=60)
    time.sleep(3)
    run([ctx.adb, "disable-verity"], timeout=60)
    run([ctx.adb, "remount"], timeout=60)
    _, id_out = run([ctx.adb, "shell", "id"], timeout=30)
    _, su_out = run([ctx.adb, "shell", "su", "-c", "id"], timeout=30)
    ok = "uid=0" in id_out or "uid=0" in su_out
    ctx.evidence["root_id"] = {"shell_id": id_out, "su_id": su_out}
    ctx.steps.append(Step("root check", ok, f"shell_id={id_out}; su_id={su_out}"))
    return ok


def write_frida_scripts(ctx: Ctx) -> Path:
    HOOKS.mkdir(parents=True, exist_ok=True)
    hook = HOOKS / "bypass_integrity.js"
    hook.write_text(r"""
'use strict';

function log(x) { console.log('[ctf-bypass] ' + x); }

Java.perform(function () {
  try {
    var StubApp = Java.use('com.stub.StubApp');
    log('StubApp loaded: ' + StubApp);
    ['interface7', 'interface8'].forEach(function (name) {
      if (StubApp[name]) {
        StubApp[name].overloads.forEach(function (ov) {
          ov.implementation = function () {
            log('forcing ' + name + ' -> true');
            return true;
          };
        });
      }
    });
    if (StubApp.getString2) {
      StubApp.getString2.overloads.forEach(function (ov) {
        var old = ov.implementation;
        ov.implementation = function () {
          var r = old.apply(this, arguments);
          log('getString2 -> ' + r);
          return r;
        };
      });
    }
  } catch (e) { log('Java StubApp hook failed: ' + e); }

  try {
    var PM = Java.use('android.app.ApplicationPackageManager');
    PM.getPackageInfo.overload('java.lang.String', 'int').implementation = function (pkg, flags) {
      var r = this.getPackageInfo(pkg, flags);
      log('getPackageInfo ' + pkg + ' flags=' + flags);
      return r;
    };
  } catch (e) { log('PackageManager hook failed: ' + e); }

  try {
    var GoogleApiClient = Java.use('com.google.android.gms.common.api.GoogleApiClient');
    log('GoogleApiClient class visible: ' + GoogleApiClient);
  } catch (e) { log('GoogleApiClient not visible yet: ' + e); }
});

setImmediate(function () {
  ['libjiagu.so', 'libjiagu_a64.so', 'libapp.so', 'libflutter.so'].forEach(function (m) {
    var base = Module.findBaseAddress(m);
    log(m + ' base=' + base);
    if (!base) return;
    ['strcmp', 'memcmp', 'strncmp'].forEach(function (sym) {
      var p = Module.findExportByName(null, sym);
      if (p) {
        Interceptor.attach(p, {
          onEnter: function (args) { this.sym = sym; },
          onLeave: function (retval) {
            if (this.sym === 'memcmp' || this.sym === 'strcmp' || this.sym === 'strncmp') {
              retval.replace(0);
            }
          }
        });
        log('hooked libc ' + sym + ' at ' + p);
      }
    });
  });
});
""".strip() + "\n", encoding="utf-8")
    ctx.steps.append(Step("frida hook script generate", True, str(hook)))
    return hook


def install_frida_server(ctx: Ctx) -> bool:
    if not ctx.adb or not adb_devices(ctx):
        ctx.steps.append(Step("frida-server install", False, "no adb device"))
        return False
    code, abi = run([ctx.adb, "shell", "getprop", "ro.product.cpu.abi"], timeout=30)
    abi = abi.strip() or "x86_64"
    arch = "android-x86_64" if "x86_64" in abi else "android-x86" if "x86" in abi else "android-arm64" if "64" in abi else "android-arm"
    code, version = run([ctx.python, "-c", "import frida; print(frida.__version__)"], timeout=30)
    version = version.strip() or "17.12.0"
    server = WORK / f"frida-server-{version}-{arch}"
    if not server.exists():
        url = f"https://github.com/frida/frida/releases/download/{version}/frida-server-{version}-{arch}.xz"
        xz = server.with_suffix(".xz")
        try:
            log(f"downloading {url}")
            urllib.request.urlretrieve(url, xz)
            server.write_bytes(lzma.decompress(xz.read_bytes()))
        except Exception as e:
            ctx.steps.append(Step("frida-server download", False, str(e)))
            return False
    run([ctx.adb, "push", server, "/data/local/tmp/frida-server"], timeout=120)
    run([ctx.adb, "shell", "chmod", "755", "/data/local/tmp/frida-server"], timeout=30)
    run([ctx.adb, "shell", "su", "-c", "pkill frida-server"], timeout=30)
    subprocess.Popen([str(ctx.adb), "shell", "su", "-c", "/data/local/tmp/frida-server >/dev/null 2>&1 &"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    code, out = run([ctx.python, "-m", "frida_tools.ps", "-U"], timeout=60)
    ok = code == 0 and ("PID" in out or "Name" in out)
    ctx.steps.append(Step("frida-server install", ok, out[:500]))
    return ok


def install_and_launch(ctx: Ctx, apk: Path, hook: Path | None = None) -> bool:
    if not ctx.adb or not adb_devices(ctx):
        ctx.steps.append(Step("dynamic install/launch", False, "no adb device"))
        return False
    _, device_abi_out = run([ctx.adb, "shell", "getprop", "ro.product.cpu.abi"], timeout=30)
    device_abi = device_abi_out.strip()
    app_abis = apk_native_abis(apk)
    ctx.evidence["dynamic_abi"] = {"device_abi": device_abi, "apk_abis": app_abis}
    if not abi_compatible(device_abi, app_abis):
        ctx.steps.append(Step("dynamic install/launch", False, f"ABI mismatch: device={device_abi}, apk={','.join(app_abis) or 'none'}"))
        return False

    install_code, install_out = run([ctx.adb, "install", "-r", "-d", apk], timeout=180)
    ctx.evidence["dynamic_install"] = {"returncode": install_code, "output": install_out[-2000:]}
    if install_code != 0:
        ctx.steps.append(Step("dynamic install/launch", False, f"install failed: {install_out[-500:]}"))
        return False

    run([ctx.adb, "logcat", "-c"], timeout=20)
    if hook:
        subprocess.Popen([str(ctx.python), "-m", "frida_tools.repl", "-U", "-f", ctx.package, "-l", str(hook)], cwd=str(ROOT))
        time.sleep(8)
        launch_code, launch_out = 0, "frida spawn attempted"
    else:
        launch_code, launch_out = run([ctx.adb, "shell", "am", "start", "-n", f"{ctx.package}/{ctx.activity}"], timeout=60)
        time.sleep(8)
    ctx.evidence["dynamic_launch"] = {"returncode": launch_code, "output": launch_out[-2000:]}
    if launch_code != 0 or "Error type" in launch_out or "does not exist" in launch_out:
        ctx.steps.append(Step("dynamic install/launch", False, f"launch failed: {launch_out[-500:]}"))
        return False

    code, logs = run([ctx.adb, "logcat", "-d", "-t", "1000"], timeout=60)
    (LOGS / "runtime-logcat.txt").write_text(logs, encoding="utf-8", errors="replace")
    filtered = "\n".join([ln for ln in logs.splitlines() if re.search(r"FATAL|AndroidRuntime|Integrity|Signature|Tamper|StubApp|jiagu", ln, re.I)])
    (LOGS / "runtime-filtered.txt").write_text(filtered, encoding="utf-8", errors="replace")
    screenshot = OUTPUT / "screenshot.png"
    if screenshot.exists():
        screenshot.unlink()
    with screenshot.open("wb") as f:
        p = subprocess.run([str(ctx.adb), "exec-out", "screencap", "-p"], stdout=f, stderr=subprocess.DEVNULL, timeout=30)
    ok = p.returncode == 0 and "FATAL EXCEPTION" not in logs and screenshot.exists() and screenshot.stat().st_size > 1000
    ctx.steps.append(Step("dynamic install/launch", ok, f"screenshot={screenshot}; filtered_log_lines={len(filtered.splitlines())}"))
    return ok


def copytree_clean(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def decode_apk(ctx: Ctx, out: Path) -> bool:
    if out.exists():
        shutil.rmtree(out)
    code, _ = run([ctx.apktool, "d", "-f", ctx.apk, "-o", out], timeout=300)
    ok = code == 0 and (out / "AndroidManifest.xml").exists()
    ctx.steps.append(Step("apk decode", ok, str(out)))
    return ok


def static_analysis_and_patch(ctx: Ctx, decoded: Path) -> Path:
    analysis = {}
    assets = decoded / "assets"
    jgapp = assets / ".jgapp"
    analysis["jgapp_exists"] = jgapp.exists()
    if jgapp.exists():
        data = jgapp.read_bytes()
        analysis["jgapp_size"] = len(data)
        analysis["jgapp_sha256"] = hashlib.sha256(data).hexdigest()
        # Lightweight XOR scoring over first 256 bytes.
        best = []
        sample = data[:256]
        for k in range(256):
            out = bytes([b ^ k for b in sample])
            score = sum(32 <= c < 127 or c in (9, 10, 13) for c in out)
            if score > 80:
                best.append({"key": k, "score": score, "preview": out[:80].decode("latin1", "replace")})
        analysis["jgapp_xor_candidates"] = best[:10]
    so_findings = {}
    for so in list((assets).glob("libjiagu*.so")) + list((decoded / "lib").glob("**/libjiagu*.so")) + list((decoded / "lib").glob("**/libapp.so")):
        b = so.read_bytes()
        strings = sorted(set(s.decode("latin1", "ignore") for s in re.findall(rb"[\x20-\x7e]{5,}", b)))
        interesting = [s for s in strings if re.search(r"sign|sig|tamper|integr|check|verify|root|frida|xposed|magisk|sha|md5|flutter|snapshot", s, re.I)]
        so_findings[str(so.relative_to(decoded))] = {"size": so.stat().st_size, "sha256": sha256(so), "interesting_strings": interesting[:80]}
    analysis["native_findings"] = so_findings
    (OUTPUT / "static-analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    patched = WORK / "static-patched"
    copytree_clean(decoded, patched)
    stub = patched / "smali" / "com" / "stub" / "StubApp.smali"
    if stub.exists():
        text = stub.read_text(encoding="utf-8", errors="replace")
        # Bypass hard termination while preserving loader flow for runtime evidence.
        text2 = text.replace("    invoke-static {v7}, Ljava/lang/System;->exit(I)V", "    # CTF patch: disabled hard exit\n    nop")
        stub.write_text(text2, encoding="utf-8")
        ctx.steps.append(Step("static smali patch", text2 != text, "disabled StubApp System.exit branch" if text2 != text else "pattern not found"))
    else:
        ctx.steps.append(Step("static smali patch", False, "StubApp.smali missing"))
    return patched


def make_keystore(ctx: Ctx, name: str, dname: str) -> Path:
    ks = WORK / f"{name}.jks"
    if not ks.exists():
        run([ctx.keytool, "-genkeypair", "-keystore", ks, "-storepass", "ctfpass123", "-keypass", "ctfpass123", "-alias", name, "-keyalg", "RSA", "-keysize", "2048", "-validity", "3650", "-dname", dname], timeout=120)
    return ks


def build_sign(ctx: Ctx, decoded: Path, stem: str, dname: str) -> Path | None:
    ascii_root = Path(tempfile.gettempdir()) / f"ctf_breach_{stem}"
    if ascii_root.exists():
        shutil.rmtree(ascii_root)
    shutil.copytree(decoded, ascii_root / "decoded")
    unsigned = ascii_root / f"{stem}-unsigned.apk"
    aligned = ascii_root / f"{stem}-aligned.apk"
    signed_tmp = ascii_root / f"{stem}-signed.apk"
    signed = OUTPUT / f"{stem}-signed.apk"
    code, _ = run([ctx.apktool, "b", ascii_root / "decoded", "-o", unsigned], timeout=300)
    if code != 0:
        ctx.steps.append(Step(f"{stem} build", False, "apktool failed"))
        return None
    code, _ = run([ctx.zipalign, "-f", "-p", "4", unsigned, aligned], timeout=120)
    if code != 0:
        ctx.steps.append(Step(f"{stem} zipalign", False, "zipalign failed"))
        return None
    ks = make_keystore(ctx, stem, dname)
    code, _ = run([ctx.apksigner, "sign", "--ks", ks, "--ks-key-alias", stem, "--ks-pass", "pass:ctfpass123", "--key-pass", "pass:ctfpass123", "--out", signed_tmp, aligned], timeout=120)
    if code != 0:
        ctx.steps.append(Step(f"{stem} sign", False, "apksigner sign failed"))
        return None
    shutil.copy2(signed_tmp, signed)
    code, verify = run([ctx.apksigner, "verify", "-v", "--print-certs", signed], timeout=120)
    cert = re.search(r"certificate SHA-256 digest: ([0-9a-f]+)", verify)
    ctx.evidence[f"{stem}_apk"] = {"path": str(signed), "sha256": sha256(signed), "verify": verify, "cert_sha256": cert.group(1) if cert else None}
    code2, za = run([ctx.zipalign, "-c", "-p", "-v", "4", signed], timeout=120)
    ctx.steps.append(Step(f"{stem} build/sign/verify", code == 0 and code2 == 0, f"{signed}"))
    return signed


def private_store_simulation(ctx: Ctx, apks: list[Path]) -> None:
    store = OUTPUT / "private-store"
    store.mkdir(exist_ok=True)
    manifest = []
    for apk in apks:
        if apk and apk.exists():
            dst = store / apk.name
            shutil.copy2(apk, dst)
            manifest.append({"file": dst.name, "sha256": sha256(dst), "size": dst.stat().st_size})
    (store / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            log("[store] " + (fmt % args))

    port = 8765
    old_cwd = os.getcwd()
    os.chdir(store)
    try:
        httpd = socketserver.TCPServer(("127.0.0.1", port), Handler)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        time.sleep(1)
        downloaded = OUTPUT / "store-download.apk"
        if manifest:
            urllib.request.urlretrieve(f"http://127.0.0.1:{port}/{manifest[0]['file']}", downloaded)
            ok = sha256(downloaded) == manifest[0]["sha256"]
            ctx.steps.append(Step("private store simulation", ok, f"http://127.0.0.1:{port}/manifest.json"))
        else:
            ctx.steps.append(Step("private store simulation", False, "no apk artifacts"))
        httpd.shutdown()
    finally:
        os.chdir(old_cwd)


def write_report(ctx: Ctx) -> int:
    ok_count = sum(1 for s in ctx.steps if s.ok)
    fail = [s for s in ctx.steps if not s.ok]
    signed_ok = any("build/sign/verify" in s.name and s.ok for s in ctx.steps)
    risk = "高：已在运行环境证明重签名/绕过后可启动" if ctx.evidence.get("dynamic_bypass_ok") else "中：静态重打包和签名链已通过，动态运行受设备/root/ABI限制未证实" if signed_ok else "低/未证实：未完成可安装产物验证"
    lines = [
        "# Final CTF Breach Audit Report",
        "",
        "## Summary",
        f"- APK: `{ctx.apk}`",
        f"- Package: `{ctx.package}`",
        f"- Activity: `{ctx.activity}`",
        f"- Steps passed: `{ok_count}/{len(ctx.steps)}`",
        f"- Production risk rating: `{risk}`",
        "",
        "## Step Results",
    ]
    for s in ctx.steps:
        lines.append(f"- [{'OK' if s.ok else 'FAIL'}] {s.name}: {s.detail}")
    lines += [
        "",
        "## Key Evidence",
        "```json",
        json.dumps(ctx.evidence, ensure_ascii=False, indent=2)[:20000],
        "```",
        "",
        "## Runnable Commands",
        "```powershell",
        r"D:\Anconda3\python.exe .\tools\ctf_breach_pipeline.py --apk .\base.apk --package com.flai.flai --activity com.flai.flai.MainActivity",
        "```",
        "",
        "## Generated Frida Hook",
        "See `output/frida/bypass_integrity.js`.",
        "",
        "## Hardening Recommendations",
        "- Bind server-side API access to package name, signing certificate SHA-256, version, device nonce, and short-lived challenge response.",
        "- Verify APK SigningInfo in Java and native code, then cross-check it on the server.",
        "- Hash critical assets and native libraries at runtime: `classes.dex`, `assets/.jgapp`, `assets/libjiagu*.so`, `lib/*/libapp.so`.",
        "- Move sensitive trust decisions server-side; treat client-side checks as telemetry and delay signals.",
        "- Add native self-integrity with diversified white-box constants and anti-hook detection, while keeping false-positive handling on the server.",
        "- Keep release provenance: APK digest, signing digest, SBOM, build ID, and store-upload attestation.",
        "",
        "## Notes",
        "- The target uses `assets/.jgapp` and `libjiagu*.so`; `.jgap/libjagu.so` were treated as typo aliases.",
        "- A re-signed APK passing v2/v3 verification is not equivalent to production identity continuity unless the original signing lineage/key is available.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if not fail else 2


def package_artifacts() -> None:
    if ARTIFACT_ZIP.exists():
        ARTIFACT_ZIP.unlink()
    with zipfile.ZipFile(ARTIFACT_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for p in OUTPUT.rglob("*"):
            if p == ARTIFACT_ZIP or p.is_dir():
                continue
            z.write(p, p.relative_to(OUTPUT.parent))
    log(f"artifact zip: {ARTIFACT_ZIP}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apk", default="base.apk")
    ap.add_argument("--package", default="com.flai.flai")
    ap.add_argument("--activity", default="com.flai.flai.MainActivity")
    ap.add_argument("--skip-dynamic", action="store_true", help="Run static/signing/store tasks only.")
    args = ap.parse_args()

    OUTPUT.mkdir(exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    HOOKS.mkdir(parents=True, exist_ok=True)
    (LOGS / "pipeline.log").write_text("", encoding="utf-8")

    ctx = Ctx(apk=(ROOT / args.apk).resolve(), package=args.package, activity=args.activity, sdk=find_android_sdk())
    find_tools(ctx)
    if not ctx.adb or not ctx.emulator:
        ensure_android_runtime_tools(ctx)
        find_tools(ctx)
    ensure_python_packages(ctx)
    hook = write_frida_scripts(ctx)

    decoded = WORK / "decoded-base"
    if ctx.apktool:
        decode_apk(ctx, decoded)
    if decoded.exists():
        patched = static_analysis_and_patch(ctx, decoded)
        apk_a = build_sign(ctx, patched, "certA-same-cn", "CN=flai, OU=flai, O=flai, L=taipei, ST=taiwan")
        apk_b = build_sign(ctx, patched, "certB-random", "CN=CTF-Random, O=Sandbox")
        existing = ROOT / "reverse-analysis" / "ctf-control-audit" / "mutated-signed.apk"
        apks = [p for p in [apk_a, apk_b, existing if existing.exists() else None] if p]
        private_store_simulation(ctx, apks)

    if not args.skip_dynamic:
        device_ok = start_emulator_if_needed(ctx)
        root_ok = try_root(ctx) if device_ok else False
        frida_ok = install_frida_server(ctx) if root_ok else False
        existing = ROOT / "reverse-analysis" / "ctf-control-audit" / "mutated-signed.apk"
        dyn_ok = install_and_launch(ctx, existing, hook if frida_ok else None) if existing.exists() and device_ok else False
        ctx.evidence["dynamic_bypass_ok"] = dyn_ok
    else:
        ctx.steps.append(Step("dynamic tests", True, "skipped by --skip-dynamic"))
        ctx.evidence["dynamic_bypass_ok"] = False

    rc = write_report(ctx)
    package_artifacts()
    log(f"report: {REPORT}")
    log(f"exit_code={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
