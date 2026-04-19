"""
VNINDEX AI Analyst - Streamlit Dashboard
Giao diện chính: Dashboard, Chiến lược, Kho lưu trữ.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from database.models import init_db
from database.db_manager import DatabaseManager
from main import run_full_pipeline, pipeline_state

# ─── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VNINDEX AI Analyst",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* Global */
    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* Main header */
    .main-header {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }
    .main-header h1 {
        color: #00d4ff;
        font-size: 2.2rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .main-header p {
        color: #a0aec0;
        font-size: 0.95rem;
        margin-top: 0.3rem;
    }

    /* Metric cards */
    .metric-card {
        background: linear-gradient(145deg, #1a1a2e, #16213e);
        padding: 1.5rem;
        border-radius: 14px;
        border: 1px solid rgba(255,255,255,0.06);
        box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 30px rgba(0,100,255,0.15);
    }
    .metric-label {
        color: #8892b0;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600;
    }
    .metric-value {
        color: #e6f1ff;
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0.3rem 0;
    }
    .metric-delta-pos { color: #64ffda; font-size: 0.85rem; font-weight: 500; }
    .metric-delta-neg { color: #ff6b6b; font-size: 0.85rem; font-weight: 500; }
    .metric-delta-neutral { color: #ffd93d; font-size: 0.85rem; font-weight: 500; }

    /* Status badges */
    .badge-buy {
        background: linear-gradient(135deg, #00b09b, #96c93d);
        color: white;
        padding: 4px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.8rem;
        display: inline-block;
    }
    .badge-sell {
        background: linear-gradient(135deg, #eb3349, #f45c43);
        color: white;
        padding: 4px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.8rem;
        display: inline-block;
    }
    .badge-hold {
        background: linear-gradient(135deg, #f7971e, #ffd200);
        color: #1a1a2e;
        padding: 4px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.8rem;
        display: inline-block;
    }
    .badge-watch {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        padding: 4px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.8rem;
        display: inline-block;
    }

    /* Alert box */
    .alert-box {
        background: rgba(255, 107, 107, 0.1);
        border-left: 4px solid #ff6b6b;
        padding: 1rem 1.2rem;
        border-radius: 0 10px 10px 0;
        margin: 0.5rem 0;
    }
    .alert-box-warn {
        background: rgba(255, 217, 61, 0.1);
        border-left: 4px solid #ffd93d;
        padding: 1rem 1.2rem;
        border-radius: 0 10px 10px 0;
        margin: 0.5rem 0;
    }
    .alert-box-ok {
        background: rgba(100, 255, 218, 0.1);
        border-left: 4px solid #64ffda;
        padding: 1rem 1.2rem;
        border-radius: 0 10px 10px 0;
        margin: 0.5rem 0;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0c29 0%, #1a1a2e 100%);
    }
    section[data-testid="stSidebar"] .stMarkdown {
        color: #a0aec0;
    }

    /* Table styling */
    .dataframe-container {
        border-radius: 12px;
        overflow: hidden;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px 10px 0 0;
        padding: 10px 24px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


def get_recommendation_badge(rec: str) -> str:
    """Trả về HTML badge cho khuyến nghị."""
    badge_map = {
        "MUA": "badge-buy",
        "BÁN": "badge-sell",
        "GIỮ": "badge-hold",
        "THEO DÕI": "badge-watch",
    }
    css_class = badge_map.get(rec, "badge-watch")
    return f'<span class="{css_class}">{rec}</span>'


def render_metric_card(label: str, value: str, delta: str = None,
                       delta_type: str = "neutral") -> str:
    delta_class = f"metric-delta-{delta_type}"
    delta_html = f'<div class="{delta_class}">{delta}</div>' if delta else ""
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>
    """


def main():
    db = DatabaseManager()

    # ─── Sidebar ───────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 🤖 VNINDEX AI Analyst")
        st.markdown("**v1.0** - Powered by Gemma")
        st.markdown("---")

        if st.button("🚀 Chạy Pipeline Ngay", use_container_width=True, type="primary"):
            with st.spinner("Đang chạy pipeline phân tích..."):
                run_full_pipeline()
            st.success("✅ Pipeline hoàn tất!")
            st.rerun()

        st.markdown("---")
        st.markdown("#### ⚙️ Cấu hình")
        st.text(f"Model: {config.OLLAMA_MODEL}")
        st.text(f"DB: {config.DB_PATH.name}")
        st.text(f"Temp: {config.OLLAMA_PARAMS['temperature']}")

        st.markdown("---")
        st.markdown("#### 📅 Lịch tự động")
        schedule_info = {
            "Vĩ mô": config.SCHEDULE_MACRO,
            "Tin tức": config.SCHEDULE_NEWS,
            "Kỹ thuật": config.SCHEDULE_TECHNICAL,
            "CIO": config.SCHEDULE_CIO,
            "Báo cáo": config.SCHEDULE_REPORT,
        }
        for name, time_str in schedule_info.items():
            st.text(f"  {time_str} → {name}")

    # ─── Header ────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="main-header">
        <h1>📈 VNINDEX AI Analyst</h1>
        <p>Hệ thống phân tích đa agent | Cập nhật: """ + datetime.now().strftime("%d/%m/%Y %H:%M") + """</p>
    </div>
    """, unsafe_allow_html=True)

    # ─── Tabs ──────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["🏠 Dashboard", "📋 Chiến lược", "⭐ Yêu thích", "📁 Kho lưu trữ"])

    # ═══════════════════════════════════════════════════════════════════════
    # TAB 1: DASHBOARD
    # ═══════════════════════════════════════════════════════════════════════
    with tab1:
        # Metrics row
        col1, col2, col3, col4 = st.columns(4)

        macro = pipeline_state.get("macro_result") or {}
        tech = pipeline_state.get("tech_result") or {}
        news = pipeline_state.get("news_result") or {}
        risk = pipeline_state.get("risk_result") or {}

        with col1:
            dxy = macro.get("dxy", "N/A")
            st.markdown(render_metric_card(
                "DXY Index", str(dxy),
                macro.get("status", ""), "pos" if macro.get("status") == "OK" else "neg"
            ), unsafe_allow_html=True)

        with col2:
            us10y = macro.get("us10y", "N/A")
            st.markdown(render_metric_card(
                "US 10Y Yield", f"{us10y}%" if us10y != "N/A" else "N/A"
            ), unsafe_allow_html=True)

        with col3:
            usd_vnd = macro.get("usd_vnd", "N/A")
            change = macro.get("exchange_rate_change_pct")
            delta = f"{change:+.2f}% vs TB5" if change else None
            delta_type = "neg" if change and change > 0.5 else "pos"
            st.markdown(render_metric_card(
                "USD/VND", f"{usd_vnd:,.0f}" if isinstance(usd_vnd, (int, float)) else "N/A",
                delta, delta_type
            ), unsafe_allow_html=True)

        with col4:
            sentiment = news.get("market_sentiment", 0)
            s_type = "pos" if sentiment > 0 else "neg" if sentiment < 0 else "neutral"
            st.markdown(render_metric_card(
                "Market Sentiment", f"{sentiment:+.4f}" if sentiment else "N/A",
                f"{'Tích cực' if sentiment > 0 else 'Tiêu cực' if sentiment < 0 else 'Trung tính'}",
                s_type
            ), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Market Breadth + Health
        col_left, col_right = st.columns([3, 2])

        with col_left:
            st.markdown("### 📊 Sức khỏe thị trường")
            breadth = tech.get("market_breadth", {})

            if breadth:
                adv = breadth.get("advance", 0)
                dec = breadth.get("decline", 0)
                unch = breadth.get("unchanged", 0)

                # Gauge chart
                ratio = breadth.get("ratio", 0.5)
                fig = go.Figure(go.Indicator(
                    mode="gauge+number+delta",
                    value=ratio * 100,
                    title={'text': "Market Breadth Index", 'font': {'size': 16, 'color': '#a0aec0'}},
                    number={'suffix': '%', 'font': {'size': 36, 'color': '#e6f1ff'}},
                    gauge={
                        'axis': {'range': [0, 100], 'tickcolor': '#4a5568'},
                        'bar': {'color': '#00d4ff'},
                        'bgcolor': '#1a1a2e',
                        'borderwidth': 0,
                        'steps': [
                            {'range': [0, 30], 'color': 'rgba(255, 107, 107, 0.3)'},
                            {'range': [30, 50], 'color': 'rgba(255, 217, 61, 0.3)'},
                            {'range': [50, 70], 'color': 'rgba(100, 255, 218, 0.2)'},
                            {'range': [70, 100], 'color': 'rgba(100, 255, 218, 0.4)'},
                        ],
                        'threshold': {
                            'line': {'color': '#ff6b6b', 'width': 3},
                            'thickness': 0.8,
                            'value': 50,
                        },
                    },
                ))
                fig.update_layout(
                    height=280,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font={'color': '#e6f1ff'},
                    margin=dict(l=20, r=20, t=40, b=20),
                )
                st.plotly_chart(fig, use_container_width=True)

                # Breadth bar
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(name='Tăng', x=['Breadth'], y=[adv],
                                      marker_color='#64ffda'))
                fig2.add_trace(go.Bar(name='Giảm', x=['Breadth'], y=[dec],
                                      marker_color='#ff6b6b'))
                fig2.add_trace(go.Bar(name='Đứng', x=['Breadth'], y=[unch],
                                      marker_color='#ffd93d'))
                fig2.update_layout(
                    barmode='group', height=200,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font={'color': '#a0aec0'},
                    margin=dict(l=20, r=20, t=20, b=20),
                    legend=dict(orientation="h", yanchor="bottom", y=-0.3),
                )
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Chưa có dữ liệu Market Breadth. Hãy chạy Pipeline.")

        with col_right:
            st.markdown("### 🚨 Cảnh báo")
            all_alerts = (
                macro.get("alerts", []) +
                risk.get("alerts", [])
            )

            if all_alerts:
                for alert in all_alerts:
                    severity = alert.get("severity", "MEDIUM")
                    css = "alert-box" if severity in ["HIGH", "CRITICAL"] else "alert-box-warn"
                    st.markdown(f"""
                    <div class="{css}">
                        <strong>{alert.get('type', '')}</strong><br>
                        {alert.get('message', '')}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="alert-box-ok">
                    <strong>✅ Tất cả bình thường</strong><br>
                    Không có cảnh báo rủi ro nào.
                </div>
                """, unsafe_allow_html=True)

            # Kéo trụ warning
            if risk.get("keo_tru_warning"):
                st.markdown("""
                <div class="alert-box">
                    <strong>🔴 XANH VỎ ĐỎ LÒNG</strong><br>
                    VNINDEX tăng nhưng đa số cổ phiếu giảm. Cẩn thận kéo trụ!
                </div>
                """, unsafe_allow_html=True)

            # Position adjustment
            adj = risk.get("position_adjustment", 1.0)
            if adj < 1.0:
                st.markdown(f"""
                <div class="alert-box-warn">
                    <strong>📉 Giảm tỷ trọng</strong><br>
                    Chỉ mua {adj*100:.0f}% khối lượng do áp lực tỷ giá.
                </div>
                """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # TAB 2: CHIẾN LƯỢC
    # ═══════════════════════════════════════════════════════════════════════
    with tab2:
        st.markdown("### 📋 Khuyến nghị đầu tư")

        cio = pipeline_state.get("cio_result") or {}
        decisions = cio.get("decisions", [])

        if decisions:
            # Overall assessment
            st.markdown(f"""
            <div class="metric-card" style="margin-bottom: 1.5rem;">
                <div class="metric-label">Đánh giá thị trường</div>
                <div style="color: #e6f1ff; margin-top: 0.5rem;">{cio.get('market_assessment', 'N/A')}</div>
                <div style="margin-top: 0.5rem;">
                    Mức rủi ro: <strong style="color: {'#ff6b6b' if cio.get('risk_level') in ['CAO', 'RẤT CAO'] else '#ffd93d' if cio.get('risk_level') == 'TRUNG BÌNH' else '#64ffda'}">{cio.get('risk_level', 'N/A')}</strong>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Decision cards
            for dec in decisions:
                sym = dec.get("symbol", "N/A")
                rec = dec.get("recommendation", "N/A")
                reason = dec.get("reasoning", "")
                stop = dec.get("trailing_stop")
                conf = dec.get("confidence", 0)

                badge = get_recommendation_badge(rec)
                stop_html = f"<br>📍 Trailing Stop: <strong>{stop:,.0f}</strong>" if stop else ""
                conf_bar_color = "#64ffda" if conf > 0.7 else "#ffd93d" if conf > 0.4 else "#ff6b6b"

                st.markdown(f"""
                <div class="metric-card" style="margin-bottom: 0.8rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="color: #00d4ff; font-size: 1.3rem; font-weight: 700;">{sym}</span>
                            <span style="margin-left: 12px;">{badge}</span>
                        </div>
                        <div style="text-align: right;">
                            <div class="metric-label">Độ tin cậy</div>
                            <div style="background: #2d2d44; border-radius: 10px; height: 8px; width: 100px; margin-top: 4px;">
                                <div style="background: {conf_bar_color}; height: 100%; border-radius: 10px; width: {conf*100:.0f}%;"></div>
                            </div>
                            <span style="color: #8892b0; font-size: 0.75rem;">{conf*100:.0f}%</span>
                        </div>
                    </div>
                    <div style="color: #a0aec0; margin-top: 0.5rem; font-size: 0.9rem;">
                        {reason}{stop_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Chưa có quyết định. Hãy chạy Pipeline để nhận khuyến nghị.")

        # Trailing Stop table
        stops = risk.get("trailing_stops", {}) if risk else {}
        if stops:
            st.markdown("### 📍 Bảng Trailing Stop")
            import pandas as pd
            stop_data = []
            for sym, s in stops.items():
                stop_data.append({
                    "Mã": sym,
                    "Giá hiện tại": f"{s.get('current_price', 0):,.0f}",
                    "Giá cao nhất 20P": f"{s.get('price_max_20', 0):,.0f}",
                    "ATR(14)": f"{s.get('atr_14', 0):,.0f}",
                    "Stop Loss": f"{s.get('stop_loss', 0):,.0f}",
                    "Khoảng cách (%)": f"{s.get('distance_pct', 0):.1f}%",
                })
            st.dataframe(pd.DataFrame(stop_data), use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════════════════════════════════════
    # TAB 3: YÊU THÍCH
    # ═══════════════════════════════════════════════════════════════════════
    with tab3:
        st.markdown("### ⭐ Danh mục theo dõi")
        
        all_tickers = db.get_all_tickers()
        fav_tickers = db.get_favorite_tickers()
        fav_symbols = [t["symbol"] for t in fav_tickers]
        
        # Chọn thêm mã vào danh sách yêu thích
        options = [t["symbol"] for t in all_tickers]
        selected_favs = st.multiselect("Chọn mã để thêm vào Yêu thích:", options, default=fav_symbols)
        
        if st.button("Lưu thay đổi"):
            # Cập nhật db
            for sym in options:
                is_fav = sym in selected_favs
                db.toggle_favorite(sym, is_fav)
            st.success("Đã cập nhật danh sách yêu thích!")
            st.rerun()
            
        st.markdown("---")
        if selected_favs:
            import pandas as pd
            fav_data = []
            for sym in selected_favs:
                latest = db.get_latest_price(sym)
                ticker_info = db.get_ticker(sym)
                if latest and ticker_info:
                    fav_data.append({
                        "Mã": sym,
                        "Công ty": ticker_info.get("company_name", ""),
                        "Sàn": ticker_info.get("exchange", ""),
                        "Ngành": ticker_info.get("industry", ""),
                        "Giá": f"{latest.get('close', 0):,.0f}",
                        "RSI(14)": f"{latest.get('rsi_14', 0):.2f}" if latest.get('rsi_14') else "N/A",
                        "MACD": f"{latest.get('macd', 0):.2f}" if latest.get('macd') else "N/A"
                    })
            if fav_data:
                st.dataframe(pd.DataFrame(fav_data), use_container_width=True, hide_index=True)
            else:
                st.info("Chưa có dữ liệu giá cho các mã này. Hãy chạy pipeline hoặc thu thập dữ liệu.")
        else:
            st.info("Danh sách yêu thích đang trống.")

    # ═══════════════════════════════════════════════════════════════════════
    # TAB 4: KHO LƯU TRỮ
    # ═══════════════════════════════════════════════════════════════════════
    with tab4:
        st.markdown("### 📁 Báo cáo PDF đã xuất")

        reports_dir = config.REPORTS_DIR
        if reports_dir.exists():
            pdf_files = sorted(reports_dir.glob("*.pdf"), reverse=True)
            if pdf_files:
                for pdf_file in pdf_files:
                    col_a, col_b, col_c = st.columns([3, 2, 1])
                    with col_a:
                        st.markdown(f"📄 **{pdf_file.name}**")
                    with col_b:
                        size_kb = pdf_file.stat().st_size / 1024
                        mod_time = datetime.fromtimestamp(pdf_file.stat().st_mtime)
                        st.text(f"{size_kb:.1f} KB | {mod_time.strftime('%H:%M %d/%m')}")
                    with col_c:
                        with open(pdf_file, "rb") as f:
                            st.download_button(
                                "⬇️ Tải",
                                data=f.read(),
                                file_name=pdf_file.name,
                                mime="application/pdf",
                                key=f"dl_{pdf_file.name}",
                            )
                    st.markdown("---")
            else:
                st.info("Chưa có báo cáo nào. Chạy Pipeline để tạo báo cáo.")
        else:
            st.info("Thư mục reports chưa tồn tại.")


if __name__ == "__main__":
    init_db()
    main()
