import io
from edits import apply_edits_bytes
from PIL import Image


def test_apply_edits_basic():
    # create a simple image
    img = Image.new('RGB', (128, 128), (120, 200, 80))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    data = buf.getvalue()

    settings = {'filter': 'None', 'brightness': 1.1, 'contrast': 1.2, 'saturation': 1.0, 'vignette': 0.2}
    out = apply_edits_bytes(data, settings)
    # ensure bytes returned and Pillow can open
    assert isinstance(out, (bytes, bytearray))
    img2 = Image.open(io.BytesIO(out))
    assert img2.size == (128, 128)


if __name__ == '__main__':
    test_apply_edits_basic()
    print('edit helper smoke test passed')
