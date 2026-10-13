# system_actions.py
import os
import glob
import subprocess
import pyautogui
import psutil
import pyperclip
import comtypes
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from rapidfuzz import process, fuzz
import win32com.client
import time


class WindowsController:
    def __init__(self):
        # مقداردهی اولیه COM برای Thread جاری
        comtypes.CoInitialize()

        # کنترل صدا
        device = AudioUtilities.GetSpeakers()
        if hasattr(device, "_dev"):
            device = device._dev

        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        self.volume = cast(interface, POINTER(IAudioEndpointVolume))

        # ایندکس کردن خودکار تمام نرم‌افزارهای نصب‌شده
        self.apps_cache = {}
        self._index_installed_apps()

    def _index_installed_apps(self):
        """اسکن منوی استارت ویندوز برای کش کردن مسیر تمام برنامه‌ها"""
        print("[*] Indexing installed applications for Dynamic Launch...")
        shell = win32com.client.Dispatch("WScript.Shell")

        # مسیرهای اصلی منوی استارت در ویندوز ۱۱
        start_menu_paths = [
            os.path.join(
                os.environ.get("ProgramData", "C:\\ProgramData"),
                "Microsoft\\Windows\\Start Menu\\Programs",
            ),
            os.path.join(
                os.environ.get("APPDATA", ""),
                "Microsoft\\Windows\\Start Menu\\Programs",
            ),
        ]

        for base_path in start_menu_paths:
            if not os.path.exists(base_path):
                continue

            # جستجوی تمام میانبرهای .lnk
            for lnk_file in glob.glob(
                os.path.join(base_path, "**", "*.lnk"), recursive=True
            ):
                app_name = os.path.splitext(os.path.basename(lnk_file))[0].lower()

                # نادیده گرفتن شورت‌کات‌های متفرقه مانند Uninstall یا Readme
                if "uninstall" in app_name or "help" in app_name:
                    continue

                try:
                    shortcut = shell.CreateShortCut(lnk_file)
                    target_path = shortcut.Targetpath

                    # ذخیره فایل‌های اجرایی
                    if target_path and target_path.lower().endswith(".exe"):
                        self.apps_cache[app_name] = target_path
                    else:
                        # در صورت اپ‌های مدرن استور (UWP)، خود فایل lnk قابل اجراست
                        self.apps_cache[app_name] = lnk_file
                except Exception:
                    continue

        print(f"[+] Successfully indexed {len(self.apps_cache)} applications!")

    def open_app_dynamic(self, query):
        """یافتن و اجرای نرم‌افزار بر اساس نام با تطبیق فازی"""
        # پاکسازی کاراکترهای اضافه مانند نقطه در انتهای جمله whisper
        query = query.strip().lower().rstrip(".")
        if not query:
            return False, "No app name provided."

        # نرمال‌سازی کلماتی مثل note pad به notepad
        normalized_query = query.replace(" ", "")

        # چک کردن دستورات خاص ویندوزی
        common_aliases = {
            "cmd": "cmd.exe",
            "terminal": "wt.exe",
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "explorer": "explorer.exe",
            "settings": "ms-settings:",
        }
        if query in common_aliases:
            try:
                os.startfile(common_aliases[query])
                return True, f"Opening {query}"
            except Exception as e:
                return False, f"Failed: {e}"

        if normalized_query in common_aliases:
            try:
                os.startfile(common_aliases[normalized_query])
                return True, f"Opening {normalized_query}"
            except Exception as e:
                return False, f"Failed: {e}"

        # جستجوی فازی بین برنامه‌های کش‌شده
        match = process.extractOne(
            query, list(self.apps_cache.keys()), scorer=fuzz.token_set_ratio
        )

        if match and match[1] >= 65:  # حد آستانه شباهت نام
            matched_app_name = match[0]
            target_path = self.apps_cache[matched_app_name]
            try:
                os.startfile(target_path)
                return True, f"Opening {matched_app_name}"
            except Exception as e:
                return False, f"Failed to launch: {e}"

        # اگر در کش نبود، تلاش مستقیم از طریق ویندوز Run
        try:
            os.startfile(f"{query}.exe")
            return True, f"Attempting to launch {query}"
        except Exception:
            return False, f"Application {query} not found."

    def close_app_dynamic(self, query):
        """بستن هوشمند نرم‌افزار بر اساس نام پردازه یا نام برنامه"""
        query = query.strip().lower().rstrip(".")
        closed = False

        for proc in psutil.process_iter(["name"]):
            try:
                proc_name = proc.info["name"].lower()
                if query in proc_name or fuzz.partial_ratio(query, proc_name) > 85:
                    proc.kill()
                    closed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if closed:
            return True, f"Closed {query}"
        return False, f"Could not find running process for {query}"

    # ----------------- متدهای سازگاری (Aliases برای main.py) -----------------
    def open_application(self, query: str) -> bool:
        success, _ = self.open_app_dynamic(query)
        return success

    def close_application(self, query: str) -> bool:
        success, _ = self.close_app_dynamic(query)
        return success

    def mute(self):
        self.volume.SetMute(1, None)

    def unmute(self):
        self.volume.SetMute(0, None)

    def volume_up(self):
        self.change_volume(0.1)

    def volume_down(self):
        self.change_volume(-0.1)

    # ----------------- سایر متدها -----------------
    def paste_text(self, text):
        old_clipboard = pyperclip.paste()
        try:
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
        finally:
            pyautogui.sleep(0.05)
            pyperclip.copy(old_clipboard)

    def set_volume(self, level):
        level = max(0.0, min(1.0, level))
        self.volume.SetMasterVolumeLevelScalar(level, None)

    def change_volume(self, delta):
        current = self.volume.GetMasterVolumeLevelScalar()
        self.set_volume(current + delta)

    def toggle_mute(self):
        current_mute = self.volume.GetMute()
        self.volume.SetMute(not current_mute, None)

    def take_screenshot(self):
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        filepath = os.path.join(desktop, "assistant_screenshot.png")
        pyautogui.screenshot(filepath)

    def lock_pc(self):
        subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)

    def close_active_window(self):
        pyautogui.hotkey("alt", "f4")

    def get_system_status(self) -> str:
        """بررسی پارامترهای تلمتری سیستم: لود پردازنده، رم آزاد و وضعیت باتری/دیسک"""
        # دریافت درصد لود CPU (با بازه نمونه‌برداری کوتاه‌مدت)
        cpu_usage = psutil.cpu_percent(interval=0.1)

        # دریافت اطلاعات رم
        ram = psutil.virtual_memory()
        ram_percent = ram.percent
        # محاسبه حافظه آزاد به گیگابایت
        free_ram_gb = round(ram.available / (1024**3), 1)

        # گزارش خلاصه و روان برای خواندن صوتی
        status_report = (
            f"CPU load is at {int(cpu_usage)} percent. "
            f"Memory usage is {int(ram_percent)} percent, "
            f"with {free_ram_gb} gigabytes of RAM available."
        )

        # اگر لپ‌تاپ باشد، درصد باتری را هم اضافه می‌کنیم
        battery = psutil.sensors_battery()
        if battery:
            status_report += f" Battery is at {int(battery.percent)} percent."

        return status_report

    def open_notepad(self):
        """باز کردن برنامه نوت‌پد در ویندوز"""
        try:
            subprocess.Popen(["notepad.exe"])
            return "Notepad opened."
        except Exception as e:
            return f"Failed to open notepad: {e}"

    def type_text(self, text: str):
        """تایپ قطعی و بدون تداخل منو در Notepad یا پنجره فعال"""
        try:
            import win32gui
            import win32con

            # پیدا کردن هندل پنجره نوت‌پد
            hwnd = win32gui.FindWindow("Notepad", None)
            if hwnd == 0:

                def enum_cb(h, extra):
                    if "notepad" in win32gui.GetWindowText(h).lower():
                        extra.append(h)

                windows = []
                win32gui.EnumWindows(enum_cb, windows)
                if windows:
                    hwnd = windows[0]

            if hwnd != 0:
                # بالا آوردن پنجره نوت‌پد به صورت تمیز
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.2)

                # پیدا کردن مختصات پنجره و کلیک در بدنه متنی برای اطمینان از خروج از منو
                rect = win32gui.GetWindowRect(hwnd)
                x = rect[0] + 150
                y = rect[1] + 150
                pyautogui.click(x, y)
                time.sleep(0.1)
            else:
                # اگر نوت‌پد باز نیست ابتدا باز شود
                self.open_notepad()
                time.sleep(0.8)

            # مطمئن شدن از آزاد بودن کلید Alt (در صورت گیر کردن احتمالی)
            pyautogui.keyUp("alt")

            # کپی در کلیپ‌بورد و پیست آنی
            pyperclip.copy(text)
            time.sleep(0.1)
            pyautogui.hotkey("ctrl", "v")
            return f"Typed: {text}"

        except Exception as e:
            # فال‌بک
            pyautogui.keyUp("alt")
            pyperclip.copy(text)
            time.sleep(0.1)
            pyautogui.hotkey("ctrl", "v")
            return f"Direct typed: {e}"

    def new_browser_tab(self):
        """باز کردن تب جدید در مرورگر فعال با میانبر Ctrl + T"""
        try:
            time.sleep(0.5)
            pyautogui.hotkey("ctrl", "t")
            return "New browser tab opened."
        except Exception as e:
            return f"Failed to open new tab: {e}"
