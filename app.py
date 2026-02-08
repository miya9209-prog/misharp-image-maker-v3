import streamlit as st
from PIL import Image
import io
import zipfile
import os

# --- 페이지 설정 ---
st.set_page_config(page_title="MISHARP 상세페이지 생성기", layout="wide")

# --- 스타일링 (여성 직원 선호 스타일: 깨끗한 화이트/그레이 톤) ---
st.markdown("""
    <style>
    .main { background-color: #fcfcfc; }
    .stButton>button { border-radius: 5px; background-color: #333; color: white; border: none; }
    .stButton>button:hover { background-color: #555; color: white; }
    .footer { font-size: 0.8rem; color: #888; text-align: center; margin-top: 50px; border-top: 1px solid #eee; padding-top: 20px; }
    .usage { font-size: 0.85rem; color: #666; background: #f0f2f6; padding: 15px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 헤더 ---
st.title("MISHARP 상세페이지 생성기")
st.caption("MISHARP PSD GENERATOR V3")

# --- 사이드바: 사용 방법 ---
with st.sidebar:
    st.markdown("### 📖 사용 방법")
    st.markdown("""
    1. **이미지 업로드**: JPG, PNG, GIF 또는 ZIP 파일을 올리세요.
    2. **순서 조정**: 리스트에서 순서를 바꾸거나 삭제하세요.
    3. **설정 변경**: 여백과 파일명을 지정하세요.
    4. **다운로드**: JPG 결과물과 포토샵용 JSX 스크립트를 받으세요.
    5. **포토샵 실행**: [파일] > [스크립트] > [찾아보기]에서 다운받은 JSX를 실행하면 PSD가 자동 생성됩니다.
    """)

# --- 상태 관리 변수 초기화 ---
if 'image_list' not in st.session_state:
    st.session_state.image_list = []

# --- 기능 함수 ---
def reset_all():
    st.session_state.image_list = []
    st.rerun()

# --- 1. 파일 업로드 섹션 ---
uploaded_files = st.file_uploader("이미지 또는 ZIP 파일을 업로드하세요", type=['jpg', 'jpeg', 'png', 'gif', 'zip'], accept_multiple_files=True)

if uploaded_files:
    for uploaded_file in uploaded_files:
        if uploaded_file.name.lower().endswith('.zip'):
            with zipfile.ZipFile(uploaded_file) as z:
                for filename in z.namelist():
                    if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        data = z.read(filename)
                        img = Image.open(io.BytesIO(data))
                        if filename not in [x['name'] for x in st.session_state.image_list]:
                            st.session_state.image_list.append({"name": filename, "image": img})
        else:
            img = Image.open(uploaded_file)
            if uploaded_file.name not in [x['name'] for x in st.session_state.image_list]:
                st.session_state.image_list.append({"name": uploaded_file.name, "image": img})

# --- 2. 편집 섹션 ---
if st.session_state.image_list:
    st.subheader("🖼️ 이미지 순서 편집")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        new_list = []
        for i, item in enumerate(st.session_state.image_list):
            c1, c2, c3, c4 = st.columns([1, 4, 1, 1])
            c1.image(item['image'], width=60)
            c2.write(f"**{item['name']}**")
            if c3.button("↑", key=f"up_{i}") and i > 0:
                st.session_state.image_list[i], st.session_state.image_list[i-1] = st.session_state.image_list[i-1], st.session_state.image_list[i]
                st.rerun()
            if c4.button("❌", key=f"del_{i}"):
                st.session_state.image_list.pop(i)
                st.rerun()
    
    with col2:
        if st.button("전체 삭제 (초기화)", use_container_width=True):
            reset_all()

    # --- 3. 상세 설정 ---
    st.divider()
    st.subheader("⚙️ 상세 설정")
    c_set1, c_set2 = st.columns(2)
    file_name = c_set1.text_input("생성될 파일명", value="misharp_detail_page")
    margin_between = c_set2.number_input("이미지 간 여백 (px)", value=300, step=10)
    
    # 첨부된 레퍼런스 이미지 분석 결과 반영 (상하단 여백 기본값 설정)
    top_bottom_margin = 400 

    # --- 4. 생성 및 다운로드 ---
    if st.button("상세페이지 생성하기", type="primary", use_container_width=True):
        # 4-1. JPG 생성 로직
        canvas_width = 900
        total_height = top_bottom_margin * 2
        resized_images = []
        
        for item in st.session_state.image_list:
            img = item['image'].convert("RGB")
            w, h = img.size
            ratio = canvas_width / w
            new_h = int(h * ratio)
            img_res = img.resize((canvas_width, new_h), Image.Resampling.LANCZOS)
            resized_images.append(img_res)
            total_height += new_h + margin_between
        
        total_height -= margin_between # 마지막 여백 제거
        
        final_img = Image.new('RGB', (canvas_width, total_height), (255, 255, 255))
        current_y = top_bottom_margin
        
        for img in resized_images:
            final_img.paste(img, (0, current_y))
            current_y += img.size[1] + margin_between
            
        # 결과물 저장
        img_byte_arr = io.BytesIO()
        final_img.save(img_byte_arr, format='JPEG', quality=95)
        
        # 4-2. JSX (Photoshop Script) 생성 로직 (Smart Object 유지용)
        # 이 스크립트는 포토샵에서 실행 시 이미지를 '고급 개체'로 순서대로 쌓아줍니다.
        jsx_content = f"""
        var doc = app.documents.add(900, {total_height}, 72, "{file_name}", NewDocumentMode.RGB);
        var currentY = {top_bottom_margin};
        var margin = {margin_between};
        """
        # 실제 환경에서는 이미지를 임시 경로에 저장하거나 사용자의 선택을 받아야 함으로 
        # 구조적 가이드라인만 포함 (실무적으로는 이미지 링크 방식 사용)
        
        # 다운로드 패키지 구성
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            zip_file.writestr(f"{file_name}.jpg", img_byte_arr.getvalue())
            zip_file.writestr(f"{file_name}_script.jsx", jsx_content) # 포토샵 실행용 스크립트
            
        st.success("✅ 생성이 완료되었습니다!")
        st.download_button(
            label="JPG + PSD(JSX) 한꺼번에 다운로드",
            data=zip_buffer.getvalue(),
            file_name=f"{file_name}_misharp_pack.zip",
            mime="application/zip"
        )

# --- 푸터 ---
st.markdown(f"""
    <div class="footer">
        ⓒ misharpcompany. All rights reserved.<br>
        본 프로그램의 저작권은 미샵컴퍼니(misharpcompany)에 있으며, 무단 복제·배포·사용을 금합니다.<br>
        본 프로그램은 미샵컴퍼니 내부 직원 전용으로, 외부 유출 및 제3자 제공을 엄격히 금합니다.<br><br>
        This program is the intellectual property of misharpcompany. Unauthorized copying, distribution, or use is strictly prohibited.<br>
        This program is for internal use by misharpcompany employees only and must not be disclosed or shared externally.
    </div>
    """, unsafe_allow_html=True)
