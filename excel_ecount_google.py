import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import google.generativeai as genai

# --- Streamlit 페이지 설정 ---
st.set_page_config(
    page_title="고래미 주식회사 AI 판매 대시보드",
    page_icon="🐳",
    layout="wide"
)

# --- Google AI 설정 ---
def configure_google_ai(api_key):
    """Google AI 모델을 설정하고 반환합니다."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model
    except Exception as e:
        # 배포 환경에서는 st.error 대신 로그를 남기는 것이 더 좋을 수 있습니다.
        # 여기서는 사용자에게 명확한 피드백을 주기 위해 st.error를 사용합니다.
        st.error(f"Google AI 모델 설정에 실패했습니다: {e}")
        st.stop() # 설정에 실패하면 앱 실행을 중단합니다.

# --- AI 분석 함수 ---
def get_ai_analysis(model, df):
    """AI를 사용하여 데이터 분석 리포트를 생성합니다."""
    if model is None:
        return "AI 모델이 설정되지 않았습니다. 관리자에게 문의하세요."

    # 데이터의 요약 정보를 프롬프트에 포함하여 AI가 더 잘 이해하도록 합니다.
    prompt = f"""
    당신은 '고래미 주식회사'의 데이터를 분석하는 전문 비즈니스 분석가입니다.
    다음 판매 현황 데이터를 기반으로, 경영진을 위한 심층 분석 리포트를 작성해주세요.

    **데이터 샘플 (상위 5개 행):**
    ```
    {df.head().to_string()}
    ```

    **주요 경영 지표:**
    - 총 매출 (합계): {df['합계'].sum():,.0f} 원
    - 총 공급가액: {df['공급가액'].sum():,.0f} 원
    - 총 판매 박스 수: {df['박스'].sum():,.0f} 개
    - 고유 거래처 수: {df['거래처명'].nunique()} 곳
    - 판매 기간: {df['일자'].min().strftime('%Y-%m-%d')} ~ {df['일자'].max().strftime('%Y-%m-%d')}

    **분석 리포트 작성 가이드라인:**
    1.  **Executive Summary (경영 요약):** 전체 판매 실적을 요약하고 가장 중요한 발견점을 2-3문장으로 제시해주세요.
    2.  **주요 제품 분석:**
        - **효자 상품:** 매출액 기준 상위 3개 제품과 그 성공 요인을 분석해주세요.
        - **개선 필요 상품:** 매출 기여도가 낮은 제품들을 언급하고, 재고 관리나 마케팅 전략 변경을 제안해주세요.
    3.  **핵심 고객 분석:**
        - **VIP 고객:** 매출액 기준 상위 3개 거래처의 특징(예: 구매 주기, 선호 제품)을 분석하고, 관계 강화를 위한 맞춤형 전략을 제시해주세요.
        - **성장 기회:** 신규 고객 확보 또는 잠재 고객 발굴을 위한 데이터 기반의 아이디어를 제안해주세요.
    4.  **시간에 따른 판매 동향 분석:**
        - 일자별/주별 매출 추이에서 발견되는 특이점(급상승, 급하락)이나 패턴을 분석하고, 가능한 원인을 추정해주세요. (예: 특정 프로모션, 계절적 요인)
    5.  **기회 및 위험 요인:**
        - **기회:** 데이터를 통해 발견할 수 있는 새로운 판매 기회(예: 특정 제품과 함께 자주 구매되는 제품)를 알려주세요.
        - **위험:** 주의해야 할 잠재적 위험 요소(예: 특정 거래처에 대한 높은 매출 의존도)를 지적해주세요.
    6.  **실행 가능한 제안 (Actionable Recommendations):**
        - 분석 결과를 바탕으로 '고래미 주식회사'가 즉시 실행해볼 수 있는 구체적인 액션 아이템 3가지를 우선순위와 함께 제안해주세요.

    결과는 반드시 마크다운 형식으로, 각 섹션을 명확히 구분하여 전문적인 보고서처럼 작성해주세요.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 분석 중 오류가 발생했습니다: {e}"

def get_ai_answer(model, df, question):
    """AI를 사용하여 사용자의 자연어 질문에 답변합니다."""
    if model is None:
        return "AI 모델이 설정되지 않았습니다. 관리자에게 문의하세요."

    prompt = f"""
    당신은 '고래미 주식회사'의 판매 데이터를 조회하는 친절한 AI 어시스턴트입니다.
    아래 제공된 전체 판매 데이터를 참고하여 사용자의 질문에 답변해주세요.

    **데이터:**
    ```
    {df.to_string()}
    ```

    **사용자 질문:** {question}

    **답변 가이드라인:**
    - 반드시 제공된 데이터에 근거하여 답변해야 합니다.
    - 데이터에 없는 내용은 '데이터에 정보가 없습니다'라고 명확히 밝혀주세요.
    - 가능한 한 질문의 요지에 맞게 간결하고 정확하게 답변해주세요.
    - 계산이 필요한 경우, 직접 계산하여 답변할 수 있습니다. (예: "A 제품의 평균 단가는 얼마야?")
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 답변 생성 중 오류가 발생했습니다: {e}"

# --- Streamlit 앱 메인 로직 ---
st.title("🐳 고래미 주식회사 AI 판매 현황 대시보드")

# Streamlit Cloud Secrets에서 API 키를 사용하여 AI 모델 설정
model = None
try:
    # st.secrets는 딕셔너리처럼 작동합니다. secrets.toml 파일의 키를 사용합니다.
    api_key = st.secrets["GOOGLE_API_KEY"]
    model = configure_google_ai(api_key)
    st.sidebar.success("✅ AI 모델이 성공적으로 연결되었습니다.")
    st.sidebar.info("엑셀 파일을 업로드하면 AI 분석 기능을 사용할 수 있습니다.")
except KeyError:
    st.sidebar.error("⚠️ GOOGLE_API_KEY를 찾을 수 없습니다.")
    st.sidebar.info("Streamlit Cloud의 'Settings > Secrets'에 GOOGLE_API_KEY를 설정해주세요.")
    st.error("AI 기능을 사용하려면 API 키 설정이 필요합니다. 관리자에게 문의하세요.")
except Exception:
    # configure_google_ai 함수 내에서 이미 에러 처리를 했으므로 여기서는 추가 메시지만 표시
    st.sidebar.error("🚨 AI 모델 연결에 실패했습니다.")


# 파일 업로더
uploaded_file = st.file_uploader("📂 판매현황 엑셀 파일을 업로드하세요.", type=["xlsx", "xls"])

if uploaded_file is not None:
    # 엑셀 파일 읽기
    try:
        df = pd.read_excel(uploaded_file, sheet_name="판매현황", header=1) # 2번째 행이 헤더
    except Exception as e:
        st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")
        st.stop()

    # 데이터 클리닝 및 전처리
    try:
        # 예상되는 컬럼 리스트
        expected_columns = [
            "일자-No.", "배송상태", "창고명", "거래처코드", "거래처명", "품목코드", "품목명(규격)",
            "박스", "낱개수량", "단가", "공급가액", "부가세", "외화금액", "합계", "적요",
            "쇼핑몰고객명", "시리얼/로트No.", "외포장_여부", "전표상태", "전표상태.1",
            "추가문자형식2", "포장박스", "추가숫자형식1", "사용자지정숫자1", "사용자지정숫자2"
        ]
        
        # 실제 컬럼 수가 부족할 경우를 대비한 방어 코드
        if len(df.columns) < len(expected_columns):
            st.warning(f"업로드된 파일의 컬럼 수가 예상({len(expected_columns)})보다 적습니다({len(df.columns)}). 누락된 컬럼은 빈 값으로 처리됩니다.")
            # 기존 컬럼 이름 유지하고, 부족한 컬럼만 추가
            new_cols = expected_columns[len(df.columns):]
            for col in new_cols:
                df[col] = None # 빈 컬럼 추가
            df.columns = expected_columns # 최종적으로 컬럼 이름 재설정
        else:
            df.columns = expected_columns

        numeric_cols = ["박스", "낱개수량", "단가", "공급가액", "부가세", "외화금액", "합계", "추가숫자형식1", "사용자지정숫자1", "사용자지정숫자2"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df['일자'] = df['일자-No.'].apply(lambda x: str(x).split('-')[0].strip() if pd.notnull(x) else None)
        df['일자'] = pd.to_datetime(df['일자'], errors='coerce', format='%Y/%m/%d')
        
        # 필수 데이터(품목코드, 일자)가 없는 행(총계 등) 제거
        df = df.dropna(subset=['품목코드', '일자'])

        st.success("데이터 로딩 및 전처리가 완료되었습니다. 탭을 선택하여 분석 결과를 확인하세요.")

    except Exception as e:
        st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
        st.stop()


    # --- 탭(Tabs) 인터페이스 구성 ---
    tab1, tab2, tab3, tab4 = st.tabs(["📊 경영 지표 요약", "🤖 AI 분석 리포트", "💬 AI에게 질문하기", "📄 전체 데이터"])

    with tab1:
        st.header("경영 지표 요약", anchor=False)
        total_sales = df['합계'].sum()
        total_supply = df['공급가액'].sum()
        total_boxes = df['박스'].sum()
        unique_customers = df['거래처명'].nunique()

        st.divider()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("총 매출 (합계)", f"{total_sales:,.0f} 원")
        col2.metric("총 공급가액", f"{total_supply:,.0f} 원")
        col3.metric("총 판매 박스", f"{total_boxes:,.0f} 개")
        col4.metric("고유 거래처 수", f"{unique_customers} 곳")
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📈 일자별 매출 추이", anchor=False)
            daily_sales = df.groupby('일자')['합계'].sum().reset_index()
            if not daily_sales.empty:
                fig_line = px.line(daily_sales, x='일자', y='합계', title='일자별 총 매출', markers=True, template="plotly_white")
                fig_line.update_layout(title_x=0.5, xaxis_title=None, yaxis_title="매출액 (원)")
                st.plotly_chart(fig_line, use_container_width=True)
            else:
                st.info("일자별 매출 데이터가 없습니다.")

        with col2:
            st.subheader("📊 품목별 매출 비중 (Top 10)", anchor=False)
            top_10_products = df.groupby('품목명(규격)')['합계'].sum().nlargest(10).reset_index()
            fig_pie = px.pie(top_10_products, values='합계', names='품목명(규격)', title='상위 10개 품목 매출 비율',
                             hover_data={'합계':':,.0f원'}, labels={'합계':'매출액'}, template="plotly_white")
            fig_pie.update_traces(textposition='inside', textinfo='percent+label', pull=[0.05 if i == 0 else 0 for i in range(len(top_10_products))])
            fig_pie.update_layout(title_x=0.5, showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True)

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🏢 상위 거래처 매출 (Top 10)", anchor=False)
            top_10_customers = df.groupby('거래처명')['합계'].sum().nlargest(10).reset_index()
            fig_bar = px.bar(top_10_customers.sort_values('합계', ascending=True),
                             x='합계', y='거래처명', title='상위 10개 거래처 매출', orientation='h', template="plotly_white", text='합계')
            fig_bar.update_traces(texttemplate='%{x:,.0f}원', textposition='outside')
            fig_bar.update_layout(title_x=0.5, xaxis_title="매출액 (원)", yaxis_title=None)
            st.plotly_chart(fig_bar, use_container_width=True)
        with col2:
            st.subheader("📦 상위 품목 판매량 (Top 10)", anchor=False)
            top_10_products_qty = df.groupby('품목명(규격)')['박스'].sum().nlargest(10).reset_index()
            fig_bar_qty = px.bar(top_10_products_qty.sort_values('박스', ascending=True),
                                 x='박스', y='품목명(규격)', title='상위 10개 품목 판매량 (박스 기준)', orientation='h', template="plotly_white", text='박스')
            fig_bar_qty.update_traces(texttemplate='%{x:,.0f}개', textposition='outside')
            fig_bar_qty.update_layout(title_x=0.5, xaxis_title="판매량 (박스)", yaxis_title=None)
            st.plotly_chart(fig_bar_qty, use_container_width=True)

    with tab2:
        st.header("🤖 AI 자동 분석 리포트", anchor=False)
        st.markdown("AI가 업로드된 판매 데이터를 종합적으로 분석하여 비즈니스 인사이트 리포트를 생성합니다.")
        if st.button("📈 리포트 생성 시작", key="generate_report"):
            if model:
                with st.spinner('AI가 데이터를 분석하고 리포트를 작성하고 있습니다... 잠시만 기다려주세요.'):
                    ai_report = get_ai_analysis(model, df)
                    st.markdown(ai_report)
            else:
                st.warning("AI 모델이 연결되지 않았습니다. 사이드바의 연결 상태를 확인해주세요.")

    with tab3:
        st.header("💬 AI에게 데이터 질문하기", anchor=False)
        st.markdown("판매 데이터에 대해 궁금한 점을 자연어로 질문해보세요.")

        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        user_question = st.chat_input("질문을 입력하세요... (예: 가장 비싼 단가의 제품은 뭐야?)")

        if user_question:
            st.session_state.messages.append({"role": "user", "content": user_question})
            with st.chat_message("user"):
                st.markdown(user_question)

            if model:
                with st.spinner('AI가 답변을 생각하고 있습니다...'):
                    with st.chat_message("assistant"):
                        ai_answer = get_ai_answer(model, df, user_question)
                        st.markdown(ai_answer)
                        st.session_state.messages.append({"role": "assistant", "content": ai_answer})
            else:
                st.warning("AI 모델이 연결되지 않아 답변할 수 없습니다. 사이드바를 확인해주세요.")

    with tab4:
        st.header("📄 전체 데이터 보기 및 다운로드", anchor=False)
        st.dataframe(df)

        output = BytesIO()
        # BytesIO 객체를 사용하여 메모리 내에서 엑셀 파일 생성
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Processed_Sales_Data', index=False)
        
        # writer가 close된 후 (with 블록 종료 후) seek(0)을 호출해야 합니다.
        output.seek(0)

        st.download_button(
            label="📥 처리된 데이터 다운로드 (Excel)",
            data=output,
            file_name="processed_sales_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.info("👆 상단의 파일 업로드 영역에 엑셀 파일을 올려주세요.")
    st.markdown("""
    ### ✨ 시작 가이드
    1.  **엑셀 파일 준비:** '판매현황' 시트가 포함된 엑셀 파일을 준비합니다. (데이터는 2번째 행부터 시작)
    2.  **파일 업로드:** 위 `[Browse files]` 버튼을 클릭하여 파일을 업로드합니다.
    3.  **AI 분석:** 파일이 성공적으로 처리되면, 각 탭에서 다양한 데이터 분석 결과를 확인 할 수 있습니다.

    ---
    *AI 기능이 정상적으로 동작하려면 Streamlit Cloud에 **Google AI API Key**가 등록되어 있어야 합니다.*
    """)
