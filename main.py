import os
import sys
import queue
import time
import numpy as np

# غیرفعال کردن هشدار symlink هاگینگ‌فیس در ویندوز
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import sounddevice as sd
import openwakeword
from openwakeword.model import Model
from faster_whisper import WhisperModel
import pyttsx3

from system_actions import WindowsController
from llm_engine import LocalLLM

# ----------------- تنظیمات صوتی -----------------
SAMPLE_RATE = 16000
CHUNK_SIZE = 1280  # فریم استریم ۸۰ میلی‌ثانیه‌ای برای openWakeWord
audio_queue = queue.Queue()

# راهنمای لغات برای ویسپر
WHISPER_PROMPT = "Jarvis, open notepad, new tab, mute, unmute, volume up, volume down, system status, type, write, dictation."


# ----------------- راه‌اندازی TTS (سنتز گفتار) -----------------
def speak(text: str):
    """پخش خروجی صوتی دستیار با رفع مشکل قفل شدن SAPI5 در ویندوز"""
    print(f"[Assistant]: {text}")
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 185)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
        del engine
    except Exception as e:
        print(f"[!] TTS Error: {e}", file=sys.stderr)


# ----------------- Callback ورودی میکروفون -----------------
def audio_callback(indata, frames, time_info, status):
    if status:
        print(f"[!] Audio stream status: {status}", file=sys.stderr)
    audio_queue.put(indata.copy())


def flush_audio_queue():
    """تخلیه کامل بافر صدای قدیمی برای جلوگیری از تاخیر"""
    while not audio_queue.empty():
        try:
            audio_queue.get_nowait()
        except queue.Empty:
            break


# ----------------- ضبط فرمان صوتی کاربر -----------------
def record_command(whisper_model, duration_seconds=4.0):
    """شنیدن صدای کاربر با اعمال فیلترهای پیشرفته DC-Offset و Peak Normalization"""
    time.sleep(0.1)
    flush_audio_queue()

    frames = []
    total_chunks = int((SAMPLE_RATE * duration_seconds) / CHUNK_SIZE)

    print("[*] Listening for command or question... (Speak now)")
    for _ in range(total_chunks):
        chunk = audio_queue.get()
        frames.append(chunk)

    # ۱. تبدیل بایت‌های خام به آرایه float32 در بازه [-1.0, 1.0]
    raw_audio = np.concatenate(frames, axis=0).flatten()
    audio_float32 = raw_audio.astype(np.float32) / 32768.0

    # ۲. فیلتر حذف DC Offset (تراز کردن موج صدا روی خط مبنای صفر)
    audio_centered = audio_float32 - np.mean(audio_float32)

    # ۳. فیلتر Peak Normalization (افزایش هوشمند ولوم صدا تا سقف استاندارد 0.95)
    max_peak = np.max(np.abs(audio_centered))
    if max_peak > 0.02:  # فقط در صورتی که صدا تولید شده باشد نرمال کن
        audio_normalized = audio_centered * (0.95 / max_peak)
    else:
        audio_normalized = audio_centered

    # ۴. فراخوانی بهینه ویسپر با تنظیمات طلایی دستیار صوتی (خارج از بلوک else)
    segments, info = whisper_model.transcribe(
        audio_normalized,
        language="en",
        beam_size=2,
        best_of=2,
        temperature=0.0,
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
        compression_ratio_threshold=2.4,
        initial_prompt=WHISPER_PROMPT,
        vad_filter=True,
        vad_parameters=dict(
            threshold=0.5,
            min_speech_duration_ms=250,
            min_silence_duration_ms=400,
            speech_pad_ms=150,
        ),
    )

    text = " ".join([seg.text for seg in segments]).strip()
    return text


# ----------------- حلقه اصلی اجرای برنامه -----------------
def main():
    print("=" * 60)
    print("      Starting Windows 11 Offline Voice Assistant      ")
    print("=" * 60)

    # ۱. بارگذاری Wake Word
    print("[*] Loading Wake Word Engine (openWakeWord)...")
    openwakeword.utils.download_models()
    wake_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

    # ۲. بارگذاری ویسپر
    print("[*] Loading STT Engine (faster-whisper: base.en)...")
    whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")

    # ۳. لود کنترلر ویندوز
    print("[*] Initializing Windows Controller...")
    controller = WindowsController()

    # ۴. لود موتور لوکال LLM
    print("[*] Initializing Local LLM (Ollama)...")
    llm = LocalLLM()

    # ۵. راه‌اندازی استریم صدا
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=CHUNK_SIZE,
        callback=audio_callback,
    )

    print("\n[✓] Assistant is ready and listening! Say 'Hey Jarvis'...\n")
    speak("System is online.")

    with stream:
        while True:
            audio_frame = audio_queue.get()
            flat_frame = audio_frame.flatten()

            prediction = wake_model.predict(flat_frame)
            score = wake_model.prediction_buffer["hey_jarvis"][-1]

            if score > 0.55:
                print(f"\n[!] Wake Word Detected! (Confidence: {score:.2f})")
                speak("Yes?")

                command = record_command(whisper_model, duration_seconds=4.0)
                print(f"[User Said]: '{command}'")

                if not command or len(command.strip()) == 0:
                    print("[!] No clear speech detected.")
                    continue

                # تمیزکاری متن برای تشخیص دقیق الگوها
                command_clean = (
                    command.lower()
                    .replace(",", "")
                    .replace(".", "")
                    .replace("?", "")
                    .replace("!", "")
                    .strip()
                )

                # ================= Intent Routing Logic =================

                # ۱. دستور تایپ مستقیم متن
                if (
                    command_clean.startswith("type ")
                    or command_clean.startswith("write ")
                    or "type that" in command_clean
                ):
                    if command_clean.startswith("type "):
                        text_to_type = command_clean[5:].strip()
                    elif command_clean.startswith("write "):
                        text_to_type = command_clean[6:].strip()
                    else:
                        text_to_type = command_clean.replace("type that", "").strip()

                    for suffix in [" in notepad", " into notepad", " on notepad"]:
                        if text_to_type.endswith(suffix):
                            text_to_type = text_to_type[: -len(suffix)].strip()

                    if text_to_type:
                        speak(f"Typing: {text_to_type}")
                        controller.type_text(text_to_type)
                    else:
                        speak("What would you like me to type?")

                # ۲. باز کردن نوت‌پد
                elif "notepad" in command_clean or "note pad" in command_clean:
                    speak("Opening Notepad.")
                    controller.open_notepad()

                # ۳. تب جدید مرورگر
                elif "new tab" in command_clean or "another tab" in command_clean:
                    speak("Opening new tab.")
                    controller.new_browser_tab()

                # ۴. حالت دیکته پیوسته
                elif "dictation" in command_clean or "start typing" in command_clean:
                    speak("Dictation mode started. Say stop dictation when done.")
                    while True:
                        dictated = record_command(whisper_model, duration_seconds=4.5)
                        if not dictated:
                            continue
                        dict_clean = (
                            dictated.lower().replace(".", "").replace(",", "").strip()
                        )
                        print(f"[Dictating]: {dictated}")
                        if (
                            "stop dictation" in dict_clean
                            or "exit dictation" in dict_clean
                        ):
                            speak("Dictation stopped.")
                            break
                        controller.type_text(dictated + " ")

                # ۵. دستورات کنترل صدا
                elif "unmute" in command_clean:
                    controller.unmute()
                    speak("Unmuted.")
                elif "mute" in command_clean:
                    controller.mute()
                    speak("Muted.")
                elif "volume up" in command_clean or "increase volume" in command_clean:
                    controller.volume_up()
                    speak("Volume increased.")
                elif (
                    "volume down" in command_clean or "decrease volume" in command_clean
                ):
                    controller.volume_down()
                    speak("Volume decreased.")

                # ۶. گزارش وضعیت سیستم
                elif any(
                    k in command_clean for k in ["status", "system state", "hardware"]
                ):
                    status_text = controller.get_system_status()
                    speak(status_text)

                # ۷. ارسال به هوش مصنوعی لوکال
                else:
                    print("[*] Routing to Local LLM...")
                    llm_response = llm.ask(command)
                    speak(llm_response)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Exiting assistant...")
