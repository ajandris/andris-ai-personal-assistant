import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

STATIC_DIR = Path(__file__).resolve().parent.parent / "app" / "static"
IMAGES_DIR = STATIC_DIR / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

def create_high_res_icon(size: int = 512) -> Image.Image:
    """Create a high-resolution 512x512 master icon with anti-aliasing."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Background gradient squircle
    # Colors: #3b82f6 (59, 130, 246) -> #6366f1 (99, 102, 241)
    radius = int(size * 0.24)
    padding = int(size * 0.04)
    inner_box = (padding, padding, size - padding, size - padding)
    
    # Create mask for rounded rectangle
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(inner_box, radius=radius, fill=255)

    # Draw gradient onto a separate image
    grad_img = Image.new("RGBA", (size, size))
    grad_draw = ImageDraw.Draw(grad_img)
    c1 = (59, 130, 246)   # #3b82f6
    c2 = (99, 102, 241)   # #6366f1
    
    for y in range(size):
        ratio_y = y / size
        for x in range(size):
            ratio_x = x / size
            t = (ratio_x + ratio_y) / 2.0
            r = int(c1[0] + (c2[0] - c1[0]) * t)
            g = int(c1[1] + (c2[1] - c1[1]) * t)
            b = int(c1[2] + (c2[2] - c1[2]) * t)
            grad_img.putpixel((x, y), (r, g, b, 255))
    
    # Composite squircle
    img.paste(grad_img, (0, 0), mask)

    # 2. Subtle glossy border highlight
    border_draw = ImageDraw.Draw(img)
    border_draw.rounded_rectangle(
        inner_box,
        radius=radius,
        outline=(255, 255, 255, 60),
        width=max(2, int(size * 0.015))
    )

    # 3. Monogram text "АЯ"
    font_size = int(size * 0.44)
    font_path = "C:/Windows/Fonts/segoeuib.ttf"
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()

    text = "АЯ"
    # Get bounding box to center accurately
    bbox = font.getbbox(text)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    
    # Offset slightly left & down for optical balance with sparkle
    x_pos = (size - w) // 2 - int(size * 0.02)
    y_pos = (size - h) // 2 - int(bbox[1]) - int(size * 0.01)

    # Subtle drop shadow for monogram
    shadow_offset = max(2, int(size * 0.015))
    draw.text((x_pos, y_pos + shadow_offset), text, font=font, fill=(15, 23, 42, 100))
    # Monogram text
    draw.text((x_pos, y_pos), text, font=font, fill=(255, 255, 255, 255))

    # 4. AI Sparkle ✦ in top-right
    # 4-pointed diamond star
    cx = int(size * 0.80)
    cy = int(size * 0.20)
    sparkle_len = int(size * 0.13)
    sparkle_width = int(size * 0.04)

    # Outer glow for the sparkle
    for dr in range(sparkle_width * 2, 0, -2):
        alpha = int(35 * (1.0 - dr / (sparkle_width * 2)))
        draw.ellipse(
            (cx - dr, cy - dr, cx + dr, cy + dr),
            fill=(56, 189, 248, alpha)
        )

    # Polygon for diamond 4-pointed star
    pts = [
        (cx, cy - sparkle_len),
        (cx + sparkle_width, cy - sparkle_width),
        (cx + sparkle_len, cy),
        (cx + sparkle_width, cy + sparkle_width),
        (cx, cy + sparkle_len),
        (cx - sparkle_width, cy + sparkle_width),
        (cx - sparkle_len, cy),
        (cx - sparkle_width, cy - sparkle_width),
    ]
    draw.polygon(pts, fill=(255, 255, 255, 255))

    return img

def main():
    print("Generating master icon...")
    master = create_high_res_icon(512)

    # 1. apple-touch-icon.png (180x180)
    apple_icon = master.resize((180, 180), Image.Resampling.LANCZOS)
    apple_icon_path = IMAGES_DIR / "apple-touch-icon.png"
    apple_icon.save(apple_icon_path, format="PNG")
    print(f"Saved: {apple_icon_path}")

    # 2. favicon-32x32.png (32x32)
    fav_32 = master.resize((32, 32), Image.Resampling.LANCZOS)
    fav_32_path = IMAGES_DIR / "favicon-32x32.png"
    fav_32.save(fav_32_path, format="PNG")
    print(f"Saved: {fav_32_path}")

    # 3. favicon-16x16.png (16x16)
    fav_16 = master.resize((16, 16), Image.Resampling.LANCZOS)
    fav_16_path = IMAGES_DIR / "favicon-16x16.png"
    fav_16.save(fav_16_path, format="PNG")
    print(f"Saved: {fav_16_path}")

    # 4. favicon.ico (multi-res 16, 32, 48)
    fav_48 = master.resize((48, 48), Image.Resampling.LANCZOS)
    ico_path = IMAGES_DIR / "favicon.ico"
    fav_32.save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)]
    )
    print(f"Saved: {ico_path}")

    # 5. favicon.svg (crisp vector SVG)
    svg_path = IMAGES_DIR / "favicon.svg"
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#3b82f6"/>
      <stop offset="100%" stop-color="#6366f1"/>
    </linearGradient>
    <linearGradient id="sparkleGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#ffffff"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="2" stdDeviation="2.5" flood-color="#000000" flood-opacity="0.35"/>
    </filter>
  </defs>

  <!-- Squircle container -->
  <rect x="2" y="2" width="60" height="60" rx="14" fill="url(#bgGrad)" filter="url(#shadow)"/>
  <rect x="3" y="3" width="58" height="58" rx="13" fill="none" stroke="rgba(255, 255, 255, 0.25)" stroke-width="1.2"/>

  <!-- Monogram text АЯ -->
  <text x="29" y="42" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif" font-size="26" font-weight="800" fill="#ffffff" text-anchor="middle" letter-spacing="-0.5">АЯ</text>

  <!-- AI Sparkle ✦ in top-right -->
  <path d="M50 7 C50 13, 53 16, 59 16 C53 16, 50 19, 50 25 C50 19, 47 16, 41 16 C47 16, 50 13, 50 7 Z" fill="url(#sparkleGrad)"/>
</svg>
"""
    svg_path.write_text(svg_content, encoding="utf-8")
    print(f"Saved: {svg_path}")

if __name__ == "__main__":
    main()
