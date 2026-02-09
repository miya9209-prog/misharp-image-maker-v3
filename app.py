import io
import os
import re
import zipfile
import hashlib
import base64
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

import streamlit as st
from PIL import Image, ImageSequence

from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


# =========================================================
# APP CONFIG
# =========================================================
APP_TITLE = "MISHARP 상세페이지 생성기"
APP_SUBTITLE = "PSD GENERATOR V3 · 내부 디자이너 전용"

CANVAS_WIDTH = 900

# ✅ 분할 규칙 (현재 운영 방식 유지: 10장 초과 시 PSD 2개로 분할, 최대 20장)
MAX_PER_PSD = 10
MAX_TOTAL_IMAGES = 20

DEFAULT_TOP_PAD = 180
DEFAULT_BOTTOM_PAD = 250
DEFAULT_GAP = 300

# ✅ 썸네일 (현재 안정버전 기준: 70)
THUMB_W = 70

STATE_ITEMS = "img_items"
STATE_SEEN = "seen_hashes"
STATE_LAST_PREVIEW = "last_preview_jpg"
STATE_LAST_ZIP = "last_bundle_zip"
STATE_LAST_META = "last_meta"

# auth states
STATE_AUTH_OK = "auth_ok"
STATE_AUTH_LABEL = "auth_label"
STATE_AUTH_ROLE = "auth_role"
STATE_AUTH_FAILS = "auth_fails"
STATE_AUTH_LOCK_UNTIL = "auth_lock_until"


# =========================================================
# BRAND (logo & colors)
# =========================================================
# 미샵 로고 배경색(이미지에서 샘플링): #4d6f4e
BRAND_BG = "#4d6f4e"
BRAND_BG_DARK = "#3f5d40"

# 로고를 app.py 안에 내장 (추가 파일 없이 배포 가능)
# (사용자가 올려준 로고 jpg를 base64로 넣어둠)
MISHARP_LOGO_B64 = (
    "/9j/4RdtRXhpZgAATU0AKgAAAAgABwESAAMAAAABAAEAAAEaAAUAAAABAAAAYgEbAAUAAAABAAAA"
    "agEoAAMAAAABAAIAAAExAAIAAAAeAAAAcgEyAAIAAAAUAAAAkIdpAAQAAAABAAAApAAAANAACvyA"
    "AAAnEAAK/IAAACcQQWRvYmUgUGhvdG9zaG9wIENTNS4xIFdpbgA4QklNBAQAAAAAABccQklNBCUA"
    "AAAAABAcQklNBDoAAAAAAEgcQklNBEwAAAAAAE4cQklNBFEAAAAAAFUcQklNBFoAAAAAAGAcQklN"
    "BF8AAAAAAGYcQklNBGQAAAAAAGwcQklNBGkAAAAAAHMcQklNBG4AAAAAAH0cQklNBG8AAAAAAIcc"
    "QklNBG8AAAAAAIgcQklNBG8AAAAAAIkcQklNBG8AAAAAAIocQklNBG8AAAAAAIscQklNBG8AAAAA"
    "AIwcQklNBG8AAAAAAI0cQklNBG8AAAAAAI4cQklNBG8AAAAAAI8cQklNBG8AAAAAAJAcQklNBG8A"
    "AAAAAJEcQklNBG8AAAAAAJIcQklNBG8AAAAAAJMcQklNBG8AAAAAAJQcQklNBG8AAAAAAJUcQklN"
    "BG8AAAAAAJYcQklNBG8AAAAAAJccQklNBG8AAAAAAJgcQklNBG8AAAAAAJkcQklNBG8AAAAAAJoc"
    "QklNBG8AAAAAAJscQklNBG8AAAAAAJwcQklNBG8AAAAAAJ0cQklNBG8AAAAAAJ4cQklNBG8AAAAA"
    "AJ8cQklNBG8AAAAAAKAcQklNBG8AAAAAAKEcQklNBG8AAAAAAKIcQklNBG8AAAAAAKMcQklNBG8A"
    "AAAAAKQcQklNBG8AAAAAAKUcQklNBG8AAAAAAKYcQklNBG8AAAAAAKccQklNBG8AAAAAAKgcQklN"
    "BG8AAAAAAKkcQklNBG8AAAAAAKocQklNBG8AAAAAAKscQklNBG8AAAAAAKwcQklNBG8AAAAAAK0c"
    "QklNBG8AAAAAAK4cQklNBG8AAAAAAK8cQklNBG8AAAAAALAcQklNBG8AAAAAALH/2wCEAAkGBxAQ"
    "EBAQEBAVEBAVEBAVEBAVFRUVFRUWFhUVFRUYHSggGBolGxUVITEhJSkrLi4uFx8zODMtNygtLisBCgoK"
    "DQ0NDg0NDysZFRkrKysrKysrKysrKysrKysrKysrKysrKysrKysrKysrKysrKysrKysrKysrKysrK//A"
    "ABEIAOEA4QMBIgACEQEDEQH/xAAcAAACAwEBAQEAAAAAAAAAAAAEBQIDBgcBAAj/xABCEAACAQMCAw"
    "QIBQcEAgMBAAABAgMABBESITEFBhMiQVFhBxQycYGRI0JSscEVQmKx0SMzQ1NicoLh8TQ0Q4PSFqPC"
    "0uP/xAAaAQACAwEBAAAAAAAAAAAAAAACAwEEBQAG/8QALREAAgIBAwMCBgIDAAAAAAAAAAECEQMSIT"
    "EEE0FRImFxkQUTgaGx8BRCQv/aAAwDAQACEQMRAD8A+qgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//Z"
)


# =========================================================
# UI STYLE (designer-friendly)
# =========================================================
def inject_style(auth_ok: bool):
    """
    - 로그인 전: 배경 브랜드그린 + 로고 카드 + 심플
    - 로그인 후: 화이트 기반, 폰트/버튼/간격을 디자이너용으로 정리
    - 사이드바 폭: 더 얇게
    """
    if not auth_ok:
        st.markdown(
            f"""
<style>
html, body, [class*="css"] {{
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Noto Sans KR", Arial, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
}}
/* 전체 배경 */
.stApp {{
  background: {BRAND_BG};
}}
/* 상단 패딩 줄이기 */
.block-container {{
  padding-top: 0.8rem;
  padding-bottom: 1.8rem;
}}
/* 로그인 카드 */
.ms-login {{
  max-width: 460px;
  margin: 7vh auto 0 auto;
  padding: 22px 22px 18px 22px;
  border-radius: 18px;
  background: rgba(255,255,255,0.10);
  border: 1px solid rgba(255,255,255,0.18);
  box-shadow: 0 10px 26px rgba(0,0,0,0.14);
  backdrop-filter: blur(6px);
}}
.ms-login h1 {{
  margin: 8px 0 0 0;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.4px;
  color: rgba(255,255,255,0.94);
}}
.ms-login p {{
  margin: 6px 0 14px 0;
  font-size: 12.5px;
  color: rgba(255,255,255,0.72);
}}
/* 입력 영역 */
.ms-login-input {{
  max-width: 460px;
  margin: 12px auto 0 auto;
}}
/* 버튼 */
.stButton button {{
  border-radius: 12px !important;
  padding: 0.60rem 0.95rem !important;
  font-weight: 700 !important;
  letter-spacing: -0.2px !important;
}}
/* 캡션 */
[data-testid="stCaptionContainer"] {{
  color: rgba(255,255,255,0.75) !important;
}}
/* 사이드바 숨김(로그인 전) */
section[data-testid="stSidebar"] {{ display: none; }}
</style>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
<style>
html, body, [class*="css"] {
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Noto Sans KR", Arial, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
}
.block-container { padding-top: 2.6rem; padding-bottom: 2.1rem; }

/* Sidebar width thinner */
section[data-testid="stSidebar"] { width: 220px !important; }
section[data-testid="stSidebar"] > div { width: 220px !important; }
@media (max-width: 900px){
  section[data-testid="stSidebar"] { width: 280px !important; }
  section[data-testid="stSidebar"] > div { width: 280px !important; }
}

/* Sidebar typography */
section[data-testid="stSidebar"] .stMarkdown p { font-size: 12.5px; }
section[data-testid="stSidebar"] .stMarkdown h3 { font-size: 14px; letter-spacing:-0.2px; }

/* Headings */
.ms-top-title { font-size: 24px; font-weight: 900; letter-spacing: -0.7px; margin: 0 0 2px 0; }
.ms-top-sub { font-size: 12.5px; opacity: 0.62; margin: 0 0 14px 0; }

/* Section label */
.ms-section {
  margin-top: 22px;
  margin-bottom: 14px;
}
.ms-section .t {
  font-size: 15px;
  font-weight: 850;
  letter-spacing: -0.25px;
  margin-bottom: 6px;
}

/* Buttons */
.stButton button, .stDownloadButton button {
  border-radius: 12px !important;
  padding: 0.56rem 0.9rem !important;
  font-weight: 700 !important;
  letter-spacing: -0.2px !important;
}

/* Softer divider */
hr { opacity: 0.18; }

/* File pills row */
.ms-pill-row {
  display:flex;
  gap:6px;
  flex-wrap:nowrap;
  overflow:hidden;
}
.ms-pill {
  padding:6px 9px;
  border-radius: 999px;
  border: 1px solid rgba(0,0,0,0.10);
  background: rgba(0,0,0,0.02);
  font-size: 12px;
  white-space: nowrap;
  max-width: 160px;
  text-overflow: ellipsis;
  overflow: hidden;
}
.ms-pill-etc { opacity: 0.65; }

/* tighten caption */
[data-testid="stCaptionContainer"] { opacity: 0.78; }
</style>
            """,
            unsafe_allow_html=True,
        )


def ms_section(title: str):
    st.markdown(
        f"""
<div class="ms-section">
  <div class="t">{title}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_uploaded_list_row(uploaded_files, max_show: int = 10):
    """
    Streamlit file_uploader 기본 UI는 3개만 보여서 <>가 생김(커스텀 불가).
    그래서 업로드 아래에 '한 줄 파일 리스트(최대 10개)'를 따로 만들어 직관적으로 보이게 함.
    """
    if not uploaded_files:
        return

    names = [uf.name for uf in uploaded_files]
    show = names[:max_show]
    more = len(names) - len(show)

    pills = []
    for n in show:
        safe = (n or "").replace("<", "&lt;").replace(">", "&gt;")
        pills.append(f'<div class="ms-pill" title="{safe}">{safe}</div>')
    if more > 0:
        pills.append(f'<div class="ms-pill ms-pill-etc">+{more} more</div>')

    st.markdown(
        f"""
<div class="ms-pill-row">
  {''.join(pills)}
</div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# AUTH (role / expires / lockout)
# =========================================================
def _truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "y", "on")


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _now_kst() -> datetime:
    if ZoneInfo is None:
        return datetime.utcnow()
    return datetime.now(ZoneInfo("Asia/Seoul"))


def _parse_expires(expires_raw: str) -> Optional[datetime]:
    """
    expires 포맷:
    - "" -> None(만료 없음)
    - YYYY-MM-DD -> 해당 날짜 23:59:59 (KST)
    - YYYY-MM-DDTHH:MM -> 해당 시각 (KST)
    """
    s = (expires_raw or "").strip()
    if not s:
        return None

    tz = ZoneInfo("Asia/Seoul") if ZoneInfo else None

    try:
        if "T" in s:
            dt = datetime.fromisoformat(s)
            if tz and dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            return dt
        else:
            d = datetime.fromisoformat(s)
            if tz and d.tzinfo is None:
                d = d.replace(tzinfo=tz)
            return d + timedelta(hours=23, minutes=59, seconds=59)
    except Exception:
        return datetime(1970, 1, 1, tzinfo=tz) if tz else datetime(1970, 1, 1)


def _parse_entry_line(line: str):
    """
    지원 포맷:
    1) "label|role|expires|hash"  (권장)
    2) "label:hash"              (기존 호환 -> staff, expires 없음)
    """
    raw = (line or "").strip()
    if not raw:
        return None

    if "|" in raw:
        parts = [p.strip() for p in raw.split("|")]
        label = parts[0] if len(parts) > 0 else ""
        role = parts[1] if len(parts) > 1 else "staff"
        expires = parts[2] if len(parts) > 2 else ""
        h = parts[3] if len(parts) > 3 else ""
        if not label or not h:
            return None
        role = (role or "staff").strip().lower()
        if role not in ("admin", "staff"):
            role = "staff"
        return {"label": label, "role": role, "expires": expires, "hash": h}

    if ":" in raw:
        label, h = raw.split(":", 1)
        label = label.strip()
        h = h.strip()
        if not label or not h:
            return None
        return {"label": label, "role": "staff", "expires": "", "hash": h}

    return None


def _load_auth_secrets():
    """
    Secrets 예시:
    AUTH_ENABLED = true

    ACCESS_CODE_ENTRIES = ["label|role|expires|hash", ...]
    또는 기존:
    ACCESS_CODE_HASHES = ["label:hash", ...]

    REVOKED_LABELS = ["label", ...]

    LOCK_MAX_FAILS = 5
    LOCK_MINUTES = 10
    """
    try:
        enabled = _truthy(st.secrets.get("AUTH_ENABLED", False))
        entries = st.secrets.get("ACCESS_CODE_ENTRIES", None)
        legacy = st.secrets.get("ACCESS_CODE_HASHES", None)
        revoked = st.secrets.get("REVOKED_LABELS", [])
        lock_max_fails = int(st.secrets.get("LOCK_MAX_FAILS", 5))
        lock_minutes = int(st.secrets.get("LOCK_MINUTES", 10))
    except Exception:
        enabled, entries, legacy, revoked, lock_max_fails, lock_minutes = False, [], [], [], 5, 10

    rows = []
    if isinstance(entries, (list, tuple)):
        for x in entries:
            if isinstance(x, str):
                r = _parse_entry_line(x)
                if r:
                    rows.append(r)

    if (not rows) and isinstance(legacy, (list, tuple)):
        for x in legacy:
            if isinstance(x, str):
                r = _parse_entry_line(x)
                if r:
                    rows.append(r)

    revoked_set = set()
    if isinstance(revoked, (list, tuple)):
        revoked_set = set([str(x).strip() for x in revoked if str(x).strip()])

    return enabled, rows, revoked_set, lock_max_fails, lock_minutes


def _lock_remaining_seconds() -> int:
    until = st.session_state.get(STATE_AUTH_LOCK_UNTIL)
    if not until:
        return 0
    try:
        now = _now_kst()
        delta = (until - now).total_seconds()
        return int(delta) if delta > 0 else 0
    except Exception:
        return 0


def require_login():
    enabled, rows, revoked_set, lock_max_fails, lock_minutes = _load_auth_secrets()

    if not enabled:
        st.session_state[STATE_AUTH_OK] = True
        st.session_state[STATE_AUTH_LABEL] = "AUTH_OFF"
        st.session_state[STATE_AUTH_ROLE] = "admin"
        return

    st.session_state.setdefault(STATE_AUTH_FAILS, 0)
    st.session_state.setdefault(STATE_AUTH_LOCK_UNTIL, None)

    if st.session_state.get(STATE_AUTH_OK) is True:
        return

    rem = _lock_remaining_seconds()

    # 로그인 전 스타일
    inject_style(auth_ok=False)

    # 잠금 화면
    if rem > 0:
        mm = rem // 60
        ss = rem % 60
        logo_uri = f"data:image/jpeg;base64,{MISHARP_LOGO_B64}"
        st.markdown(
            f"""
<div class="ms-login">
  <img src="{logo_uri}" style="width:160px;display:block;margin:0 auto 10px auto;border-radius:12px;" />
  <h1 style="text-align:center;">잠금 상태</h1>
  <p style="text-align:center;">로그인 시도 횟수 초과로 잠시 잠겼어요.</p>
  <div style="text-align:center;font-size:16px;font-weight:800;color:rgba(255,255,255,0.95);">
    남은 시간: {mm}분 {ss}초
  </div>
  <p style="text-align:center;margin-top:10px;">조금만 기다렸다가 다시 시도해 주세요.</p>
</div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()

    # 잠금 시간이 지났으면 해제
    st.session_state[STATE_AUTH_LOCK_UNTIL] = None

    logo_uri = f"data:image/jpeg;base64,{MISHARP_LOGO_B64}"
    st.markdown(
        f"""
<div class="ms-login">
  <img src="{logo_uri}" style="width:170px;display:block;margin:0 auto 10px auto;border-radius:12px;" />
  <h1 style="text-align:center;">내부 전용 로그인</h1>
  <p style="text-align:center;">접속 코드를 입력하면 바로 시작돼요.</p>
</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="ms-login-input">', unsafe_allow_html=True)
    code = st.text_input(
        "접속 코드",
        type="password",
        placeholder="MSPGV3-XXXX-XXXX-XXXX",
        key="tmp_code",
        label_visibility="collapsed",
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        login_clicked = st.button("로그인", type="primary", use_container_width=True)
    with c2:
        st.button("지우기", use_container_width=True, on_click=lambda: st.session_state.__setitem__("tmp_code", ""))

    st.caption("ⓒ misharpcompany · 내부 직원 전용")
    st.markdown("</div>", unsafe_allow_html=True)

    if not login_clicked:
        st.stop()

    raw = (code or "").strip().upper()
    raw = re.sub(r"\s+", "", raw)
    if not raw:
        st.error("코드를 입력해 주세요.")
        st.stop()

    entered_hash = _sha256(raw)

    matched = None
    for r in rows:
        if entered_hash == str(r.get("hash", "")).strip():
            matched = r
            break

    if matched is None:
        st.session_state[STATE_AUTH_FAILS] = int(st.session_state.get(STATE_AUTH_FAILS, 0)) + 1
        fails = st.session_state[STATE_AUTH_FAILS]
        if fails >= lock_max_fails:
            st.session_state[STATE_AUTH_FAILS] = 0
            st.session_state[STATE_AUTH_LOCK_UNTIL] = _now_kst() + timedelta(minutes=lock_minutes)
            st.error(f"코드가 올바르지 않아요. {lock_max_fails}회 실패로 {lock_minutes}분 잠금됩니다.")
        else:
            st.error(f"코드가 올바르지 않아요. (실패 {fails}/{lock_max_fails})")
        st.stop()

    label = matched["label"]
    role = matched.get("role", "staff")
    expires_raw = matched.get("expires", "")

    if label in revoked_set:
        st.error("해당 코드는 차단되었습니다. 관리자에게 문의하세요.")
        st.stop()

    exp_dt = _parse_expires(expires_raw)
    if exp_dt is not None:
        now = _now_kst()
        if now > exp_dt:
            st.error("해당 코드는 만료되었습니다. 관리자에게 재발급을 요청하세요.")
            st.stop()

    st.session_state[STATE_AUTH_OK] = True
    st.session_state[STATE_AUTH_LABEL] = label
    st.session_state[STATE_AUTH_ROLE] = role
    st.session_state[STATE_AUTH_FAILS] = 0
    st.session_state[STATE_AUTH_LOCK_UNTIL] = None

    st.success("로그인 성공! 이동합니다.")
    st.rerun()


def sidebar_auth_box():
    with st.sidebar:
        st.markdown("### 접근 상태")
        st.caption(f"label: **{st.session_state.get(STATE_AUTH_LABEL, '-') }**")
        st.caption(f"role: **{st.session_state.get(STATE_AUTH_ROLE, '-') }**")
        if st.button("로그아웃", use_container_width=True):
            st.session_state.pop(STATE_AUTH_OK, None)
            st.session_state.pop(STATE_AUTH_LABEL, None)
            st.session_state.pop(STATE_AUTH_ROLE, None)
            st.session_state.pop(STATE_AUTH_FAILS, None)
            st.session_state.pop(STATE_AUTH_LOCK_UNTIL, None)
            st.session_state.pop("tmp_code", None)
            st.rerun()


# =========================================================
# IMAGE UTIL
# =========================================================
@dataclass
class ImgItem:
    name: str
    bytes_data: bytes
    pil: Image.Image
    ext: str
    sha1: str


def _sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _sanitize_filename(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return "misharp_detailpage"
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^0-9A-Za-z가-힣_\-]+", "", name)
    return name[:80] or "misharp_detailpage"


def _is_image_filename(fn: str) -> bool:
    fn_l = fn.lower()
    return fn_l.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))


def _open_image_any(data: bytes) -> Image.Image:
    im = Image.open(io.BytesIO(data))
    if getattr(im, "is_animated", False):
        frame0 = next(ImageSequence.Iterator(im))
        im = frame0.copy()
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    return im


def _fit_to_width_900(im: Image.Image, width: int = CANVAS_WIDTH) -> Image.Image:
    w, h = im.size
    if w == width:
        return im.convert("RGB") if im.mode != "RGB" else im
    scale = width / float(w)
    new_h = int(round(h * scale))
    resized = im.resize((width, new_h), resample=Image.Resampling.LANCZOS)
    return resized.convert("RGB")


def _make_thumb(im: Image.Image, w: int = THUMB_W) -> bytes:
    thumb = im.copy()
    scale = w / float(thumb.size[0])
    th = max(1, int(round(thumb.size[1] * scale)))
    thumb = thumb.resize((w, th), resample=Image.Resampling.LANCZOS)
    out = io.BytesIO()
    thumb.save(out, format="PNG")
    return out.getvalue()


def _extract_zip_images(zip_bytes: bytes) -> List[Tuple[str, bytes]]:
    out: List[Tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if _is_image_filename(name):
                out.append((os.path.basename(name), zf.read(info)))
    return out


def _compose_long_jpg(resized_images: List[Image.Image], top_pad: int, bottom_pad: int, gap: int) -> Image.Image:
    heights = [im.size[1] for im in resized_images]
    total_h = top_pad + bottom_pad + sum(heights) + gap * (len(resized_images) - 1)

    canvas = Image.new("RGB", (CANVAS_WIDTH, total_h), color=(255, 255, 255))
    y = top_pad
    for idx, im in enumerate(resized_images):
        canvas.paste(im, (0, y))
        y += im.size[1]
        if idx != len(resized_images) - 1:
            y += gap
    return canvas


def _save_jpg_bytes(im: Image.Image) -> bytes:
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=95, subsampling=0, optimize=True)
    return out.getvalue()


def _calc_total_height(resized_heights: List[int], top_pad: int, bottom_pad: int, gap: int) -> int:
    if not resized_heights:
        return 0
    return top_pad + bottom_pad + sum(resized_heights) + gap * (len(resized_heights) - 1)


def _build_jsx(
    base_name: str,
    canvas_h: int,
    top_pad: int,
    gap: int,
    heights: List[int],
    image_files: List[str],
    images_folder_name: str,
) -> str:
    y_positions = []
    y = top_pad
    for h in heights:
        y_positions.append(y)
        y += h + gap

    lines = []
    lines.append("#target photoshop")
    lines.append("app.displayDialogs = DialogModes.NO;")
    lines.append("")
    lines.append("var _oldRulerUnits = app.preferences.rulerUnits;")
    lines.append("var _oldTypeUnits  = app.preferences.typeUnits;")
    lines.append("app.preferences.rulerUnits = Units.PIXELS;")
    lines.append("app.preferences.typeUnits  = TypeUnits.PIXELS;")
    lines.append("function _restoreUnits(){ app.preferences.rulerUnits=_oldRulerUnits; app.preferences.typeUnits=_oldTypeUnits; }")
    lines.append("")
    lines.append("function placeSmartObject(file){")
    lines.append("  var desc=new ActionDescriptor();")
    lines.append('  desc.putPath(charIDToTypeID("null"), file);')
    lines.append('  desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcs0"));')
    lines.append("  var ofs=new ActionDescriptor();")
    lines.append('  ofs.putUnitDouble(charIDToTypeID("Hrzn"), charIDToTypeID("#Pxl"), 0);')
    lines.append('  ofs.putUnitDouble(charIDToTypeID("Vrtc"), charIDToTypeID("#Pxl"), 0);')
    lines.append('  desc.putObject(charIDToTypeID("Ofst"), charIDToTypeID("Ofst"), ofs);')
    lines.append('  executeAction(charIDToTypeID("Plc "), desc, DialogModes.NO);')
    lines.append("}")
    lines.append("")
    lines.append("function safeTranslate(layer, dx, dy){")
    lines.append("  var maxStep=5000;")
    lines.append("  var sx=dx, sy=dy;")
    lines.append("  while(Math.abs(sx)>maxStep || Math.abs(sy)>maxStep){")
    lines.append("    var stepX=Math.max(-maxStep, Math.min(maxStep, sx));")
    lines.append("    var stepY=Math.max(-maxStep, Math.min(maxStep, sy));")
    lines.append("    layer.translate(stepX, stepY);")
    lines.append("    sx-=stepX; sy-=stepY;")
    lines.append("  }")
    lines.append("  if(sx!==0 || sy!==0) layer.translate(sx, sy);")
    lines.append("}")
    lines.append("")
    lines.append("function moveLayerToXY(layer, x, y){")
    lines.append("  var b=layer.bounds;")
    lines.append('  var left=b[0].as("px");')
    lines.append('  var top=b[1].as("px");')
    lines.append("  safeTranslate(layer, x-left, y-top);")
    lines.append("}")
    lines.append("")
    lines.append("try {")
    lines.append("  var jsxFile=new File($.fileName);")
    lines.append("  var baseFolder=jsxFile.parent;")
    lines.append(f'  var imgFolder=new Folder(baseFolder.fsName + "/{images_folder_name}");')
    lines.append('  if(!imgFolder.exists){ alert("이미지 폴더 없음: " + imgFolder.fsName); throw new Error("Missing images folder"); }')
    lines.append(f'  var doc=app.documents.add({CANVAS_WIDTH}, {canvas_h}, 72, "{base_name}", NewDocumentMode.RGB, DocumentFill.WHITE);')
    lines.append("  var files=[];")
    for fn in image_files:
        lines.append(f'  files.push(new File(imgFolder.fsName + "/{fn}"));')
    lines.append("  var ys=[")
    for i, yp in enumerate(y_positions):
        comma = "," if i != len(y_positions) - 1 else ""
        lines.append(f"    {int(yp)}{comma}")
    lines.append("  ];")
    lines.append("  for(var i=0;i<files.length;i++){")
    lines.append("    if(!files[i].exists){ alert('이미지 파일 없음: ' + files[i].fsName); throw new Error('Missing file'); }")
    lines.append("    placeSmartObject(files[i]);")
    lines.append("    var layer=doc.activeLayer;")
    lines.append("    moveLayerToXY(layer, 0, ys[i]);")
    lines.append('    layer.name="IMG_" + (i+1);')
    lines.append("  }")
    lines.append(f'  var outPsd=new File(baseFolder.fsName + "/{base_name}.psd");')
    lines.append("  var psdOpt=new PhotoshopSaveOptions();")
    lines.append("  psdOpt.embedColorProfile=true;")
    lines.append("  psdOpt.maximizeCompatibility=true;")
    lines.append("  doc.saveAs(outPsd, psdOpt, true, Extension.LOWERCASE);")
    lines.append('  alert("PSD 생성 완료: " + outPsd.fsName);')
    lines.append("} catch(e) { alert('PSD 생성 오류: ' + e); } finally { _restoreUnits(); }")
    return "\n".join(lines)


def _build_readme() -> str:
    return (
        "MISHARP 상세페이지 생성기 (내부용)\n\n"
        "[규칙]\n"
        "- JPG: 전체 이미지 1장으로 생성\n"
        f"- PSD: {MAX_PER_PSD}장 초과 시 자동 2개로 분할\n"
        f"- 최대 등록: {MAX_TOTAL_IMAGES}장\n\n"
        "[PSD 생성 방법]\n"
        "1) ZIP 압축 해제\n"
        "2) Photoshop 실행(CS 이상 권장)\n"
        "3) 파일 > 스크립트 > 찾아보기...\n"
        "4) *_psd_build.jsx 실행\n"
        "5) 같은 폴더에 .psd 생성\n\n"
        "ⓒ misharpcompany. All rights reserved.\n"
    )


def _zip_bundle(
    base_name: str,
    jpg_bytes: bytes,
    jsx_entries: List[Tuple[str, str]],
    resized_groups: List[Tuple[str, List[Tuple[str, bytes]]]],
) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{base_name}.jpg", jpg_bytes)
        zf.writestr("README.txt", _build_readme())
        for jsx_name, jsx_text in jsx_entries:
            zf.writestr(jsx_name, jsx_text)
        for folder_name, files in resized_groups:
            for fn, b in files:
                zf.writestr(f"{folder_name}/{fn}", b)
    return out.getvalue()


def _init_state():
    st.session_state.setdefault(STATE_ITEMS, [])
    st.session_state.setdefault(STATE_SEEN, set())
    st.session_state.setdefault(STATE_LAST_PREVIEW, None)
    st.session_state.setdefault(STATE_LAST_ZIP, None)
    st.session_state.setdefault(STATE_LAST_META, None)


def _reset_all():
    st.session_state[STATE_ITEMS] = []
    st.session_state[STATE_SEEN] = set()
    st.session_state[STATE_LAST_PREVIEW] = None
    st.session_state[STATE_LAST_ZIP] = None
    st.session_state[STATE_LAST_META] = None


def _add_one_image(name: str, raw: bytes) -> bool:
    h = _sha1(raw)
    seen = st.session_state[STATE_SEEN]
    if h in seen:
        return False
    im = _open_image_any(raw)
    ext = os.path.splitext(name)[1].lower().lstrip(".") or "jpg"
    st.session_state[STATE_ITEMS].append(ImgItem(name=name, bytes_data=raw, pil=im, ext=ext, sha1=h))
    seen.add(h)
    st.session_state[STATE_SEEN] = seen
    return True


def _add_items_from_uploads(uploaded_files) -> Tuple[int, int]:
    added = 0
    skipped_over_limit = 0

    for uf in uploaded_files:
        remaining = MAX_TOTAL_IMAGES - len(st.session_state[STATE_ITEMS])
        if remaining <= 0:
            skipped_over_limit += 1
            continue

        raw = uf.getvalue()
        name = uf.name

        if name.lower().endswith(".zip"):
            extracted = _extract_zip_images(raw)
            for iname, ibytes in extracted:
                remaining = MAX_TOTAL_IMAGES - len(st.session_state[STATE_ITEMS])
                if remaining <= 0:
                    skipped_over_limit += 1
                    break
                if _add_one_image(iname, ibytes):
                    added += 1
        else:
            if _add_one_image(name, raw):
                added += 1

    return added, skipped_over_limit


def _build_outputs(base_name: str, top_pad: int, bottom_pad: int, gap: int):
    items: List[ImgItem] = st.session_state[STATE_ITEMS]

    uniq: List[ImgItem] = []
    seen2 = set()
    for it in items:
        if it.sha1 in seen2:
            continue
        uniq.append(it)
        seen2.add(it.sha1)

    resized_all = [_fit_to_width_900(it.pil) for it in uniq]
    heights_all = [im.size[1] for im in resized_all]

    long_img = _compose_long_jpg(resized_all, top_pad=top_pad, bottom_pad=bottom_pad, gap=gap)
    jpg_bytes = _save_jpg_bytes(long_img)

    if len(resized_all) <= MAX_PER_PSD:
        parts = [resized_all]
    else:
        parts = [resized_all[:MAX_PER_PSD], resized_all[MAX_PER_PSD:]]

    jsx_entries: List[Tuple[str, str]] = []
    resized_groups: List[Tuple[str, List[Tuple[str, bytes]]]] = []

    for pi, part_imgs in enumerate(parts, start=1):
        part_heights = [im.size[1] for im in part_imgs]
        part_canvas_h = _calc_total_height(part_heights, top_pad, bottom_pad, gap)

        part_suffix = f"part{pi}"
        part_base = f"{base_name}_{part_suffix}" if len(parts) > 1 else base_name
        folder_name = f"images_{part_suffix}" if len(parts) > 1 else "images"

        files: List[Tuple[str, bytes]] = []
        fns: List[str] = []
        for idx, im in enumerate(part_imgs, start=1):
            fn = f"img_{idx:02d}.jpg"
            files.append((fn, _save_jpg_bytes(im)))
            fns.append(fn)

        resized_groups.append((folder_name, files))

        jsx_text = _build_jsx(
            base_name=part_base,
            canvas_h=part_canvas_h,
            top_pad=top_pad,
            gap=gap,
            heights=part_heights,
            image_files=fns,
            images_folder_name=folder_name,
        )
        jsx_entries.append((f"{part_base}_psd_build.jsx", jsx_text))

    meta = {
        "count": len(resized_all),
        "total_height": _calc_total_height(heights_all, top_pad, bottom_pad, gap),
        "top": top_pad,
        "bottom": bottom_pad,
        "gap": gap,
        "psd_parts": len(parts),
        "max_total": MAX_TOTAL_IMAGES,
        "max_per_psd": MAX_PER_PSD,
    }

    zip_bytes = _zip_bundle(base_name, jpg_bytes, jsx_entries, resized_groups)
    return jpg_bytes, zip_bytes, meta


# =========================================================
# UI
# =========================================================
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")

    # 로그인 (로그인 전 스타일은 require_login 내부에서 주입)
    require_login()

    # 로그인 후 스타일
    inject_style(auth_ok=True)

    sidebar_auth_box()
    _init_state()

    # Top title
    st.markdown(
        f"""
<div style="padding:6px 0 2px 0;">
  <div class="ms-top-title">{APP_TITLE}</div>
  <div class="ms-top-sub">{APP_SUBTITLE}</div>
</div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.25, 0.75], gap="large")

    with left:
        # 1) Upload
        ms_section("1) 업로드")
        cA, cB = st.columns([0.66, 0.34])
        with cA:
            uploaded = st.file_uploader(
                "JPG / PNG / GIF / WEBP / ZIP 업로드 가능",
                type=["jpg", "jpeg", "png", "gif", "webp", "zip"],
                accept_multiple_files=True,
                label_visibility="collapsed",
                key="uploader",
            )
        with cB:
            replace_mode = st.checkbox("기존 목록 비우고 새로 담기", value=False)

        # ✅ 업로드 파일을 한 줄로(최대 10개) 보여주는 영역 (요청사항)
        if uploaded:
            st.caption("업로드 선택 파일(최대 10개 표시)")
            render_uploaded_list_row(uploaded, max_show=10)

        current_count = len(st.session_state[STATE_ITEMS])
        st.caption(f"현재 목록: {current_count}/{MAX_TOTAL_IMAGES}장")

        add_clicked = st.button(
            "업로드 파일 목록에 추가",
            type="primary",
            use_container_width=True,
            disabled=(not uploaded) and (not replace_mode),
        )

        if add_clicked and uploaded:
            if replace_mode:
                _reset_all()
                current_count = 0

            added, skipped_limit = _add_items_from_uploads(uploaded)
            if added == 0:
                st.warning("추가된 새 이미지가 없습니다. (중복 제외 또는 제한 초과)")
            else:
                st.success(f"추가 완료: 새 이미지 {added}개")

            if skipped_limit > 0:
                st.warning(f"최대 {MAX_TOTAL_IMAGES}장 제한으로 {skipped_limit}개 파일(또는 ZIP 내 이미지)이 추가되지 않았습니다.")

        # 2) Layout settings
        ms_section("2) 레이아웃 설정")
        c1, c2 = st.columns([0.58, 0.42])
        with c1:
            base_name_raw = st.text_input("파일명(확장자 제외)", value="misharp_detailpage")
        with c2:
            gap = st.number_input("이미지 간 여백(px)", min_value=0, max_value=2000, value=DEFAULT_GAP, step=10)

        base_name = _sanitize_filename(base_name_raw)

        with st.expander("상단/하단 여백(기본값은 샘플 기준)", expanded=False):
            top_pad = st.number_input("상단 여백(px)", min_value=0, max_value=5000, value=DEFAULT_TOP_PAD, step=10)
            bottom_pad = st.number_input("하단 여백(px)", min_value=0, max_value=5000, value=DEFAULT_BOTTOM_PAD, step=10)

        # 3) Reorder / delete
        ms_section("3) 순서 변경 / 삭제")
        items: List[ImgItem] = st.session_state[STATE_ITEMS]

        if not items:
            st.info("업로드된 이미지가 없습니다.")
        else:
            for i, it in enumerate(items):
                row = st.columns([0.14, 0.56, 0.10, 0.10, 0.10])
                with row[0]:
                    st.image(_make_thumb(it.pil), use_column_width=True)
                with row[1]:
                    short = it.name if len(it.name) <= 44 else (it.name[:41] + "…")
                    st.markdown(f"**{i+1}. {short}**  \n원본: {it.pil.size[0]}×{it.pil.size[1]}")
                with row[2]:
                    up = st.button("▲", key=f"up_{i}", disabled=(i == 0), use_container_width=True)
                with row[3]:
                    down = st.button("▼", key=f"down_{i}", disabled=(i == len(items) - 1), use_container_width=True)
                with row[4]:
                    delete = st.button("삭제", key=f"del_{i}", use_container_width=True)

                if up:
                    items[i - 1], items[i] = items[i], items[i - 1]
                    st.session_state[STATE_ITEMS] = items
                    st.rerun()
                if down:
                    items[i + 1], items[i] = items[i], items[i + 1]
                    st.session_state[STATE_ITEMS] = items
                    st.rerun()
                if delete:
                    removed = items.pop(i)
                    st.session_state[STATE_ITEMS] = items
                    seen = st.session_state[STATE_SEEN]
                    if removed.sha1 in seen:
                        seen.remove(removed.sha1)
                    st.session_state[STATE_SEEN] = seen
                    st.rerun()

        st.divider()

        cX, cY = st.columns([0.72, 0.28])
        with cX:
            disabled = (len(st.session_state[STATE_ITEMS]) == 0) or (not base_name.strip())
            gen = st.button("상세페이지 생성하기", type="primary", use_container_width=True, disabled=disabled)
        with cY:
            if st.button("전체 초기화", use_container_width=True):
                _reset_all()
                st.rerun()

        if gen:
            jpg_bytes, zip_bytes, meta = _build_outputs(base_name, int(top_pad), int(bottom_pad), int(gap))
            st.session_state[STATE_LAST_PREVIEW] = jpg_bytes
            st.session_state[STATE_LAST_ZIP] = zip_bytes
            st.session_state[STATE_LAST_META] = meta
            st.success("생성 완료! 오른쪽에서 미리보기/다운로드 하세요.")

    with right:
        ms_section("미리보기")
        meta = st.session_state[STATE_LAST_META]
        jpg_bytes = st.session_state[STATE_LAST_PREVIEW]
        zip_bytes = st.session_state[STATE_LAST_ZIP]

        if meta and jpg_bytes:
            parts_txt = "1개" if meta.get("psd_parts", 1) == 1 else f"{meta['psd_parts']}개(자동 분할)"
            st.caption(
                f"총 {meta['count']}장 · 최종 높이 {meta['total_height']:,}px · "
                f"상단 {meta['top']} / 하단 {meta['bottom']} / 간격 {meta['gap']}px · PSD: {parts_txt}"
            )
            st.image(jpg_bytes, use_column_width=True)

            ms_section("다운로드")
            st.download_button(
                "JPG 다운로드",
                data=jpg_bytes,
                file_name=f"{base_name}.jpg",
                mime="image/jpeg",
                use_container_width=True,
            )
            st.download_button(
                "ZIP(PSD용 JSX + images 포함) 다운로드",
                data=zip_bytes,
                file_name=f"{base_name}_bundle.zip",
                mime="application/zip",
                use_container_width=True,
            )
        else:
            st.info("아직 생성된 결과가 없습니다. 왼쪽에서 생성 버튼을 눌러주세요.")

        with st.expander("사용방법", expanded=True):
            st.markdown(
                f"""
**업로드 규칙**
- 권장: 보통 5장 내외
- 최대: {MAX_TOTAL_IMAGES}장까지 목록 등록 가능
- {MAX_PER_PSD}장 초과 시: PSD는 자동으로 2개로 분할 생성

**사용 순서**
1) 업로드 → ‘업로드 파일 목록에 추가’  
2) 순서/여백 확인  
3) ‘상세페이지 생성하기’ → 오른쪽에서 다운로드

**PSD 만들기(중요)**
1) ZIP 압축 해제  
2) Photoshop 실행(CS 이상 권장)  
3) `파일 > 스크립트 > 찾아보기...`  
4) `*_psd_build.jsx` 실행  
→ Smart Object PSD 생성
                """.strip()
            )

        st.divider()
        st.caption(
            "ⓒ misharpcompany. All rights reserved.\n"
            "본 프로그램은 미샵컴퍼니 내부 직원 전용입니다. 외부 유출 및 제3자 제공을 금합니다."
        )


if __name__ == "__main__":
    main()
