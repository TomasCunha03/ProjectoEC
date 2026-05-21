"""
PMC full-text crawler for preventive medicine articles.

Uses the NCBI E-utilities API (esearch + efetch) to retrieve open-access
articles from PubMed Central that match a set of MeSH-term queries.  Each
article is fetched as JATS XML, parsed to extract the title, abstract, and
body text, then filtered to confirm medical relevance before being saved to
a JSON file suitable for downstream ingestion into ChromaDB.
"""

import json
import time
from datetime import datetime

import requests
from lxml import etree
from tqdm import tqdm

# MeSH-term queries sent to the NCBI esearch endpoint
PMC_QUERIES = [
    "preventive medicine[MeSH Terms]",
    "disease prevention[MeSH Terms]",
    "public health[MeSH Terms]",
    "mass screening[MeSH Terms]",
    "health promotion[MeSH Terms]",
]

MAX_RESULTS_PER_QUERY = 10
OUTPUT_FILE = "pmc_preventive_medicine_clean.json"

# Keywords used as a secondary relevance filter after fetching the article
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
    """Search PMC via esearch and return a list of PMC article IDs.

    Args:
        query: A MeSH or free-text query string accepted by the NCBI esearch API.
        max_results: Maximum number of article IDs to return.

    Returns:
        A list of PMC ID strings (integers encoded as strings by the API).
    """
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

    params = {"db": "pmc", "term": query, "retmax": max_results, "retmode": "json"}

    r = requests.get(url, params=params, timeout=30)
    data = r.json()

    return data["esearchresult"]["idlist"]


def fetch_pmc_xml(pmc_id):
    """Fetch the full JATS XML for a single PMC article.

    Args:
        pmc_id: The PMC numeric ID (as a string) to fetch.

    Returns:
        The raw XML response text, or None if the request failed or the
        response does not contain article markup.
    """
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    params = {"db": "pmc", "id": pmc_id, "retmode": "xml"}

    r = requests.get(url, params=params, timeout=30)

    # Guard against API errors and non-article responses (e.g. plain error XML)
    if r.status_code == 200 and "<article" in r.text:
        return r.text

    return None


def extract_text_from_xml(xml_text):
    """Parse JATS XML and extract the article title, abstract, and body text.

    Body paragraphs shorter than 80 characters are skipped because they are
    typically captions, section headers, or other noise rather than
    substantive prose.

    Args:
        xml_text: Raw JATS XML string for a single PMC article.

    Returns:
        A tuple of (title, abstract, full_body_text).  Any field that cannot
        be extracted is returned as an empty string.
    """
    try:
        # recover=True allows lxml to handle slightly malformed XML from the API
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

        # body paragraphs — collect only substantive paragraphs
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
    """Return True if the article title or abstract contains at least one medical keyword.

    This acts as a cheap relevance guard to discard off-topic articles that
    happen to appear in the MeSH query results.

    Args:
        title: Article title string.
        abstract: Article abstract string.

    Returns:
        True if any keyword from MEDICAL_KEYWORDS is found (case-insensitive).
    """
    text = (title + " " + abstract).lower()

    for kw in MEDICAL_KEYWORDS:
        if kw in text:
            return True
    return False


def crawl_pmc_medical():
    """Run all PMC queries and return a deduplicated list of article records.

    Iterates over PMC_QUERIES, fetches and parses each result, applies
    relevance and length filters, and records a 0.5-second delay between
    requests to respect NCBI rate limits (max 3 req/s without an API key).

    Returns:
        A list of dicts, each containing pmc_id, title, abstract, text,
        mesh_query, source_url, and data_crawling timestamp.
    """
    records = []
    seen = set()  # track already-processed PMC IDs to avoid cross-query duplicates

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

            # Filters — skip articles that are off-topic or too short to be useful for RAG
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

            # Stay within NCBI's unauthenticated rate limit of ~3 requests/second
            time.sleep(0.5)

    return records


def save_json(data, file):
    """Serialise *data* to *file* as pretty-printed UTF-8 JSON.

    Args:
        data: Any JSON-serialisable Python object.
        file: Path to the output file (created or overwritten).
    """
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    data = crawl_pmc_medical()

    print(f"\nCollected {len(data)} medical PMC articles")

    save_json(data, OUTPUT_FILE)

    print("Saved:", OUTPUT_FILE)
