# main.py
import os
from PIL import Image
import streamlit as st
import pandas as pd
import json
from modules.common import extract_data_from_file, generate_download_link, json_from_LLM_response
from modules.construction_agents import quoting_analyzis_agents_team, quoting_material_agents_team
from modules.hospital_agents import hospital_agents_team
from datetime import datetime
from authlib.integrations.requests_client import OAuth2Session

st.set_page_config(page_title="Material Price Checker", layout="wide")

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"


def get_authorization_url():
    client = OAuth2Session(CLIENT_ID, CLIENT_SECRET,
                           scope="openid email profile", redirect_uri=REDIRECT_URI)
    uri, state = client.create_authorization_url(AUTHORIZATION_ENDPOINT)
    st.session_state['oauth_state_sent'] = state
    return uri


def fetch_token(code, state_from_google_redirect):
    client = OAuth2Session(CLIENT_ID, CLIENT_SECRET,
                           redirect_uri=REDIRECT_URI, state=state_from_google_redirect)
    token = client.fetch_token(TOKEN_ENDPOINT, code=code)
    return token


def get_user_info(token):
    client = OAuth2Session(CLIENT_ID, CLIENT_SECRET, token=token)
    resp = client.get(USERINFO_ENDPOINT)
    return resp.json()


def logout():
    if "user_info" in st.session_state:
        del st.session_state["user_info"]
    if "oauth_state_sent" in st.session_state:
        del st.session_state["oauth_state_sent"]
    st.query_params.clear()


def show_login_screen(error_message=None):
    """Displays the improved login screen."""

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        try:
            logo = Image.open("assets/app_logo.png")
            st.image(logo, width=200)
        except FileNotFoundError:
            st.warning(
                "O arquivo 'app_logo.png' não foi encontrado. Usando um texto de placeholder.")
            st.markdown(
                "<h1 style='text-align: center;'>Material Price Checker</h1>", unsafe_allow_html=True)

        st.title("Bem-vindo ao Material Price Checker")
        st.write("Faça login com sua conta Google para continuar.")

        if error_message:
            st.error(error_message)

        auth_url = get_authorization_url()

        st.link_button("Entrar com Google", url=auth_url,
                       help="Clique para fazer login com sua conta Google")

        st.markdown("---")
        st.markdown(
            f"<p style='text-align: center; color: gray;'>Ao fazer login, você concorda com nossos Termos de Serviço.</p>", unsafe_allow_html=True)

    return True


def main():
    query_params = st.query_params

    if "user_info" not in st.session_state:
        if "code" in query_params:
            auth_code = query_params["code"]
            state_from_google = query_params.get("state")
            original_state_sent = st.session_state.get('oauth_state_sent')

            if state_from_google:
                try:
                    token = fetch_token(auth_code, state_from_google)
                    user_info = get_user_info(token)
                    st.session_state["user_info"] = user_info

                    st.query_params.clear()
                    if 'oauth_state_sent' in st.session_state:
                        del st.session_state['oauth_state_sent']

                    st.rerun()
                except Exception as e:
                    if show_login_screen(error_message=f"Erro ao fazer login. Por favor, tente novamente. Detalhes: {e}"):
                        st.stop()
            else:
                if show_login_screen(error_message="Parâmetro 'state' ausente na URL de redirecionamento. Tentando fazer login novamente."):
                    st.stop()
        else:
            if show_login_screen():
                st.stop()

    user_info = st.session_state["user_info"]
    st.success(f"Bem-vindo(a) {user_info['name']} ({user_info['email']})")

    st.sidebar.button("Sair (Logout)", on_click=logout)

    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        st.sidebar.error(
            'Ocorreu algum erro ao registrar a CHAVE da API do GOOGLE.')
    else:
        st.sidebar.header("⚙️ Configurações do Modelo")
        gemini_models = [
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-2.0-flash"
        ]
        selected_model = st.sidebar.selectbox(
            "Selecione o Modelo:",
            gemini_models,
            index=gemini_models.index("gemini-2.0-flash")
        )

        st.sidebar.header("⚙️ Configurações do Programa")

        material_type = st.sidebar.radio(
            "Selecione o programa:",
            ["Construção", "Hospital"]
        )

        if material_type == 'Construção':
            construction_program(selected_model, google_api_key)
        else:
            hospital_program(selected_model, google_api_key)


def construction_program(selected_model, google_api_key):
    st.title("🏗️ Material Price Checker")

    today_date = datetime.now().strftime("%d/%m/%Y")

    option = st.radio("Selecione uma opção:", options=[
                      'Cotação de produto', 'Análise de cotação'], horizontal=True)

    if option == 'Análise de cotação':
        st.write("Envie um arquivo PDF ou XLSX com orçamento de materiais de construção para verificar possíveis preços inconsistentes.")
        uploaded_file = st.file_uploader(
            "Faça upload do arquivo (.xlsx ou .pdf)", type=["xlsx", "pdf"], disabled=not google_api_key)

        if st.button(label='Iniciar análise', disabled=uploaded_file is None):
            with st.spinner("Extraindo dados do arquivo..."):
                raw_text_content = extract_data_from_file(uploaded_file)

            if not raw_text_content:
                st.error(
                    "Não foi possível extrair texto do arquivo. Por favor, verifique o formato ou o conteúdo.")
            else:
                st.success(
                    "Texto extraído com sucesso. Iniciando análise de preços...")

                analysis_df = pd.DataFrame()

                with st.spinner(f"Analisando materiais e pesquisando preços de mercado com {selected_model}..."):
                    try:
                        result = quoting_analyzis_agents_team(
                            raw_text_content, today_date, selected_model)
                        json_string_analysis = result.get("analise_json")

                        if json_string_analysis:                            
                            analysis_data = json_from_LLM_response(json_string_analysis)
                            analysis_df = pd.DataFrame(analysis_data)
                        else:
                            st.warning(
                                "O agente não retornou dados de análise no formato esperado.")

                    except json.JSONDecodeError as e:
                        st.error(
                            f"Erro ao decodificar JSON da análise: {e}. Saída bruta: {json_string_analysis[:500]}...")
                    except RuntimeError as e:
                        if "503" in str(e):
                            st.error("❌ O modelo está sobrecarregado (503 Service Unavailable). Por favor, tente novamente em alguns minutos.")
                        else:
                            st.error(f"⚠️ {str(e)}")
                    except Exception as e:
                        st.error(
                            f"Ocorreu um erro inesperado durante a orquestração dos agentes: {e}")

                if not analysis_df.empty:
                    st.subheader("📊 Resumo da Análise de Preços")

                    status_counts = analysis_df['status'].value_counts()
                    st.write(
                        f"Total de materiais analisados: **{len(analysis_df)}**")
                    for status, count in status_counts.items():
                        if status == "Within market":
                            st.success(f"**{status}**: {count} materiais")
                        elif status == "Pesquisa necessária":
                            st.info(
                                f"**{status}**: {count} materiais (preços de mercado não encontrados/definidos)")
                        else:
                            st.warning(f"**{status}**: {count} materiais")

                    st.markdown("---")

                    st.subheader("Detalhes da Análise")

                    def color_status(val):
                        if val == "Above market":
                            color = '#FF8C00'
                        elif val == "Below market":
                            color = '#DC143C'
                        elif val == "Within market":
                            color = '#3CB371'
                        elif val == "Research needed":
                            color = '#4682B4'
                        else:
                            color = ''
                        return f'background-color: {color}'

                    st.dataframe(analysis_df.style.applymap(
                        color_status, subset=['status']))

                    st.markdown("---")

                    for _, row in analysis_df.iterrows():
                        links = set(row['lowest_price_links'] or [])
                        if links:
                            st.markdown(
                                f"Menores preços para {row['material']}:")
                            for link in list(links):
                                st.info(link)

                    flagged_materials_df = analysis_df[
                        (analysis_df['status'] == "Above market") |
                        (analysis_df['status'] == "Below market") |
                        (analysis_df['status'] == "Research needed")
                    ]

                    if not flagged_materials_df.empty:
                        st.warning(
                            "⚠️ **Materiais com Potenciais Inconsistências ou que Requerem Pesquisa:**")
                        st.dataframe(flagged_materials_df.style.applymap(
                            color_status, subset=['status']))
                    else:
                        st.success(
                            "🎉 Nenhum material encontrado com preço fora da faixa ou que precise de pesquisa adicional.")

                    st.write("📥 Baixar o resultado da análise:")
                    link = generate_download_link(
                        df=analysis_df, fileName="resultado_analise.csv")
                    st.markdown(link, unsafe_allow_html=True)

                else:
                    st.info(
                        "Nenhum dado de material foi processado para análise. Por favor, verifique a saída dos agentes.")
    elif option == 'Cotação de produto':
        material_description = st.text_input(label='Insira a descrição do produto para cotação', help='Quanto melhor a descrição, mais consistente será o resultado.')
        if st.button(label='Cotar produto', disabled=material_description.strip() == ''):
            with st.spinner("Realizando cotação..."):
                try:
                    result = quoting_material_agents_team(material_description,today_date, selected_model)
                    st.success("Cotação realizada com sucesso!")
                    st.subheader(f'📊 Cotação do material "{material_description}":')

                    if result['highest_price']:
                        st.write(f'Maior preço: R$ {result['highest_price']}')
                    if result['lowest_price']:
                        st.write(f'Menor preço: R$ {result['lowest_price']}')
                    if result['research_results']:
                        for item in result['research_results']:
                            st.info(f"Preço: R$ {item['price']} - {item['link']}")

                except json.JSONDecodeError as e:
                    st.error(
                        f"Erro ao decodificar JSON da análise: {e}. Saída bruta: {json_string_analysis[:500]}...")
                except RuntimeError as e:
                    if "503" in str(e):
                        st.error("❌ O modelo está sobrecarregado (503 Service Unavailable). Por favor, tente novamente em alguns minutos.")
                    else:
                        st.error(f"⚠️ {str(e)}")
                except Exception as e:
                    st.error(
                        f"Ocorreu um erro inesperado durante a orquestração dos agentes: {e}")

def hospital_program(selected_model, google_api_key):
    st.title("📦 Hospital Material Checker")
    st.write("Envie um arquivo PDF ou XLSX com orçamento de materiais para verificar possíveis preços inconsistentes.")

    uploaded_file = st.file_uploader(
        "Faça upload do arquivo (.xlsx ou .pdf)", type=["xlsx", "pdf"], disabled=not google_api_key)

    if uploaded_file:
        with st.spinner("Extraindo dados do arquivo..."):
            raw_text_content = extract_data_from_file(uploaded_file)

        if not raw_text_content:
            st.error(
                "Não foi possível extrair texto do arquivo. Por favor, verifique o formato ou o conteúdo.")
        else:
            st.success(
                "Texto extraído com sucesso. Iniciando análise de preços...")

            today_date = datetime.now().strftime("%d/%m/%Y")

            analysis_df = pd.DataFrame()

            with st.spinner(f"Analisando materiais e pesquisando preços de mercado com {selected_model}..."):
                try:
                    result = hospital_agents_team(
                        raw_text_content, today_date, selected_model)
                    json_string_analysis = result.get("analise_json")

                    if json_string_analysis:                        
                        analysis_data = json_from_LLM_response(json_string_analysis)
                        analysis_df = pd.DataFrame(analysis_data)
                    else:
                        st.warning(
                            "O agente não retornou dados de análise no formato esperado.")

                except json.JSONDecodeError as e:
                    st.error(
                        f"Erro ao decodificar JSON da análise: {e}. Saída bruta: {json_string_analysis[:500]}...")
                except RuntimeError as e:
                    if "503" in str(e):
                        st.error("❌ O modelo está sobrecarregado (503 Service Unavailable). Por favor, tente novamente em alguns minutos.")
                    else:
                        st.error(f"⚠️ {str(e)}")
                except Exception as e:
                    st.error(
                        f"Ocorreu um erro durante a orquestração dos agentes: {e}")

            if not analysis_df.empty:
                st.subheader("📊 Resumo da Análise de Preços")

                status_counts = analysis_df['status'].value_counts()
                st.write(
                    f"Total de materiais analisados: **{len(analysis_df)}**")
                for status, count in status_counts.items():
                    if status == "Within market":
                        st.success(f"**{status}**: {count} materiais")
                    elif status == "Pesquisa necessária":
                        st.info(
                            f"**{status}**: {count} materiais (preços de mercado não encontrados/definidos)")
                    else:
                        st.warning(f"**{status}**: {count} materiais")

                st.markdown("---")

                st.subheader("Detalhes da Análise")

                def color_status(val):
                    if val == "Above market":
                        color = '#FF8C00'
                    elif val == "Below market":
                        color = '#DC143C'
                    elif val == "Within market":
                        color = '#3CB371'
                    elif val == "Research needed":
                        color = '#4682B4'
                    else:
                        color = ''
                    return f'background-color: {color}'

                st.dataframe(analysis_df.style.applymap(
                    color_status, subset=['status']))

                st.markdown("---")

                for _, row in analysis_df.iterrows():
                    links = set(row['lowest_price_links'] or [])
                    if links:
                        st.markdown(f"Menores preços para {row['material']}:")
                        for link in list(links):
                            st.info(link)

                flagged_materials_df = analysis_df[
                    (analysis_df['status'] == "Above market") |
                    (analysis_df['status'] == "Below market") |
                    (analysis_df['status'] == "Research needed")
                ]

                if not flagged_materials_df.empty:
                    st.warning(
                        "⚠️ **Materiais com Potenciais Inconsistências ou que Requerem Pesquisa:**")
                    st.dataframe(flagged_materials_df.style.applymap(
                        color_status, subset=['status']))
                else:
                    st.success(
                        "🎉 Nenhum material encontrado com preço fora da faixa ou que precise de pesquisa adicional.")
                st.write("📥 Baixar o resultado da análise:")
                link = generate_download_link(
                    df=analysis_df, fileName="resultado_analise.csv")
                st.markdown(link, unsafe_allow_html=True)
            else:
                st.info(
                    "Nenhum dado de material foi processado para análise. Por favor, verifique a saída dos agentes.")


if __name__ == "__main__":
    main()
