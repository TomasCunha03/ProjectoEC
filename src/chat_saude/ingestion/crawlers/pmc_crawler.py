import json
import time
from datetime import datetime

import requests
from lxml import etree
from tqdm import tqdm

PMC_QUERIES = [
    "preventive medicine[MeSH Terms]",
    "disease prevention[MeSH Terms]",
    "public health[MeSH Terms]",
    "mass screening[MeSH Terms]",
    "health promotion[MeSH Terms]",
]

MAX_RESULTS_PER_QUERY = 10
OUTPUT_FILE = "pmc_preventive_medicine_clean.json"

MEDICAL_KEYWORDS = [
    "prevent",
    "prevention",
    "public health",
    "screening",
    "epidemiology",
    "risk factor",
    "health promotion",
    "chronic disease",
    "population health",
    "primary prevention",
    "secondary prevention",
]


def search_pmc(query, max_results=10):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

    params = {"db": "pmc", "term": query, "retmax": max_results, "retmode": "json"}

    r = requests.get(url, params=params, timeout=30)
    data = r.json()

    return data["esearchresult"]["idlist"]


def fetch_pmc_xml(pmc_id):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    params = {"db": "pmc", "id": pmc_id, "retmode": "xml"}

    r = requests.get(url, params=params, timeout=30)

    if r.status_code == 200 and "<article" in r.text:
        return r.text

    return None


def extract_text_from_xml(xml_text):
    try:
        parser = etree.XMLParser(recover=True)
        root = etree.fromstring(xml_text.encode("utf-8"), parser=parser)

        title = ""
        abstract = ""
        body_text = []

        # title
        title_el = root.find(".//article-title")
        if title_el is not None:
            title = " ".join(title_el.itertext())

        # abstract
        abs_el = root.find(".//abstract")
        if abs_el is not None:
            abstract = " ".join(abs_el.itertext())

        # body paragraphs
        for p in root.findall(".//body//p"):
            txt = " ".join(p.itertext()).strip()
            if len(txt) > 80:
                body_text.append(txt)

        full_text = "\n\n".join(body_text)

        return title, abstract, full_text

    except Exception as e:
        print("XML parse error:", e)
        return "", "", ""


def is_medical_article(title, abstract):
    text = (title + " " + abstract).lower()

    for kw in MEDICAL_KEYWORDS:
        if kw in text:
            return True
    return False


def crawl_pmc_medical():
    records = []
    seen = set()

    for query in PMC_QUERIES:
        print(f"\nSearching PMC: {query}")

        ids = search_pmc(query, MAX_RESULTS_PER_QUERY)

        for pmc_id in tqdm(ids):
            if pmc_id in seen:
                continue

            xml = fetch_pmc_xml(pmc_id)
            if not xml:
                continue

            title, abstract, text = extract_text_from_xml(xml)

            # filtros
            if not is_medical_article(title, abstract):
                continue

            if len(text) < 1000:
                continue

            record = {
                "pmc_id": pmc_id,
                "title": title,
                "abstract": abstract,
                "text": text,
                "mesh_query": query,
                "source_url": f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/",
                "data_crawling": datetime.now().isoformat(),
            }

            records.append(record)
            seen.add(pmc_id)

            time.sleep(0.5)

    return records


def save_json(data, file):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    data = crawl_pmc_medical()

    print(f"\nCollected {len(data)} medical PMC articles")

    save_json(data, OUTPUT_FILE)

    print("Saved:", OUTPUT_FILE)
