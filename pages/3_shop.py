import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sys
import os

# 1. 프로젝트 최상위 폴더(루트) 절대 경로 계산 (현재 파일 위치 기준 2단계 위)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import auth
from utils import region_selectors, filter_places
from db import get_favorites, toggle_favorite

auth.login_widget()

st.title("용품점 찾기")
st.write("지역을 선택하면 가까운 반려동물 용품점을 지도에서 보여드려요.")

# 이 페이지에서 다루는 즐겨찾기 종류
FAV_KIND = "store"


# 2. 데이터 로드 함수 정의
@st.cache_data
def load_data(file_path):
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()


CSV_PATH = os.path.join(BASE_DIR, "data", "stores.csv")
df = load_data(CSV_PATH)


CATEGORY_STYLE = {
    "용품점": {"color": "green", "icon": "shopping-cart"},
    "미용점": {"color": "purple", "icon": "scissors"},
}


def build_popup_html(row):
    """마커 클릭 시 보일 카드. 전화 걸기 / 길찾기 링크 포함."""
    tel_link = f"tel:{row['전화번호']}"
    map_link = f"https://map.kakao.com/link/to/{row['가게명']},{row['위도']},{row['경도']}"
    return f"""
    <div style="font-family: -apple-system, sans-serif; width: 220px;">
        <div style="font-size:15px; font-weight:700; margin-bottom:2px;">
            {row['가게명']}
        </div>
        <div style="font-size:12px; color:#888; margin-bottom:6px;">
            {row['종류']} · {row['시군구']} {row['동']}
        </div>
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


def store_card(row, favs, prefix=""):
    """가게 한 곳을 카드로 그린다. 별표 버튼으로 즐겨찾기 토글."""
    name = row["가게명"]
    is_fav = name in favs
    with st.container(border=True):
        c1, c2, c3 = st.columns([5, 2, 1])
        with c1:
            st.write(f"**{name}**  ·  {row['종류']}")
            st.caption(f"{row['시군구']} {row['동']}  ·  "
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
            # 로그인한 사용자에게만 즐겨찾기 별표를 보여준다.
            if auth.is_logged_in():
                label = "⭐" if is_fav else "☆"
                if st.button(label, key=f"fav_{FAV_KIND}_{prefix}_{name}",
                             help="즐겨찾기"):
                    added = toggle_favorite(FAV_KIND, name)
                    if added:
                        st.toast(f"⭐ '{name}'을(를) 즐겨찾기에 추가했어요.")
                    else:
                        st.toast(f"☆ '{name}'을(를) 즐겨찾기에서 뺐어요.")
                    st.rerun()


if df.empty:
    st.warning("표시할 가게 데이터가 없습니다. data 폴더 안에 stores.csv 파일이 "
               "올바르게 있는지 확인해주세요.")
else:
    # 로그인한 사용자만 즐겨찾기를 불러온다. 비로그인은 빈 집합.
    favs = get_favorites(FAV_KIND) if auth.is_logged_in() else set()

    # ── 상단: 내 즐겨찾기 섹션 (로그인 시에만) ────────────────────
    if auth.is_logged_in():
        st.divider()
        st.subheader("내 즐겨찾기")
        fav_df = df[df["가게명"].isin(favs)]
        if fav_df.empty:
            st.caption("아직 즐겨찾기한 가게가 없어요. 아래 목록에서 별을 눌러 담아 보세요.")
        else:
            for _, row in fav_df.iterrows():
                store_card(row, favs, prefix="topfav")

    # ── 검색 영역 ─────────────────────────────────────────────────
    st.divider()
    st.subheader("가게 찾기")

    sido, sigungu, dong = region_selectors(df, key_prefix="shop")
    filtered = filter_places(df, sido, sigungu, dong)

    all_categories = ["용품점", "미용점"]
    chosen = st.multiselect(
        "가게 종류 (선택 안 하면 전체)",
        options=all_categories,
        default=all_categories,
    )
    if chosen:
        filtered = filtered[filtered["종류"].isin(chosen)]

    st.write(f"**검색 결과 {len(filtered)}곳**")

    if not filtered.empty:
        avg_lat = filtered['위도'].mean()
        avg_lon = filtered['경도'].mean()
        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=14, control_scale=True)

        for _, row in filtered.iterrows():
            style = CATEGORY_STYLE.get(row["종류"], {"color": "blue", "icon": "info-sign"})
            folium.Marker(
                [row['위도'], row['경도']],
                popup=folium.Popup(build_popup_html(row), max_width=260),
                tooltip=f"{row['가게명']} ({row['종류']})",
                icon=folium.Icon(color=style["color"], icon=style["icon"], prefix="fa"),
            ).add_to(m)

        if len(filtered) > 1:
            bounds = [
                [filtered['위도'].min(), filtered['경도'].min()],
                [filtered['위도'].max(), filtered['경도'].max()],
            ]
            m.fit_bounds(bounds, padding=(30, 30))

        st_folium(m, use_container_width=True, height=500, returned_objects=[])
        st.caption("초록 마커는 용품점, 보라 마커는 미용실이에요.")

        # 목록 (별표로 즐겨찾기 토글)
        st.divider()
        if auth.is_logged_in():
            st.write("**가게 목록**  ·  별을 눌러 즐겨찾기에 담아요")
        else:
            st.write("**가게 목록**")
            st.caption("로그인하면 즐겨찾기에 담을 수 있어요.")
        for _, row in filtered.iterrows():
            store_card(row, favs, prefix="list")
    else:
        st.info("선택한 조건에 맞는 가게가 없습니다. 지역이나 종류를 바꿔보세요.")