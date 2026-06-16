import streamlit as st
import pandas as pd
import sys, os
import folium
from streamlit_folium import st_folium

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import auth
from utils import region_selectors, filter_places
from db import get_favorites, toggle_favorite

auth.login_widget()

st.title(" 가족 찾기")
st.write("보호자님의 라이프스타일에 딱 맞는 아이를 추천해 드리고, 주변에서 따뜻한 손길을 기다리는 보호소를 안내해 드려요.")

st.divider()

FAV_KIND = "adoption"

# =========================
# CSV 로드
# =========================
BREEDS_PATH = os.path.join(BASE_DIR, "data", "breeds.csv")
PETSHOP_PATH = os.path.join(BASE_DIR, "data", "petshop.csv")


@st.cache_data
def load_csv(path):
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    return df


df = load_csv(BREEDS_PATH)
shop_df = load_csv(PETSHOP_PATH)

df["allergy_friendly"] = df["allergy_friendly"].astype(str).str.lower().eq("true")


# =========================
# 사용자 입력 (품종 추천용)
# =========================
col1, col2 = st.columns(2)
with col1:
    pet_type = st.selectbox("선호하는 동물", ["강아지", "고양이", "상관없음"])
    living_env = st.radio("주거 환경", ["아파트/빌라", "단독주택", "마당 있는 집"])

# 선호 동물이 바뀌면 추천 결과 초기화
if "last_pet_type" not in st.session_state:
    st.session_state.last_pet_type = pet_type
if st.session_state.last_pet_type != pet_type:
    st.session_state.top3 = None
    st.session_state.selected = None
    st.session_state.last_pet_type = pet_type

with col2:
    activity_level = st.select_slider(
        "활동량", options=["매우 적음", "보통", "활동적", "매우 활동적"]
    )
    has_allergy = st.checkbox("털 알러지가 있나요?")


def score(row):
    s = 0
    if pet_type == "상관없음":
        s += 3
    elif row["type"] == pet_type:
        s += 3
    if row["energy"] == activity_level:
        s += 3
    if living_env == "아파트/빌라" and row["size"] == "소형":
        s += 2
    elif living_env == "단독주택" and row["size"] in ["소형", "중형"]:
        s += 2
    elif living_env == "마당 있는 집" and row["size"] in ["중형", "대형"]:
        s += 2
    if has_allergy:
        s += 3 if row["allergy_friendly"] else -3
    return s


if "top3" not in st.session_state:
    st.session_state.top3 = None
if "selected" not in st.session_state:
    st.session_state.selected = None


# =========================
# 추천 실행
# =========================
if st.button("추천 품종 보기", type="primary"):
    result = df.copy()
    result["score"] = result.apply(score, axis=1)
    if pet_type == "상관없음":
        dog = result[result["type"] == "강아지"].sort_values("score", ascending=False).head(3)
        cat = result[result["type"] == "고양이"].sort_values("score", ascending=False).head(3)
        st.session_state.top3 = pd.concat([dog, cat])
    else:
        st.session_state.top3 = result.sort_values("score", ascending=False).head(3)
    st.session_state.selected = None


# =========================
# TOP3 출력
# =========================
def breed_cards(rows, emoji, key_prefix):
    cols = st.columns(len(rows)) if len(rows) > 0 else []
    for col, (_, row) in zip(cols, rows.iterrows()):
        with col:
            with st.container(border=True):
                st.markdown(f"### {row['breed']}")
                st.write(f"크기  {row['size']}")
                if st.button("상세 보기", key=f"{key_prefix}_{row['breed']}"):
                    st.session_state.selected = row


if st.session_state.top3 is not None:
    if pet_type == "상관없음":
        dog = st.session_state.top3[st.session_state.top3["type"] == "강아지"]
        cat = st.session_state.top3[st.session_state.top3["type"] == "고양이"]
        st.success("강아지 추천 3")
        breed_cards(dog, "🐶", "dog")
        st.success("고양이 추천 3")
        breed_cards(cat, "😺", "cat")
    else:
        st.success("추천 3")
        emoji = "🐶" if pet_type == "강아지" else "😺"
        breed_cards(st.session_state.top3, emoji, "pick")


# =========================
# 상세 정보
# =========================
if st.session_state.selected is not None:
    pet = st.session_state.selected
    st.divider()
    st.subheader(f"{pet['breed']} 자세히 보기")
    st.write(f"대표 질환  {pet['main_disease']}")
    st.write(f"기대 수명  {pet['life_span']}")
    st.write(f"월 양육비  {pet['cost']}")
    st.write(f"활동량  {pet['energy']}")
    st.write(f"털 빠짐  {pet['shedding']}")
    if pet["allergy_friendly"]:
        st.success("알러지 친화 품종")
    if st.button("상세 닫기"):
        st.session_state.selected = None
        st.rerun()


# =========================
# 위치 기반 입양처 찾기 (시군구 선택 방식)
# =========================
st.divider()
st.subheader("내 지역 입양처 찾기")
st.caption("지역을 선택하면 그 지역의 보호소와 센터를 모두 보여드려요.")

sido, sigungu, dong = region_selectors(shop_df, key_prefix="adopt")
filtered = filter_places(shop_df, sido, sigungu, dong)

st.write(f"**📍 검색 결과: {len(filtered)}곳**")


def build_popup_html(row):
    tel = ""  # petshop.csv 에 전화번호가 없으면 생략
    map_link = f"https://map.kakao.com/link/to/{row['name']},{row['lat']},{row['lon']}"
    return f"""
    <div style="font-family:-apple-system,sans-serif; width:220px;">
        <div style="font-size:15px; font-weight:700; margin-bottom:2px;">{row['name']}</div>
        <div style="font-size:12px; color:#888; margin-bottom:6px;">
            {row['시군구']} {row['동']} · {row['animal_type']}
        </div>
        <div style="font-size:13px; margin-bottom:8px;">🐾 입양 가능: {row['breed']}</div>
        <a href="{map_link}" target="_blank"
           style="display:inline-block; padding:5px 10px; background:#2196F3;
                  color:#fff; text-decoration:none; border-radius:5px; font-size:13px;">
           🧭 길찾기</a>
    </div>
    """


def adopt_card(row, favs, prefix="", idx=0):
    name = row["name"]
    is_fav = name in favs
    with st.container(border=True):
        c1, c2, c3 = st.columns([5, 2, 1])
        with c1:
            st.write(f"**{name}**  ·  {row['animal_type']}")
            st.caption(f"{row['시군구']} {row['동']}  ·  입양 가능  {row['breed']}")
        with c2:
            map_link = f"https://map.kakao.com/link/to/{name},{row['lat']},{row['lon']}"
            st.markdown(
                f"<a href='{map_link}' target='_blank' "
                f"style='text-decoration:none;'>🧭 길찾기</a>",
                unsafe_allow_html=True,
            )
        with c3:
            if auth.is_logged_in():
                label = "⭐" if is_fav else "☆"
                if st.button(label, key=f"fav_{FAV_KIND}_{prefix}_{idx}", help="즐겨찾기"):
                    added = toggle_favorite(FAV_KIND, name)
                    if added:
                        st.toast(f"⭐ '{name}'을(를) 즐겨찾기에 추가했어요.")
                    else:
                        st.toast(f"☆ '{name}'을(를) 즐겨찾기에서 뺐어요.")
                    st.rerun()


if filtered.empty:
    st.info("선택한 지역에 등록된 입양처가 없어요. 다른 지역이나 '전체'로 검색해 보세요.")
else:
    favs = get_favorites(FAV_KIND) if auth.is_logged_in() else set()

    # 즐겨찾기 섹션 (로그인 시에만)
    if auth.is_logged_in():
        fav_df = filtered[filtered["name"].isin(favs)]
        if not fav_df.empty:
            st.markdown("##### 이 지역의 즐겨찾기")
            for i, (_, row) in enumerate(fav_df.iterrows()):
                adopt_card(row, favs, prefix="topfav", idx=i)
            st.divider()

    # 지도 (좌표가 비어있는 행은 안전하게 제외)
    map_df = filtered.copy()
    map_df["lat"] = pd.to_numeric(map_df["lat"], errors="coerce")
    map_df["lon"] = pd.to_numeric(map_df["lon"], errors="coerce")
    map_df = map_df.dropna(subset=["lat", "lon"])

    if map_df.empty:
        st.info("이 지역에는 지도에 표시할 수 있는 위치 정보가 없어요.")
    else:
        avg_lat = map_df["lat"].mean()
        avg_lon = map_df["lon"].mean()
        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=12, control_scale=True)
        for _, row in map_df.iterrows():
            folium.Marker(
                [row["lat"], row["lon"]],
                popup=folium.Popup(build_popup_html(row), max_width=260),
                tooltip=row["name"],
                icon=folium.Icon(color="orange", icon="home", prefix="fa"),
            ).add_to(m)
        if len(map_df) > 1:
            bounds = [
                [map_df["lat"].min(), map_df["lon"].min()],
                [map_df["lat"].max(), map_df["lon"].max()],
            ]
            m.fit_bounds(bounds, padding=(30, 30))
        st_folium(m, use_container_width=True, height=500, returned_objects=[])

    # 목록
    if auth.is_logged_in():
        st.markdown("##### 입양처 목록  ·  별을 눌러 즐겨찾기에 담아요")
    else:
        st.markdown("##### 입양처 목록")
        st.caption("로그인하면 즐겨찾기에 담을 수 있어요.")
    for i, (_, row) in enumerate(filtered.iterrows()):
        adopt_card(row, favs, prefix="list", idx=i)