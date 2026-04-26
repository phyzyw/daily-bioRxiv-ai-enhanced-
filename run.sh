#!/bin/bash

echo "=== Local Debug Environment Check ==="

if [ -z "$CLOUDFLARE_ACCOUNT_ID" ] || [ -z "$CLOUDFLARE_API_TOKEN" ]; then
    echo "Warning: CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN not set"
    echo "Required variables:"
    echo "   export CLOUDFLARE_ACCOUNT_ID=\"your-account-id\""
    echo "   export CLOUDFLARE_API_TOKEN=\"your-api-token\""
    echo ""
    echo "Optional variables:"
    echo "   export LANGUAGE=\"Chinese\""
    echo "   export KEYWORDS=\"molecular dynamics,machine learning\""
    echo "   export MODEL_NAME=\"@cf/meta/llama-3-8b-instruct\""
    echo ""
    read -p "Continue with partial workflow (crawl only)? (y/N): " continue_partial
    if [[ ! $continue_partial =~ ^[Yy]$ ]]; then
        exit 0
    fi
    PARTIAL_MODE=true
else
    echo "Cloudflare credentials are set"
    PARTIAL_MODE=false
    export LANGUAGE="${LANGUAGE:-Chinese}"
    export KEYWORDS="${KEYWORDS:-molecular dynamics,machine learning}"
    export MODEL_NAME="${MODEL_NAME:-@cf/meta/llama-3-8b-instruct}"
fi

echo ""
echo "=== Starting Local Debug Workflow ==="

today=`date -u "+%Y-%m-%d"`
echo "Local test: Crawling $today bioRxiv papers..."

echo "Step 1: Starting crawl..."
if [ -f "data/${today}.json" ]; then
    echo "Found existing today's file, deleting for fresh start..."
    rm "data/${today}.json"
fi

export OUTPUT_FILE="data/${today}.json"
python daily_biorxiv/daily_biorxiv/spiders/spider_biorxiv.py

if [ ! -f "data/${today}.json" ]; then
    echo "Crawling failed, no data file generated"
    exit 1
fi

echo "Step 2: Performing deduplication check..."
cd daily_biorxiv
python daily_biorxiv/check_stats.py
dedup_exit_code=$?

case $dedup_exit_code in
    0) ;;
    1) exit 1 ;;
    2) exit 2 ;;
    *) exit 1 ;;
esac

cd ..

if [ "$PARTIAL_MODE" = "false" ]; then
    echo "Step 3: AI enhancement processing..."
    cd ai
    python enhance.py --data ../data/${today}.json --max_workers 2
    if [ $? -ne 0 ]; then echo "AI processing failed"; exit 1; fi
    echo "AI enhancement processing completed"
    cd ..

    echo "Step 4: Converting to Markdown..."
    cd to_md
    if [ -f "../data/${today}_AI_enhanced_${LANGUAGE}.jsonl" ]; then
        python convert.py --data ../data/${today}_AI_enhanced_${LANGUAGE}.jsonl
        if [ $? -ne 0 ]; then echo "Markdown conversion failed"; exit 1; fi
    else
        echo "Error: AI enhanced file not found"
        exit 1
    fi
    cd ..
else
    echo "Skipping AI processing (partial mode)"
fi

echo "Step 5: Updating file list..."
ls data/*.json data/*.jsonl 2>/dev/null | sed 's|data/||' > assets/file-list.txt || true
echo "File list updated"

echo ""
echo "=== Local Debug Completed ==="
