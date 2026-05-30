"""
Lightweight preventive medicine web crawler.

Iterates over a hardcoded list of WHO and PMC URLs, extracts clean article
text using trafilatura, and falls back to PyMuPDF (fitz) for any PDF links.
Results are saved as a JSON file for downstream ingestion.  This is the
"simple" variant of the crawler — no MeSH search, no deduplication logic.
"""

import json
import os
import random
import time
from datetime import datetime

import fitz
import requests
import trafilatura

PDF_FOLDER = "pdfs_medicina_preventiva"
os.makedirs(PDF_FOLDER, exist_ok=True)


# Seed URLs covering WHO fact sheets and open-access PMC articles
urls = [
    "https://www.who.int/news-room/fact-sheets/detail/physical-activity",
    "https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight",
    "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8051856/",
    "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6990290/",
]


def download_pdf(url, save_folder=PDF_FOLDER):
    """Download a PDF from *url* and save it locally, skipping if already cached.

    Only downloads if the server responds with a PDF content type.

    Args:
        url: URL of the PDF resource.
        save_folder: Local directory where the file should be saved.

    Returns:
        The local file path if the download succeeded, otherwise None.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, stream=True, timeout=30)
        if r.status_code == 200 and "application/pdf" in r.headers.get("Content-Type", ""):
            filename = os.path.join(save_folder, url.split("/")[-1])
            # Skip re-downloading files that are already on disk
            if not os.path.exists(filename):
                with open(filename, "wb") as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
            return filename
    except Exception as e:
        print(f"Error downloading PDF {url}: {e}")
    return None


def extract_text_from_url(url):
    """Extract the main readable text from an HTML page using trafilatura.

    trafilatura removes boilerplate (navigation, ads, footers) and returns
    only the core article content.

    Args:
        url: URL of the HTML page to scrape.

    Returns:
        Extracted plain text, or an empty string if extraction fails.
    """
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            return text
    except Exception as e:
        print(f"Error extracting HTML {url}: {e}")
    return ""


def crawl_medicina_preventiva(urls, keyword="medicina preventiva"):
    """Crawl a list of URLs and return structured document records.

    For each URL the function first attempts HTML extraction via trafilatura.
    If that yields nothing and the URL points to a PDF, the file is downloaded
    and parsed with PyMuPDF.  URLs that produce no text at all are skipped.

    A random delay between 2–5 seconds is applied between requests to avoid
    overloading the target servers.

    Args:
        urls: List of page or document URLs to crawl.
        keyword: Topic label stored in each record's 'keyword' field.

    Returns:
        A list of dicts, each containing title, authors, year, source_url,
        keyword, text, and data_crawling timestamp.
    """
    results = []
    for url in urls:
        print(f"\nProcessing: {url}")
        text = ""
        # Primary: clean HTML extraction
        text = extract_text_from_url(url)
        if not text and url.lower().endswith(".pdf"):
            # Fallback: download and read PDF with PyMuPDF
            pdf_file = download_pdf(url)
            if pdf_file:
                doc = fitz.open(pdf_file)
                for page in doc:
                    text += page.get_text() + "\n\n"
        if not text:
            print("No text extracted, skipping URL")
            continue
        # Derive a human-readable title from the URL slug
        result = {
            "title": url.split("/")[-1].replace("-", " ").capitalize(),
            "authors": [],
            "year": None,
            "source_url": url,
            "keyword": keyword,
            "text": text,
            "data_crawling": datetime.now().isoformat(),
        }
        print(f"Extracted {len(text)} characters")
        results.append(result)
        # Polite crawl delay — randomised to reduce the chance of rate-limiting
        time.sleep(random.uniform(2, 5))
    return results


def main():
    """Entry point: crawl all seed URLs and write results to JSON."""
    data = crawl_medicina_preventiva(urls)
    with open("medicina_preventiva_fulltext.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(data)} documents to medicina_preventiva_fulltext.json")


if __name__ == "__main__":
    main()
