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
请用中文对以下学术论文生成JSON格式的摘要总结：

{content}

请严格按以下JSON格式返回（所有字段内容必须使用中文）：
{{
  "tldr": "简洁摘要（1-2句话）",
  "motivation": "研究动机",
  "method": "使用的方法",
  "result": "主要结果",
  "conclusion": "结论与意义"
}}

重要：所有字段内容必须用中文撰写，不要使用英文。只返回JSON对象，不要包含任何其他文字。
"""

SYSTEM = """
你是一个学术论文摘要AI助手。请用中文对论文进行总结，只返回一个有效的JSON对象，包含以下字段：tldr, motivation, method, result, conclusion。
所有字段内容必须使用中文。不要在JSON之外包含任何文字。
"""


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, required=True, help="json or jsonline data file")
    parser.add_argument("--max_workers", type=int, default=1, help="Maximum number of parallel workers")
    parser.add_argument("--max_tokens", type=int, default=2048, help="Maximum output tokens")
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


def call_cloudflare_api(account_id, api_token, model_name, prompt, max_tokens=2048):
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
        response_text = None
        if 'result' in result:
            r = result['result']
            if isinstance(r, dict) and 'response' in r:
                response_text = r['response']
            elif isinstance(r, str):
                response_text = r
            elif isinstance(r, list) and len(r) > 0:
                first = r[0]
                if isinstance(first, dict) and 'response' in first:
                    response_text = first['response']
                elif isinstance(first, str):
                    response_text = first
        elif 'response' in result:
            response_text = result['response']
        if response_text is not None:
            if isinstance(response_text, list):
                response_text = ' '.join(str(x) for x in response_text)
            return str(response_text)
        else:
            print(f"Unexpected API response structure: {json.dumps(result)[:500]}", file=sys.stderr)
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


def process_single_item(item: Dict, language: str, max_output_tokens: int = 2048) -> Dict:
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN")
    model_name = os.environ.get("MODEL_NAME", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")

    MODEL_CONTEXT_LIMITS = {
        "@cf/meta/llama-3-8b-instruct": 7968,
        "@cf/meta/llama-3.1-8b-instruct": 8192,
        "@cf/meta/llama-3.1-8b-instruct-fast": 8192,
        "@cf/meta/llama-3.3-70b-instruct-fp8-fast": 131072,
        "@cf/qwen/qwen3-30b-a3b-fp8": 40960,
        "@cf/mistral/mistral-small-3.1-24b-instruct": 131072,
        "@cf/google/gemma-3-12b-it": 131072,
    }
    context_limit = MODEL_CONTEXT_LIMITS.get(model_name, 8000)
    max_output_tokens = min(max_output_tokens, context_limit - 500)

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

    max_content_length = 10000
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
            estimated_input_tokens = estimate_token_count(prompt)
            total_estimated = estimated_input_tokens + max_output_tokens

            print(f"Processing {item.get('id', 'unknown')}, attempt {attempt + 1}, model: {model_name}, context_limit: {context_limit}, input_tokens: {estimated_input_tokens}, max_output: {max_output_tokens}, total: {total_estimated}", file=sys.stderr)

            if total_estimated > context_limit:
                available_for_content = context_limit - max_output_tokens - 500
                if available_for_content > 500:
                    max_content_length = min(max_content_length, available_for_content * 4)
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
                if max_content_length < 500:
                    max_content_length = 500

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
