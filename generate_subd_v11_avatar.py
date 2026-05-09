from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, PngImagePlugin


SIZE = 1024
OUTPUT = Path("subd_v1_1_avatar.png")
VERSION_TEXT = "1.1"
TITLE_TEXT = "SUBD"
SUBTITLE_TEXT = "SIX ETF"


def _hex(rgb: str) -> tuple[int, int, int]:
    rgb = rgb.lstrip("#")
    return tuple(int(rgb[i : i + 2], 16) for i in (0, 2, 4))


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
        Path(r"C:\Windows\Fonts\Arialbd.ttf"),
        Path(r"C:\Windows\Fonts\segoeuib.ttf"),
        Path(r"C:\Windows\Fonts\seguisb.ttf"),
        Path(r"C:\Windows\Fonts\bahnschrift.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _teal_gradient(size: int) -> Image.Image:
    dark = _hex("#021617")
    green = _hex("#08756f")
    teal = _hex("#1fb6a6")
    mint = _hex("#8ef5de")
    ice = _hex("#eafff9")
    img = Image.new("RGB", (size, size))
    px = img.load()
    cx, cy = size * 0.60, size * 0.28
    max_r = math.hypot(size, size)

    for y in range(size):
        for x in range(size):
            linear = (x * 0.76 + y * 1.08) / (size * 1.84)
            radial = math.hypot(x - cx, y - cy) / max_r
            if linear < 0.40:
                color = _lerp(dark, green, linear / 0.40)
            elif linear < 0.75:
                color = _lerp(green, teal, (linear - 0.40) / 0.35)
            else:
                color = _lerp(teal, mint, (linear - 0.75) / 0.25)
            if radial < 0.22:
                color = _lerp(color, ice, (0.22 - radial) / 0.22 * 0.36)
            vignette = math.hypot(x - size / 2, y - size / 2) / (size * 0.72)
            color = _lerp(color, dark, max(0.0, vignette - 0.48) * 0.62)
            px[x, y] = color
    return img


def _draw_market_texture(base: Image.Image) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    for x in range(-210, SIZE + 260, 78):
        draw.line((x, 70, x + 380, SIZE - 30), fill=(170, 255, 235, 24), width=2)
    for y in range(152, SIZE, 106):
        draw.line((0, y, SIZE, y - 78), fill=(2, 36, 39, 46), width=2)

    candle_x = 150
    heights = [64, 104, 78, 138, 114, 168, 132, 204, 160]
    for i, h in enumerate(heights):
        x = candle_x + i * 86
        top = 762 - h
        bottom = 762
        color = (205, 255, 243, 58) if i % 2 else (0, 48, 51, 92)
        draw.line((x + 12, top - 34, x + 12, bottom + 28), fill=color, width=4)
        draw.rounded_rectangle((x, top, x + 24, bottom), radius=6, fill=color)

    points = [(130, 724), (244, 690), (352, 706), (468, 640), (590, 604), (730, 548), (888, 486)]
    draw.line(points, fill=(223, 255, 246, 102), width=8, joint="curve")
    draw.line(points, fill=(16, 207, 177, 170), width=4, joint="curve")

    layer = layer.filter(ImageFilter.GaussianBlur(radius=0.35))
    base.alpha_composite(layer)


def _draw_robot_frame(base: Image.Image) -> None:
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle((108, 132, 916, 920), radius=118, fill=(0, 17, 20, 180))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=26))
    base.alpha_composite(shadow)

    panel = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(panel)
    draw.rounded_rectangle((106, 108, 918, 914), radius=122, fill=(236, 255, 250, 28))
    draw.rounded_rectangle((106, 108, 918, 914), radius=122, outline=(222, 255, 248, 150), width=5)
    draw.rounded_rectangle((170, 206, 854, 610), radius=82, fill=(246, 255, 253, 42))
    draw.rounded_rectangle((170, 206, 854, 610), radius=82, outline=(214, 255, 246, 118), width=3)
    draw.rounded_rectangle((282, 300, 742, 510), radius=52, fill=(2, 25, 28, 150))
    draw.ellipse((308, 360, 378, 430), fill=(129, 255, 228, 232))
    draw.ellipse((646, 360, 716, 430), fill=(129, 255, 228, 232))
    draw.arc((390, 396, 634, 552), start=18, end=162, fill=(169, 255, 236, 205), width=8)
    base.alpha_composite(panel)


def _draw_centered_text(
    base: Image.Image,
    text: str,
    font: ImageFont.FreeTypeFont,
    y_center: int,
    fill: tuple[int, int, int],
    shadow: tuple[int, int, int],
    shadow_blur: int,
    stroke: tuple[int, int, int] | None = None,
    stroke_width: int = 0,
) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    x = (base.width - (bbox[2] - bbox[0])) / 2
    y = y_center - (bbox[3] - bbox[1]) / 2 - bbox[1]

    draw.text((x + 14, y + 18), text, font=font, fill=shadow + (218,), stroke_width=stroke_width)
    layer = layer.filter(ImageFilter.GaussianBlur(radius=shadow_blur))
    base.alpha_composite(layer)

    draw = ImageDraw.Draw(base)
    kwargs = {}
    if stroke is not None and stroke_width:
        kwargs = {"stroke_width": stroke_width, "stroke_fill": stroke + (255,)}
    draw.text((x, y), text, font=font, fill=fill + (255,), **kwargs)


def _draw_version_badge(base: Image.Image) -> None:
    badge = (620, 760, 944, 942)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle(badge, radius=40, fill=(235, 255, 250, 238))
    draw.rounded_rectangle(badge, radius=40, outline=(2, 56, 59, 180), width=4)
    layer = layer.filter(ImageFilter.GaussianBlur(radius=0.15))
    base.alpha_composite(layer)

    font = _load_font(118)
    text = "V1.1"
    text_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)
    bbox = text_draw.textbbox((0, 0), text, font=font)
    x = badge[0] + (badge[2] - badge[0] - (bbox[2] - bbox[0])) / 2 - bbox[0]
    y = badge[1] + (badge[3] - badge[1] - (bbox[3] - bbox[1])) / 2 - bbox[1] - 2
    text_draw.text((x + 6, y + 7), text, font=font, fill=(149, 255, 236, 180))
    text_layer = text_layer.filter(ImageFilter.GaussianBlur(radius=2))
    base.alpha_composite(text_layer)
    draw = ImageDraw.Draw(base)
    draw.text((x, y), text, font=font, fill=_hex("#043f3f") + (255,))


def create_avatar(output: Path = OUTPUT) -> Path:
    bg = _teal_gradient(SIZE).convert("RGBA")
    _draw_market_texture(bg)
    _draw_robot_frame(bg)

    _draw_centered_text(
        bg,
        TITLE_TEXT,
        _load_font(132),
        y_center=642,
        fill=_hex("#ecfffb"),
        shadow=_hex("#011b1d"),
        shadow_blur=8,
        stroke=_hex("#057c77"),
        stroke_width=2,
    )
    _draw_centered_text(
        bg,
        SUBTITLE_TEXT,
        _load_font(50),
        y_center=720,
        fill=_hex("#a8fff0"),
        shadow=_hex("#011b1d"),
        shadow_blur=4,
    )
    _draw_version_badge(bg)

    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("Title", "SubD Six ETF V1.1 Avatar")
    metadata.add_text("Version", "V1.1")
    metadata.add_text("Strategy", "SubD Six ETF")
    output = Path(output)
    bg.convert("RGB").save(output, pnginfo=metadata)
    return output.resolve()


def main() -> None:
    print(create_avatar())


if __name__ == "__main__":
    main()
