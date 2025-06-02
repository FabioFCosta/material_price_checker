# agents.py
import uuid
from google.adk.agents import Agent
from google.adk.tools import google_search
from modules.common import call_agent

def extract_data_from_text(text_content: str, current_date: str, user_id: str, session_id: str, model_name: str):
    extractor = Agent(
        name='extractor_agent',
        model=model_name,
        description='Agent specialized in extracting hospital materials and their unit prices from various documents.',
        tools=[google_search],
        instruction="""
            You are a highly efficient and flexible data extraction assistant.
            Your task is to carefully read the provided text and identify all hospital materials or items related to projects (such as specific services, equipment, etc.) and their respective unit prices.

            **Detailed extraction instructions:**

            1. **Item Identification:**
                * Look for numbered lists, bullet points, or continuous text descriptions that represent an item or service.
                * The material or item name may be immediately followed by the price or separated by punctuation (such as ellipses, dashes, or parentheses).
                * Pay attention to items that may seem like a description but represent a specific material or equipment (e.g., "Jacuzzi Filtration Set", "Ozone Generator").

            2. **Price Identification:**
                * The unit price will always be in monetary format (e.g., "R$ 5.120,00", "5.795,00 R$", "R$ 7.900,00").
                * Ignore total values ("Total Value" in tables) if the "Unit Value" is available. If only the total is presented and it is clear it refers to a single unit, you can consider it as the "unit_price".
                * If an item is listed without a clear unit price, the 'unit_price' must be `null`.
                * Also consider "Unit Price" columns in tables.

            3. **MANDATORY Output Format:**
                * The output must be a **list of JSON objects**.
                * Each JSON object must contain **EXACTLY** two keys:
                    * `"material"` (string): The full and descriptive name of the material or item. Remove list numbers, bullets, or irrelevant prefixes.
                    * `"unit_price"` (float or null): The numerical unit price. Remove currency symbols (R$), thousand separators (.), and use a dot as the decimal separator. If the price is not found, use `null`.

            **Examples of handling different formats:**

            * **Tabular format:**
                `"CÓD.","ITEM","QTD","UND","MATERIAL","Unit Value", ...`
                `"1","1,00","Vb.","Dry sauna","R$ 7.900,00", ...`
                **Expected extraction:** `{"material": "Dry sauna", "unit_price": 7900.00}`

            * **List/descriptive format:**
                `1. Supply of 01 Jacuzzi Filtration Set TP... .R$ 5.120,00`
                `3. Supply of 08 LED Monochromatic Reflectors... .R$ 5.795,00`
                **Expected extraction:**
                `{"material": "Jacuzzi Filtration Set TP", "unit_price": 5120.00}`
                `{"material": "LED Monochromatic Reflectors", "unit_price": 5795.00}`

            * **Different price layouts:**
                `"PVC pipes 100mm", "R$ 45.00"` -> `{"material": "PVC pipes 100mm", "unit_price": 45.00}`
                `"Electric wires 2.5mm" ... "120.00 R$"` -> `{"material": "Electric wires 2.5mm", "unit_price": 120.00}`

            Carefully analyze the text to ensure all materials and their unit prices are accurately extracted.
            Provide ONLY the list of JSON objects.
        """
    )
    input_text = f"Document text for analysis: {text_content}\nCurrent date for context: {current_date}"
    return call_agent(extractor, input_text, user_id, session_id)


def search_market_price(text_content: str, current_date: str, user_id: str, session_id: str, model_name: str):
    searcher = Agent(
        name='search_agent',
        model=model_name,
        description='Agent that searches the price range of materials.',
        tools=[google_search],
        instruction="""
            You are an expert in procurement and price quotation for hospital materials in Brazil.
            Analyze the provided materials and, using the google-search tool, indicate the average current price range (considering today’s date) for each material found.
            
            The input will be a list of JSON objects with 'material' and 'unit_price'.
            The output should be a list of JSON objects, including:
            - 'material'
            - 'quoted_price' (the original unit_price)
            - 'highest_price' found
            - 'lowest_price' found

            If a value is not found, return it with null in the corresponding field (highest_price or lowest_price).

            **Example output:**
            [
                {
                    "material": "Portland Cement CP II E-32",
                    "quoted_price": 35.50,
                    "highest_price": 70.00,
                    "lowest_price": 30.00
                },
                {
                    "material": "Medium Sand",
                    "quoted_price": 80.00,
                    "highest_price": 70.00,
                    "lowest_price": 62.00
                },
                {
                    "material": "Ceramic Brick 8 holes",
                    "quoted_price": 1.20,
                    "highest_price": 4.00,
                    "lowest_price": 1.00
                },
                {
                    "material": "Recalque Pump",
                    "quoted_price": 19860.00,
                    "highest_price": null,
                    "lowest_price": null
                }
            ]

            Provide ONLY the list of JSON objects.
        """
    )
    input_text = f"Materials to search for market prices: {text_content}\nCurrent date: {current_date}"
    return call_agent(searcher, input_text, user_id, session_id)


def analyze_material_prices(text_content: str, current_date: str, user_id: str, session_id: str, model_name: str):
    """
    Compares extracted prices with market prices and flags inconsistencies.
    """
    analyzer = Agent(
        name='price_analyzer_agent',
        model=model_name,
        description='Agent that analyzes and compares hospital material prices.',
        tools=[google_search],
        instruction="""
            You are an expert in procurement and price analysis for hospital materials in Brazil.
            
            The input will be a list of JSON objects. Each object will contain:
            - 'material'
            - 'quoted_price'
            - 'highest_price'
            - 'lowest_price'

            Compare 'quoted_price' with the price range ('lowest_price' and 'highest_price').

            If 'quoted_price' is not within 'lowest_price' and 'highest_price' (inclusive), or if 'highest_price' or 'lowest_price' are null,
            perform a search using the google-search tool to check the most current market price for the material.

            Based on your analysis and search, determine the 'status' for each material:
            - "Within market": if the quoted price is within the range or considered reasonable after research.
            - "Above market": if the quoted price is significantly higher than the market range or research.
            - "Below market": if the quoted price is significantly lower than the market range or research.
            - "Research needed": if 'highest_price' or 'lowest_price' are null and you cannot determine the status after research.

            Calculate the percentage variation between 'quoted_price' and the average of 'lowest_price' and 'highest_price' (if both are available).
            Formula: ((quoted_price - average) / average) * 100

            Return a list of JSON objects, each representing an analyzed material, with the keys:
            - "material" (string)
            - "quoted_price" (float or null)
            - "highest_price" (float or null)
            - "lowest_price" (float or null)
            - "percentage_variation" (float or null)
            - "status" (string)

            Provide ONLY the list of JSON objects.
        """
    )
    input_text = f"Analyze the following data: {text_content}\nCurrent date: {current_date}"
    return call_agent(analyzer, input_text, user_id, session_id)


def hospital_agents_team(materiais: str, data_de_hoje: str, model_name: str):
    user_id = f"user-{uuid.uuid4()}"
    session_id = f"session-{uuid.uuid4()}"

    extracao = extract_data_from_text(materiais, data_de_hoje, user_id, session_id, model_name)
    busca = search_market_price(extracao, data_de_hoje, user_id, session_id, model_name)
    analise_json_string = analyze_material_prices(busca, data_de_hoje, user_id, session_id, model_name)

    return {"analise_json": analise_json_string}