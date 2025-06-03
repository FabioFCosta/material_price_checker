# agents.py
import uuid
from google.adk.agents import Agent
from google.adk.tools import google_search
from modules.common import call_agent, json_from_LLM_response, process_prices, run_agent_or_fail


def extract_data_from_text(text_content: str, user_id: str, session_id: str, model_name: str):
    extractor = Agent(
        name='extractor_agent',
        model=model_name,
        description='Agent specialized in extracting construction materials and their unit prices from various documents.',
        tools=[google_search],
        instruction="""
            You are a highly efficient and flexible data extraction assistant.
            Your task is to carefully read the provided text and identify all construction materials or items related to projects (such as specific services, equipment, etc.) and their respective unit prices (always in BRL unit - R$).

            **Detailed extraction instructions:**

            1. **Item Identification:**
                * Look for numbered lists, bullet points, or continuous text descriptions that represent an item or service.
                * The material or item name may be immediately followed by the price or separated by punctuation (such as ellipses, dashes, or parentheses).
                * Pay attention to items that may seem like a description but represent a specific material or equipment (e.g., "Jacuzzi Filtration Set", "Ozone Generator").

            2. **Price Identification:**
                * The unit price will always be in monetary format (e.g., "R$ 5.120,00", "5.795,00 R$", "R$ 7.900,00").
                * Ignore total values ("Total Value" in tables) if the "Unit Value" is available. If only the total is presented and it is clear it refers to a single unit, you can consider it as the "unit_price".
                * If an item is listed without a clear unit price, the 'unit_price' must be `0`.
                * Also consider "Unit Price" columns in tables.

            3. **MANDATORY Output Format:**
                * The output must be a **list of JSON objects**.
                * Each JSON object must contain **EXACTLY** two keys:
                    * `"material"` (string): The full and descriptive name of the material or item. Remove list numbers, bullets, or irrelevant prefixes.
                    * `"unit_price"` (float): The numerical unit price. Remove currency symbols (R$), thousand separators (.), and use a dot as the decimal separator. If the price is not found, use `0`.

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
            VERY IMPORTANT: DO NOT CREATE DATA, ONLY USE THE DOCUMENT TEXT FOR ANALYSIS!
            Remember: Output STRICTLY a valid JSON array. Do not include any additional commentary or explanations. No text outside JSON brackets.
        """
    )
    input_text = f"Document text for analysis: {text_content}"
    output = call_agent(extractor, input_text, user_id, session_id)

    return output


def validate_extracted_data(text_content: str, extracted_json: str, user_id: str, session_id: str, model_name: str):
    validator = Agent(
        name='validate_extraction_agent',
        model=model_name,
        description='Agent that validates if the extracted materials and unit prices are accurate based on the provided text.',
        tools=[google_search],
        instruction="""
            You are a rigorous data validation assistant.

            Your task is to analyze whether the extracted materials and their unit prices accurately reflect the content of the provided document text.

            **Validation Rules:**
            1. Check if all materials and their unit prices present in the document are included in the extracted JSON list.
            2. Check if any item in the extracted JSON does NOT actually exist in the document text (i.e., hallucinated data).
            3. DO NOT invent or assume data. Only consider exact matches from the text content.

            **Output Format:**
            Return a JSON object with:
            - "missing_items": a list of materials (strings) that were present in the document but missing in the extracted JSON (or its price was present but missing in JSON).
            - "hallucinated_items": a list of materials (strings) that are in the extracted JSON but do not exist in the document (or their price in JSON is not the same in the document).
            
            **Example Output:**
            {
                "missing_items": ["Jacuzzi Filtration Set", "LED Monochromatic Reflectors"],
                "hallucinated_items": [],
            }

            VERY IMPORTANT: Return ONLY the JSON object. No explanations, comments, or text outside the JSON.
        """
    )
    input_text = f"""
    Document text content:
    {text_content}

    \nExtracted JSON:
    {extracted_json}

    """
    output = call_agent(validator, input_text, user_id, session_id)

    return output


def find_missing_items(text_content: str, extracted_json: str, user_id: str, session_id: str, model_name: str):
    finder = Agent(
        name='find_missing_items_agent',
        model=model_name,
        description='Agent that find missing items from the extracted data.',
        tools=[google_search],
        instruction="""
            You are an expert assistant in text analysis.

            Your task is to carefully read the provided document and find the items and their prices (in BRL - R$) that are related in json.

            - Input 1: Full document text.
            - Input 2: List of missing material.

            Output:
            A JSON array containing ONLY the information about items that were missed:
            [
                {"material": "Jacuzzi Filtration Set TP", "unit_price": 5120.00}
            ]

            If no items were missed, return an empty JSON array ([]).
            VERY IMPORTANT: Return ONLY the JSON object. No explanations, comments, or text outside the JSON.
        """
    )
    input_text = f"""
    Document text content:
    {text_content}

    \nExtracted JSON:
    {extracted_json}
    """
    output = call_agent(finder, input_text, user_id, session_id)

    return output


def search_market_price(text_content: str, current_date: str, user_id: str, session_id: str, model_name: str):
    searcher = Agent(
        name='search_agent',
        model=model_name,
        description='Agent that searches the price range of materials.',
        tools=[google_search],
        instruction="""
            You are an expert in procurement and price quotation for construction materials in Brazil (Price in BRL - R$).
            Analyze the provided materials and, using the google-search tool, indicate the average current price range (considering today’s date) for each material found.
            
            The input will be a list of JSON objects with 'material' and 'unit_price'.
            The output should be a list of JSON objects, including:
            - 'material'
            - 'quoted_price' (the original unit_price in R$)
            - 'highest_price' found in R$
            - 'lowest_price' found in R$
            - 'lowest_price_links' maximum of 5 found links with lowest prices.

            If a value is not found, return it with null in the corresponding field (highest_price or lowest_price).

            **Example output:**
            [
                {
                    "material": "Portland Cement CP II E-32",
                    "quoted_price": 35.50,
                    "highest_price": 70.00,
                    "lowest_price": 30.00,
                    "lowest_price_links": ["link1","link2"]
                },
                {
                    "material": "Medium Sand",
                    "quoted_price": 80.00,
                    "highest_price": 70.00,
                    "lowest_price": 62.00,
                    "lowest_price_links": ["link1","link2", "link3"]
                },
                {
                    "material": "Ceramic Brick 8 holes",
                    "quoted_price": 1.20,
                    "highest_price": 4.00,
                    "lowest_price": 1.00,
                    "lowest_price_links": ["link1","link2", "link3", "link4", "link5"]
                },
                {
                    "material": "Recalque Pump",
                    "quoted_price": 19860.00,
                    "highest_price": null,
                    "lowest_price": null,
                    "lowest_price_links": null
                }
            ]

            Remember: Output STRICTLY a valid JSON array. Do not include any additional commentary or explanations. No text outside JSON brackets.
        """
    )
    input_text = f"Materials to search for market prices: {text_content}\nCurrent date: {current_date}"
    output = call_agent(searcher, input_text, user_id, session_id)
    return output


def analyze_material_prices(text_content: str, current_date: str, user_id: str, session_id: str, model_name: str):
    """
    Compares extracted prices with market prices and flags inconsistencies.
    """
    analyzer = Agent(
        name='price_analyzer_agent',
        model=model_name,
        description='Agent that analyzes and compares construction material prices.',
        tools=[google_search],
        instruction="""
            You are an expert in procurement and price analysis for construction materials in Brazil.
            
            The input will be a list of JSON objects. Each object will contain:
            - 'material'
            - 'quoted_price'
            - 'highest_price'
            - 'lowest_price'
            - 'lowest_price_links'

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
            - "quoted_price" (float)
            - "highest_price" (float or null)
            - "lowest_price" (float or null)
            - "percentage_variation" (float or null)
            - "status" (Within market, Above market, Below market or Research needed)
            - "lowest_price_links" (string Array)

            Remember: Output STRICTLY a valid JSON array. Do not include any additional commentary or explanations. No text outside JSON brackets.
        """
    )
    input_text = f"Analyze the following data: {text_content}\nCurrent date: {current_date}"
    output = call_agent(analyzer, input_text, user_id, session_id)
    return output


def robust_extraction_pipeline(text_content: str, user_id: str, session_id: str, model_name: str):
    MAX_ITERATIONS = 3
    iterations = 0

    extraction = extract_data_from_text(
        text_content, user_id, session_id, model_name)

    while iterations < MAX_ITERATIONS:
        validation = validate_extracted_data(
            text_content, extraction, user_id, session_id, model_name)

        validation_data = json_from_LLM_response(validation)

        hallucinated_items = validation_data.get('hallucinated_items', [])
        missing_items = validation_data.get('missing_items', [])

        if hallucinated_items:
            extraction = [
                item for item in extraction if item['material'] not in hallucinated_items]

        if missing_items:
            missing = find_missing_items(
                text_content, missing_items, user_id, session_id, model_name)
            if missing:
                extraction = merge_items(extraction, missing)

        if not hallucinated_items and not missing_items:
            break

        iterations += 1
    else:
        raise Exception(
            "Número máximo de tentativas de extração alcançado. A extração de dados pode estar incompleta.")

    return extraction


def material_quoting(material_description: str, current_date: str, user_id: str, session_id: str, model_name: str, min_links: int):
    searcher = Agent(
        name='quoting_agent',
        model=model_name,
        description='Agent that searches the price range of material.',
        tools=[google_search],
        instruction=f"""
            You are a purchasing assistant. Your job is to generate a price quotation for the material described below.

            -> Search for the material considering Brazilian suppliers. Only consider reliable sources (e.g., Leroy Merlin, Mercado Livre, Amazon BR, official distributor sites).
            -> Do not use results from blogs, forums, YouTube, or unrelated content.
            -> Open the page (if possible) and confirm that the product matches exactly the description. If the page is broken, skip it.
            -> If the price is visible and trustworthy, capture it. Otherwise, do not use it.
            -> Return the JSON format with:

            - material: (string) description of the material.

            - links: (array of minimum {min_links}) valid links where the items were obtained. All links must be functional and relevant.

            If you cannot find any valid price, return an empty list for links.

            **Example output:**            
                {{
                    "material": "Portland Cement CP II E-32",
                    "links": ["link1","link2"]
                }}

            Remember: Output STRICTLY a valid JSON object. Do not include any additional commentary or explanations. No text outside JSON brackets.
        """
    )
    input_text = f"Material to search for market prices: {material_description}\nCurrent date: {current_date}"
    output = call_agent(searcher, input_text, user_id, session_id)
    return output


def material_price_revision(material_quoting: str, current_date: str, user_id: str, session_id: str, model_name: str):
    searcher = Agent(
        name='quoting_agent',
        model=model_name,
        description='Agent that searches the price range of material.',
        tools=[google_search],
        instruction="""
            You are an assistant responsible for revising material price quotations.

        -> Your job is to verify if the material price quotation is accurate by checking the provided links and optionally performing a complementary search.

            Validation Rules:

        -> Open each link and verify:

                - The product matches exactly the described material.

                - The page is functional (no errors like 404 Not Found).

                - The price is visible, in Brazilian Real (BRL), and reliable.

        -> Discard links that are broken, incorrect, or lead to unrelated products.

        Output Format (JSON):

            - material: description.

            - research_results : Array of prices and links

            links: only valid, functional links that match the material.

            **Example output:**            
                {
                    "material": "Portland Cement CP II E-32",
                    "research_results": [
                        {
                        "price": float,
                        "link": "string"
                        },
                        ...
                    ]
                }

            - If no valid price is found, return research_results as an empty list and set highest_price and lowest_price to null.
            - Do not include links that are broken, irrelevant, or unrelated.

            Remember: Output STRICTLY a valid JSON object. Do not include any additional commentary or explanations. No text outside JSON brackets.
        """
    )
    input_text = f"Material to revision: {material_quoting}\nCurrent date: {current_date}"
    output = call_agent(searcher, input_text, user_id, session_id)
    return output


def quoting_analyzis_agents_team(materials: str, current_date: str, model_name: str):
    user_id = f"user-{uuid.uuid4()}"
    session_id = f"session-{uuid.uuid4()}"

    extracao = run_agent_or_fail(robust_extraction_pipeline, materials,
                                 user_id, session_id, model_name, agent_name="de extração")
    busca = run_agent_or_fail(search_market_price, extracao, current_date,
                              user_id, session_id, model_name, agent_name="de busca de preços")
    analise_json_string = run_agent_or_fail(
        analyze_material_prices, busca, current_date, user_id, session_id, model_name, agent_name="de análise de preços")

    return {"analise_json": analise_json_string}


def quoting_material_agents_team(material: str, current_date: str, model_name: str, min_links: int):
    user_id = f"user-{uuid.uuid4()}"
    session_id = f"session-{uuid.uuid4()}"

    quoting = run_agent_or_fail(material_quoting, material, current_date,
                                user_id, session_id, model_name, min_links, agent_name="de cotação")
    revision = run_agent_or_fail(material_price_revision, quoting, current_date,
                                 user_id, session_id, model_name, agent_name="de revisão de cotação")
    response = json_from_LLM_response(revision)
    prices = process_prices(response['research_results'])
    response['highest_price'] = prices['highest_price']
    response['lowest_price'] = prices['lowest_price']
    print(response)

    return response


def merge_items(existing_items: list, new_items: list):
    existing_materials = {item.get['material'].lower().strip()
                          for item in existing_items}
    merged = existing_items.copy()

    for item in new_items:
        if item['material'].lower().strip() not in existing_materials:
            merged.append(item)

    return merged
