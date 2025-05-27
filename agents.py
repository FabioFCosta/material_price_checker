# agents.py
import uuid
import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search
from google.genai import types

load_dotenv()

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
                        final_response += part.text
                        final_response += "\n"
        return final_response
    except Exception as e:
        return f"Erro ao processar o agente {agent.name}: {str(e)}"



# Adicione 'model_name' como argumento para cada função de agente
def extract_data_from_text(text_content: str, data_de_hoje: str, user_id: str, session_id: str, model_name: str):
    extrator = Agent(
        name='agente_extrator',
        model=model_name, # USA O MODELO SELECIONADO AQUI
        description='Agente especializado na extração de materiais de construção e seus preços unitários de documentos variados.',
        tools=[google_search],
        instruction="""
            Você é um assistente de extração de dados altamente eficiente e flexível.
            Sua tarefa é ler atentamente o texto fornecido e identificar todos os materiais de construção ou itens relacionados a projetos (como serviços específicos, equipamentos, etc.) e seus respectivos preços unitários.

            **Instruções detalhadas para extração:**

            1.  **Identificação de Itens:**
                * Procure por listas numeradas, bullet points, ou descrições em texto corrido que representem um item ou serviço.
                * Considere que o nome do material ou item pode ser seguido imediatamente pelo preço, ou ter alguma pontuação (como reticências, travessões, ou parênteses) antes do preço.
                * Seja atento a itens que podem parecer uma descrição, mas que representam um material ou equipamento específico (ex: "Conjunto Filtrante Jacuzzi", "Gerador de Ozônio").

            2.  **Identificação de Preços:**
                * O preço unitário sempre virá no formato monetário (ex: "R$ 5.120,00", "5.795,00 R$", "R$ 7.900,00").
                * Ignore valores totais ("Valor Total" em tabelas) se o "Valor Unitário" estiver disponível. Se apenas o valor total for apresentado e for claro que se refere a uma única unidade do item, você pode considerá-lo como o "preco_unitario".
                * Se um item for listado sem um preço unitário claro ou identificável, o 'preco_unitario' deve ser `null`.
                * Considere também colunas de "Valor Unitário" em tabelas.

            3.  **Formato de Saída OBRIGATÓRIO:**
                * A saída deve ser uma **lista de objetos JSON**.
                * Cada objeto JSON deve conter **EXATAMENTE** duas chaves:
                    * `"material"` (string): O nome completo e descritivo do material ou item. Remova números de lista, bullets ou prefixos irrelevantes que não façam parte do nome do item.
                    * `"preco_unitario"` (float ou null): O valor numérico do preço unitário. Remova símbolos de moeda (R$), separadores de milhar (.), e use ponto como separador decimal. Se o preço não for encontrado, use `null`.

            **Exemplos de como lidar com diferentes formatos:**

            * **Formato tabular (como o primeiro PDF):**
                `"CÓD.","ITEM","QTD","UND","MATERIAL","Valor Unitário", ...`
                `"1","1,00","Vb.","Sauna seca","R$ 7.900,00", ...`
                **Extração esperada:** `{"material": "Sauna seca", "preco_unitario": 7900.00}`

            * **Formato de lista/descritivo (como o segundo PDF):**
                `1. Fornecimento de 01 (um) Conjunto Filtrante Jacuzzi linha TP... .R$ 5.120,00`
                `3. Fornecimento de 08 (oito) Refletores de Led Monocromáticos... .R$ 5.795,00`
                **Extração esperada:**
                `{"material": "Conjunto Filtrante Jacuzzi linha TP", "preco_unitario": 5120.00}`
                `{"material": "Refletores de Led Monocromáticos", "preco_unitario": 5795.00}`

            * **Considerando diferentes layouts de preço:**
                `"Tubos de PVC 100mm", "R$ 45.00"` -> `{"material": "Tubos de PVC 100mm", "preco_unitario": 45.00}`
                `"Fios elétricos 2.5mm" ... "120,00 R$"` -> `{"material": "Fios elétricos 2.5mm", "preco_unitario": 120.00}`

            Analise o texto cuidadosamente para garantir que todos os materiais e seus preços unitários sejam extraídos com precisão.
            Forneça APENAS a lista de objetos JSON.
        """
    )
    entrada = f"Texto do documento para análise: {text_content}\nData atual para contexto: {data_de_hoje}"
    return call_agent(extrator, entrada, user_id, session_id)


def search_market_price(text_content: str, data_de_hoje: str, user_id: str, session_id: str, model_name: str):
    buscador = Agent(
        name='agente_buscador', # Mudei o nome para ser mais específico
        model=model_name, # USA O MODELO SELECIONADO AQUI
        description='Agente que busca a margem de preço dos materiais.',
        tools=[google_search],
        instruction="""
            Você é um especialista em compras e cotação de material para construção civil no Brasil.
            Analise os materiais informados e, através de pesquisa com a ferramenta google-search, indique
            a variação média de preço atual (considerando a data de hoje) para cada material encontrado.
            A entrada será uma lista de objetos JSON com 'material' e 'preco_unitario'.
            A saída deve ser uma lista de objetos JSON, incluindo 'material', 'preco_cotacao' (o preco_unitario original),
            'maior_preco' e 'menor_preco' encontrados na pesquisa.
            Se não encontrar um valor, retorne-o na lista com o valor null no campo correspondente (maior_preco ou menor_preco).

            Exemplo de formato de saída (lista de objetos JSON com 1 material por objeto):
            [
                {
                    "material": "Cimento Portland CP II E-32",
                    "preco_cotacao": 35.50,
                    "maior_preco": 70.00,
                    "menor_preco": 30.00
                },
                {
                    "material": "Areia Média",
                    "preco_cotacao": 80.00,
                    "maior_preco": 70.00,
                    "menor_preco": 62.00
                },
                {
                    "material": "Tijolo Cerâmico 8 furos",
                    "preco_cotacao": 1.20,
                    "maior_preco": 4.00,
                    "menor_preco": 1.00
                },
                {
                    "material": "Bomba de recalque",
                    "preco_cotacao": 19860.00,
                    "maior_preco": null,
                    "menor_preco": null
                }
            ]
            Forneça APENAS a lista de objetos JSON.
        """
    )
    entrada = f"Materiais para buscar preços de mercado: {text_content}\nData atual: {data_de_hoje}"
    return call_agent(buscador, entrada, user_id, session_id)


def analyze_material_prices(text_content: str, data_de_hoje: str, user_id: str, session_id: str, model_name: str):
    """
    Compara os preços extraídos com os preços de mercado e sinaliza inconsistências.
    """
    analizador = Agent(
        name='agente_analisador_precos',
        model=model_name, # USA O MODELO SELECIONADO AQUI
        description='Agente que analisa e compara preços de materiais de construção.',
        tools=[google_search],
        instruction="""
            Você é um especialista em compras e cotação de material para construção civil no Brasil.
            A entrada será uma lista de objetos JSON. Cada objeto terá 'material', 'preco_cotacao', 'maior_preco' e 'menor_preco'.
            
            Compare o 'preco_cotacao' com a faixa de preços ('menor_preco' e 'maior_preco').
            
            Se o 'preco_cotacao' não estiver entre 'menor_preco' e 'maior_preco' (inclusive), ou se 'maior_preco' ou 'menor_preco' forem null,
            realize uma pesquisa usando a ferramenta google-search para verificar o preço de mercado mais atual para o material.
            
            Com base na sua análise e pesquisa, determine o 'status' para cada material:
            - "Dentro do mercado": se o preço cotado estiver dentro da faixa ou for considerado razoável após a pesquisa.
            - "Acima do mercado": se o preço cotado for significativamente maior que a faixa de mercado ou o encontrado na pesquisa.
            - "Abaixo do mercado": se o preço cotado for significativamente menor que a faixa de mercado ou o encontrado na pesquisa.
            - "Pesquisa necessária": se 'maior_preco' ou 'menor_preco' forem null e você não conseguir determinar o status após a pesquisa.

            Retorne uma lista de objetos JSON, onde cada objeto representa um material analisado.
            Inclua as chaves: "material", "preco_cotacao", "maior_preco", "menor_preco", "variacao_porcentual" (calculada se possível), e "status".
            A 'variacao_porcentual' deve ser a diferença percentual do 'preco_cotacao' em relação ao 'preco_mercado_medio' (se puder calcular) ou ao limite mais próximo.
            Se um valor for null, mantenha-o como null no JSON.

            Exemplo do formato de saída (lista de objetos JSON):
            [
                {
                    "material": "Cimento Portland CP II E-32",
                    "preco_cotacao": 35.50,
                    "maior_preco": 70.00,
                    "menor_preco": 30.00,
                    "variacao_porcentual": 0.0,
                    "status": "Dentro do mercado"
                },
                {
                    "material": "Areia Média",
                    "preco_cotacao": 140.00,
                    "maior_preco": 70.00,
                    "menor_preco": 62.00,
                    "variacao_porcentual": 100.0,
                    "status": "Acima do mercado"
                },
                {
                    "material": "Hidromassagem externa aquecimento elétrico piscina",
                    "preco_cotacao": 14395.00,
                    "maior_preco": null,
                    "menor_preco": null,
                    "variacao_porcentual": null,
                    "status": "Pesquisa necessária"
                }
            ]
            Forneça APENAS a lista de objetos JSON.
        """
    )
    entrada = f"Dados dos materiais para análise: {text_content}\nData atual: {data_de_hoje}"
    return call_agent(analizador, entrada, user_id, session_id)


# Modifique a função orquestrar_agentes para aceitar model_name
def orquestrar_agentes(materiais: str, data_de_hoje: str, model_name: str):
    user_id = f"user-{uuid.uuid4()}"
    session_id = f"session-{uuid.uuid4()}"

    extracao = extract_data_from_text(materiais, data_de_hoje, user_id, session_id, model_name)
    busca = search_market_price(extracao, data_de_hoje, user_id, session_id, model_name)
    analise_json_string = analyze_material_prices(busca, data_de_hoje, user_id, session_id, model_name)

    return {"analise_json": analise_json_string}