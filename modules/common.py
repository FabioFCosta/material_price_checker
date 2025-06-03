#common_modules.py
import json
import os
import re
import pandas as pd
import PyPDF2
from io import BytesIO
import base64
import pandas as pd

from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents import Agent

os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")


def call_agent(agent: Agent, message_text: str, user_id: str, session_id: str) -> str:
    session_service = InMemorySessionService()
    session = session_service.create_session(
        app_name=agent.name,
        user_id=user_id,
        session_id=session_id
    )
    runner = Runner(agent=agent, app_name=agent.name,
                    session_service=session_service)
    content = types.Content(role="user", parts=[types.Part(text=message_text)])

    final_response = ""
    try:
        for event in runner.run(user_id=user_id, session_id=session_id, new_message=content):
            if event.is_final_response():
                for part in event.content.parts:
                    if part.text is not None:
                        final_response += part.text + "\n"
        return final_response
    except Exception as e:
        return f"Error processing agent {agent.name}: {str(e)}"
    


def extract_data_from_file(uploaded_file):
    """
    Extrai o conteúdo textual de arquivos XLSX ou PDF.
    Retorna o conteúdo como uma string. Se a extração falhar, retorna uma string vazia.
    """
    file_type = uploaded_file.type

    if file_type == "application/pdf":
        return _extract_text_from_pdf(uploaded_file)
    elif file_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        return _extract_text_from_xlsx(uploaded_file)
    else:
        return ""


def _extract_text_from_pdf(pdf_file):
    text = ""
    try:
        reader = PyPDF2.PdfReader(BytesIO(pdf_file.read()))
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            text += page.extract_text() or ""
        text = " ".join(text.split()).strip()
    except Exception as e:
        print(f"Erro ao extrair texto do PDF com PyPDF2: {e}")
        return ""  
    return text


def _extract_text_from_xlsx(xlsx_file):
    try:
        df = pd.read_excel(BytesIO(xlsx_file.read()))
        text_content = df.to_string(index=False, na_rep="")
        text_content = " ".join(text_content.split()).strip()
        return text_content
    except Exception as e:
        print(f"Erro ao extrair texto do XLSX com pandas: {e}")

        return ""

def generate_download_link(df: pd.DataFrame, fileName: str = "data.csv") -> str:
    """
    Generates a link to download the given dataframe as a CSV file.

    Parameters:
    - df (pd.DataFrame): The dataframe to download.
    - filename (str): The name of the CSV file.

    Returns:
    - str: HTML anchor tag as a string for the download link.
    """
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()

    href = f'<a href="data:file/csv;base64,{b64}" download="{fileName}">📥 Download CSV</a>'
    return href

def json_from_LLM_response(llm_response: str):
    """
    Extracts JSON from an LLM response that may be surrounded by markdown syntax.
    """
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', llm_response, re.DOTALL)

    if match:
        json_str = match.group(1)
    else:
        json_str = llm_response.strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from LLM response: {e}\nResponse: {llm_response}")