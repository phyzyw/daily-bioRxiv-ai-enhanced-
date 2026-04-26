# About
This tool daily crawls https://www.biorxiv.org for papers related to **molecular dynamics** and **machine learning**, and uses LLMs to summarize them.

# How to use
This repo will daily crawl bioRxiv papers about **molecular dynamics** and **machine learning**, and use **Cloudflare Workers AI** to summarize the papers in **Chinese**.

**Instructions:**
1. Fork this repo to your own account
2. Go to: your-own-repo -> Settings -> Secrets and variables -> Actions
3. Go to Secrets. Create two repository secrets:
   - `CLOUDFLARE_ACCOUNT_ID`: Your Cloudflare account ID
   - `CLOUDFLARE_API_TOKEN`: Your Cloudflare API token
4. Go to Variables. Create the following repository variables:
   - `KEYWORDS`: keywords separated by ",", such as "molecular dynamics,machine learning"
   - `LANGUAGE`: such as "Chinese" or "English"
   - `MODEL_NAME`: such as "@cf/meta/llama-3-8b-instruct"
   - `EMAIL`: your email for push to github
   - `NAME`: your name for push to github
   - `DAYS`: how many days to look back (default: "4")
5. Go to your-own-repo -> Actions -> bioRxiv-daily-ai-enhanced
6. Click **Run workflow** to test

# Content
{readme_content}
