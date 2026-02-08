import io
import os
import zipfile
from dataclasses import dataclass
from typing import List, Tuple, Optional

import streamlit as st
from PIL import Image, ImageSequence

APP_TITLE = "MISHARP 상세페이지 생성기"
APP_SUBTITLE = "MISHARP PSD GENERATOR V3"

CANVAS_WIDTH = 900

# 첨부 상세페이지(샘플) 기반: (267px 폭 프리뷰에서 상단 54px, 하단 74px 관측)
# 900px로 환산(900/267≈3.37) → 상단≈182px, 하단≈249px → 깔끔히 라운딩
DEFAULT_TOP_PAD = 180
DEFAULT_BOTTOM_PAD = 250
DEFAULT_GAP = 300

THUMB_W = 140


@dataclass
class ImgItem:
    name: str
    bytes_data: bytes
    pil: Image.Image  # 원본(또는 gif 1프레임) PIL
    ext: str


def _is_image_filename(fn: str) -> bool:
    fn_l = fn.lower()
    return fn_l.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))


def _open_image_any(data: bytes) -> Image.Image:
    """색보정/필터 없이 로딩. gif는 첫 프레임만 사용(요구: 다양한 입력 허용)."""
    im = Image.open(io.BytesIO(data))
    # GIF(애니메이션)일 경우 첫 프레임만
    if getattr(im, "is_animated", False):
        frame0 = next(ImageSequence.Iterator(im))
        im = frame0.copy()
    # 색상은 보정 금지. 다만 JPG 저장 위해 RGB로만 변환.
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    return im


def _fit_to_width_900(im: Image.Image, width: int = CANVAS_WIDTH) -> Image.Image:
    """자르기 금지. 비율 유지 리사이즈만."""
    w, h = im.size
    if w == width:
        return im.convert("RGB") if im.mode != "RGB" else im
    scale = width / float(w)
    new_h = int(round(h * scale))
    # LANCZOS: 리사이즈 품질 좋고, 색보정은 아님
    resized = im.resize((width, new_h), resample=Image.Resampling.LANCZOS)
    return resized.convert("RGB")


def _make_thumb(im: Image.Image, w: int = THUMB_W) -> bytes:
    thumb = im.copy()
    tw = w
    scale = tw / float(thumb.size[0])
    th = max(1, int(round(thumb.size[1] * scale)))
    thumb = thumb.resize((tw, th), resample=Image.Resampling.LANCZOS)
    out = io.BytesIO()
    thumb.save(out, format="PNG")
    return out.getvalue()


def _extract_zip_images(zip_bytes: bytes) -> List[Tuple[str, bytes]]:
    """ZIP을 자동 해제해 이미지 파일만 추출(업로드 순서 유지: zip 내부 순서)."""
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
    if not resized_images:
        raise ValueError("No images")
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


def _build_jsx(
    base_name: str,
    top_pad: int,
    bottom_pad: int,
    gap: int,
    heights: List[int],
    image_files: List[str],
) -> str:
    """
    Photoshop ExtendScript(JSX):
    - 현재 jsx 위치 기준 ./images/ 폴더의 파일들을
    - 새 문서(900 x totalHeight)에 Smart Object로 place
    - PSD 저장
    """
    # 누적 y 계산
    y_positions = []
    y = top_pad
    for h in heights:
        y_positions.append(y)
        y += h + gap
    total_h = top_pad + bottom_pad + sum(heights) + gap * (len(heights) - 1)

    # JSX는 배열/숫자만 정확히 박아주면 디버깅 쉬움
    lines = []
    lines.append('#target photoshop')
    lines.append('app.displayDialogs = DialogModes.NO;')
    lines.append('')
    lines.append('function placeSmartObject(file) {')
    lines.append('  var desc = new ActionDescriptor();')
    lines.append('  desc.putPath(charIDToTypeID("null"), file);')
    lines.append('  desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcs0"));')
    lines.append('  var ofs = new ActionDescriptor();')
    lines.append('  ofs.putUnitDouble(charIDToTypeID("Hrzn"), charIDToTypeID("#Pxl"), 0);')
    lines.append('  ofs.putUnitDouble(charIDToTypeID("Vrtc"), charIDToTypeID("#Pxl"), 0);')
    lines.append('  desc.putObject(charIDToTypeID("Ofst"), charIDToTypeID("Ofst"), ofs);')
    lines.append('  executeAction(charIDToTypeID("Plc "), desc, DialogModes.NO);')
    lines.append('}')
    lines.append('')
    lines.append('function moveLayerToXY(layer, x, y) {')
    lines.append('  var b = layer.bounds;')
    lines.append('  var left = b[0].as("px");')
    lines.append('  var top = b[1].as("px");')
    lines.append('  layer.translate(x - left, y - top);')
    lines.append('}')
    lines.append('')
    lines.append('var jsxFile = new File($.fileName);')
    lines.append('var baseFolder = jsxFile.parent;')
    lines.append('var imgFolder = new Folder(baseFolder.fsName + "/images");')
    lines.append('if (!imgFolder.exists) { alert("images 폴더를 찾을 수 없습니다: " + imgFolder.fsName); throw new Error("Missing images folder"); }')
    lines.append('')
    lines.append(f'var doc = app.documents.add({CANVAS_WIDTH}, {total_h}, 72, "{base_name}", NewDocumentMode.RGB, DocumentFill.WHITE);')
    lines.append('')
    lines.append('var files = [];')
    for fn in image_files:
        # 안전하게 파일명만 사용 (상대경로)
        lines.append(f'files.push(new File(imgFolder.fsName + "/{fn}"));')
    lines.append('')
    lines.append('for (var i = 0; i < files.length; i++) {')
    lines.append('  if (!files[i].exists) { alert("이미지 파일 없음: " + files[i].fsName); throw new Error("Missing file"); }')
    lines.append('  placeSmartObject(files[i]);')
    lines.append('  var layer = doc.activeLayer;')
    lines.append('  // x=0, y=계산값으로 이동 (이미지 폭 900px로 맞춰져 있어야 함)')
    lines.append('  var ys = [')
    for i, yp in enumerate(y_positions):
        comma = "," if i != len(y_positions) - 1 else ""
        lines.append(f'    {int(yp)}{comma}')
    lines.append('  ];')
    lines.append('  moveLayerToXY(layer, 0, ys[i]);')
    lines.append('  layer.name = "IMG_" + (i+1);')
    lines.append('}')
    lines.append('')
    lines.append(f'var outPsd = new File(baseFolder.fsName + "/{base_name}.psd");')
    lines.append('var psdOpt = new PhotoshopSaveOptions();')
    lines.append('psdOpt.embedColorProfile = true;')
    lines.append('psdOpt.maximizeCompatibility = true;')
    lines.append('doc.saveAs(outPsd, psdOpt, true, Extension.LOWERCASE);')
    lines.append('alert("PSD 생성 완료: " + outPsd.fsName);')

    return "\n".join(lines)


def _build_readme() -> str:
    return (
        "MISHARP 상세페이지 생성기 (내부용)\n"
        "\n"
        "[다운로드 ZIP 구성]\n"
        "1) 상세페이지 JPG\n"
        "2) PSD 생성용 JSX (Smart Object 유지)\n"
        "3) images/ 폴더 (PSD에 들어갈 900px 리사이즈 이미지)\n"
        "\n"
        "[PSD 생성 방법]\n"
        "1) ZIP 압축 해제\n"
        "2) Adobe Photoshop 실행 (CS 이상 권장)\n"
        "3) 파일 > 스크립트 > 찾아보기...\n"
        "4) *_psd_build.jsx 선택 후 실행\n"
        "5) 같은 폴더에 .psd가 생성됩니다.\n"
        "\n"
        "ⓒ misharpcompany. All rights reserved.\n"
        "본 프로그램은 미샵컴퍼니 내부 직원 전용입니다.\n"
    )


def _zip_bundle(
    base_name: str,
    jpg_bytes: bytes,
    jsx_text: str,
    resized_jpgs: List[Tuple[str, bytes]],
) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{base_name}.jpg", jpg_bytes)
        zf.writestr(f"{base_name}_psd_build.jsx", jsx_text)
        zf.writestr("README.txt", _build_readme())
        for fn, b in resized_jpgs:
            zf.writestr(f"images/{fn}", b)
    return out.getvalue()


def _init_state():
    if "items" not in st.session_state:
        st.session_state.items = []  # List[ImgItem]


def _add_items_from_uploads(uploaded_files):
    new_items: List[ImgItem] = []
    for uf in uploaded_files:
        raw = uf.read()
        name = uf.name
        if name.lower().endswith(".zip"):
            for iname, ibytes in _extract_zip_images(raw):
                im = _open_image_any(ibytes)
                ext = os.path.splitext(iname)[1].lower().lstrip(".") or "jpg"
                new_items.append(ImgItem(name=iname, bytes_data=ibytes, pil=im, ext=ext))
        else:
            im = _open_image_any(raw)
            ext = os.path.splitext(name)[1].lower().lstrip(".") or "jpg"
            new_items.append(ImgItem(name=name, bytes_data=raw, pil=im, ext=ext))

    st.session_state.items.extend(new_items)


def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")

    _init_state()

    # ===== Header =====
    st.markdown(
        f"""
        <div style="padding:14px 0 6px 0;">
          <div style="font-size:28px; font-weight:800; letter-spacing:-0.5px;">{APP_TITLE}</div>
          <div style="font-size:13px; opacity:0.7; margin-top:2px;">{APP_SUBTITLE}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.35, 0.65], gap="large")

    # ===== Left: Builder =====
    with left:
        st.subheader("1) 이미지 업로드")
        uploaded = st.file_uploader(
            "JPG / PNG / GIF / WEBP / ZIP 업로드 가능 (여러 개 선택 가능)",
            type=["jpg", "jpeg", "png", "gif", "webp", "zip"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
        if uploaded:
            _add_items_from_uploads(uploaded)
            st.success(f"추가됨: {len(uploaded)}개 업로드 항목 처리 완료")

        c1, c2, c3 = st.columns([0.45, 0.3, 0.25])
        with c1:
            base_name = st.text_input("파일명(기본)", value="misharp_detailpage", help="생성될 JPG/PSD 파일명(확장자 제외)")
        with c2:
            gap = st.number_input("이미지 간 여백(px)", min_value=0, max_value=2000, value=DEFAULT_GAP, step=10)
        with c3:
            st.write("")
            st.write("")
            if st.button("전체 삭제(초기화)", use_container_width=True):
                st.session_state.items = []
                st.rerun()

        with st.expander("상단/하단 여백 (기본값은 샘플 상세페이지 기준)", expanded=False):
            top_pad = st.number_input("상단 여백(px)", min_value=0, max_value=5000, value=DEFAULT_TOP_PAD, step=10)
            bottom_pad = st.number_input("하단 여백(px)", min_value=0, max_value=5000, value=DEFAULT_BOTTOM_PAD, step=10)

        if "top_pad" not in locals():
            top_pad = DEFAULT_TOP_PAD
        if "bottom_pad" not in locals():
            bottom_pad = DEFAULT_BOTTOM_PAD

        st.divider()
        st.subheader("2) 순서 변경 / 삭제")

        items: List[ImgItem] = st.session_state.items
        if not items:
            st.info("업로드된 이미지가 없습니다.")
        else:
            # 썸네일 + 순서 변경 UI
            for i, it in enumerate(list(items)):
                row = st.columns([0.18, 0.52, 0.10, 0.10, 0.10])
                with row[0]:
                    st.image(_make_thumb(it.pil), caption="", use_column_width=True)
                with row[1]:
                    st.markdown(f"**{i+1}. {it.name}**  \n원본크기: {it.pil.size[0]}×{it.pil.size[1]}")
                with row[2]:
                    up = st.button("▲", key=f"up_{i}", disabled=(i == 0), use_container_width=True)
                with row[3]:
                    down = st.button("▼", key=f"down_{i}", disabled=(i == len(items) - 1), use_container_width=True)
                with row[4]:
                    delete = st.button("삭제", key=f"del_{i}", use_container_width=True)

                if up:
                    items[i - 1], items[i] = items[i], items[i - 1]
                    st.session_state.items = items
                    st.rerun()
                if down:
                    items[i + 1], items[i] = items[i], items[i + 1]
                    st.session_state.items = items
                    st.rerun()
                if delete:
                    items.pop(i)
                    st.session_state.items = items
                    st.rerun()

        st.divider()
        st.subheader("3) 생성 & 다운로드")

        disabled = len(st.session_state.items) == 0 or not base_name.strip()
        gen = st.button("상세페이지 생성하기", type="primary", use_container_width=True, disabled=disabled)

        if gen:
            # 1) 리사이즈(900폭), 2) 합치기(JPG), 3) JSX 생성, 4) ZIP 생성
            resized = [_fit_to_width_900(it.pil) for it in st.session_state.items]
            heights = [im.size[1] for im in resized]

            long_img = _compose_long_jpg(resized, top_pad=int(top_pad), bottom_pad=int(bottom_pad), gap=int(gap))
            jpg_bytes = _save_jpg_bytes(long_img)

            # PSD용 이미지 저장은 JPG로 통일(포토샵 place 안정성 높음)
            resized_files: List[Tuple[str, bytes]] = []
            image_filenames: List[str] = []
            for idx, im in enumerate(resized, start=1):
                fn = f"img_{idx:02d}.jpg"
                b = _save_jpg_bytes(im)
                resized_files.append((fn, b))
                image_filenames.append(fn)

            jsx = _build_jsx(
                base_name=base_name.strip(),
                top_pad=int(top_pad),
                bottom_pad=int(bottom_pad),
                gap=int(gap),
                heights=heights,
                image_files=image_filenames,
            )

            zip_bytes = _zip_bundle(
                base_name=base_name.strip(),
                jpg_bytes=jpg_bytes,
                jsx_text=jsx,
                resized_jpgs=resized_files,
            )

            st.success("생성 완료! 아래에서 다운로드하세요.")
            st.download_button(
                "JPG 다운로드",
                data=jpg_bytes,
                file_name=f"{base_name.strip()}.jpg",
                mime="image/jpeg",
                use_container_width=True,
            )
            st.download_button(
                "JPG + PSD용 JSX + images 폴더 ZIP 다운로드",
                data=zip_bytes,
                file_name=f"{base_name.strip()}_bundle.zip",
                mime="application/zip",
                use_container_width=True,
            )

    # ===== Right: How to / Policy / Footer =====
    with right:
        st.subheader("사용방법")
        st.markdown(
            """
- **이미지 업로드**: JPG/PNG/GIF/WEBP 또는 ZIP 가능  
- **순서 변경**: 썸네일 옆 ▲▼ 버튼  
- **여백 조절**: 이미지 간 여백 / 상단·하단 여백  
- **다운로드**: JPG 또는 ZIP(PSD용 JSX 포함)

**PSD 만들기(중요)**  
1) ZIP 압축 해제  
2) Photoshop 실행(CS 이상)  
3) `파일 > 스크립트 > 찾아보기...`  
4) `*_psd_build.jsx` 실행  
→ Smart Object 레이어가 살아있는 PSD가 생성됩니다.
            """.strip()
        )

        st.divider()
        st.caption(
            "ⓒ misharpcompany. All rights reserved.\n"
            "본 프로그램의 저작권은 미샵컴퍼니(misharpcompany)에 있으며, 무단 복제·배포·사용을 금합니다.\n"
            "본 프로그램은 미샵컴퍼니 내부 직원 전용으로, 외부 유출 및 제3자 제공을 엄격히 금합니다.\n\n"
            "ⓒ misharpcompany. All rights reserved.\n"
            "This program is the intellectual property of misharpcompany. Unauthorized copying, distribution, or use is strictly prohibited.\n"
            "This program is for internal use by misharpcompany employees only and must not be disclosed or shared externally."
        )


if __name__ == "__main__":
    main()
