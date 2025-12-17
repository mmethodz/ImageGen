"""Image post-processing helpers.
Provides apply_edits_bytes(image_bytes, settings) which returns PNG bytes.
Attempts to use NumPy for a fast vignette; falls back to Pillow-only implementation.
"""
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import io

try:
    import numpy as np
    _HAS_NUMPY = True
except Exception:
    _HAS_NUMPY = False


def _pillow_vignette(img: Image.Image, vig: float) -> Image.Image:
    width, height = img.size
    vignette = Image.new('L', (width, height), 255)
    for y in range(height):
        for x in range(width):
            dx = (x - width / 2) / (width / 2)
            dy = (y - height / 2) / (height / 2)
            d = (dx * dx + dy * dy) ** 0.5
            val = 255 - int(255 * min(1.0, d * vig * 1.5))
            vignette.putpixel((x, y), max(0, min(255, val)))
    img.putalpha(vignette)
    background = Image.new('RGB', img.size, (0, 0, 0))
    background.paste(img, mask=img.split()[3])
    return background


def _numpy_vignette(img: Image.Image, vig: float) -> Image.Image:
    # img is RGB
    arr = np.asarray(img).astype(np.float32)
    h, w = arr.shape[:2]
    # normalized coordinates in range [-1,1]
    y = np.linspace(-1.0, 1.0, h)[:, None]
    x = np.linspace(-1.0, 1.0, w)[None, :]
    d = np.sqrt(x * x + y * y)
    # mask: 1 in center (larger untouched radius), decreased toward edges
    # increased from 0.5 to 0.65 for even larger untouched center area
    mask = 1.0 - np.clip((d - 0.65) * vig * 2.0, 0.0, 1.0)
    mask = mask[..., None]
    arr = arr * mask
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def apply_edits_bytes(image_bytes: bytes, settings: dict) -> bytes:
    """Apply filters and adjustments to image bytes and return PNG bytes.

    settings keys:
      - filter: name ('None','Grayscale','Sepia','Blur','Sharpen')
      - brightness: float (e.g., 1.0)
      - contrast: float
      - saturation: float
      - vignette: float (0.0-1.0)
      - sharpness: float (0.0-2.0, default 1.0 = no change)
    """
    bio = io.BytesIO(image_bytes)

    # For filters that are simple convolutions (Blur/Sharpen) we use PIL first,
    # otherwise prefer a fast NumPy pipeline for color math if available.
    filt = settings.get('filter', 'None')
    if filt in ('Blur', 'Sharpen'):
        img = Image.open(bio).convert('RGB')
        if filt == 'Blur':
            img = img.filter(ImageFilter.GaussianBlur(radius=2))
        else:
            img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
        # continue with numpy or pillow adjustments below using this img
    else:
        img = Image.open(bio).convert('RGB')

    bri = float(settings.get('brightness', 1.0))
    con = float(settings.get('contrast', 1.0))
    sat = float(settings.get('saturation', 1.0))
    vig = float(settings.get('vignette', 0.0))
    shp = float(settings.get('sharpness', 1.0))

    if _HAS_NUMPY:
        arr = np.asarray(img).astype(np.float32)

        # Grayscale
        if filt == 'Grayscale':
            gray = arr[..., 0] * 0.2989 + arr[..., 1] * 0.5870 + arr[..., 2] * 0.1140
            arr[..., 0] = gray
            arr[..., 1] = gray
            arr[..., 2] = gray
        # Sepia
        elif filt == 'Sepia':
            r = arr[..., 0].copy()
            g = arr[..., 1].copy()
            b = arr[..., 2].copy()
            tr = 0.393 * r + 0.769 * g + 0.189 * b
            tg = 0.349 * r + 0.686 * g + 0.168 * b
            tb = 0.272 * r + 0.534 * g + 0.131 * b
            arr[..., 0] = np.clip(tr, 0, 255)
            arr[..., 1] = np.clip(tg, 0, 255)
            arr[..., 2] = np.clip(tb, 0, 255)

        # Brightness (scale)
        if bri != 1.0:
            arr = arr * bri

        # Contrast: scale relative to midpoint 128
        if con != 1.0:
            arr = (arr - 128.0) * con + 128.0

        # Saturation: interpolate between gray and color
        if sat != 1.0:
            gray = arr[..., 0] * 0.2989 + arr[..., 1] * 0.5870 + arr[..., 2] * 0.1140
            gray = gray[..., None]
            arr = gray + (arr - gray) * sat

        # Vignette (use numpy method)
        if vig and vig > 0.0:
            h, w = arr.shape[:2]
            y = np.linspace(-1.0, 1.0, h)[:, None]
            x = np.linspace(-1.0, 1.0, w)[None, :]
            d = np.sqrt(x * x + y * y)
            mask = 1.0 - np.clip(d * vig * 1.5, 0.0, 1.0)
            mask = mask[..., None]
            arr = arr * mask

        arr = np.clip(arr, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)
    else:
        # Fallback to Pillow pipeline
        # Filters already applied for Blur/Sharpen; apply other filters
        if filt == 'Grayscale':
            img = ImageOps.grayscale(img).convert('RGB')
        elif filt == 'Sepia':
            img = ImageOps.colorize(ImageOps.grayscale(img), '#704214', '#C0A080')

        if bri != 1.0:
            img = ImageEnhance.Brightness(img).enhance(bri)
        if con != 1.0:
            img = ImageEnhance.Contrast(img).enhance(con)
        if sat != 1.0:
            img = ImageEnhance.Color(img).enhance(sat)

        if vig and vig > 0.0:
            try:
                img = _pillow_vignette(img, vig)
            except Exception:
                pass

    # Apply adjustable sharpness (1.0 = no change, <1.0 = blur, >1.0 = sharpen)
    if shp != 1.0:
        if shp > 1.0:
            # Sharpen: use UnsharpMask with intensity based on sharpness value
            # shp=1.5 → 50% sharp, shp=2.0 → 100% sharp
            intensity = (shp - 1.0) * 200  # maps 1.0-2.0 to 0-200%
            img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=int(intensity), threshold=3))
        elif shp < 1.0:
            # Blur: use GaussianBlur with radius based on how far below 1.0
            # shp=0.5 → radius 2.5, shp=0 → radius 5
            radius = (1.0 - shp) * 5
            img = img.filter(ImageFilter.GaussianBlur(radius=radius))

    # Additional 'Film' filter: slight S-curve + warm midtones
    filt = settings.get('filter', 'None')
    if filt == 'Film':
        try:
            # apply a lightweight S-curve via numpy if available
            if _HAS_NUMPY:
                arr = np.asarray(img).astype(np.float32)
                # simple contrast S-curve: scale, then gamma-like tweak
                arr = (arr - 128.0) * 1.08 + 128.0
                # gentle filmic gamma
                arr = 255.0 * (arr / 255.0) ** 0.95
                # warm midtones: add small bias to R channel
                arr[..., 0] = np.clip(arr[..., 0] * 1.02 + 4.0, 0, 255)
                arr = np.clip(arr, 0, 255).astype(np.uint8)
                img = Image.fromarray(arr)
            else:
                # pillow fallback: increase contrast and color slightly
                img = ImageEnhance.Contrast(img).enhance(1.08)
                img = ImageEnhance.Color(img).enhance(1.05)
                # warm tint
                r, g, b = img.split()
                r = ImageEnhance.Brightness(r).enhance(1.02)
                img = Image.merge('RGB', (r, g, b))
        except Exception:
            pass

    out = io.BytesIO()
    img.save(out, format='PNG')
    return out.getvalue()
