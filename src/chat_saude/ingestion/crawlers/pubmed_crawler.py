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

# --- Pastas de output ---
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
JSON_PATH = os.path.join(OUTPUT_DIR, "dataset_pubmed_preventive.json")

# --- Termos de pesquisa focados em medicina preventiva ---
TERMOS_MEDICINA_PREVENTIVA = [
    # Diretrizes Gerais
    "preventive medicine guidelines",
    "primary care screening recommendations",
    # Doenças Crónicas
    "type 2 diabetes prevention lifestyle",
    "hypertension dietary approaches",
    "cardiovascular disease risk reduction",
    "obesity management strategies",
    # Estilo de Vida
    "mediterranean diet health benefits",
    "physical activity chronic disease prevention",
    "smoking cessation interventions",
    "sleep hygiene guidelines",
]


def iniciar_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.cookies": 2,
    }
    options.add_experimental_option("prefs", prefs)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


# --- CRAWLER ---
def extrair_dados_pubmed(driver, termo_pesquisa: str, num_paginas: int = 5) -> list[dict]:
    dados_locais = []

    for pagina in range(1, num_paginas + 1):
        try:
            url = f"https://pubmed.ncbi.nlm.nih.gov/?term={termo_pesquisa}&page={pagina}"
            print(f" >> A recolher '{termo_pesquisa}' | Pag {pagina}/{num_paginas}")
            driver.get(url)

            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a.docsum-title"))
                )
            except Exception:
                print("    Sem mais resultados. A saltar termo.")
                break

            links = [
                e.get_attribute("href")
                for e in driver.find_elements(By.CSS_SELECTOR, "a.docsum-title")
            ]

            # Navegar em cada link encontrado
            for link in links:
                if link in [d["url"] for d in dados_locais]:
                    continue  # Evitar duplicados locais

                try:
                    driver.get(link)
                    # Espera apenas pelo título
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "h1.heading-title"))
                    )

                    # Extração
                    titulo = driver.find_element(By.CSS_SELECTOR, "h1.heading-title").text.strip()
                    try:
                        abstract = driver.find_element(
                            By.CSS_SELECTOR, "div.abstract-content"
                        ).text.strip()
                    except Exception:
                        abstract = ""  # Se não tem abstract, não serve para RAG

                    # Filtro de Qualidade: Só guarda se tiver Abstract
                    if abstract and len(abstract) > 50:
                        # Extrair PMID e Ano
                        try:
                            meta_str = driver.find_element(By.CSS_SELECTOR, "span.cit").text
                            year_match = re.search(r"\d{4}", meta_str)
                            year = year_match.group(0) if year_match else "2024"
                        except Exception:
                            year = "2024"

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
                    pass

        except Exception as e:
            print(f"Erro na página {pagina}: {e}")

    return dados_locais


# --- EXECUCAO ---
if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    todos_resultados = []

    for termo in TERMOS_MEDICINA_PREVENTIVA:
        print(f"\n=== A pesquisar: '{termo}' ===")
        resultados = extrair_dados_pubmed(iniciar_driver(), termo)
        todos_resultados.extend(resultados)
        print(f"Total parcial: {len(todos_resultados)} artigos recolhidos.")
        time.sleep(3)

    if todos_resultados:
        # Remove duplicados por pmid
        vistos = set()
        unicos = []
        for r in todos_resultados:
            if r["pmid"] not in vistos:
                vistos.add(r["pmid"])
                unicos.append(r)

        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(unicos, f, ensure_ascii=False, indent=2)

        print(f"\nSucesso! {len(unicos)} artigos guardados em '{JSON_PATH}'.")
    else:
        print("Nenhum dado recolhido.")
