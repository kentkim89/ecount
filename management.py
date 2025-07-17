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

# --- 2. ECOUNT API 연동 함수 (실서버 URL로 수정) ---

def ecount_login(com_code, user_id, api_cert_key):
    """ECOUNT 실서버 API 로그인을 하고 세션 ID를 반환합니다."""
    # [수정] 실서버용 URL로 변경. zone이 필요 없습니다.
    url = 'https://oapi.ecount.com/OAPI/V2/OAPILogin'
    data = {
        "COM_CODE": com_code, "USER_ID": user_id, "API_CERT_KEY": api_cert_key,
        "LAN_TYPE": "ko-KR"
    }
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        contents = response.json()
        
        if contents.get("Status") == "200" and "SESSION_ID" in contents.get("Data", {}).get("Datas", {}):
            return contents['Data']['Datas']['SESSION_ID'], None
        else:
            error_obj = contents.get("Data") # 실서버용 키 오류는 'Data' 객체에 담겨 옴
            if error_obj and isinstance(error_obj, dict):
                error_message = error_obj.get("Message", f"알 수 없는 로그인 오류. 응답: {contents}")
            else:
                error_message = f"알 수 없는 로그인 오류. 응답: {contents}"
            return None, error_message
            
    except requests.exceptions.RequestException as e:
        return None, f"API 서버 연결 실패: {e}"
    except json.JSONDecodeError:
        return None, f"API 응답 분석 실패 (JSON 형식이 아님): {response.text}"

def get_sales_data(session_id, from_date, to_date):
    """지정된 기간의 판매 데이터를 ECOUNT 실서버 API로 조회합니다."""
    # [수정] 실서버용 URL로 변경. zone이 필요 없습니다.
    url = 'https://oapi.ecount.com/OAPI/V2/Sale/GetListSale'
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
            errors = contents.get("Errors")
            if errors and isinstance(errors, list) and len(errors) > 0:
                first_error = errors[0]
                if "EXP00001" in first_error.get("Code", ""):
                     return None, "API 키(세션) 인증에 실패했습니다. API 키가 '검증' 상태인지, 사용자 권한이 충분한지 확인하세요."
                error_message = first_error.get("Message", f"알 수 없는 오류. 응답: {contents}")
            else:
                error_message = f"데이터 조회 중 오류 발생. 응답: {contents}"
            return None, error_message

    except requests.exceptions.RequestException as e:
        return None, f"API 서버 연결 실패: {e}"
    except json.JSONDecodeError:
        return None, f"API 응답 분석 실패 (JSON 형식이 아님): {response.text}"


# --- 3. Streamlit UI 구성 ---

with st.sidebar:
    st.header("⚙️ ECOUNT 연동 정보")
    st.info("이 정보는 Streamlit의 Secrets 기능을 통해 안전하게 관리됩니다.", icon="🔒")

    default_com_code = st.secrets.get("ECOUNT_COM_CODE", "")
    default_user_id = st.secrets.get("ECOUNT_USER_ID", "")
    default_api_key = st.secrets.get("ECOUNT_API_KEY", "")

    com_code = st.text_input("회사코드", value=default_com_code)
    user_id = st.text_input("사용자 ID", value=default_user_id)
    api_key = st.text_input("API 인증키", value=default_api_key, type="password")

    st.markdown("---")
    st.header("🗓️ 조회 기간 선택")
    
    today = datetime.now()
    selected_date = st.date_input("조회할 날짜를 선택하세요", today, min_value=today - timedelta(days=365*3), max_value=today, format="YYYY-MM-DD")

    if st.button("📈 데이터 조회하기"):
        if not all([com_code, user_id, api_key, selected_date]):
            st.error("모든 연동 정보와 날짜를 입력해주세요.")
        else:
            with st.spinner('ECOUNT에 로그인 중...'):
                # [수정] zone 파라미터 제거
                session_id, error = ecount_login(com_code, user_id, api_key)

            if error:
                st.error(f"로그인 실패: {error}")
            else:
                st.success("로그인 성공!")
                from_date = selected_date.strftime("%Y%m%d")
                to_date = selected_date.strftime("%Y%m%d")

                with st.spinner(f"{selected_date.strftime('%Y년 %m월 %d일')}의 판매 데이터를 가져오는 중..."):
                    # [수정] zone 파라미터 제거
                    sales_data, error = get_sales_data(session_id, from_date, to_date)
                
                if error:
                    st.error(f"데이터 조회 실패: {error}")
                    if 'sales_df' in st.session_state:
                        del st.session_state['sales_df']
                elif not sales_data:
                    st.warning("해당 날짜에 판매 데이터가 없습니다.")
                    if 'sales_df' in st.session_state:
                        del st.session_state['sales_df']
                else:
                    df = pd.DataFrame(sales_data)
                    numeric_cols = ['QTY', 'PRICE', 'SUPPLY_AMT', 'VAT_AMT', 'TOTAL_AMT']
                    for col in numeric_cols:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    st.session_state['sales_df'] = df
                    st.success("데이터를 성공적으로 가져왔습니다!")

st.title("📊 ECOUNT 일일 매출 대시보드")

if 'sales_df' in st.session_state:
    df = st.session_state['sales_df']
    st.markdown(f"### 📅 **{pd.to_datetime(df['IO_DATE'].iloc[0]).strftime('%Y년 %m월 %d일')} 판매 현황 요약**")
    
    total_revenue = int(df['TOTAL_AMT'].sum())
    total_sales_count = len(df['IO_NO'].unique())
    total_items_sold = int(df['QTY'].sum())

    col1, col2, col3 = st.columns(3)
    col1.metric("총 매출액 (합계)", f"{total_revenue:,} 원")
    col2.metric("총 판매 건수", f"{total_sales_count} 건")
    col3.metric("총 판매 수량", f"{total_items_sold:,} 개")

    st.markdown("---")
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("📦 품목별 판매 수량")
        items_by_qty = df.groupby('PROD_DES')['QTY'].sum().sort_values(ascending=False)
        st.bar_chart(items_by_qty)

    with col2:
        st.subheader("🏢 거래처별 매출액")
        revenue_by_cust = df.groupby('CUST_DES')['TOTAL_AMT'].sum().sort_values(ascending=False)
        st.bar_chart(revenue_by_cust)

    st.subheader("📋 상세 판매 내역")
    display_df = df[[
        'IO_DATE', 'CUST_DES', 'PROD_DES', 'QTY', 'PRICE', 'SUPPLY_AMT', 'VAT_AMT', 'TOTAL_AMT', 'WH_DES'
    ]].rename(columns={
        'IO_DATE': '판매일', 'CUST_DES': '거래처', 'PROD_DES': '품목명', 'QTY': '수량',
        'PRICE': '단가', 'SUPPLY_AMT': '공급가액', 'VAT_AMT': '부가세', 'TOTAL_AMT': '합계금액', 'WH_DES': '출하창고'
    })
    st.dataframe(display_df, use_container_width=True, hide_index=True)

else:
    st.info("좌측 사이드바에서 ECOUNT 정보를 입력하고 날짜를 선택한 후 '데이터 조회하기' 버튼을 눌러주세요.")
