# llm_engine.py
import ollama


class LocalLLM:
    def __init__(self, model_name: str = "qwen2.5:1.5b"):
        self.model_name = model_name
        print(f"[*] Initializing connection to Local LLM ({self.model_name})...")
        try:
            ollama.list()
            print("[+] Ollama connection established successfully.")
        except Exception as e:
            print(
                f"[!] Warning: Make sure Ollama app is running in the background: {e}"
            )

    def ask(self, prompt: str) -> str:
        """
        ارسال ورودی کاربر به مدل محلی و دریافت پاسخ مناسب خروجی صوتی (Concise & Voice-ready)
        """
        system_instruction = (
            "You are Jarvis, an offline voice assistant on Windows 11. "
            "Answer the question directly, clearly, and concisely in 1 to 2 short sentences. "
            "Do NOT use markdown, emojis, asterisks, bullet points, or code snippets. "
            "Output plain natural conversational English."
        )

        try:
            # استفاده از stream=True برای مشاهده آنی توکن‌ها بدون قفل شدن
            response_stream = ollama.chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                options={
                    "temperature": 0.5,
                    "num_predict": 60,
                },
                stream=True,
            )

            full_response = []
            for chunk in response_stream:
                token = chunk["message"]["content"]
                print(token, end="", flush=True)  # نمایش کلمه به کلمه در ترمینال
                full_response.append(token)

            print()  # خط جدید
            return "".join(full_response).strip()

        except Exception as err:
            print(f"\n[LLM Error]: {err}")
            return "Sorry, I could not process that request."


if __name__ == "__main__":
    llm = LocalLLM()
    test_question = "What is RAM in computer architecture?"
    print(f"\nUser: {test_question}\nThinking...", flush=True)
    answer = llm.ask(test_question)
