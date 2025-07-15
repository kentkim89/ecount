import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# Streamlit 앱 제목
st.title("Ecount ERP 경영지표 대시보드")

# 사이드바: API 설정 및 날짜 입력
st.sidebar.header("설정")
com_code = st.sidebar.text_input("회사 코드 (COM_CODE, 6자리)")
user_id = st.sidebar.text_input("사용자 ID (USER_ID)")
api_cert_key = st.sidebar.text_input("API 인증 키 (API_CERT_KEY)", type="password")
zone = st.sidebar.text_input("존 ID (ZONE, optional - 자동 조회 가능)")
start_date = st.sidebar.date_input("시작 날짜", value=datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("종료 날짜", value=datetime.now())
lan_type = 'ko-KR'  # 기본값: 한국어

# ZONE 자동 조회 함수 (COM_CODE로 ZONE 가져오기)
def fetch_zone(com_code):
    url = "https://sboapi.ecount.com/OAPI/V2/Zone"
    payload = {"COM_CODE": com_code}
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("Data", {}).get("ZONE")  # ZONE 값 추출 (예: 'CC')
    else:
        st.error(f"ZONE 조회 실패: {response.status_code} - {response.text}")
        return None

# 로그인 함수 (SESSION_ID 가져오기)
def login(com_code, user_id, zone, api_cert_key, lan_type):
    base_url = f"https://sboapi{zone}.ecount.com/OAPI/V2/"
    endpoint = "OAPILogin"
    url = base_url + endpoint
    payload = {
        "COM_CODE": com_code,
        "USER_ID": user_id,
        "ZONE": zone,
        "API_CERT_KEY": api_cert_key,
        "LAN_TYPE": lan_type
    }
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("Data", {}).get("SESSION_ID")  # SESSION_ID 추출
    else:
        st.error(f"로그인 실패: {response.status_code} - {response.text}")
        return None

# 매출 데이터 가져오기 함수 (예시 엔드포인트 - 실제로 Ecount 문서 확인)
def fetch_sales_data(session_id, zone, com_code, user_id, api_cert_key, lan_type, start_date, end_date):
    base_url = f"https://sboapi{zone}.ecount.com/OAPI/V2/"
    endpoint = "Sales/SearchSales"  # 예시: 실제 매출 조회 엔드포인트로 교체 (e.g., SearchSales 또는 GetListSales)
    url = base_url + endpoint + f"?SESSION_ID={session_id}"
    payload = {
        "COM_CODE": com_code,
        "USER_ID": user_id,
        "ZONE": zone,
        "API_CERT_KEY": api_cert_key,
        "LAN_TYPE": lan_type,
        "FROM_DATE": start_date.strftime("%Y%m%d"),  # 예시 파라미터 (문서 확인)
        "TO_DATE": end_date.strftime("%Y%m%d")
    }
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get("Data", [])  # 실제 응답 구조에 따라 조정 (e.g., data['sales'])
    else:
        st.error(f"API 호출 실패: {response.status_code} - {response.text}")
        return []

# 데이터 가져오기 버튼
if st.sidebar.button("데이터 불러오기"):
    if com_code and user_id and api_cert_key:
        # ZONE 자동 조회 nếu 없음
        if not zone:
            zone = fetch_zone(com_code)
            if not zone:
                st.stop()

        # 로그인
        session_id = login(com_code, user_id, zone, api_cert_key, lan_type)
        if not session_id:
            st.stop()

        # 매출 데이터 가져오기
        data = fetch_sales_data(session_id, zone, com_code, user_id, api_cert_key, lan_type, start_date, end_date)
        if data:
            df = pd.DataFrame(data)
            if 'date' in df.columns and 'amount' in df.columns:  # 실제 컬럼명으로 조정 (e.g., 'IO_DATE', 'SUPPLY_AMT')
                df['date'] = pd.to_datetime(df['date'])
                df_monthly = df.resample('M', on='date').sum(numeric_only=True)
                df_monthly['growth_rate'] = df_monthly['amount'].pct_change() * 100
                
                # 테이블 표시
                st.subheader("월별 경영지표 테이블")
                st.dataframe(df_monthly)
                
                # 그래프 표시
                st.subheader("월별 매출 추이 그래프")
                df_chart = df_monthly.reset_index()[['date', 'amount']].rename(columns={'date': '월', 'amount': '매출액'})
                st.line_chart(df_chart, x='월', y='매출액')
                
                # 추가 지표
                total_sales = df['amount'].sum()
                avg_growth = df_monthly['growth_rate'].mean()
                st.metric("총 매출", f"{total_sales:,.0f} 원")
                st.metric("평균 성장률", f"{avg_growth:.2f}%")
            else:
                st.warning("데이터 구조가 예상과 다릅니다. API 응답과 컬럼명('date', 'amount' 등)을 확인하세요.")
        else:
            st.warning("데이터가 없습니다.")
    else:
        st.warning("필수 입력값(COM_CODE, USER_ID, API_CERT_KEY)을 입력하세요.")

# 추가 설명
st.info("이 앱은 Ecount API 로그인 후 데이터를 가져옵니다. 실제 엔드포인트와 파라미터는 Ecount 내부 API 문서를 확인하세요 (로그인 후 Self-Customizing > 도움말 또는 지원팀 문의). 더 많은 지표 추가 가능.")
