import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
import re

# =============================================
# 🔑 페이지 기본 설정
# =============================================

st.set_page_config(
    page_title="유튜브 댓글 분석기",
    page_icon="🎬",
    layout="wide"
)

# =============================================
# 🎨 CSS 스타일
# =============================================

st.markdown("""
    <style>
        .main-title {
            font-size: 2.5rem;
            font-weight: bold;
            color: #FF0000;
            text-align: center;
            margin-bottom: 0.2rem;
        }
        .sub-title {
            font-size: 1rem;
            color: gray;
            text-align: center;
            margin-bottom: 2rem;
        }
        .stat-box {
            background-color: #f0f2f6;
            border-radius: 12px;
            padding: 1rem 1.5rem;
            text-align: center;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        }
        .stat-number {
            font-size: 2rem;
            font-weight: bold;
            color: #FF0000;
        }
        .stat-label {
            font-size: 0.9rem;
            color: #555;
        }
        .comment-card {
            background-color: #ffffff;
            border-left: 4px solid #FF0000;
            border-radius: 8px;
            padding: 0.8rem 1.2rem;
            margin-bottom: 0.8rem;
            box-shadow: 0 1px 4px rgba(0,0,0,0.07);
        }
        .author-name {
            font-weight: bold;
            color: #333;
            font-size: 0.95rem;
        }
        .comment-text {
            color: #444;
            margin: 0.3rem 0;
            font-size: 0.93rem;
        }
        .comment-meta {
            font-size: 0.8rem;
            color: #999;
        }
    </style>
""", unsafe_allow_html=True)

# =============================================
# 🔑 API 키 불러오기
# =============================================

def get_api_key():
    """Streamlit secrets에서 API 키를 불러오는 함수"""
    try:
        return st.secrets["YOUTUBE_API_KEY"]
    except Exception:
        st.error("❌ API 키를 불러올 수 없습니다. Streamlit Cloud의 Secrets 설정을 확인하세요.")
        st.stop()

# =============================================
# 🔗 영상 ID 추출 함수
# =============================================

def extract_video_id(url: str):
    """
    다양한 형태의 유튜브 URL에서 영상 ID를 추출하는 함수
    지원 형식:
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://youtu.be/VIDEO_ID
      - https://youtube.com/shorts/VIDEO_ID
      - https://www.youtube.com/embed/VIDEO_ID
    """
    patterns = [
        r"(?:v=)([0-9A-Za-z_-]{11})",          # watch?v=
        r"(?:youtu\.be/)([0-9A-Za-z_-]{11})",   # 단축 URL
        r"(?:shorts/)([0-9A-Za-z_-]{11})",       # Shorts
        r"(?:embed/)([0-9A-Za-z_-]{11})",        # embed
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# =============================================
# 📥 영상 정보 가져오기
# =============================================

def get_video_info(youtube, video_id: str):
    """영상 제목, 채널명, 조회수 등 기본 정보를 가져오는 함수"""
    try:
        response = youtube.videos().list(
            part="snippet,statistics",
            id=video_id
        ).execute()

        if not response["items"]:
            return None

        item = response["items"][0]
        snippet = item["snippet"]
        stats = item["statistics"]

        return {
            "제목": snippet.get("title", "알 수 없음"),
            "채널": snippet.get("channelTitle", "알 수 없음"),
            "조회수": int(stats.get("viewCount", 0)),
            "좋아요수": int(stats.get("likeCount", 0)),
            "댓글수": int(stats.get("commentCount", 0)),
            "썸네일": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            "업로드일": snippet.get("publishedAt", "")[:10],
        }
    except Exception as e:
        st.error(f"❌ 영상 정보를 불러오는 중 오류 발생: {e}")
        return None

# =============================================
# 💬 댓글 수집 함수
# =============================================

def get_comments(youtube, video_id: str, max_results: int = 100, order: str = "relevance"):
    """
    유튜브 댓글을 수집하는 함수
    order: "relevance"(관련순) or "time"(최신순)
    """
    comments = []
    next_page_token = None

    progress_bar = st.progress(0, text="💬 댓글을 불러오는 중...")

    try:
        while len(comments) < max_results:
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(100, max_results - len(comments)),
                pageToken=next_page_token,
                textFormat="plainText",
                order=order
            )
            response = request.execute()

            for item in response.get("items", []):
                c = item["snippet"]["topLevelComment"]["snippet"]
                comments.append({
                    "작성자": c.get("authorDisplayName", "익명"),
                    "댓글": c.get("textDisplay", ""),
                    "좋아요수": int(c.get("likeCount", 0)),
                    "답글수": int(item["snippet"].get("totalReplyCount", 0)),
                    "작성일": c.get("publishedAt", "")[:10],
                })

            next_page_token = response.get("nextPageToken")

            # 진행률 업데이트
            progress = min(len(comments) / max_results, 1.0)
            progress_bar.progress(progress, text=f"💬 {len(comments)}개 수집 중...")

            if not next_page_token:
                break

        progress_bar.progress(1.0, text=f"✅ 총 {len(comments)}개 댓글 수집 완료!")

    except Exception as e:
        progress_bar.empty()
        if "commentsDisabled" in str(e):
            st.error("❌ 이 영상은 댓글이 비활성화되어 있습니다.")
        elif "quotaExceeded" in str(e):
            st.error("❌ API 일일 할당량을 초과했습니다. 내일 다시 시도해주세요.")
        else:
            st.error(f"❌ 오류 발생: {e}")
        return []

    return comments

# =============================================
# 📊 통계 카드 렌더링
# =============================================

def render_stat_card(col, number, label, prefix="", suffix=""):
    """통계 카드를 렌더링하는 함수"""
    with col:
        st.markdown(f"""
            <div class="stat-box">
                <div class="stat-number">{prefix}{number:,}{suffix}</div>
                <div class="stat-label">{label}</div>
            </div>
        """, unsafe_allow_html=True)

# =============================================
# 💬 댓글 카드 렌더링
# =============================================

def render_comment_card(author, text, likes, replies, date):
    """댓글 카드를 렌더링하는 함수"""
    st.markdown(f"""
        <div class="comment-card">
            <div class="author-name">👤 {author}</div>
            <div class="comment-text">{text}</div>
            <div class="comment-meta">
                👍 좋아요 {likes:,}개 &nbsp;|&nbsp;
                💬 답글 {replies}개 &nbsp;|&nbsp;
                📅 {date}
            </div>
        </div>
    """, unsafe_allow_html=True)

# =============================================
# 🚀 메인 앱
# =============================================

def main():

    # 타이틀
    st.markdown('<div class="main-title">🎬 유튜브 댓글 분석기</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">유튜브 영상 링크를 입력하면 댓글을 불러옵니다</div>', unsafe_allow_html=True)

    # API 초기화
    api_key = get_api_key()
    youtube = build("youtube", "v3", developerKey=api_key)

    # ── 입력 영역 ──────────────────────────────────
    st.markdown("---")

    col_input, col_option1, col_option2 = st.columns([3, 1, 1])

    with col_input:
        url_input = st.text_input(
            "🔗 유튜브 링크 입력",
            placeholder="https://www.youtube.com/watch?v=...",
            label_visibility="collapsed"
        )

    with col_option1:
        max_comments = st.selectbox(
            "최대 댓글 수",
            options=[50, 100, 200, 500],
            index=1
        )

    with col_option2:
        order = st.selectbox(
            "정렬 방식",
            options=["관련순", "최신순"],
            index=0
        )

    order_map = {"관련순": "relevance", "최신순": "time"}

    # 분석 버튼
    run_button = st.button("🔍 댓글 불러오기", use_container_width=True, type="primary")

    # ── 실행 ──────────────────────────────────────
    if run_button:
        if not url_input.strip():
            st.warning("⚠️ 유튜브 링크를 입력해주세요.")
            st.stop()

        video_id = extract_video_id(url_input.strip())

        if not video_id:
            st.error("❌ 올바른 유튜브 링크를 입력해주세요.")
            st.stop()

        # 영상 정보 불러오기
        with st.spinner("📡 영상 정보를 불러오는 중..."):
            video_info = get_video_info(youtube, video_id)

        if not video_info:
            st.error("❌ 영상 정보를 불러올 수 없습니다. 링크를 확인해주세요.")
            st.stop()

        # ── 영상 정보 표시 ─────────────────────────
        st.markdown("---")
        st.markdown("### 📺 영상 정보")

        info_col1, info_col2 = st.columns([1, 2])

        with info_col1:
            if video_info["썸네일"]:
                st.image(video_info["썸네일"], use_container_width=True)

        with info_col2:
            st.markdown(f"**🎬 제목:** {video_info['제목']}")
            st.markdown(f"**📺 채널:** {video_info['채널']}")
            st.markdown(f"**📅 업로드일:** {video_info['업로드일']}")
            st.markdown("---")

            s1, s2, s3 = st.columns(3)
            render_stat_card(s1, video_info["조회수"], "👀 조회수")
            render_stat_card(s2, video_info["좋아요수"], "👍 좋아요")
            render_stat_card(s3, video_info["댓글수"], "💬 전체 댓글")

        # ── 댓글 수집 ──────────────────────────────
        st.markdown("---")

        comments = get_comments(
            youtube,
            video_id,
            max_results=max_comments,
            order=order_map[order]
        )

        if not comments:
            st.stop()

        df = pd.DataFrame(comments)

        # ── 수집된 댓글 통계 ────────────────────────
        st.markdown("### 📊 수집된 댓글 통계")

        sc1, sc2, sc3, sc4 = st.columns(4)
        render_stat_card(sc1, len(df), "📥 수집된 댓글 수")
        render_stat_card(sc2, int(df["좋아요수"].mean()), "👍 평균 좋아요")
        render_stat_card(sc3, int(df["좋아요수"].max()), "🏆 최고 좋아요")
        render_stat_card(sc4, int(df["댓글"].apply(len).mean()), "✏️ 평균 글자수", suffix="자")

        # ── 댓글 목록 ──────────────────────────────
        st.markdown("---")
        st.markdown("### 💬 댓글 목록")

        # 필터 옵션
        filter_col1, filter_col2 = st.columns([2, 1])

        with filter_col1:
            search_keyword = st.text_input(
                "🔍 댓글 검색",
                placeholder="키워드를 입력하면 해당 댓글만 표시됩니다"
            )

        with filter_col2:
            sort_option = st.selectbox(
                "댓글 정렬",
                options=["수집 순서", "좋아요 많은 순", "좋아요 적은 순", "최신순", "오래된 순"]
            )

        # 필터 적용
        filtered_df = df.copy()

        if search_keyword:
            filtered_df = filtered_df[
                filtered_df["댓글"].str.contains(search_keyword, case=False, na=False)
            ]

        # 정렬 적용
        sort_map = {
            "수집 순서": ("index", False),
            "좋아요 많은 순": ("좋아요수", False),
            "좋아요 적은 순": ("좋아요수", True),
            "최신순": ("작성일", False),
            "오래된 순": ("작성일", True),
        }

        sort_col, sort_asc = sort_map[sort_option]
        if sort_col == "index":
            filtered_df = filtered_df.reset_index(drop=True)
        else:
            filtered_df = filtered_df.sort_values(by=sort_col, ascending=sort_asc).reset_index(drop=True)

        st.markdown(f"**검색 결과: {len(filtered_df):,}개 댓글**")

        if filtered_df.empty:
            st.info("😥 검색 결과가 없습니다.")
        else:
            # 페이지네이션
            comments_per_page = 20
            total_pages = max(1, (len(filtered_df) - 1) // comments_per_page + 1)

            page = st.number_input(
                f"페이지 (전체 {total_pages}페이지)",
                min_value=1,
                max_value=total_pages,
                value=1,
                step=1
            )

            start_idx = (page - 1) * comments_per_page
            end_idx = start_idx + comments_per_page
            page_df = filtered_df.iloc[start_idx:end_idx]

            for _, row in page_df.iterrows():
                render_comment_card(
                    author=row["작성자"],
                    text=row["댓글"],
                    likes=row["좋아요수"],
                    replies=row["답글수"],
                    date=row["작성일"]
                )

        # ── CSV 다운로드 ────────────────────────────
        st.markdown("---")
        st.markdown("### 💾 데이터 다운로드")

        csv_data = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

        st.download_button(
            label="📥 전체 댓글 CSV 다운로드",
            data=csv_data,
            file_name=f"comments_{video_id}.csv",
            mime="text/csv",
            use_container_width=True
        )


if __name__ == "__main__":
    main()
