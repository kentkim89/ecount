import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# Streamlit 앱 제목
st.title("Ecount ERP 경영지표 대시보드 (테스트 API 지원)")

# 사이드바: API 설정 및 날짜 입력
st.sidebar.header("설정")
com_code = st.sidebar.text_input("회사 코드 (COM_CODE, 테스트 계정의 6자리 코드)")
user_id = st.sidebar.text_input("사용자 ID (USER_ID, 로그인 ID)")
api_cert_key = st.sidebar.text_input("API 인증 키 (API_CERT_KEY, 테스트 키)", type="password")
zone = st.sidebar.text_input("존 ID (ZONE, optional - 자동 조회)")
start_date = st.sidebar.date_input("시작 날짜", value=datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("종료 날짜", value=datetime.now())
lan_type = 'ko-KR'  # 기본: 한국어

# ZONE 자동 조회 함수
def fetch_zone(com_code):
    url = "https://sboapi.ecount.com/OAPI/V2/Zone"
    payload = {"COM_CODE": com_code}
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("Data", {}).get("ZONE")  # ZONE 반환 (e.g., 'CC')
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
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("Data", {}).get("SESSION_ID")
    else:
        st.error(f"로그인 실패: {response.status_code} - {response.text}")
        return None

# 데이터 가져오기 함수 (검증된 API 엔드포인트 사용: 매출/매입 전표 조회)
def fetch_sales_data(session_id, zone, com_code, user_id, api_cert_key, lan_type, start_date, end_date):
    base_url = f"https://sboapi{zone}.ecount.com/OAPI/V2/"
    endpoint = "Account/SearchSlip"  # 검증된 API 예시: 매출/매입 전표 조회 (문서 확인 필요; 대안: Account/SearchSlipII)
    url = base_url + endpoint + f"?SESSION_ID={session_id}"
    payload = {
        "COM_CODE": com_code,
        "USER_ID": user_id,
        "ZONE": zone,
        "API_CERT_KEY": api_cert_key,
        "LAN_TYPE": lan_type,
        "FROM_DATE": start_date.strftime("%Y%m%d"),
        "TO_DATE": end_date.strftime("%Y%m%d"),
        # 추가 파라미터 (필요 시): "SLIP_TYPE": "S"  # S: 매출, P: 매입 등 문서 확인
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    
    # 디버깅: raw 응답 출력
    st.subheader("API Raw 응답 (디버깅용)")
    st.write(response.json())  # 전체 응답 확인
    
    if response.status_code == 200:
        data = response.json().get("Data", {})
        if isinstance(data, dict) and "List" in data:
            return data["List"]
        elif isinstance(data, list):
            return data
        else:
            st.warning("응답에 데이터가 없거나 구조가 다릅니다. raw 응답 확인.")
            return []
    else:
        st.error(f"API 호출 실패: {response.status_code} - {response.text}")
        return []

# 데이터 가져오기 버튼
if st.sidebar.button("데이터 불러오기"):
    if com_code and user_id and api_cert_key:
        # ZONE 자동 조회
        if not zone:
            zone = fetch_zone(com_code)
            if not zone:
                st.stop()

        # 로그인
        session_id = login(com_code, user_id, zone, api_cert_key, lan_type)
        if not session_id:
            st.stop()

        # 데이터 가져오기
        data = fetch_sales_data(session_id, zone, com_code, user_id, api_cert_key, lan_type, start_date, end_date)
        if data:
            df = pd.DataFrame(data)
            # 컬럼명 실제로 조정 (raw 응답에서 확인 e.g., 'SLIP_DATE' for date, 'SUPPLY_AMT' for amount)
            if 'SLIP_DATE' in df.columns and 'SUPPLY_AMT' in df.columns:
                df['date'] = pd.to_datetime(df['SLIP_DATE'], format='%Y%m%d', errors='coerce')
                df['amount'] = pd.to_numeric(df['SUPPLY_AMT'], errors='coerce')
                df = df.dropna(subset=['date', 'amount'])
                if not df.empty:
                    df_monthly = df.resample('M', on='date').sum(numeric_only=True)
                    df_monthly['growth_rate'] = df_monthly['amount'].pct_change() * 100
                    
                    st.subheader("월별 경영지표 테이블")
                    st.dataframe(df_monthly)
                    
                    st.subheader("월별 매출 추이 그래프")
                    df_chart = df_monthly.reset_index()[['date', 'amount']].rename(columns={'date': '월', 'amount': '매출액'})
                    st.line_chart(df_chart, x='월', y='매출액')
                    
                    total_sales = df['amount'].sum()
                    avg_growth = df_monthly['growth_rate'].mean()
                    st.metric("총 매출", f"{total_sales:,.0f} 원")
                    st.metric("평균 성장률", f"{avg_growth:.2f}%")
                else:
                    st.warning("유효한 데이터가 없습니다. raw 응답 확인.")
            else:
                st.warning("예상 컬럼 (SLIP_DATE, SUPPLY_AMT)이 없습니다. raw 응답에서 실제 컬럼명으로 코드 조정하세요.")
        else:
            st.warning("데이터가 없습니다. 검증 요청 후 재시도하거나, Ecount에 샘플 데이터 입력하세요.")
    else:
        st.warning("필수 입력값 (COM_CODE, USER_ID, API_CERT_KEY)을 입력하세요.")

# 추가 설명
st.info("미검증 API는 지원팀 검증 후 사용하세요. raw 응답으로 구조 확인. 더 많은 지표 추가 가능.")
