import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import random
import base64
from datetime import date
import sys
import os

# 프로젝트 루트 경로 추가
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import auth
from utils import region_selectors, filter_places
from db import (get_favorites, toggle_favorite,
                get_album_photo, set_album_photo, delete_album_photo,
                get_memories, add_memory, delete_memory)

auth.login_widget()

st.title("🕯️ 따뜻한 마지막 안녕")
st.write("내 위치(시/군/구/동)를 선택하면 가까운 반려동물 장례식장을 지도에 표시해 드립니다.")

FAV_KIND = "facility"   # 즐겨찾기 종류 (shop 은 'store')


# ── 데이터 로드 ────────────────────────────────────────────────────
@st.cache_data
def load_data(file_path):
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()


CSV_PATH = os.path.join(BASE_DIR, "data", "facilities.csv")
df = load_data(CSV_PATH)


# ── 위로 메시지 (페이지 상단에 하나 랜덤 표시) ──────────────────────
@st.cache_data
def load_comfort():
    path = os.path.join(BASE_DIR, "data", "comfort_message.csv")
    try:
        msgs = pd.read_csv(path, encoding='utf-8-sig')["message"].tolist()
        return msgs
    except Exception:
        return []


comfort_msgs = load_comfort()
if comfort_msgs:
    # 세션마다 한 번 고른 메시지를 유지 (새로고침 때마다 안 바뀌도록)
    if "comfort_msg" not in st.session_state:
        st.session_state.comfort_msg = random.choice(comfort_msgs)
    st.info(f"🌈 {st.session_state.comfort_msg}")


def build_popup_html(row):
    """마커 클릭 시 보일 카드. 전화 / 길찾기 + 허가 여부 표시."""
    tel_link = f"tel:{row['전화번호']}"
    map_link = f"https://map.kakao.com/link/to/{row['시설명']},{row['위도']},{row['경도']}"
    license_badge = "✅ 정식 허가 시설" if str(row.get('허가', '')).strip() == "허가" else ""
    return f"""
    <div style="font-family: -apple-system, sans-serif; width: 230px;">
        <div style="font-size:15px; font-weight:700; margin-bottom:2px;">
            {row['시설명']}
        </div>
        <div style="font-size:12px; color:#888; margin-bottom:4px;">
            {row['시군구']} {row['동']}
        </div>
        <div style="font-size:12px; color:#2e7d32; margin-bottom:4px;">{license_badge}</div>
        <div style="font-size:13px; margin-bottom:4px;">🏷️ {row['특징']}</div>
        <div style="font-size:13px; margin-bottom:8px;">☎ {row['전화번호']}</div>
        <div>
            <a href="{tel_link}"
               style="display:inline-block; padding:5px 10px; margin-right:4px;
                      background:#4CAF50; color:#fff; text-decoration:none;
                      border-radius:5px; font-size:13px;">📞 전화</a>
            <a href="{map_link}" target="_blank"
               style="display:inline-block; padding:5px 10px;
                      background:#2196F3; color:#fff; text-decoration:none;
                      border-radius:5px; font-size:13px;">🧭 길찾기</a>
        </div>
    </div>
    """


def facility_card(row, favs, prefix=""):
    """장례식장 한 곳을 카드로. 별표로 즐겨찾기 토글."""
    name = row["시설명"]
    is_fav = name in favs
    with st.container(border=True):
        c1, c2, c3 = st.columns([5, 2, 1])
        with c1:
            badge = "  ✅ 정식 허가" if str(row.get('허가', '')).strip() == "허가" else ""
            st.write(f"**{name}**{badge}")
            st.caption(f"📍 {row['시군구']} {row['동']}  ·  "
                       f"🏷️ {row['특징']}  ·  ☎ {row['전화번호']}")
        with c2:
            map_link = (f"https://map.kakao.com/link/to/"
                        f"{name},{row['위도']},{row['경도']}")
            st.markdown(
                f"<a href='tel:{row['전화번호']}' "
                f"style='text-decoration:none; margin-right:8px;'>📞 전화</a>"
                f"<a href='{map_link}' target='_blank' "
                f"style='text-decoration:none;'>🧭 길찾기</a>",
                unsafe_allow_html=True,
            )
        with c3:
            if auth.is_logged_in():
                label = "⭐" if is_fav else "☆"
                if st.button(label, key=f"fav_{FAV_KIND}_{prefix}_{name}", help="즐겨찾기"):
                    added = toggle_favorite(FAV_KIND, name)
                    if added:
                        st.toast(f"⭐ '{name}'을(를) 즐겨찾기에 추가했어요.")
                    else:
                        st.toast(f"☆ '{name}'을(를) 즐겨찾기에서 뺐어요.")
                    st.rerun()


if df.empty:
    st.warning("표시할 장례식장 데이터가 없습니다. data 폴더 안에 facilities.csv 파일이 "
               "올바르게 있는지 확인해주세요.")
else:
    favs = get_favorites(FAV_KIND) if auth.is_logged_in() else set()

    # ── 상단: 내 즐겨찾기 (로그인 시에만) ─────────────────────────
    if auth.is_logged_in():
        st.divider()
        st.subheader("⭐ 내 즐겨찾기")
        fav_df = df[df["시설명"].isin(favs)]
        if fav_df.empty:
            st.caption("아직 즐겨찾기한 장례식장이 없어요. 아래 목록에서 ☆ 별을 눌러 추가해 보세요.")
        else:
            for _, row in fav_df.iterrows():
                facility_card(row, favs, prefix="topfav")

    # ── 검색 영역 ─────────────────────────────────────────────────
    st.divider()
    st.subheader("🔎 장례식장 찾기")

    sido, sigungu, dong = region_selectors(df, key_prefix="memorial")
    filtered = filter_places(df, sido, sigungu, dong)

    # 시설 유형 필터 (개별 화장 / 봉안당)
    type_filter = st.multiselect(
        "원하는 시설 유형 (선택 안 하면 전체)",
        options=["개별 화장 가능", "봉안당 있음"],
        default=[],
    )
    if "개별 화장 가능" in type_filter:
        filtered = filtered[filtered["개별화장"].astype(str).str.strip() == "O"]
    if "봉안당 있음" in type_filter:
        filtered = filtered[filtered["봉안당"].astype(str).str.strip() == "O"]

    st.write(f"**📍 검색 결과: {len(filtered)}곳**")

    if not filtered.empty:
        avg_lat = filtered['위도'].mean()
        avg_lon = filtered['경도'].mean()
        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=12, control_scale=True)

        for _, row in filtered.iterrows():
            folium.Marker(
                [row['위도'], row['경도']],
                popup=folium.Popup(build_popup_html(row), max_width=270),
                tooltip=row['시설명'],
                icon=folium.Icon(color="purple", icon="leaf", prefix="fa"),
            ).add_to(m)

        if len(filtered) > 1:
            bounds = [
                [filtered['위도'].min(), filtered['경도'].min()],
                [filtered['위도'].max(), filtered['경도'].max()],
            ]
            m.fit_bounds(bounds, padding=(30, 30))

        st_folium(m, use_container_width=True, height=500, returned_objects=[])
        st.caption("🟣 반려동물 장례식장   ·   ✅ 표시는 정식 허가 시설입니다")

        # 목록
        st.divider()
        if auth.is_logged_in():
            st.write("📋 **장례식장 목록**  ·  ☆ 별을 눌러 즐겨찾기에 추가하세요")
        else:
            st.write("📋 **장례식장 목록**")
            st.caption("로그인하면 ⭐ 즐겨찾기에 추가할 수 있어요.")
        for _, row in filtered.iterrows():
            facility_card(row, favs, prefix="list")
    else:
        st.info("선택한 조건에 맞는 장례식장이 없습니다. 지역이나 시설 유형을 바꿔보세요.")

# ── 장례 절차 안내 (pet-life-care 의 guide.html 내용을 가져옴) ──────
st.divider()
with st.expander("📖 반려동물 장례 절차 안내"):
    st.markdown("""
    1. **사망 확인** — 동물병원에서 사망을 확인합니다.
    2. **장례식장 예약** — 위에서 가까운 정식 허가 시설을 찾아 연락합니다.
    3. **추모 시간** — 마지막 인사를 나눕니다.
    4. **화장** — 개별 화장 또는 공동 화장을 진행합니다.
    5. **유골 수습** — 유골을 수습합니다.
    6. **봉안 / 자연장** — 봉안당에 모시거나 수목장으로 자연으로 돌려보냅니다.

    ※ 반려동물 사체를 임의로 매장하는 것은 폐기물관리법상 금지되어 있어요.
       정식 허가받은 장례식장을 이용하는 것이 안전합니다.
    """)

# ── 비대면 상담 신청 (기존 기능 유지) ──────────────────────────────
st.divider()
st.subheader("비대면 장례 상담 신청")
contact = st.text_input(
    "연락처를 남겨주시면 전문 상담원이 안내해 드립니다.",
    placeholder="010-XXXX-XXXX",
)
if st.button("상담 신청하기"):
    if contact.strip():
        st.success("신청이 완료되었습니다. 곧 연락드리겠습니다.")
    else:
        st.warning("연락처를 입력해 주세요.")


# ════════════════════════════════════════════════════════════════════
# 추억 앨범 (로그인한 사용자만)
# ════════════════════════════════════════════════════════════════════
st.divider()
st.header("📷 우리 아이 추억 앨범")

if not auth.is_logged_in():
    st.info("🔒 추억 앨범은 로그인 후 이용할 수 있어요. "
            "왼쪽 사이드바에서 닉네임으로 로그인해 주세요.")
else:
    st.caption("대표 사진 한 장과 소중한 추억들을 기록해 보세요.")

    # ── 대표 사진 ──────────────────────────────────────────────────
    st.subheader("🖼️ 대표 사진")
    photo_b64 = get_album_photo()
    if photo_b64:
        st.image(base64.b64decode(photo_b64), width=300)
        if st.button("사진 삭제", key="album_del_photo"):
            delete_album_photo()
            st.toast("대표 사진을 삭제했어요.")
            st.rerun()
    else:
        st.caption("아직 대표 사진이 없어요. 아래에서 한 장 올려보세요.")

    uploaded = st.file_uploader("사진 업로드 (JPG/PNG)", type=["jpg", "jpeg", "png"],
                                key="album_uploader")
    if uploaded is not None:
        if uploaded.size > 5 * 1024 * 1024:
            st.warning("5MB 이하 이미지만 올릴 수 있어요.")
        else:
            if st.button("이 사진으로 저장", type="primary", key="album_save_photo"):
                b64 = base64.b64encode(uploaded.getvalue()).decode("utf-8")
                set_album_photo(b64)
                st.toast("대표 사진을 저장했어요! 📷")
                st.rerun()

    st.divider()

    # ── 추억 기록 추가 ────────────────────────────────────────────
    st.subheader("📝 추억 기록 추가")
    col1, col2 = st.columns([1, 3])
    with col1:
        mem_date = st.date_input("날짜", value=date.today(), key="album_mem_date")
    with col2:
        mem_text = st.text_input("추억 메모", placeholder="예: 처음 우리 집에 온 날",
                                 key="album_mem_text")
    if st.button("추억 추가", type="primary", key="album_add_mem"):
        if mem_text.strip():
            add_memory(mem_date, mem_text.strip())
            st.toast("추억을 기록했어요 🐾")
            st.rerun()
        else:
            st.warning("추억 메모를 입력해 주세요.")

    st.divider()

    # ── 추억 타임라인 ─────────────────────────────────────────────
    st.subheader("📅 추억 타임라인")
    memories = get_memories()
    if not memories:
        st.caption("아직 기록된 추억이 없어요. 위에서 첫 추억을 남겨보세요.")
    else:
        for m in memories:
            with st.container(border=True):
                c1, c2 = st.columns([5, 1])
                c1.write(f"**{m['memory_date']}**  ·  {m['memo']}")
                if c2.button("삭제", key=f"album_del_mem_{m['id']}"):
                    delete_memory(m["id"])
                    st.toast("추억을 삭제했어요.")
                    st.rerun()