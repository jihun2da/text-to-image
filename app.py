import io
import zipfile
from PIL import Image, ImageDraw, ImageFont
import streamlit as st

# ======================
# 고정 설정(사용자 조절 X)
# ======================
BOX_WIDTH = 700

PADDING = 48
PANEL_PADDING = 34

LINE_GAP = 14
PARAGRAPH_GAP = 34

SHADOW_STRENGTH = 1.0
TEXT_COLOR = (30, 30, 30)

HIGHLIGHT_FILL = (255, 236, 156)

REG_FONT_PATH = "fonts/NotoSansKR-Regular.ttf"
BOLD_FONT_PATH = "fonts/NotoSansKR-Bold.ttf"

BASE_SIZE = 28
BOLD_SIZE = 28
EMPH_SIZE = 32
TITLE_SIZE = 46
SUBTITLE_SIZE = 34

MIN_SCALE = 0.65  # 한 줄이 너무 길 때 최소 축소 비율

_font_cache = {}


def get_font(path, size):
    key = (path, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, size=size)
    return _font_cache[key]


def tokenize_line(line: str):
    tokens = []
    i = 0
    while i < len(line):
        if line.startswith("==", i):
            j = line.find("==", i + 2)
            if j != -1:
                tokens.append(("EMPH", line[i+2:j]))
                i = j + 2
                continue

        if line.startswith("**", i):
            j = line.find("**", i + 2)
            if j != -1:
                tokens.append(("BOLD", line[i+2:j]))
                i = j + 2
                continue

        next_pos = len(line)
        for mark in ["==", "**"]:
            p = line.find(mark, i)
            if p != -1:
                next_pos = min(next_pos, p)

        chunk = line[i:next_pos]
        if chunk:
            tokens.append(("NORMAL", chunk))
        i = next_pos

    return tokens


def draw_centered_line(draw, x_left, x_right, y, tokens, base_fonts):
    content_width = x_right - x_left

    def line_width(fonts):
        w = 0
        for style, text in tokens:
            w += draw.textlength(text, font=fonts[style])
        return w

    w0 = line_width(base_fonts)

    scale = 1.0
    if w0 > content_width and w0 > 0:
        scale = max(MIN_SCALE, content_width / w0)

    def scaled_font(path, base_size):
        new_size = max(12, int(base_size * scale))
        return get_font(path, new_size)

    fonts = {
        "NORMAL": scaled_font(REG_FONT_PATH, BASE_SIZE),
        "BOLD": scaled_font(BOLD_FONT_PATH, BOLD_SIZE),
        "EMPH": scaled_font(BOLD_FONT_PATH, EMPH_SIZE),
        "TITLE": scaled_font(BOLD_FONT_PATH, TITLE_SIZE),
        "SUBTITLE": scaled_font(BOLD_FONT_PATH, SUBTITLE_SIZE),
    }

    w = line_width(fonts)
    x = x_left + (content_width - w) / 2

    has_emph = any(style == "EMPH" and text for style, text in tokens)
    if has_emph:
        max_h = max(fonts[style].size for style, text in tokens if text)
        box_h = max_h + 14
        box_y1 = y - 6
        box_y2 = box_y1 + box_h

        pad_lr = int(content_width * 0.04)
        bx1 = x_left + pad_lr
        bx2 = x_right - pad_lr
        draw.rounded_rectangle([bx1, box_y1, bx2, box_y2], radius=16, fill=HIGHLIGHT_FILL)

    for style, text in tokens:
        draw.text((x, y), text, fill=TEXT_COLOR, font=fonts[style])
        x += draw.textlength(text, font=fonts[style])

    max_size = max(fonts[style].size for style, text in tokens if text)
    return max_size + LINE_GAP


def render_image(input_text: str, template: str, bg_hex: str):
    bg_rgb = tuple(int(bg_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
    use_panel = (template != "A_미니멀")

    base_fonts = {
        "NORMAL": get_font(REG_FONT_PATH, BASE_SIZE),
        "BOLD": get_font(BOLD_FONT_PATH, BOLD_SIZE),
        "EMPH": get_font(BOLD_FONT_PATH, EMPH_SIZE),
        "TITLE": get_font(BOLD_FONT_PATH, TITLE_SIZE),
        "SUBTITLE": get_font(BOLD_FONT_PATH, SUBTITLE_SIZE),
    }

    raw_lines = input_text.splitlines()

    lines = []
    for raw in raw_lines:
        s = raw.rstrip("\n")
        if s.strip() == "":
            lines.append({"type": "EMPTY"})
            continue

        if s.startswith("## "):
            tokens = [("SUBTITLE", s[3:].strip())]
        elif s.startswith("# "):
            tokens = [("TITLE", s[2:].strip())]
        else:
            tokens = tokenize_line(s)

        lines.append({"type": "TEXT", "tokens": tokens})

    tmp = Image.new("RGB", (BOX_WIDTH, 10), "white")
    d = ImageDraw.Draw(tmp)

    x_left = PADDING
    x_right = BOX_WIDTH - PADDING
    if use_panel:
        x_left = PADDING + PANEL_PADDING
        x_right = BOX_WIDTH - (PADDING + PANEL_PADDING)

    total_h = PADDING * 2
    if use_panel:
        total_h += PANEL_PADDING * 2

    for obj in lines:
        if obj["type"] == "EMPTY":
            total_h += PARAGRAPH_GAP
        else:
            max_size = max(base_fonts[s].size for s, t in obj["tokens"] if t)
            total_h += max_size + LINE_GAP

    img = Image.new("RGB", (BOX_WIDTH, total_h), bg_rgb)
    draw = ImageDraw.Draw(img)

    if use_panel:
        panel_left = PADDING
        panel_top = PADDING
        panel_right = BOX_WIDTH - PADDING
        panel_bottom = total_h - PADDING

        panel_fill = (
            min(bg_rgb[0] + 18, 255),
            min(bg_rgb[1] + 18, 255),
            min(bg_rgb[2] + 18, 255),
        )

        if SHADOW_STRENGTH > 0:
            shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
            sd = ImageDraw.Draw(shadow)
            sx, sy = 3, 6
            alpha = int(25 * SHADOW_STRENGTH)
            sd.rounded_rectangle(
                [panel_left + sx, panel_top + sy, panel_right + sx, panel_bottom + sy],
                radius=26,
                fill=(0, 0, 0, alpha)
            )
            img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")
            draw = ImageDraw.Draw(img)

        draw.rounded_rectangle(
            [panel_left, panel_top, panel_right, panel_bottom],
            radius=26,
            fill=panel_fill
        )

    y = PADDING + (PANEL_PADDING if use_panel else 0)

    for obj in lines:
        if obj["type"] == "EMPTY":
            y += PARAGRAPH_GAP
            continue

        h = draw_centered_line(draw, x_left, x_right, y, obj["tokens"], base_fonts)
        y += h

    return img


# ======================
# Streamlit UI
# ======================
st.set_page_config(page_title="텍스트 → JPG 이미지(멀티)", layout="centered")
st.title("상품설명 텍스트 → JPG 이미지 (여러 개 한 번에)")

st.markdown(
"""
- 템플릿/배경색만 선택하고, 아래 입력칸에 여러 개의 텍스트를 각각 넣으면 됩니다.
- ✅ 앱이 임의로 줄을 나누지 않습니다(엔터 그대로).
- ✅ 한 줄이 길면 줄바꿈 대신 그 줄의 글자 크기를 자동 축소합니다.
- 문법: `# 제목`, `## 부제`, `**굵게**`, `==강조==`
"""
)

template = st.selectbox("템플릿", ["A_미니멀", "B_카드형", "C_포스터형"], index=1)
bg = st.color_picker("배경색", "#FFFFFF" if template == "A_미니멀" else "#F6F7FB")

# --- 멀티 입력칸 관리
if "blocks" not in st.session_state:
    st.session_state.blocks = [""]  # 기본 1개

col_a, col_b = st.columns(2)
with col_a:
    if st.button("입력칸 + 추가"):
        st.session_state.blocks.append("")
with col_b:
    if st.button("입력칸 - 삭제"):
        if len(st.session_state.blocks) > 1:
            st.session_state.blocks.pop()

st.divider()

# 입력칸 출력
for i in range(len(st.session_state.blocks)):
    st.session_state.blocks[i] = st.text_area(
        f"텍스트 {i+1}",
        value=st.session_state.blocks[i],
        height=220,
        key=f"txt_{i}"
    )

st.divider()

if st.button("이미지 한 번에 생성"):
    # 비어있지 않은 것만 처리
    valid_blocks = [b.strip() for b in st.session_state.blocks if b.strip()]

    if not valid_blocks:
        st.warning("최소 1개 텍스트는 입력해야 합니다.")
    else:
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, block in enumerate(valid_blocks, start=1):
                img = render_image(block, template, bg)

                if img.mode != "RGB":
                    img = img.convert("RGB")

                img_buf = io.BytesIO()
                img.save(img_buf, format="JPEG", quality=95)

                filename = f"product_{idx}.jpg"
                zf.writestr(filename, img_buf.getvalue())

                st.image(img, caption=f"미리보기 {idx}", use_container_width=False)

                st.download_button(
                    f"JPG 다운로드 {idx}",
                    data=img_buf.getvalue(),
                    file_name=filename,
                    mime="image/jpeg",
                    key=f"dl_{idx}"
                )

        st.download_button(
            "모든 JPG ZIP 다운로드",
            data=zip_buffer.getvalue(),
            file_name="product_images.zip",
            mime="application/zip"
        )
