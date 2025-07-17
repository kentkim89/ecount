# 라이브러리 import
import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import json

# --- 1. 기본 페이지 설정 ---
st.set_page_config(
    page_title="ECOUNT 매출 대시보드",
    page_icon="📊",
    layout="wide",
)

# --- 2. ECOUNT API 연동 함수 ---

# API 로그인을 위한 함수
def ecount_login(com_code, user_id, api_cert_key, zone="AA"):
    """ECOUNT API 로그인을 하고 세션 ID를 반환합니다."""
    url = f'https://sboapi{zone}.ecount.com/OAPI/V2/OAPILogin'
    data = {
        "COM_CODE": com_code,
        "USER_ID": user_id,
        "API_CERT_KEY": api_cert_key,
        "LAN_TYPE": "ko-KR",
        "ZONE": zone
    }
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
        contents = response.json()
        if contents.get("Status") == "200" and "SESSION_ID" in contents.get("Data", {}).get("Datas", {}):
            return contents['Data']['Datas']['SESSION_ID'], None
        else:
            error_message = contents.get("Error", {}).get("Message", "알 수 없는 로그인 오류")
            return None, error_message
    except requests.exceptions.RequestException as e:
        return None, f"API 요청 실패: {e}"
    except json.JSONDecodeError:
        return None, f"API 응답 분석 실패: {response.text}"

# 판매 데이터 조회를 위한 함수
def get_sales_data(session_id, from_date, to_date, zone="AA"):
    """지정된 기간의 판매 데이터를 ECOUNT API로 조회합니다."""
    url = f'https://sboapi{zone}.ecount.com/OAPI/V2/Sale/GetListSale'
    data = {
        "SESSION_ID": session_id,
        "FROM_DATE": from_date,
        "TO_DATE": to_date
    }
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        contents = response.json()
        if contents.get("Status") == "200":
            return contents.get("Data", []), None
        else:
            # "Please login" 오류를 명확하게 처리
            if "Errors" in contents and any("EXP00001" in error.get("Code", "") for error in contents["Errors"]):
                 return None, "API 키(세션) 인증에 실패했습니다. API 키가 '검증' 상태인지, 사용자 권한이 충분한지 확인하세요."
            error_message = contents.get("Error", {}).get("Message", "데이터 조회 중 오류 발생")
            return None, error_message
    except requests.exceptions.RequestException as e:
        return None, f"API 요청 실패: {e}"
    except json.JSONDecodeError:
        return None, f"API 응답 분석 실패: {response.text}"


# --- 3. Streamlit UI 구성 ---

# 사이드바: 사용자 입력
with st.sidebar:
    st.header("⚙️ ECOUNT 연동 정보")
    st.info("이 정보는 서버에 저장되지 않습니다. Streamlit의 Secrets 기능을 사용하여 안전하게 관리하세요.", icon="🔒")

    # Streamlit의 Secrets 기능 사용을 권장
    # 로컬 테스트 시에는 직접 입력할 수 있도록 구성
    default_com_code = st.secrets.get("ECOUNT_COM_CODE", "")
    default_user_id = st.secrets.get("ECOUNT_USER_ID", "")
    default_api_key = st.secrets.get("ECOUNT_API_KEY", "")

    com_code = st.text_input("회사코드", value=default_com_code, placeholder="예: 123456")
    user_id = st.text_input("사용자 ID", value=default_user_id, placeholder="예: admin")
    api_key = st.text_input("API 인증키", value=default_api_key, type="password", placeholder="발급받은 API 인증키")

    st.markdown("---")
    st.header("🗓️ 조회 기간 선택")
    
    # 기본값: 오늘 날짜
    today = datetime.now()
    selected_date = st.date_input(
        "조회할 날짜를 선택하세요",
        today,
        min_value=today - timedelta(days=365*3), # 3년 전까지
        max_value=today,
        format="YYYY-MM-DD"
    )

    # 조회 버튼
    if st.button("📈 데이터 조회하기"):
        # 입력값 검증
        if not all([com_code, user_id, api_key, selected_date]):
            st.error("모든 연동 정보와 날짜를 입력해주세요.")
        else:
            # 로딩 상태 표시
            with st.spinner('ECOUNT에 로그인 중...'):
                session_id, error = ecount_login(com_code, user_id, api_key)

            if error:
                st.error(f"로그인 실패: {error}")
            else:
                st.success("로그인 성공!")
                # 날짜 형식 변환 (YYYYMMDD)
                from_date = selected_date.strftime("%Y%m%d")
                to_date = selected_date.strftime("%Y%m%d")

                with st.spinner(f"{selected_date.strftime('%Y년 %m월 %d일')}의 판매 데이터를 가져오는 중..."):
                    sales_data, error = get_sales_data(session_id, from_date, to_date)
                
                if error:
                    st.error(f"데이터 조회 실패: {error}")
                    # 세션 정보를 st.session_state에서 삭제
                    if 'sales_df' in st.session_state:
                        del st.session_state['sales_df']
                elif not sales_data:
                    st.warning("해당 날짜에 판매 데이터가 없습니다.")
                    if 'sales_df' in st.session_state:
                        del st.session_state['sales_df']
                else:
                    # 데이터 처리 및 세션 상태에 저장
                    df = pd.DataFrame(sales_data)
                    # 숫자형 데이터 변환 (오류 발생 시 0으로 처리)
                    numeric_cols = ['QTY', 'PRICE', 'SUPPLY_AMT', 'VAT_AMT', 'TOTAL_AMT']
                    for col in numeric_cols:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    st.session_state['sales_df'] = df
                    st.success("데이터를 성공적으로 가져왔습니다!")


# 메인 화면: 대시보드
st.title("📊 ECOUNT 일일 매출 대시보드")

# st.session_state에 데이터가 있을 경우에만 대시보드 표시
if 'sales_df' in st.session_state:
    df = st.session_state['sales_df']
    
    st.markdown(f"### 📅 **{pd.to_datetime(df['IO_DATE'].iloc[0]).strftime('%Y년 %m월 %d일')} 판매 현황 요약**")
    
    # --- 4. 핵심 지표 (KPI) 표시 ---
    total_revenue = int(df['TOTAL_AMT'].sum())
    total_sales_count = len(df['IO_NO'].unique())
    total_items_sold = int(df['QTY'].sum())

    col1, col2, col3 = st.columns(3)
    col1.metric("총 매출액 (합계)", f"{total_revenue:,} 원")
    col2.metric("총 판매 건수", f"{total_sales_count} 건")
    col3.metric("총 판매 수량", f"{total_items_sold:,} 개")

    st.markdown("---")

    # --- 5. 데이터 시각화 ---
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📦 품목별 판매 수량")
        # 품목별로 수량 합계 계산
        items_by_qty = df.groupby('PROD_DES')['QTY'].sum().sort_values(ascending=False)
        st.bar_chart(items_by_qty)

    with col2:
        st.subheader("🏢 거래처별 매출액")
        # 거래처별로 매출액 합계 계산
        revenue_by_cust = df.groupby('CUST_DES')['TOTAL_AMT'].sum().sort_values(ascending=False)
        st.bar_chart(revenue_by_cust)

    # --- 6. 상세 데이터 테이블 표시 ---
    st.subheader("📋 상세 판매 내역")
    # 보여줄 컬럼 선택 및 이름 변경
    display_df = df[[
        'IO_DATE', 'CUST_DES', 'PROD_DES', 'QTY', 'PRICE', 'SUPPLY_AMT', 'VAT_AMT', 'TOTAL_AMT', 'WH_DES'
    ]].rename(columns={
        'IO_DATE': '판매일', 'CUST_DES': '거래처', 'PROD_DES': '품목명', 'QTY': '수량',
        'PRICE': '단가', 'SUPPLY_AMT': '공급가액', 'VAT_AMT': '부가세', 'TOTAL_AMT': '합계금액', 'WH_DES': '출하창고'
    })
    st.dataframe(display_df, use_container_width=True, hide_index=True)

else:
    st.info("좌측 사이드바에서 ECOUNT 정보를 입력하고 날짜를 선택한 후 '데이터 조회하기' 버튼을 눌러주세요.")
