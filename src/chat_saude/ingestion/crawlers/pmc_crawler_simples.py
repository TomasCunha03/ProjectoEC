import json
import os
import random
import time
from datetime import datetime

import requests
import trafilatura

PDF_FOLDER = "pdfs_medicina_preventiva"
os.makedirs(PDF_FOLDER, exist_ok=True)


urls = [
    "https://www.who.int/news-room/fact-sheets/detail/physical-activity",
    "https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight",
    "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8051856/",
    "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6990290/",
]


def download_pdf(url, save_folder=PDF_FOLDER):
    """Baixa PDF se URL terminar em .pdf"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, stream=True, timeout=30)
        if r.status_code == 200 and "application/pdf" in r.headers.get("Content-Type", ""):
            filename = os.path.join(save_folder, url.split("/")[-1])
            if not os.path.exists(filename):
                with open(filename, "wb") as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
            return filename
    except Exception as e:
        print(f"Erro ao baixar PDF {url}: {e}")
    return None


def extract_text_from_url(url):
    """Extrai texto limpo de HTML"""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            return text
    except Exception as e:
        print(f"Erro ao extrair HTML {url}: {e}")
    return ""


def crawl_medicina_preventiva(urls, keyword="medicina preventiva"):
    results = []
    for url in urls:
        print(f"\n Processando: {url}")
        text = ""
        # Tenta extrair texto limpo
        text = extract_text_from_url(url)
        if not text and url.lower().endswith(".pdf"):
            pdf_file = download_pdf(url)
            if pdf_file:
                import fitz

                doc = fitz.open(pdf_file)
                for page in doc:
                    text += page.get_text() + "\n\n"
        if not text:
            print(" Nenhum texto extraído, ignorando URL")
            continue
        result = {
            "title": url.split("/")[-1].replace("-", " ").capitalize(),
            "authors": [],
            "year": None,
            "source_url": url,
            "keyword": keyword,
            "text": text,
            "data_crawling": datetime.now().isoformat(),
        }
        print(f" Extraído {len(text)} caracteres")
        results.append(result)
        time.sleep(random.uniform(2, 5))
    return results


def main():
    data = crawl_medicina_preventiva(urls)
    with open("medicina_preventiva_fulltext.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n Guardado {len(data)} documentos em medicina_preventiva_fulltext.json")


if __name__ == "__main__":
    main()
