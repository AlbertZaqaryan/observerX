"""Image handling: normalize/downscale and encode as a data URI so the image
can be passed natively to the vision-capable model via the OpenAI schema."""
import base64
import io

from PIL import Image

from .. import config


def to_data_uri(data: bytes) -> str:
    """Downscale oversized images and return a base64 JPEG/PNG data URI."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        # Not a decodable image; fall back to passing the raw bytes as-is.
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:image/png;base64,{b64}"

    has_alpha = img.mode in ("RGBA", "LA", "P")
    img = img.convert("RGBA") if has_alpha else img.convert("RGB")

    max_edge = config.IMAGE_MAX_EDGE
    if max(img.size) > max_edge:
        ratio = max_edge / float(max(img.size))
        new_size = (max(1, int(img.width * ratio)), max(1, int(img.height * ratio)))
        img = img.resize(new_size, Image.LANCZOS)

    buf = io.BytesIO()
    if has_alpha:
        img.save(buf, format="PNG", optimize=True)
        mime = "image/png"
    else:
        img.save(buf, format="JPEG", quality=88)
        mime = "image/jpeg"

    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:{mime};base64,{b64}"
