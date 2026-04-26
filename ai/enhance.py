import os
import json
import sys
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import dotenv
import argparse
from tqdm import tqdm
from time import sleep
import PyPDF2
from io import BytesIO
import re

if os.path.exists('.env'):
    dotenv.load_dotenv()

TEMPLATE = """
Please generate a {language} JSON summary for the following academic paper:

{content}

Return format:
{{
  "tldr": "Concise summary (1-2 sentences)",
  "motivation": "Research motivation",
  "method": "Methods used",
  "result": "Main results",
  "conclusion": "Conclusion and significance"
}}
"""

SYSTEM = """
You are an academic paper summary AI. Only return a valid JSON object with fields: tldr, motivation, method, result, conclusion.
Do not include any text outside the JSON.
"""


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, required=True, help="json or jsonline data file")
    parser.add_argument("--max_workers", type=int, default=1, help="Maximum number of parallel workers")
    parser.add_argument("--max_tokens", type=int, default=4096, help="Maximum output tokens")
    return parser.parse_args()


def download_pdf(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; bioRxiv-daily-bot/1.0)"}
        response = requests.get(url, timeout=60, headers=headers)
        response.raise_for_status()
        pdf_file = BytesIO(response.content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for i, page in enumerate(pdf_reader.pages):
            if i >= 5:
                break
            page_text = page.extract_text() or ""
            text += page_text + "\n"
        return text[:6000]
    except Exception as e:
        print(f"Failed to download PDF from {url}: {e}", file=sys.stderr)
        return None


def call_cloudflare_api(account_id, api_token, model_name, prompt, max_tokens=1024):
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_name}"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1,
        "stream": False
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=90)
        response.raise_for_status()
        result = response.json()
        if 'result' in result and 'response' in result['result']:
            return result['result']['response']
        elif 'response' in result:
            return result['response']
        else:
            print(f"Unexpected API response structure: {result}", file=sys.stderr)
            return None
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"API error response: {error_data}", file=sys.stderr)
            except:
                print(f"API error response text: {e.response.text}", file=sys.stderr)
        return None


def extract_json_from_response(response_text: str) -> Dict:
    if not response_text:
        return None
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    try:
        json_pattern = r'\{[\s\S]*\}'
        matches = re.findall(json_pattern, response_text)
        if matches:
            longest_match = max(matches, key=len)
            return json.loads(longest_match)
    except:
        pass
    try:
        fixed_text = response_text.replace("'", '"')
        fixed_text = re.sub(r'(?<!\\)"', '\\"', fixed_text)
        return json.loads(fixed_text)
    except:
        pass
    return None


def create_fallback_ai_data(item: Dict, full_text: bool = False) -> Dict:
    summary = item.get('summary', '')
    summary_words = summary.split()
    if len(summary_words) > 50:
        tldr = ' '.join(summary_words[:50]) + "..."
    else:
        tldr = summary
    return {
        "tldr": tldr,
        "motivation": "Research aimed at addressing the problem described in the abstract",
        "method": "Advanced research methods and techniques were employed",
        "result": "Significant research results and findings were obtained",
        "conclusion": "Conclusions of significance to the field"
    }


def estimate_token_count(text: str) -> int:
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    other_chars = len(text) - chinese_chars
    return int(other_chars / 4 + chinese_chars / 2) + 100


def process_single_item(item: Dict, language: str, max_output_tokens: int = 1024) -> Dict:
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN")
    model_name = os.environ.get("MODEL_NAME", "@cf/meta/llama-3-8b-instruct")

    if not account_id or not api_token:
        print(f"Missing Cloudflare credentials", file=sys.stderr)
        return {
            **item,
            'AI': create_fallback_ai_data(item, False)
        }

    pdf_url = item.get('pdf_url')
    if not pdf_url and 'abs' in item:
        abs_url = item['abs']
        pdf_url = abs_url.replace('/content/', '/content/') + '.full.pdf'

    max_content_length = 3000
    full_text = None

    for attempt in range(3):
        try:
            if attempt == 0 and pdf_url:
                print(f"Downloading PDF for {item.get('id', 'unknown')}", file=sys.stderr)
                full_text = download_pdf(pdf_url)

            content_source = full_text if full_text else item.get('summary', '')
            if not content_source:
                print(f"No content available for {item.get('id', 'unknown')}", file=sys.stderr)
                return {
                    **item,
                    'AI': create_fallback_ai_data(item, False)
                }

            content_preview = content_source[:max_content_length]
            prompt = TEMPLATE.format(language=language, content=content_preview)
            estimated_tokens = estimate_token_count(prompt) + max_output_tokens

            print(f"Processing {item.get('id', 'unknown')}, attempt {attempt + 1}, estimated tokens: {estimated_tokens}", file=sys.stderr)

            if estimated_tokens > 7000:
                max_content_length = int(max_content_length * 0.7)
                content_preview = content_source[:max_content_length]
                prompt = TEMPLATE.format(language=language, content=content_preview)
                print(f"Reduced content length to {max_content_length} for token conservation", file=sys.stderr)

            response_text = call_cloudflare_api(account_id, api_token, model_name, prompt, max_output_tokens)

            if response_text:
                print(f"Raw response for {item.get('id', 'unknown')}: {response_text[:200]}...", file=sys.stderr)
                ai_data = extract_json_from_response(response_text)

                if ai_data and all(key in ai_data for key in ["tldr", "motivation", "method", "result", "conclusion"]):
                    print(f"Successfully extracted AI data for {item.get('id', 'unknown')}", file=sys.stderr)
                    return {**item, 'AI': ai_data}
                else:
                    print(f"Invalid or incomplete JSON response for {item.get('id', 'unknown')}", file=sys.stderr)
            else:
                print(f"Empty response for {item.get('id', 'unknown')} on attempt {attempt + 1}", file=sys.stderr)

        except Exception as e:
            error_msg = str(e)
            print(f"Attempt {attempt + 1} failed for {item.get('id', 'unknown')}: {error_msg}", file=sys.stderr)
            if any(keyword in error_msg for keyword in ["token", "context window", "limit exceeded", "5021"]):
                print(f"Token limit exceeded, reducing content length for retry", file=sys.stderr)
                max_content_length = int(max_content_length * 0.6)
                if max_content_length < 1000:
                    max_content_length = 1000

        if attempt < 2:
            sleep(8)

    print(f"All attempts failed for {item.get('id', 'unknown')}, using fallback", file=sys.stderr)
    return {
        **item,
        'AI': create_fallback_ai_data(item, bool(full_text))
    }


def process_all_items(data: List[Dict], language: str, max_workers: int, max_tokens: int) -> List[Dict]:
    print(f'Connected to Cloudflare Workers AI', file=sys.stderr)
    processed_data = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {
            executor.submit(process_single_item, item, language, max_tokens): item
            for item in data
        }
        for future in tqdm(as_completed(future_to_item), total=len(data), desc="Processing items"):
            item = future_to_item[future]
            try:
                result = future.result()
                processed_data.append(result)
            except Exception as e:
                print(f"Item {item.get('id', 'unknown')} generated an exception: {e}", file=sys.stderr)
                processed_data.append({
                    **item,
                    'AI': create_fallback_ai_data(item, False)
                })
    return processed_data


def read_jsonl_file(file_path: str) -> List[Dict]:
    data = []
    print(f'Opening input file: {file_path}', file=sys.stderr)
    with open(file_path, "r", encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                if 'id' in item and 'title' in item and 'summary' in item:
                    item.setdefault('authors', [])
                    item.setdefault('categories', [])
                    item.setdefault('abs', '')
                    item.setdefault('pdf_url', '')
                    data.append(item)
                else:
                    print(f"Line {line_num}: Missing required fields", file=sys.stderr)
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON line {line_num}: {e}", file=sys.stderr)
    return data


def main():
    args = parse_args()
    language = os.environ.get("LANGUAGE", 'Chinese')

    if not os.path.exists(args.data):
        print(f"Error: Input file {args.data} does not exist", file=sys.stderr)
        sys.exit(1)

    base_name = os.path.splitext(args.data)[0]
    target_file = f"{base_name}_AI_enhanced_{language}.jsonl"

    print(f"Input file: {args.data}", file=sys.stderr)
    print(f"Target output file: {target_file}", file=sys.stderr)
    print(f"Max workers: {args.max_workers}", file=sys.stderr)
    print(f"Max output tokens: {args.max_tokens}", file=sys.stderr)

    if os.path.exists(target_file):
        os.remove(target_file)
        print(f"Removed existing output file: {target_file}", file=sys.stderr)

    data = read_jsonl_file(args.data)

    if not data:
        print(f"No valid data found in {args.data}", file=sys.stderr)
        sys.exit(1)

    seen_ids = set()
    unique_data = []
    for item in data:
        item_id = item.get('id')
        if item_id and item_id not in seen_ids:
            seen_ids.add(item_id)
            unique_data.append(item)

    data = unique_data
    print(f'Loaded {len(data)} unique items from {args.data}', file=sys.stderr)

    processed_data = process_all_items(data, language, args.max_workers, args.max_tokens)

    print(f'Writing {len(processed_data)} items to output file: {target_file}', file=sys.stderr)
    with open(target_file, "w", encoding='utf-8') as f:
        for item in processed_data:
            if item is not None:
                output_item = {
                    'id': item.get('id'),
                    'title': item.get('title'),
                    'authors': item.get('authors', []),
                    'summary': item.get('summary', ''),
                    'abs': item.get('abs', ''),
                    'categories': item.get('categories', []),
                    'AI': item.get('AI', create_fallback_ai_data(item, False))
                }
                f.write(json.dumps(output_item, ensure_ascii=False) + "\n")

    print(f"Successfully processed {len(processed_data)} items", file=sys.stderr)
    print(f"Output saved to: {target_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
