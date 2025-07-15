import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Streamlit 앱 제목
st.title("Ecount ERP 경영지표 대시보드")

# 사이드바: API 설정 및 날짜 입력
st.sidebar.header("설정")
api_key = st.sidebar.text_input("API 인증 키", type="password")  # 보안 위해 입력받음
zone = st.sidebar.text_input("회사 존 ID")
start_date = st.sidebar.date_input("시작 날짜", value=datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("종료 날짜", value=datetime.now())

# API 호출 함수 (Ecount API 예시 - 실제 엔드포인트로 대체)
def fetch_sales_data(api_key, zone, start_date, end_date):
    base_url = "https://api.ecount.com/v1/"  # 실제 URL 확인
    endpoint = "sales/data"  # 가정: 매출 데이터 엔드포인트
    params = {
        'api_key': api_key,
        'zone': zone,
        'start_date': start_date.strftime("%Y-%m-%d"),
        'end_date': end_date.strftime("%Y-%m-%d")
    }
    response = requests.get(base_url + endpoint, params=params)
    if response.status_code == 200:
        return response.json().get('sales', [])  # JSON 데이터 반환 (구조에 따라 조정)
    else:
        st.error(f"API 호출 실패: {response.status_code} - {response.text}")
        return []

# 데이터 가져오기 버튼
if st.sidebar.button("데이터 불러오기"):
    if api_key and zone:
        data = fetch_sales_data(api_key, zone, start_date, end_date)
        if data:
            df = pd.DataFrame(data)
            if 'date' in df.columns and 'amount' in df.columns:  # 데이터 구조 확인
                df['date'] = pd.to_datetime(df['date'])
                df_monthly = df.resample('M', on='date').sum(numeric_only=True)
                df_monthly['growth_rate'] = df_monthly['amount'].pct_change() * 100
                
                # 테이블 표시
                st.subheader("월별 경영지표 테이블")
                st.dataframe(df_monthly)
                
                # 그래프 표시
                st.subheader("월별 매출 추이 그래프")
                fig, ax = plt.subplots(figsize=(10, 5))
                ax.plot(df_monthly.index, df_monthly['amount'], label='월별 매출', marker='o')
                ax.set_xlabel('월')
                ax.set_ylabel('매출액')
                ax.legend()
                st.pyplot(fig)
                
                # 추가 지표 예시
                total_sales = df['amount'].sum()
                avg_growth = df_monthly['growth_rate'].mean()
                st.metric("총 매출", f"{total_sales:,.0f} 원")
                st.metric("평균 성장률", f"{avg_growth:.2f}%")
            else:
                st.warning("데이터 구조가 예상과 다릅니다. API 응답을 확인하세요.")
        else:
            st.warning("데이터가 없습니다.")
    else:
        st.warning("API 키와 존 ID를 입력하세요.")

# 추가 설명
st.info("이 앱은 Ecount API에서 데이터를 가져와 경영지표를 계산합니다. 더 많은 지표(재고 회전율, ROI 등)를 추가하려면 df를 확장하세요.")
