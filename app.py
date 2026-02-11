import io
from PIL import Image, ImageDraw, ImageFont
import streamlit as st

# ======================
# 고정 설정(사용자 조절 X)
# ======================
BOX_WIDTH = 700

PADDING = 48           # 바깥 여백 고정
PANEL_PADDING = 34     # 카드형 텍스트 안쪽 여백 고정

LINE_GAP = 14          # 줄 간격 고정
PARAGRAPH_GAP = 34     # 빈 줄(문단) 간격 고정

SHADOW_STRENGTH = 1.0  # 그림자 강도 고정 (0이면 없음)
TEXT_COLOR = (30, 30, 30)

# 강조(== ==) 하이라이트 색 고정 (포인트 컬러 기능 제거)
HIGHLIGHT_FILL = (255, 236, 156)

# 폰트 경로
REG_FONT_PATH = "fonts/NotoSansKR-Regular.ttf"
BOLD_FONT_PATH = "fonts/NotoSansKR-Bold.ttf"

# 기본 폰트 크기 (필요하면 한 줄 단위로 자동 축소)
BASE_SIZE = 28
BOLD_SIZE = 28
EMPH_SIZE = 32
TITLE_SIZE = 46
SUBTITLE_SIZE = 34

MIN_SCALE = 0.65  # 한 줄이 너무 길 때 최소 축소 비율(너무 작아지는 거 방지)


# ======================
# 폰트 캐시
# ======================
_font_cache = {}

def get_font(path, size):
    key = (path, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, size=size)
    return _font_cache[key]


def tokenize_line(line: str):
    """
    한 줄 안에서만 스타일 적용.
    - ==강조== -> EMPH (줄 전체 하이라이트 박스 + 텍스트는 굵고 조금 크게)
    - **굵게** -> BOLD
    - 나머지 -> NORMAL
    """
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
    """
    ✅ 절대 줄바꿈 안 함.
    한 줄이 폭을 넘으면 => 줄바꿈 대신 "그 줄의 폰트 크기"를 자동으로 줄여 한 줄에 맞춤.
    """
    content_width = x_right - x_left

    # 1) 현재 폰트로 줄 너비 계산
    def line_width(fonts):
        w = 0
        for style, text in tokens:
            w += draw.textlength(text, font=fonts[style])
        return w

    w0 = line_width(base_fonts)

    # 2) 폭 초과 시, 줄 전체를 축소(폰트 크기 줄이기)
    scale = 1.0
    if w0 > content_width and w0 > 0:
        scale = max(MIN_SCALE, content_width / w0)

    # 축소 폰트 생성(라인 단위)
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

    # 3) EMPH가 있으면 줄 전체 하이라이트 박스(줄바꿈 없음)
    has_emph = any(style == "EMPH" and text for style, text in tokens)
    if has_emph:
        max_h = max(fonts[style].size for style, text in tokens if text)
        box_h = max_h + 14
        box_y1 = y - 6
        box_y2 = box_y1 + box_h

        # 줄 전체 폭의 92% 정도 박스
        pad_lr = int(content_width * 0.04)
        bx1 = x_left + pad_lr
        bx2 = x_right - pad_lr
        draw.rounded_rectangle([bx1, box_y1, bx2, box_y2], radius=16, fill=HIGHLIGHT_FILL)

    # 4) 문자 출력
    for style, text in tokens:
        draw.text((x, y), text, fill=TEXT_COLOR, font=fonts[style])
        x += draw.textlength(text, font=fonts[style])

    # 5) 라인 높이 리턴
    max_size = max(fonts[style].size for style, text in tokens if text)
    return max_size + LINE_GAP


def render_image(input_text: str, template: str, bg_hex: str):
    bg_rgb = tuple(int(bg_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

    # 템플릿 옵션(사용자 조절 X)
    use_panel = (template != "A_미니멀")

    # base 폰트(라인 스케일 계산 기준)
    base_fonts = {
        "NORMAL": get_font(REG_FONT_PATH, BASE_SIZE),
        "BOLD": get_font(BOLD_FONT_PATH, BOLD_SIZE),
        "EMPH": get_font(BOLD_FONT_PATH, EMPH_SIZE),
        "TITLE": get_font(BOLD_FONT_PATH, TITLE_SIZE),
        "SUBTITLE": get_font(BOLD_FONT_PATH, SUBTITLE_SIZE),
    }

    # 입력 줄을 "그대로" 사용 (✅ 자동 줄바꿈 금지)
    raw_lines = input_text.splitlines()

    # 렌더용 라인 구성: 빈 줄은 문단 간격만 추가
    lines = []
    for raw in raw_lines:
        s = raw.rstrip("\n")
        if s.strip() == "":
            lines.append({"type": "EMPTY"})
            continue

        # 제목/부제 처리(한 줄 그대로)
        if s.startswith("## "):
            tokens = [("SUBTITLE", s[3:].strip())]
        elif s.startswith("# "):
            tokens = [("TITLE", s[2:].strip())]
        else:
            tokens = tokenize_line(s)

        lines.append({"type": "TEXT", "tokens": tokens})

    # 높이 계산용 임시 드로우
    tmp = Image.new("RGB", (BOX_WIDTH, 10), "white")
    d = ImageDraw.Draw(tmp)

    # 컨텐츠 폭 계산
    x_left = PADDING
    x_right = BOX_WIDTH - PADDING
    if use_panel:
        x_left = PADDING + PANEL_PADDING
        x_right = BOX_WIDTH - (PADDING + PANEL_PADDING)

    total_h = PADDING * 2
    if use_panel:
        total_h += PANEL_PADDING * 2

    # 라인별 높이 계산(줄바꿈 없이, 필요 시 라인 폰트 축소)
    # EMPTY는 PARAGRAPH_GAP만 추가
    for obj in lines:
        if obj["type"] == "EMPTY":
            total_h += PARAGRAPH_GAP
        else:
            # 높이 추정: 축소될 수 있으니 base 높이 기준으로 잡고,
            # 실제 렌더 때 반환되는 높이로 맞춰도 되지만, 2-pass로 안정적 처리
            max_size = max(base_fonts[s].size for s, t in obj["tokens"] if t)
            total_h += max_size + LINE_GAP

    # 캔버스 생성
    img = Image.new("RGB", (BOX_WIDTH, total_h), bg_rgb)
    draw = ImageDraw.Draw(img)

    # 카드 패널(템플릿 B,C)
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

    # 실제 렌더링(2-pass: 높이 오차 없이)
    y = PADDING + (PANEL_PADDING if use_panel else 0)

    for obj in lines:
        if obj["type"] == "EMPTY":
            y += PARAGRAPH_GAP
            continue

        h = draw_centered_line(draw, x_left, x_right, y, obj["tokens"], base_fonts)
        y += h

    return img


# ======================
# Streamlit UI (요구대로 최소화)
# ======================
st.set_page_config(page_title="텍스트 → 이미지(700px)", layout="centered")
st.title("상품설명 텍스트 → 이미지 변환 (줄바꿈 그대로)")

st.markdown(
"""
- ✅ 입력한 **줄바꿈(엔터) 그대로** 이미지에 반영됩니다.  
- ✅ 앱이 **임의로 줄을 나누지 않습니다.**  
- ✅ 한 줄이 너무 길면 **줄바꿈 대신 그 줄의 글자 크기를 자동으로 줄여서** 700px 박스에 맞춥니다.
- 문법: `# 제목`, `## 부제`, `**굵게**`, `==강조==`
"""
)

template = st.selectbox("템플릿", ["A_미니멀", "B_카드형", "C_포스터형"], index=1)
bg = st.color_picker("배경색", "#FFFFFF" if template == "A_미니멀" else "#F6F7FB")

text = st.text_area("설명 텍스트 붙여넣기", height=320, placeholder="여기에 붙여넣기...")

if st.button("이미지 생성"):
    if not text.strip():
        st.warning("텍스트를 먼저 붙여넣어줘.")
    else:
        img = render_image(text, template, bg)

        st.image(img, caption=f"미리보기 ({template})", use_container_width=False)

        # 🔽 여기서부터 JPG 저장
        buf = io.BytesIO()

        # JPG는 RGB 필요
        if img.mode != "RGB":
            img = img.convert("RGB")

        img.save(buf, format="JPEG", quality=95)

        st.download_button(
            "JPG 다운로드",
            data=buf.getvalue(),
            file_name="product_description.jpg",
            mime="image/jpeg"
        )

