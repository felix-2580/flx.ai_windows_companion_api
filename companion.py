"""FLX.AI Windows Companion: allow-listed local actions for the FLX.AI website."""
from __future__ import annotations

import ast
import ctypes
import json
import os
import operator
import re
import shutil
import subprocess
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from flask import Flask, jsonify, request
from flask_cors import CORS

APP = Flask(__name__)
CORS(APP, resources={r"/*": {"origins": [
    "https://flx-ai-demo.onrender.com", "http://127.0.0.1:5000",
    "http://localhost:5000", "null"
]}}, methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"])

SAFE_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

WEBSITES = {
    "youtube": "https://www.youtube.com/", "google": "https://www.google.com/",
    "gmail": "https://mail.google.com/", "chatgpt": "https://chatgpt.com/",
    "github": "https://github.com/", "instagram": "https://www.instagram.com/",
    "facebook": "https://www.facebook.com/", "whatsapp": "https://web.whatsapp.com/",
    "spotify": "https://open.spotify.com/", "netflix": "https://www.netflix.com/",
    "reddit": "https://www.reddit.com/", "amazon": "https://www.amazon.com/",
    "google classroom": "https://classroom.google.com/",
    "google drive": "https://drive.google.com/", "google docs": "https://docs.google.com/",
    "google meet": "https://meet.google.com/", "google maps": "https://maps.google.com/",
    "wikipedia": "https://www.wikipedia.org/", "linkedin": "https://www.linkedin.com/",
    "discord": "https://discord.com/",
}

# Explicit application aliases only. Spotify is a website unless the user says "Spotify app".
APP_TARGETS = {
    "chrome": ("chrome.exe", "Google Chrome"), "google chrome": ("chrome.exe", "Google Chrome"),
    "edge": ("msedge.exe", "Microsoft Edge"), "microsoft edge": ("msedge.exe", "Microsoft Edge"),
    "firefox": ("firefox.exe", "Firefox"), "file explorer": ("explorer.exe", "File Explorer"),
    "explorer": ("explorer.exe", "File Explorer"), "notepad": ("notepad.exe", "Notepad"),
    "calculator": ("calc.exe", "Calculator"), "calc": ("calc.exe", "Calculator"),
    "snipping tool": ("ms-screenclip:", "Snipping Tool"), "clock": ("ms-clock:", "Clock"),
    "settings": ("ms-settings:", "Settings"), "task manager": ("taskmgr.exe", "Task Manager"),
    "control panel": ("control.exe", "Control Panel"), "terminal": ("wt.exe", "Windows Terminal"),
    "windows terminal": ("wt.exe", "Windows Terminal"), "command prompt": ("cmd.exe", "Command Prompt"),
    "cmd": ("cmd.exe", "Command Prompt"), "powershell": ("powershell.exe", "PowerShell"),
    "paint": ("mspaint.exe", "Paint"), "photos": ("ms-photos:", "Photos"),
    "media player": ("mswindowsmusic:", "Media Player"), "word": ("winword.exe", "Microsoft Word"),
    "microsoft word": ("winword.exe", "Microsoft Word"), "excel": ("excel.exe", "Microsoft Excel"),
    "microsoft excel": ("excel.exe", "Microsoft Excel"), "powerpoint": ("powerpnt.exe", "Microsoft PowerPoint"),
    "power point": ("powerpnt.exe", "Microsoft PowerPoint"), "microsoft powerpoint": ("powerpnt.exe", "Microsoft PowerPoint"),
    "vscode": ("code", "Visual Studio Code"), "visual studio code": ("code", "Visual Studio Code"),
    "pycharm": ("pycharm64.exe", "PyCharm"), "spotify app": ("spotify:", "Spotify application"),
}

FOLDER_ALIASES = {
    "downloads": "Downloads", "download": "Downloads", "documents": "Documents",
    "document": "Documents", "desktop": "Desktop", "pictures": "Pictures",
    "picture": "Pictures", "videos": "Videos", "video": "Videos", "music": "Music",
    "home folder": "Home", "home": "Home",
}


def result(message: str, success: bool, command: str = "", confirmation_required: bool = False):
    data = {"success": bool(success), "message": str(message),
            "state": "success" if success else "error", "command": command}
    if confirmation_required:
        data["confirmation_required"] = True
    return data


def normalize(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^\w\s.%:/\\-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def resolve_executable(target: str) -> str | None:
    found = shutil.which(target)
    if found:
        return found
    if os.name != "nt":
        return None
    # Check Windows App Paths registry entries, which cover many installed desktop apps.
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{target}") as key:
            value, _ = winreg.QueryValueEx(key, "")
            if value and Path(value).exists(): return value
    except Exception:
        pass
    roots = [os.environ.get("PROGRAMFILES", r"C:\Program Files"),
             os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
             os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))]
    candidates = {
        "chrome.exe": [r"Google\Chrome\Application\chrome.exe", r"Google\Chrome\Application\chrome.exe"],
        "msedge.exe": [r"Microsoft\Edge\Application\msedge.exe"],
        "firefox.exe": [r"Mozilla Firefox\firefox.exe"],
        "winword.exe": [r"Microsoft Office\root\Office16\WINWORD.EXE", r"Microsoft Office\Office16\WINWORD.EXE"],
        "excel.exe": [r"Microsoft Office\root\Office16\EXCEL.EXE", r"Microsoft Office\Office16\EXCEL.EXE"],
        "powerpnt.exe": [r"Microsoft Office\root\Office16\POWERPNT.EXE", r"Microsoft Office\Office16\POWERPNT.EXE"],
        "pycharm64.exe": [r"JetBrains\PyCharm\bin\pycharm64.exe", r"JetBrains\PyCharm Community Edition\bin\pycharm64.exe"],
        "code": [r"Programs\Microsoft VS Code\Code.exe", r"Microsoft VS Code\Code.exe"],
    }
    for root in roots:
        for relative in candidates.get(target.lower(), []):
            path = Path(root) / relative
            if path.exists(): return str(path)
    return None


def launch(target: str, label: str) -> tuple[str, bool]:
    try:
        if target.startswith("ms-") or target.endswith(":"):
            os.startfile(target)  # Windows URI/protocol handler
        elif target == "explorer.exe":
            subprocess.Popen([target], shell=False)
        else:
            executable = resolve_executable(target)
            if not executable:
                raise FileNotFoundError(target)
            subprocess.Popen([executable], shell=False)
        return f"Opened {label}.", True
    except Exception:
        return f"Couldn't open {label}. Check that it is installed and available on this PC.", False


def open_website(name: str) -> tuple[str, bool]:
    url = WEBSITES[name]
    try:
        if webbrowser.open(url, new=2):
            return f"Opened {name.title()} in your default browser.", True
        return f"Couldn't open {name.title()} in your default browser.", False
    except Exception:
        return f"Couldn't open {name.title()} in your default browser.", False


def open_folder(name: str) -> tuple[str, bool]:
    try:
        if name == "Home":
            path = Path.home()
        else:
            path = known_folder(name)
        if not path or not path.exists() or not path.is_dir():
            return f"Couldn't find the {name} folder on this PC.", False
        os.startfile(str(path))
        return f"Opened {name} folder.", True
    except Exception:
        return f"Couldn't open the {name} folder.", False


def known_folder(name: str) -> Path | None:
    """Resolve Windows known-folder locations, including redirected folders where available."""
    if os.name != "nt":
        return Path.home() / name
    try:
        import winreg
        keys = {
            "Desktop": "Desktop", "Documents": "Personal", "Pictures": "My Pictures",
            "Music": "My Music", "Videos": "My Video",
        }
        if name == "Downloads":
            value_name = "{374DE290-123F-4565-9164-39C4925E467B}"
        else:
            value_name = keys[name]
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
            value, _ = winreg.QueryValueEx(key, value_name)
        return Path(os.path.expandvars(value))
    except Exception:
        return Path.home() / name


def set_volume(command: str) -> tuple[str, bool]:
    try:
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        device = AudioUtilities.GetSpeakers()
        # Newer pycaw versions expose EndpointVolume directly; older ones expose Activate().
        endpoint = getattr(device, "EndpointVolume", None)
        if endpoint is None:
            interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            endpoint = cast(interface, POINTER(IAudioEndpointVolume))
        if command in {"mute", "mute volume", "mute audio"}:
            endpoint.SetMute(1, None)
            return "System audio muted.", True
        if command in {"unmute", "unmute volume", "unmute audio"}:
            endpoint.SetMute(0, None)
            return "System audio unmuted.", True
        current = round(endpoint.GetMasterVolumeLevelScalar() * 100)
        m = re.fullmatch(r"set volume to (\d{1,3})(?:\s*(?:%|percent))?", command)
        if m:
            target = int(m.group(1))
        else:
            m = re.fullmatch(r"(?:increase|decrease) volume by (\d{1,3})(?:\s*(?:%|percent))?", command)
            if m:
                amount = int(m.group(1))
                target = current + amount if command.startswith("increase") else current - amount
            elif command in {"increase volume", "volume up", "volume increase", "louder", "turn volume up"}:
                target = current + 5
            elif command in {"decrease volume", "volume down", "volume decrease", "quieter", "turn volume down"}:
                target = current - 5
            else:
                return "Unsupported volume command.", False
        target = max(0, min(100, target))
        endpoint.SetMasterVolumeLevelScalar(target / 100, None)
        return f"System volume set to {target}%.", True
    except Exception as exc:
        return f"Volume control failed: {type(exc).__name__}. Check the companion audio dependencies and Windows audio device.", False


def set_brightness(command: str) -> tuple[str, bool]:
    try:
        import screen_brightness_control as sbc
        values = sbc.get_brightness(display=0)
        current = int(values[0] if isinstance(values, list) else values)
        m = re.fullmatch(r"set brightness to (\d{1,3})(?:\s*(?:%|percent))?", command)
        if m:
            target = int(m.group(1))
        else:
            m = re.fullmatch(r"(?:increase|decrease) brightness by (\d{1,3})(?:\s*(?:%|percent))?", command)
            if m:
                amount = int(m.group(1))
                target = current + amount if command.startswith("increase") else current - amount
            elif command in {"increase brightness", "brightness up", "brighter", "turn brightness up"}:
                target = current + 10
            elif command in {"decrease brightness", "brightness down", "dimmer", "turn brightness down"}:
                target = current - 10
            else:
                return "Unsupported brightness command.", False
        target = max(0, min(100, target))
        sbc.set_brightness(target, display=0)
        return f"Screen brightness set to {target}%.", True
    except Exception:
        return "Brightness control is unsupported by this display or driver, or permission was denied.", False


def toggle_adapter(kind: str, enable: bool) -> tuple[str, bool]:
    if os.name != "nt":
        return f"{kind} controls are only supported on Windows.", False
    if kind == "Wi-Fi":
        script = r"""
$a = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'Wi-Fi|WiFi|Wireless' -or $_.InterfaceDescription -match 'Wireless|Wi-Fi' } | Select-Object -First 1
if ($null -eq $a) { Write-Output 'FLX_NO_ADAPTER'; exit 3 }
try { ACTION -Name $a.Name -Confirm:$false -ErrorAction Stop; Start-Sleep -Milliseconds 500; $v = Get-NetAdapter -Name $a.Name; if ((EXPECTED)) { Write-Output 'FLX_OK' } else { Write-Output 'FLX_NOT_CHANGED'; exit 4 } } catch { Write-Output 'FLX_DENIED'; exit 5 }
"""
        action = "Enable-NetAdapter" if enable else "Disable-NetAdapter"
        expected = "$v.Status -eq 'Up'" if enable else "$v.Status -ne 'Up'"
        script = script.replace("ACTION", action).replace("(EXPECTED)", expected)
    else:
        # Restrict selection to likely Bluetooth radio/adapter entries, not paired peripherals.
        script = r"""
$a = Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | Where-Object { $_.FriendlyName -match 'Bluetooth.*(Adapter|Radio)|(Adapter|Radio).*Bluetooth' } | Select-Object -First 1
if ($null -eq $a) { Write-Output 'FLX_NO_ADAPTER'; exit 3 }
try { ACTION -InstanceId $a.InstanceId -ErrorAction Stop; Start-Sleep -Milliseconds 700; $v = Get-PnpDevice -InstanceId $a.InstanceId; if ((EXPECTED)) { Write-Output 'FLX_OK' } else { Write-Output 'FLX_NOT_CHANGED'; exit 4 } } catch { Write-Output 'FLX_DENIED'; exit 5 }
"""
        action = "Enable-PnpDevice" if enable else "Disable-PnpDevice"
        expected = "$v.Status -eq 'OK'" if enable else "$v.Status -ne 'OK'"
        script = script.replace("ACTION", action).replace("(EXPECTED)", expected)
    try:
        run = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                             capture_output=True, text=True, timeout=20)
        output = (run.stdout + "\n" + run.stderr).upper()
        if run.returncode == 0 and "FLX_OK" in output:
            return f"{kind} adapter {'enabled' if enable else 'disabled'}.", True
        if "FLX_NO_ADAPTER" in output:
            return f"Couldn't find a suitable {kind} adapter.", False
        if "FLX_DENIED" in output or "ACCESS IS DENIED" in output or "ADMINISTRATOR" in output:
            return f"Windows denied the {kind} change. Try running the companion with suitable permissions.", False
        return f"Windows couldn't confirm that the {kind} adapter was {'enabled' if enable else 'disabled'}. Check Windows permissions and adapter support.", False
    except Exception:
        return f"Couldn't control {kind}. PowerShell or the adapter may be unavailable.", False


def safe_calculate(expression: str):
    expression = expression.strip().replace("^", "**")
    if not expression or len(expression) > 100:
        raise ValueError("Enter a short arithmetic expression.")
    tree = ast.parse(expression, mode="eval")
    def visit(node):
        if isinstance(node, ast.Expression): return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float): return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in SAFE_OPERATORS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 8: raise ValueError("Exponent is too large.")
            value = SAFE_OPERATORS[type(node.op)](left, right)
            if abs(value) > 1e100: raise ValueError("Result is too large.")
            return value
        if isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_OPERATORS:
            return SAFE_OPERATORS[type(node.op)](visit(node.operand))
        raise ValueError("Use numbers and basic operators only.")
    return visit(tree)


def system_information(command: str) -> tuple[str, bool]:
    try:
        import psutil
        if command in {"show battery", "battery status"}:
            battery = psutil.sensors_battery()
            if battery is None: return "Battery information is unavailable; this PC may not have a battery.", False
            state = "charging" if battery.power_plugged else "not charging"
            return f"Battery: {battery.percent:.0f}% ({state}).", True
        if command == "show cpu usage":
            return f"CPU usage: {psutil.cpu_percent(interval=0.5):.1f}%.", True
        if command in {"show memory usage", "show ram usage"}:
            m = psutil.virtual_memory()
            return f"RAM usage: {m.percent:.1f}% ({m.used / (1024**3):.1f} GB used of {m.total / (1024**3):.1f} GB).", True
        if command == "show disk space":
            root = os.environ.get("SystemDrive", "C:") + "\\"
            d = psutil.disk_usage(root)
            return f"Disk space ({root}): {d.free / (1024**3):.1f} GB free of {d.total / (1024**3):.1f} GB ({d.percent:.1f}% used).", True
        if command == "show running processes":
            names = []
            for proc in psutil.process_iter(["name"]):
                try:
                    name = proc.info.get("name")
                    if name: names.append(name)
                except (psutil.NoSuchProcess, psutil.AccessDenied): pass
            names = sorted(set(names), key=str.lower)
            if not names: return "No process names could be retrieved.", False
            return "Running processes (sample):\n" + "\n".join(names[:35]) + (f"\n…and {len(names)-35} more." if len(names) > 35 else ""), True
        if command == "show network status":
            stats = psutil.net_if_stats()
            lines = [f"{name}: {'connected' if info.isup else 'disconnected'}" for name, info in stats.items()]
            if not lines: return "Network status is unavailable.", False
            return "Network status:\n" + "\n".join(lines[:20]), True
        if command == "show system information":
            import platform
            return f"System: {platform.system()} {platform.release()}\nComputer: {platform.node()}\nProcessor: {platform.processor() or 'Not reported'}\nCPU cores: {psutil.cpu_count(logical=False) or '?'} physical / {psutil.cpu_count(logical=True) or '?'} logical\nRAM: {psutil.virtual_memory().total / (1024**3):.1f} GB.", True
    except Exception:
        return "Couldn't retrieve that system information. Check that psutil is installed and permissions allow access.", False
    return "Unsupported system-information command.", False


def clipboard_read() -> tuple[str, bool]:
    try:
        import tkinter as tk
        root = tk.Tk(); root.withdraw()
        try: value = root.clipboard_get()
        finally: root.destroy()
        if not value: return "The clipboard is empty.", True
        return "Clipboard text:\n" + value[:4000], True
    except Exception:
        return "Couldn't read text from the clipboard. Make sure a Windows desktop session is available.", False


def clipboard_write(text: str) -> tuple[str, bool]:
    try:
        import tkinter as tk
        root = tk.Tk(); root.withdraw(); root.clipboard_clear(); root.clipboard_append(text); root.update(); root.destroy()
        return "Text copied to the clipboard.", True
    except Exception:
        return "Couldn't write to the clipboard. Make sure a Windows desktop session is available.", False


def screenshot() -> tuple[str, bool]:
    try:
        import pyautogui
        folder = Path.home() / "Pictures" / "FLX.AI Screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / ("Screenshot_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".png")
        pyautogui.screenshot().save(str(path))
        if not path.exists() or path.stat().st_size == 0: return "Screenshot could not be verified after saving.", False
        return f"Screenshot saved to {path}.", True
    except Exception:
        return "Couldn't capture a screenshot. Check that pyautogui and desktop permissions are available.", False


def process_command(raw: str, confirmed: bool = False) -> dict:
    original = (raw or "").strip()
    if not original:
        return result("Please type or speak a command.", False, original)
    if len(original) > 500:
        return result("Please keep commands under 500 characters.", False, original)
    command = normalize(original)

    # 1. Google search: only the explicit leading word "search" triggers a search.
    m = re.match(r"^search\b(.*)$", original, re.I)
    if m:
        query = m.group(1).strip()
        if not query: return result("Enter a search query after 'search'.", False, original)
        try:
            url = "https://www.google.com/search?q=" + quote_plus(query)
            if webbrowser.open(url, new=2): return result(f"Searching Google for: {query}", True, original)
            return result("Couldn't open Google Search in your default browser.", False, original)
        except Exception:
            return result("Couldn't open Google Search in your default browser.", False, original)

    # 2. Open commands: applications, websites and folders are resolved separately.
    if command.startswith("open "):
        target = command[5:].strip()
        if target in WEBSITES: 
            msg, ok = open_website(target); return result(msg, ok, original)
        if target in APP_TARGETS:
            msg, ok = launch(*APP_TARGETS[target]); return result(msg, ok, original)
        if target in FOLDER_ALIASES:
            msg, ok = open_folder(FOLDER_ALIASES[target]); return result(msg, ok, original)
        m = re.fullmatch(r"folder\s+(.+)", target)
        if m:
            path_text = original.strip()[len("open folder"):].strip().strip('"')
            try:
                path = Path(os.path.expandvars(os.path.expanduser(path_text))).resolve(strict=True)
                if not path.is_dir(): return result("The specified path exists but is not a folder.", False, original)
                os.startfile(str(path)); return result(f"Opened folder: {path}", True, original)
            except Exception:
                return result("Couldn't open that folder. Check the path and make sure the folder exists.", False, original)
        return result("Unknown application, website, or folder. No search was performed.", False, original)

    # 3. Volume controls, with exact target/amount matching before generic adjustments.
    if command in {"mute", "mute volume", "unmute", "unmute volume", "mute audio", "unmute audio"} or \
       command in {"increase volume", "volume up", "volume increase", "louder", "turn volume up", "decrease volume", "volume down", "volume decrease", "quieter", "turn volume down"} or \
       re.fullmatch(r"(?:set volume to|(?:increase|decrease) volume by) \d{1,3}(?:\s*(?:%|percent))?", command):
        msg, ok = set_volume(command); return result(msg, ok, original)

    # 4. Brightness controls.
    if command in {"increase brightness", "brightness up", "brighter", "turn brightness up", "decrease brightness", "brightness down", "dimmer", "turn brightness down"} or \
       re.fullmatch(r"(?:set brightness to|(?:increase|decrease) brightness by) \d{1,3}(?:\s*(?:%|percent))?", command):
        msg, ok = set_brightness(command); return result(msg, ok, original)

    # 5. Wi-Fi.
    if command in {"turn wifi on", "turn wifi off", "turn wi fi on", "turn wi fi off", "enable wifi", "disable wifi", "wifi on", "wifi off", "enable wireless", "disable wireless", "enable wi fi", "disable wi fi"}:
        enable = command in {"turn wifi on", "turn wi fi on", "enable wifi", "wifi on", "enable wireless", "enable wi fi"}
        msg, ok = toggle_adapter("Wi-Fi", enable); return result(msg, ok, original)

    # 6. Bluetooth.
    if command in {"turn bluetooth on", "turn bluetooth off", "enable bluetooth", "disable bluetooth", "bluetooth on", "bluetooth off"}:
        enable = command in {"turn bluetooth on", "enable bluetooth", "bluetooth on"}
        msg, ok = toggle_adapter("Bluetooth", enable); return result(msg, ok, original)

    # 7. Lock and power commands. Shutdown/restart are always confirmation-gated.
    if command in {"lock computer", "lock pc"}:
        try:
            if ctypes.windll.user32.LockWorkStation(): return result("Windows session locked.", True, original)
            return result("Windows couldn't lock the session.", False, original)
        except Exception: return result("Locking the Windows session failed.", False, original)
    if command in {"sleep computer", "sleep pc"}:
        try:
            subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], shell=False)
            return result("Sleep request sent to Windows.", True, original)
        except Exception: return result("Windows couldn't enter sleep mode.", False, original)
    if command in {"shut down computer", "shutdown computer", "restart computer"}:
        if not confirmed:
            action = "shut down" if command != "restart computer" else "restart"
            return result(f"Please confirm: do you want to {action} this computer?", False, original, True)
        try:
            args = ["shutdown.exe", "/s", "/t", "0"] if command != "restart computer" else ["shutdown.exe", "/r", "/t", "0"]
            subprocess.Popen(args, shell=False)
            return result("Windows accepted the shutdown/restart request.", True, original)
        except Exception: return result("Windows couldn't start the requested power action.", False, original)
    if command == "cancel shutdown":
        try:
            p = subprocess.run(["shutdown.exe", "/a"], capture_output=True, text=True, timeout=5)
            if p.returncode == 0: return result("Pending shutdown cancelled.", True, original)
            return result("Windows reported no cancellable shutdown, or cancellation was denied.", False, original)
        except Exception: return result("Couldn't cancel the pending shutdown.", False, original)

    # 8. Folders are also supported through "open <folder>" above.

    # 9. Media controls use Windows media keys. They send a key event; they cannot guarantee an app starts music.
    media_keys = {
        "play pause": "playpause", "pause music": "playpause", "resume music": "playpause",
        "next track": "nexttrack", "previous track": "prevtrack",
    }
    if command in media_keys:
        try:
            import pyautogui
            pyautogui.press(media_keys[command])
            return result("Media-control key sent to Windows. Playback depends on the active media app.", True, original)
        except Exception: return result("Couldn't send the media-control key. Check pyautogui and desktop permissions.", False, original)

    # 10. System information.
    if command in {"show battery", "battery status", "show system information", "show cpu usage", "show memory usage", "show ram usage", "show disk space", "show running processes", "show network status"}:
        msg, ok = system_information(command); return result(msg, ok, original)

    # 11. Screenshot and clipboard.
    if command == "take screenshot":
        msg, ok = screenshot(); return result(msg, ok, original)
    if command == "copy clipboard":
        msg, ok = clipboard_read(); return result(msg, ok, original)
    if command == "clear clipboard":
        if not confirmed: return result("Please confirm that you want to clear the clipboard.", False, original, True)
        msg, ok = clipboard_write(""); return result("Clipboard cleared." if ok else msg, ok, original)
    if command.startswith("copy text "):
        text_to_copy = original[len("copy text "):]
        if not text_to_copy.strip(): return result("Enter the text to copy after 'copy text'.", False, original)
        msg, ok = clipboard_write(text_to_copy); return result(msg, ok, original)
    if command == "copy text": return result("Enter the text to copy after 'copy text'.", False, original)

    # Preserve existing local utility functionality without sending unknown commands to a search engine or AI.
    if command in {"what time", "current time", "tell me the time", "time now"}:
        return result("Local time: " + datetime.now().astimezone().strftime("%I:%M %p"), True, original)
    if command in {"today's date", "todays date", "what date", "current date", "date today"}:
        return result("Local date: " + datetime.now().astimezone().strftime("%A, %d %B %Y"), True, original)
    expression = None
    for prefix in ("calculate ", "compute ", "what is ", "what's "):
        if command.startswith(prefix): expression = command[len(prefix):].strip().rstrip("?"); break
    if expression is None and re.fullmatch(r"[\d\s.+\-*/()%^]+", command): expression = command
    if expression is not None:
        try:
            value = safe_calculate(expression)
            if isinstance(value, float) and value.is_integer(): value = int(value)
            return result(f"{expression} = {value}", True, original)
        except Exception as exc: return result(f"I couldn't calculate that: {exc}", False, original)

    if command in {"help", "commands", "what can you do", "show commands"}:
        return result("Try: search Python tutorials; open Chrome, YouTube, Calculator, Google Classroom or Downloads; set volume to 50; increase brightness; turn Wi-Fi off; turn Bluetooth on; lock PC; take screenshot; show battery; copy text hello.", True, original)

    return result("Command not supported. Please enter a valid FLX.AI command.", False, original)


@APP.get("/health")
def health():
    return jsonify({"ok": True, "app": "FLX.AI Windows Companion", "version": "4.0"})


@APP.route("/command", methods=["POST", "OPTIONS"])
def command_route():
    if request.method == "OPTIONS": return "", 204
    payload = request.get_json(silent=True) or {}
    raw = str(payload.get("command", ""))
    confirmed = payload.get("confirmed") is True
    data = process_command(raw, confirmed=confirmed)
    return jsonify(data), (200 if data["success"] or data.get("confirmation_required") else 400)


def open_page():
    time.sleep(1.2)
    try: webbrowser.open("https://flx-ai-demo.onrender.com")
    except Exception: pass


if __name__ == "__main__":
    print("FLX.AI Windows Companion v4 running. Health: http://127.0.0.1:8765/health")
    threading.Thread(target=open_page, daemon=True).start()
    APP.run(host="127.0.0.1", port=8765, debug=False, threaded=True)
