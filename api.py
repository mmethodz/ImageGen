import os
import io
from typing import Optional
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont


class BillingRequired(Exception):
    """Raised when the Imagen API requires a billed Google account."""
    pass


def generate_image(prompt: str, aspect_ratio: str = "1:1") -> Optional[bytes]:
    """
    Generate an image using Google Imagen API.

    Uses the GEMINI_API_KEY environment variable for authentication.
    Falls back to a local placeholder if the key is missing or the API call fails.
    
    Args:
        prompt: Text description of the image to generate.
        aspect_ratio: Aspect ratio as string (e.g., "1:1", "16:9", "9:16", "4:3", "3:4").
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        return _placeholder_image("(No GEMINI_API_KEY set)")

    try:
        # Configure the Gemini client (the client will read GEMINI_API_KEY if available)
        client = genai.Client(api_key=api_key)

        # Auto-discover image-capable models available to this API key
        candidate_models = []
        try:
            models = client.models.list()
            model_names = []
            for m in models:
                name = getattr(m, 'name', None) or getattr(m, 'model', None) or str(m)
                model_names.append(name)

            # Heuristic: choose models whose name mentions 'imagen' or 'image'
            for n in model_names:
                ln = n.lower()
                if 'imagen' in ln or ('gemini' in ln and 'image' in ln):
                    candidate_models.append(n)

            # Prioritize gemini-2.5-flash-image (most reliable, no billing required)
            preferred = 'models/gemini-2.5-flash-image'
            if preferred in candidate_models:
                candidate_models.insert(0, candidate_models.pop(candidate_models.index(preferred)))

        except Exception:
            # If discovery fails, fall back to known models
            pass

        # Determine which models to try: prefer detected candidate models, else fall back to known models
        if candidate_models:
            models_to_try = candidate_models
        else:
            models_to_try = [
                "models/gemini-2.5-flash-image",
                "models/imagen-4.0-generate-001",
                "models/imagen-4.0-fast-generate-001",
            ]

        for model in models_to_try:
            try:
                response = client.models.generate_images(
                    model=model,
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        aspect_ratio=aspect_ratio,
                    ),
                )

                if getattr(response, 'generated_images', None):
                    generated_image = response.generated_images[0]
                    image_bytes = None
                    
                    # Extract bytes: try image_bytes first (raw API bytes), then PIL Image fallback
                    if hasattr(generated_image, 'image') and hasattr(generated_image.image, 'image_bytes'):
                        image_bytes = generated_image.image.image_bytes
                    elif hasattr(generated_image, 'image') and hasattr(generated_image.image, 'save'):
                        bio = io.BytesIO()
                        generated_image.image.save(bio, format="PNG")
                        bio.seek(0)
                        image_bytes = bio.getvalue()
                    
                    if image_bytes:
                        return image_bytes
            except Exception as model_error:
                msg = str(model_error)
                if "billing" in msg.lower() or "billed" in msg.lower():
                    raise BillingRequired("Imagen requires a billed Google account. Enable billing in AI Studio.")
                continue

        # If all models failed, fall back to placeholder with informative text
        return _placeholder_image(f"No images generated for: {prompt[:40]} (check model access/billing)")

    except Exception as e:
        # If this is a billing-related signal, re-raise so the GUI can handle it
        if isinstance(e, BillingRequired):
            raise
        error_msg = str(e)[:100]
        return _placeholder_image(f"(API error: {error_msg})")



def _placeholder_image(text: str) -> bytes:
    w, h = 1024, 768
    img = Image.new("RGB", (w, h), color=(28, 28, 30))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font = ImageFont.load_default()

    margin = 20
    lines = _wrap_text(draw, text, font, w - 2 * margin)
    y = margin
    for line in lines:
        draw.text((margin, y), line, font=font, fill=(220, 220, 220))
        # compute line height in a way compatible with multiple Pillow versions
        _, line_h = _text_size(draw, line, font)
        y += line_h + 8

    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


def _wrap_text(draw: ImageDraw.Draw, text: str, font: ImageFont.ImageFont, max_width: int):
    words = text.split()
    lines = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        test_w, _ = _text_size(draw, test, font)
        if test_w <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _text_size(draw: ImageDraw.Draw, text: str, font: ImageFont.ImageFont):
    """Return (width, height) of text using available Pillow APIs.

    Tries multiple methods for compatibility across Pillow versions.
    """
    # Preferred: ImageDraw.textsize
    try:
        size = draw.textsize(text, font=font)
        return size
    except Exception:
        pass

    # Newer Pillow: ImageDraw.textbbox
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])
    except Exception:
        pass

    # Fallback to font methods
    try:
        size = font.getsize(text)
        return size
    except Exception:
        pass

    try:
        bbox = font.getbbox(text)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])
    except Exception:
        # Last resort: estimate
        return (len(text) * 7, 16)
