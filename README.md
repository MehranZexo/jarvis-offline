# 🎙️ Jarvis: Offline Windows Voice Assistant

یک دستیار صوتی لوکال و کاملاً آفلاین برای کنترل ویندوز ۱۱ و پاسخ‌دهی به دستورات کاربر با کمترین تاخیر (Low Latency).

---

## ⚡ ویژگی‌های کلیدی
- **کاملاً آفلاین و ایمن:** بدون ارسال هیچ‌گونه داده صوتی یا متنی به سرورهای خارجی.
- **تشخیص کلمه بیدارباش (Wake Word):** مبتنی بر فریم‌ورک سبک و دقیق `openWakeWord` (کلمه پیش‌فرض: *Hey Jarvis*).
- **تبدیل گفتار به متن (STT):** استفاده از موتور بهینه‌شده `faster-whisper`.
- **مغز متفکر هوش مصنوعی (LLM):** ادغام با مدل لوکال کوانتایز شده `Qwen 2.5` با فرمت GGUF.
- **کنترل هوشمند ویندوز:** تایپ سریع و دقیق در نوت‌پد و برنامه‌ها، باز کردن نرم‌افزارها، مدیریت تب‌ها و مانیتورینگ منابع سیستم (CPU/RAM).

---

## 📋 پیش‌نیازها

1. سیستم‌عامل **Windows 10 / 11**
2. نسخه **Python 3.10** یا بالاتر
3. ابزار خط‌فرمان Git

---

## 🚀 راهنمای نصب و راه‌اندازی

### ۱. کلون کردن ریپازیتوری
```bash
git clone https://github.com/MehranZexo/jarvis-offline.git
cd jarvis-offline

python -m venv venv
# در PowerShell ویندوز:
.\venv\Scripts\Activate.ps1
# یا در CMD:
.\venv\Scripts\activate.bat


pip install -r requirements.txt
