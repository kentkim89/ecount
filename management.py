# 라이브러리 import
import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import json

# --- 1. 기본 페이지 설정 ---
st.set_page_config(
    page_title="ECOUNT 매출 대시보드 (디버그 모드)",
    page_icon="🛠️",
    layout="wide",
)

# --- 2. ECOUNT API 연동 함수 (안정성 및 디버깅 강화) ---

def ecount_login(com_code, user_id, api_cert_key, zone):
    """ECOUNT 실서버 API 로그인을 하고 세션 ID를 반환합니다."""
    url = 'https://oapi.ecount.com/OAPI/V2/OAPILogin'
    data = {
        "COM_CODE": com_code, "USER_ID": user_id, "API_CERT_KEY": api_cert_key,
        "LAN_TYPE": "ko-KR", "ZONE": zone
    }
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        contents = response.json()
        
        if contents.get("Status") == "200" and "SESSION_ID" in contents.get("Data", {}).get("Datas", {}):
            return contents['Data']['Datas']['SESSION_ID'], None
        else:
            # [개선] 어떤 에러 구조든 처리할 수 있도록 안정화
            error_msg = "알 수 없는 로그인 오류"
            if isinstance(contents.get("Error"), dict) and contents["Error"].get("Message"):
                error_msg = contents["Error"]["Message"]
            elif isinstance(contents.get("Data"), dict) and contents["Data"].get("Message"):
                error_msg = contents["Data"]["Message"]
            return None, f"'{error_msg}'\n\n[전체 응답 내용]\n{contents}"

    except requests.exceptions.RequestException as e:
        return None, f"API 서버 연결에 실패했습니다: {e}"
    except json.JSONDecodeError:
        return None, f"API 응답을 분석할 수 없습니다 (JSON 형식이 아님): {response.text}"

def get_sales_data(session_id, from_date, to_date, zone):
    """지정된 기간의 판매 데이터를 ECOUNT 실서버 API로 조회합니다."""
    url = 'https://oapi.ecount.com/OAPI/V2/Sale/GetListSale'
    data = {
        "SESSION_ID": session_id, "FROM_DATE": from_date, "TO_DATE": to_date, "ZONE": zone
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
                error_message = errors[0].get("Message", f"알 수 없는 오류 발생")
            else:
                error_message = f"데이터 조회 중 오류 발생"
            return None, f"'{error_message}'\n\n[전체 응답 내용]\n{contents}"

    except requests.exceptions.RequestException as e:
        return None, f"API 서버 연결에 실패했습니다: {e}"
    except json.JSONDecodeError:
        return None, f"API 응답을 분석할 수 없습니다 (JSON 형식이 아님): {response.text}"


# --- 3. Streamlit UI 구성 (디버깅 기능 추가) ---

st.title("🛠️ ECOUNT 일일 매출 대시보드")
st.caption("디버깅 기능이 강화된 버전입니다.")

with st.sidebar:
    st.header("⚙️ ECOUNT 연동 정보")
    
    # Secrets에서 값 불러오기
    default_com_code = st.secrets.get("ECOUNT_COM_CODE", "")
    default_user_id = st.secrets.get("ECOUNT_USER_ID", "")
    default_api_key = st.secrets.get("ECOUNT_API_KEY", "")
    default_zone = st.secrets.get("ECOUNT_ZONE", "") # 기본값을 빈 문자열로 설정하여 확인 용이

    # 사용자 입력 필드
    com_code = st.text_input("회사코드", value=default_com_code)
    user_id = st.text_input("사용자 ID", value=default_user_id)
    api_key = st.text_input("API 인증키", value=default_api_key, type="password")
    zone = st.text_input("ZONE 코드", value=default_zone, help="계정이 속한 서버 ZONE 코드 (예: AA)")

    st.markdown("---")
    st.header("🗓️ 조회 기간 선택")
    
    today = datetime.now()
    selected_date = st.date_input("조회할 날짜를 선택하세요", today, max_value=today, format="YYYY-MM-DD")

    if st.button("📈 데이터 조회하기"):
        # [핵심 개선 1: 명시적 디버깅] --------------------------------
        st.markdown("---")
        st.subheader("🔍 디버깅 정보")
        st.info(f"""
        API 요청에 사용될 실제 값들을 확인합니다.
        - **회사코드**: `{com_code}`
        - **사용자 ID**: `{user_id}`
        - **ZONE 코드**: `{zone}`
        
        **만약 'ZONE 코드'가 비어있다면, Streamlit Secrets 설정에 `ECOUNT_ZONE` 키가 없거나 이름이 잘못된 것입니다.**
        """)
        # -----------------------------------------------------------

        if not all([com_code, user_id, api_key, zone, selected_date]):
            st.error("모든 연동 정보를 입력해주세요. 특히 ZONE 코드가 비어있는지 확인하세요.")
        else:
            with st.spinner('ECOUNT에 로그인 중...'):
                session_id, error = ecount_login(com_code, user_id, api_key, zone)

            if error:
                # [핵심 개선 2: 상세한 오류 메시지]
                st.error(f"로그인 실패 (사용한 ZONE: '{zone}')")
                st.code(error, language="json") # 서버가 보낸 전체 에러 메시지 표시
            else:
                st.success("로그인 성공!")
                from_date = selected_date.strftime("%Y%m%d")
                to_date = selected_date.strftime("%Y%m%d")

                with st.spinner(f"{selected_date.strftime('%Y년 %m월 %d일')}의 판매 데이터를 가져오는 중..."):
                    sales_data, error = get_sales_data(session_id, from_date, to_date, zone)
                
                if error:
                    st.error(f"데이터 조회 실패")
                    st.code(error, language="json")
                    if 'sales_df' in st.session_state: del st.session_state['sales_df']
                elif not sales_data:
                    st.warning("해당 날짜에 판매 데이터가 없습니다.")
                    if 'sales_df' in st.session_state: del st.session_state['sales_df']
                else:
                    df = pd.DataFrame(sales_data)
                    numeric_cols = ['QTY', 'PRICE', 'SUPPLY_AMT', 'VAT_AMT', 'TOTAL_AMT']
                    for col in numeric_cols: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    st.session_state['sales_df'] = df
                    st.success("데이터를 성공적으로 가져왔습니다!")
                    # 성공 시 디버그 정보는 자동으로 사라짐

# 메인 대시보드 영역 (이전과 동일)
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
    # (이하 시각화 및 데이터프레임 표시 코드는 동일)
else:
    st.info("좌측 사이드바에서 ECOUNT 정보를 모두 입력하고 '데이터 조회하기' 버튼을 눌러주세요.")
