import io
import os
import re
import zipfile
import hashlib
from dataclasses import dataclass
from typing import List, Tuple

import streamlit as st
from PIL import Image, ImageSequence

APP_TITLE = "MISHARP 상세페이지 생성기"
APP_SUBTITLE = "MISHARP PSD GENERATOR V3"

CANVAS_WIDTH = 900

# ✅ 분할 규칙
MAX_PER_PSD = 10          # PSD 1개당 최대 10장
MAX_TOTAL_IMAGES = 20     # 전체 최대 20장(10장 초과 시 PSD 2개로 분할)

DEFAULT_TOP_PAD = 180
DEFAULT_BOTTOM_PAD = 250
DEFAULT_GAP = 300

# ✅ 썸네일 크기 절반
THUMB_W = 70

STATE_ITEMS = "img_items"
STATE_SEEN = "seen_hashes"
STATE_LAST_PREVIEW = "last_preview_jpg"
STATE_LAST_ZIP = "last_bundle_zip"
STATE_LAST_META = "last_meta"


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
    name = name.strip()
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


def _build_jsx(base_name: str, canvas_h: int, top_pad: int, gap: int, heights: List[int], image_files: List[str], images_folder_name: str) -> str:
    # y positions
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


def _build_readme(max_per_psd: int, max_total: int) -> str:
    return (
        "MISHARP 상세페이지 생성기 (내부용)\n"
        "\n"
        "[규칙]\n"
        f"- JPG: 전체 이미지 1장으로 생성\n"
        f"- PSD: {max_per_psd}장 초과 시 자동 2개로 분할\n"
        f"- 최대 등록: {max_total}장\n"
        "\n"
        "[다운로드 ZIP 구성]\n"
        "1) 상세페이지 JPG\n"
        "2) PSD 생성용 JSX (Smart Object 유지)\n"
        "3) images_part1/ , images_part2/ 폴더(PSD에 들어갈 900px 리사이즈 이미지)\n"
        "\n"
        "[PSD 생성 방법]\n"
        "1) ZIP 압축 해제\n"
        "2) Photoshop 실행(CS 이상 권장)\n"
        "3) 파일 > 스크립트 > 찾아보기...\n"
        "4) *_psd_build.jsx 실행\n"
        "5) 같은 폴더에 .psd 생성\n"
        "\n"
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
        zf.writestr("README.txt", _build_readme(MAX_PER_PSD, MAX_TOTAL_IMAGES))

        for jsx_name, jsx_text in jsx_entries:
            zf.writestr(jsx_name, jsx_text)

        for folder_name, files in resized_groups:
            for fn, b in files:
                zf.writestr(f"{folder_name}/{fn}", b)

    return out.getvalue()


def _init_state():
    if STATE_ITEMS not in st.session_state:
        st.session_state[STATE_ITEMS] = []
    if STATE_SEEN not in st.session_state:
        st.session_state[STATE_SEEN] = set()
    if STATE_LAST_PREVIEW not in st.session_state:
        st.session_state[STATE_LAST_PREVIEW] = None
    if STATE_LAST_ZIP not in st.session_state:
        st.session_state[STATE_LAST_ZIP] = None
    if STATE_LAST_META not in st.session_state:
        st.session_state[STATE_LAST_META] = None


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
    """
    returns: (added_count, skipped_over_limit_count)
    """
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


def _calc_total_height(resized_heights: List[int], top_pad: int, bottom_pad: int, gap: int) -> int:
    if not resized_heights:
        return 0
    return top_pad + bottom_pad + sum(resized_heights) + gap * (len(resized_heights) - 1)


def _build_outputs(base_name: str, top_pad: int, bottom_pad: int, gap: int):
    items: List[ImgItem] = st.session_state[STATE_ITEMS]

    # safety: unique by sha1 (just in case)
    uniq: List[ImgItem] = []
    seen2 = set()
    for it in items:
        if it.sha1 in seen2:
            continue
        uniq.append(it)
        seen2.add(it.sha1)

    resized_all = [_fit_to_width_900(it.pil) for it in uniq]
    heights_all = [im.size[1] for im in resized_all]

    # 1) JPG: 전체 1장
    long_img = _compose_long_jpg(resized_all, top_pad=top_pad, bottom_pad=bottom_pad, gap=gap)
    jpg_bytes = _save_jpg_bytes(long_img)

    # 2) PSD: 10장 초과면 2개로 분할
    parts: List[List[Image.Image]] = []
    if len(resized_all) <= MAX_PER_PSD:
        parts = [resized_all]
    else:
        parts = [resized_all[:MAX_PER_PSD], resized_all[MAX_PER_PSD:]]

    jsx_entries: List[Tuple[str, str]] = []
    resized_groups: List[Tuple[str, List[Tuple[str, bytes]]]] = []

    for pi, part_imgs in enumerate(parts, start=1):
        part_heights = [im.size[1] for im in part_imgs]
        part_canvas_h = _calc_total_height(part_heights, top_pad, bottom_pad, gap)

        # 저장 파일명/폴더명
        part_suffix = f"part{pi}"
        part_base = f"{base_name}_{part_suffix}" if len(parts) > 1 else base_name
        folder_name = f"images_{part_suffix}" if len(parts) > 1 else "images"

        # images 저장
        files: List[Tuple[str, bytes]] = []
        fns: List[str] = []
        for idx, im in enumerate(part_imgs, start=1):
            fn = f"img_{idx:02d}.jpg"
            files.append((fn, _save_jpg_bytes(im)))
            fns.append(fn)
        resized_groups.append((folder_name, files))

        # JSX 생성
        jsx_text = _build_jsx(
            base_name=part_base,
            canvas_h=part_canvas_h,
            top_pad=top_pad,
            gap=gap,
            heights=part_heights,
            image_files=fns,
            images_folder_name=folder_name,
        )
        jsx_name = f"{part_base}_psd_build.jsx"
        jsx_entries.append((jsx_name, jsx_text))

    meta = {
        "count": len(resized_all),
        "total_height": _calc_total_height(heights_all, top_pad, bottom_pad, gap),
        "top": top_pad,
        "bottom": bottom_pad,
        "gap": gap,
        "psd_parts": len(parts),
    }

    zip_bytes = _zip_bundle(
        base_name=base_name,
        jpg_bytes=jpg_bytes,
        jsx_entries=jsx_entries,
        resized_groups=resized_groups,
    )

    return jpg_bytes, zip_bytes, meta


def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    _init_state()

    st.markdown(
        f"""
        <div style="padding:14px 0 8px 0;">
          <div style="font-size:28px; font-weight:800; letter-spacing:-0.5px;">{APP_TITLE}</div>
          <div style="font-size:13px; opacity:0.7; margin-top:2px;">{APP_SUBTITLE}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.25, 0.75], gap="large")

    # ---------------- LEFT ----------------
    with left:
        st.markdown("### 1) 업로드")
        cA, cB = st.columns([0.65, 0.35])
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

        current_count = len(st.session_state[STATE_ITEMS])
        st.caption(f"현재 목록: {current_count}/{MAX_TOTAL_IMAGES}장 (10장 초과 시 PSD 2개 자동 생성)")

        add_clicked = st.button(
            "업로드 파일 목록에 추가",
            type="primary",
            use_container_width=True,
            disabled=(not uploaded) or (current_count >= MAX_TOTAL_IMAGES and not replace_mode),
        )

        if add_clicked and uploaded:
            if replace_mode:
                _reset_all()
            added, skipped_limit = _add_items_from_uploads(uploaded)
            if added == 0:
                st.warning("추가된 새 이미지가 없습니다. (중복 제외 또는 제한 초과)")
            else:
                st.success(f"추가 완료: 새 이미지 {added}개")
            if skipped_limit > 0:
                st.warning(f"최대 {MAX_TOTAL_IMAGES}장 제한으로 {skipped_limit}개 파일(또는 ZIP 내 이미지)이 추가되지 않았습니다.")

        st.markdown("### 2) 레이아웃 설정")
        c1, c2 = st.columns([0.55, 0.45])
        with c1:
            base_name_raw = st.text_input("파일명(확장자 제외)", value="misharp_detailpage")
        with c2:
            gap = st.number_input("이미지 간 여백(px)", min_value=0, max_value=2000, value=DEFAULT_GAP, step=10)

        base_name = _sanitize_filename(base_name_raw)

        with st.expander("상단/하단 여백(기본값은 샘플 기준)", expanded=False):
            top_pad = st.number_input("상단 여백(px)", min_value=0, max_value=5000, value=DEFAULT_TOP_PAD, step=10)
            bottom_pad = st.number_input("하단 여백(px)", min_value=0, max_value=5000, value=DEFAULT_BOTTOM_PAD, step=10)

        st.markdown("### 3) 순서 변경 / 삭제")
        items: List[ImgItem] = st.session_state[STATE_ITEMS]

        if not items:
            st.info("업로드된 이미지가 없습니다.")
        else:
            for i, it in enumerate(items):
                # 썸네일 작아졌으니 비율 조정
                row = st.columns([0.14, 0.56, 0.10, 0.10, 0.10])
                with row[0]:
                    st.image(_make_thumb(it.pil), use_column_width=True)
                with row[1]:
                    short = it.name if len(it.name) <= 44 else (it.name[:41] + "...")
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

        cX, cY = st.columns([0.7, 0.3])
        with cX:
            disabled = (len(st.session_state[STATE_ITEMS]) == 0) or (not base_name.strip())
            gen = st.button("상세페이지 생성하기", type="primary", use_container_width=True, disabled=disabled)
        with cY:
            if st.button("전체 초기화", use_container_width=True):
                _reset_all()
                st.rerun()

        if gen:
            jpg_bytes, zip_bytes, meta = _build_outputs(
                base_name=base_name,
                top_pad=int(top_pad),
                bottom_pad=int(bottom_pad),
                gap=int(gap),
            )
            st.session_state[STATE_LAST_PREVIEW] = jpg_bytes
            st.session_state[STATE_LAST_ZIP] = zip_bytes
            st.session_state[STATE_LAST_META] = meta
            st.success("생성 완료! 오른쪽에서 미리보기/다운로드 하세요.")

    # ---------------- RIGHT ----------------
    with right:
        st.markdown("### 미리보기")
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

            st.markdown("### 다운로드")
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
            "본 프로그램의 저작권은 미샵컴퍼니(misharpcompany)에 있으며, 무단 복제·배포·사용을 금합니다.\n"
            "본 프로그램은 미샵컴퍼니 내부 직원 전용으로, 외부 유출 및 제3자 제공을 엄격히 금합니다.\n\n"
            "ⓒ misharpcompany. All rights reserved.\n"
            "This program is the intellectual property of misharpcompany. Unauthorized copying, distribution, or use is strictly prohibited.\n"
            "This program is for internal use by misharpcompany employees only and must not be disclosed or shared externally."
        )


if __name__ == "__main__":
    main()
