# utils.py
import pandas as pd
import PyPDF2
from io import BytesIO


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
