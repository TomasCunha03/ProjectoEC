"""
PubMed preventive medicine crawler (Selenium-based).

Uses a headless Chrome browser to search PubMed for a set of preventive
medicine topics, visit each article page, and extract the title, abstract,
PMID, and publication year.  Articles without a usable abstract are dropped
because they add no value to the RAG knowledge base.  Results are
deduplicated by PMID before being written to a JSON file.

Note: A new driver instance is created per search term so that browser state
does not carry over between searches.
"""

import json
import os
import re
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Output is written next to the package's data directory
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
JSON_PATH = os.path.join(OUTPUT_DIR, "dataset_pubmed_preventive.json")

# Search terms focused on preventive medicine
TERMOS_MEDICINA_PREVENTIVA = [
    # General guidelines
    "preventive medicine guidelines",
    "primary care screening recommendations",
    # Chronic diseases
    "type 2 diabetes prevention lifestyle",
    "hypertension dietary approaches",
    "cardiovascular disease risk reduction",
    "obesity management strategies",
    # Lifestyle
    "mediterranean diet health benefits",
    "physical activity chronic disease prevention",
    "smoking cessation interventions",
    "sleep hygiene guidelines",
]


def iniciar_driver():
    """Create and return a headless Chrome WebDriver instance.

    Images, stylesheets, cookies, and notifications are disabled to speed up
    page loads.  The user-agent string is set to a common desktop browser
    value to avoid being blocked by bot-detection heuristics.

    Returns:
        A configured selenium.webdriver.Chrome instance.
    """
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    prefs = {
        # Disable images and stylesheets — we only need text content
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.cookies": 2,
    }
    options.add_experimental_option("prefs", prefs)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def extrair_dados_pubmed(driver, termo_pesquisa: str, num_paginas: int = 5) -> list[dict]:
    """Crawl PubMed search results for *termo_pesquisa* and return article records.

    Iterates over result pages, collects article links from the search listing,
    then visits each article page individually to extract structured metadata.
    Only articles with a non-trivial abstract (>50 characters) are retained.

    Args:
        driver: An active Selenium WebDriver instance.
        termo_pesquisa: The search query string passed to PubMed.
        num_paginas: Number of result pages to visit per search term.

    Returns:
        A list of dicts containing pmid, title, abstract, year, search_term,
        and url for each qualifying article found during this search.
    """
    dados_locais = []

    for pagina in range(1, num_paginas + 1):
        try:
            url = f"https://pubmed.ncbi.nlm.nih.gov/?term={termo_pesquisa}&page={pagina}"
            print(f" >> Collecting '{termo_pesquisa}' | Page {pagina}/{num_paginas}")
            driver.get(url)

            try:
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.docsum-title")))
            except Exception:
                # No results element appeared — either the page is empty or we exceeded available pages
                print("    No more results. Skipping term.")
                break

            links = [e.get_attribute("href") for e in driver.find_elements(By.CSS_SELECTOR, "a.docsum-title")]

            # Navigate each found link
            for link in links:
                if link in [d["url"] for d in dados_locais]:
                    continue  # Avoid local duplicates within this search term

                try:
                    driver.get(link)
                    # Wait only for the title to appear before reading the page
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.heading-title")))

                    titulo = driver.find_element(By.CSS_SELECTOR, "h1.heading-title").text.strip()
                    try:
                        abstract = driver.find_element(By.CSS_SELECTOR, "div.abstract-content").text.strip()
                    except Exception:
                        abstract = ""  # Articles without an abstract are not useful for RAG

                    # Quality filter: keep only if it has a meaningful abstract
                    if abstract and len(abstract) > 50:
                        # Extract year from the citation metadata string (e.g. "2023 Jan;12(1):34-45")
                        try:
                            meta_str = driver.find_element(By.CSS_SELECTOR, "span.cit").text
                            year_match = re.search(r"\d{4}", meta_str)
                            year = year_match.group(0) if year_match else "2024"
                        except Exception:
                            year = "2024"

                        # Extract PMID from the article URL path
                        pmid_match = re.search(r"/(\d+)/?$", link)
                        pmid = pmid_match.group(1) if pmid_match else "N/A"

                        dados_locais.append(
                            {
                                "pmid": pmid,
                                "title": titulo,
                                "abstract": abstract,
                                "year": year,
                                "search_term": termo_pesquisa,
                                "url": link,
                            }
                        )
                except Exception:
                    pass  # Silently skip individual articles that fail to load

        except Exception as e:
            print(f"Error on page {pagina}: {e}")

    return dados_locais


# --- Execution ---
if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    todos_resultados = []

    for termo in TERMOS_MEDICINA_PREVENTIVA:
        print(f"\n=== Searching: '{termo}' ===")
        # A fresh driver per term avoids session state accumulation
        resultados = extrair_dados_pubmed(iniciar_driver(), termo)
        todos_resultados.extend(resultados)
        print(f"Partial total: {len(todos_resultados)} articles collected.")
        # Brief pause between search terms to be courteous to the PubMed servers
        time.sleep(3)

    if todos_resultados:
        # Remove duplicates by PMID — the same article can appear for multiple search terms
        vistos = set()
        unicos = []
        for r in todos_resultados:
            if r["pmid"] not in vistos:
                vistos.add(r["pmid"])
                unicos.append(r)

        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(unicos, f, ensure_ascii=False, indent=2)

        print(f"\nSuccess! {len(unicos)} articles saved to '{JSON_PATH}'.")
    else:
        print("No data collected.")
