import requests
import json
import os

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def ask_llm(prompt, model="mistral"):
    """
    Sends a prompt to the LLM. 
    Uses Google Gemini if API key is present (Cloud mode), 
    otherwise falls back to local Ollama (Local mode).
    """
    # ── CLOUD MODE: USE GEMINI ──
    if GEMINI_API_KEY:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return data['candidates'][0]['content']['parts'][0]['text']
            else:
                print(f"Gemini API Error {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"Gemini Request Failed: {e}")

    # ── LOCAL MODE: USE OLLAMA ──
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True
    }
    try:
        full_response = ""
        with requests.post(OLLAMA_URL, json=payload, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    chunk = json.loads(line.decode("utf-8"))
                    full_response += chunk.get("response", "")
                    if chunk.get("done"):
                        break
        return full_response
    except Exception as e:
        print(f"Ollama API Error: {e}")
        return ""
