import os
import logging
import json
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests


class BiorxivAPISpider:
    def __init__(self, keywords=None, days=3):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        if keywords is None:
            kw_str = os.environ.get("KEYWORDS", "molecular dynamics,machine learning")
            self.keywords = [kw.strip() for kw in kw_str.split(",")] if kw_str else []
        else:
            self.keywords = keywords
        if not self.keywords:
            raise ValueError("At least one keyword is required")
        self.days = days
        self.end_date = datetime.now(ZoneInfo("UTC"))
        self.start_date = self.end_date - timedelta(days=days)
        self.logger.info(f"Search date range: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")
        self.logger.info(f"Keywords: {self.keywords}")

    def fetch_papers_from_api(self, begin_date, end_date, cursor=0):
        url = f"https://api.biorxiv.org/details/biorxiv/{begin_date}/{end_date}/{cursor}"
        self.logger.info(f"Fetching: {url}")
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data
        except Exception as e:
            self.logger.error(f"API request failed: {e}")
            return None

    def keyword_matches(self, text):
        if not text:
            return False
        text_lower = text.lower()
        for kw in self.keywords:
            if kw.lower() not in text_lower:
                return False
        return True

    def search_all_papers(self):
        begin_str = self.start_date.strftime('%Y-%m-%d')
        end_str = self.end_date.strftime('%Y-%m-%d')
        all_papers = []
        cursor = 0
        while True:
            data = self.fetch_papers_from_api(begin_str, end_str, cursor)
            if not data or 'collection' not in data:
                break
            collection = data['collection']
            if not collection:
                break
            for paper in collection:
                title = paper.get('title', '')
                abstract = paper.get('abstract', '')
                if self.keyword_matches(title) and self.keyword_matches(abstract):
                    doi = paper.get('doi', '')
                    date_str = paper.get('date', '')
                    authors_str = paper.get('authors', '')
                    authors = [a.strip() for a in authors_str.split(';') if a.strip()] if authors_str else []
                    category = paper.get('category', 'Uncategorized')
                    subjects_str = paper.get('subjects', '')
                    categories = [s.strip() for s in subjects_str.split(',') if s.strip()] if subjects_str else [category]
                    paper_id = doi.split('/')[-1] if doi else ''
                    abs_url = f"https://www.biorxiv.org/content/{doi}" if doi else ''
                    pdf_url = f"https://www.biorxiv.org/content/{doi}.full.pdf" if doi else ''
                    all_papers.append({
                        "id": paper_id,
                        "doi": doi,
                        "title": title.replace('\n', ''),
                        "authors": authors,
                        "summary": abstract.replace('\n', ' '),
                        "published": date_str,
                        "categories": categories,
                        "category": category,
                        "pdf_url": pdf_url,
                        "abs": abs_url,
                        "primary_category": categories[0] if categories else category
                    })
            messages = data.get('messages', [])
            total = 0
            if messages and len(messages) > 0:
                total = int(messages[0].get('total', 0))
            cursor += len(collection)
            if cursor >= total:
                break
            time.sleep(0.5)
        seen_ids = set()
        unique = []
        for p in all_papers:
            if p['id'] and p['id'] not in seen_ids:
                seen_ids.add(p['id'])
                unique.append(p)
        return unique

    def run(self, output_file=None):
        self.logger.info(f"Searching papers from last {self.days} days with keywords: {self.keywords}...")
        results = self.search_all_papers()
        self.logger.info(f"Found {len(results)} matching papers")
        grouped = {}
        for r in results:
            d = r['published']
            grouped.setdefault(d, []).append(r)
        for date, articles in grouped.items():
            self.logger.info(f"Date {date}: {len(articles)} papers")
        for r in results:
            self.logger.info(f"Found: {r['id']}, date: {r['published']}, title: {r['title'][:50]}...")
        if not output_file:
            today = datetime.now(ZoneInfo("UTC")).strftime('%Y-%m-%d')
            output_file = f"data/{today}.json"
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            for r in results:
                json.dump(r, f, ensure_ascii=False)
                f.write('\n')
        self.logger.info(f"Results saved to {output_file}")
        return results


if __name__ == "__main__":
    keywords = os.environ.get("KEYWORDS", "molecular dynamics,machine learning")
    days = int(os.environ.get("DAYS", "4"))
    today = datetime.now(ZoneInfo("UTC")).strftime('%Y-%m-%d')
    output_file = os.environ.get("OUTPUT_FILE", f"data/{today}.json")
    spider = BiorxivAPISpider(
        keywords=[kw.strip() for kw in keywords.split(",")],
        days=days
    )
    results = spider.run(output_file=output_file)
    print(f"\nFound {len(results)} papers (last {days} days):")
    grouped_results = {}
    for r in results:
        d = r['published']
        grouped_results.setdefault(d, []).append(r)
    for date, articles in sorted(grouped_results.items(), reverse=True):
        print(f"\n{date} ({len(articles)} papers):")
        for r in articles:
            print(f" - {r['id']}: {r['title'][:60]}...")
            print(f"   Categories: {r['categories']}")
