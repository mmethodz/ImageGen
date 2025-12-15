# Gemini ImageGen

Simple windowed desktop app that uses a Gemini-like API to generate images from a user prompt and display them with a "Save as PNG" option. The UI uses a dark theme and scales the displayed image to the window.

Prerequisites
- Python 3.11+
- Install dependencies from `requirements.txt` (see below)
- Optionally set `GEMINI_API_KEY` and `GEMINI_ENDPOINT` environment variables for a real API.

Install

Open PowerShell and run:

```powershell
python -m pip install -r requirements.txt
```

Running

To run the app:

```powershell
# From the project folder
python main.py
```

Environment variables (optional)

- `GEMINI_API_KEY` : Your API key (if omitted, the app shows a placeholder image locally).
- `GEMINI_ENDPOINT` : The image generation endpoint (defaults to a placeholder URL in `api.py`).

PowerShell example to set the key for the session:

```powershell
$env:GEMINI_API_KEY = "YOUR_KEY_HERE"
python main.py
```

Notes for integrating a real Gemini endpoint

The `api.generate_image` function shows how to send a JSON payload with a `prompt` field and handles two common response shapes:
- `image_base64` (base64 string containing image bytes) or
- `image_url` (URL pointing to the generated image)

Adjust `api.py` to match the exact Gemini request and response format your account expects.

Files
- `main.py` — app entry
- `gui.py` — Qt UI and threading
- `api.py` — Gemini adapter + placeholder image generator
- `requirements.txt` — dependencies
