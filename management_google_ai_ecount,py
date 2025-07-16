import streamlit as st
import pandas as pd
import plotly.express as px
import requests  # 이카운트 API 요청을 위해 필요

# --------------------------------------------------------------------------
# 이카운트 ERP API 연동 (가상 함수)
# 실제 환경에서는 이 부분에 이카운트 API와 통신하는 코드를 작성해야 합니다.
# --------------------------------------------------------------------------

def get_ecount_data(api_key, start_date, end_date):
    """
    이카운트 ERP에서 데이터를 가져오는 함수 (가상).
    실제로는 requests 라이브러리를 사용하여 API에 요청을 보내야 합니다.
    """
    # === 실제 API 연동 시 필요한 부분 ===
    # API_URL = "https://oapi.ecount.com/OAPI/V2/..."  # 실제 API 엔드포인트
    # headers = {"Authorization": f"Bearer {api_key}"}
    # params = {
    #     "start_date": start_date,
    #     "end_date": end_date,
    #     # 기타 필요한 파라미터 추가
    # }
    # response = requests.get(API_URL, headers=headers, params=params)
    # if response.status_code == 200:
    #     return response.json()
    # else:
    #     st.error("이카운트 API 데이터 조회에 실패했습니다.")
    #     return None
    # =====================================

    # --- 가상 데이터 생성 (실제 API 연동 전 테스트용) ---
    data = {
        'date': pd.to_datetime(pd.date_range(start_date, end_date)),
        'sales': [150, 200, 180, 220, 250, 230, 270, 300, 280, 320, 350, 330, 380, 400, 390],
        'purchase': [100, 120, 110, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230, 240],
        'inventory': [500, 530, 500, 590, 600, 680, 700, 730, 750, 780, 800, 820, 850, 880, 900],
        'profit': [50, 80, 70, 90, 110, 80, 110, 130, 100, 130, 150, 120, 160, 170, 150]
    }
    # 날짜 길이에 맞게 데이터 슬라이싱
    num_days = len(data['date'])
    for key in ['sales', 'purchase', 'inventory', 'profit']:
        data[key] = data[key][:num_days]

    return pd.DataFrame(data)
    # --------------------------------------------------


# --------------------------------------------------------------------------
# Streamlit 대시보드 구현
# --------------------------------------------------------------------------

st.set_page_config(layout="wide")

st.title("📈 경영지표 대시보드 (이카운트 ERP 연동)")

# --- 사이드바: API Key 및 날짜 범위 입력 ---
with st.sidebar:
    st.header("⚙️ 설정")
    api_key = st.text_input("이카운트 API Key", "YOUR_API_KEY", type="password")

    # 기본 날짜 설정 (최근 15일)
    end_date = pd.to_datetime("today")
    start_date = end_date - pd.Timedelta(days=14)

    date_range = st.date_input(
        "조회 기간",
        (start_date, end_date),
        format="YYYY-MM-DD"
    )

    # 날짜 범위가 올바르게 선택되었는지 확인
    if len(date_range) == 2:
        start_date, end_date = date_range
    else:
        st.warning("시작일과 종료일을 모두 선택해주세요.")
        st.stop()


# --- 데이터 로딩 및 전처리 ---
data = get_ecount_data(api_key, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

if data is not None:
    # --- 주요 지표 (KPI) 표시 ---
    st.header("📊 주요 경영 지표")
    total_sales = data['sales'].sum()
    total_profit = data['profit'].sum()
    current_inventory = data['inventory'].iloc[-1]

    col1, col2, col3 = st.columns(3)
    col1.metric("총 매출", f"{total_sales:,} 원")
    col2.metric("총 이익", f"{total_profit:,} 원")
    col3.metric("현재고", f"{current_inventory:,} 개")

    st.markdown("---")

    # --- 시각화 ---
    st.header("📈 시계열 데이터 분석")

    # 매출 및 매입 추이
    fig_sales_purchase = px.line(
        data,
        x='date',
        y=['sales', 'purchase'],
        title='매출 및 매입 추이',
        labels={'value': '금액 (원)', 'variable': '항목', 'date': '날짜'},
        color_discrete_map={'sales': '#1f77b4', 'purchase': '#ff7f0e'}
    )
    st.plotly_chart(fig_sales_purchase, use_container_width=True)

    # 이익 및 재고 추이
    col1, col2 = st.columns(2)
    with col1:
        fig_profit = px.bar(
            data,
            x='date',
            y='profit',
            title='일별 이익',
            labels={'profit': '이익 (원)', 'date': '날짜'}
        )
        st.plotly_chart(fig_profit, use_container_width=True)
    with col2:
        fig_inventory = px.area(
            data,
            x='date',
            y='inventory',
            title='재고 추이',
            labels={'inventory': '재고량 (개)', 'date': '날짜'}
        )
        st.plotly_chart(fig_inventory, use_container_width=True)


    # --- 원본 데이터 표시 ---
    st.header("📄 원본 데이터")
    st.dataframe(data.style.format({"sales": "{:,}", "purchase": "{:,}", "profit": "{:,}", "inventory": "{:,}"}))

else:
    st.info("사이드바에서 API Key와 날짜를 설정한 후 데이터를 조회해주세요.")
