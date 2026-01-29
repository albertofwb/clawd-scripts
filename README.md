# Clawd Scripts 🤖

Automation scripts for [Clawdbot](https://github.com/clawdbot/clawdbot) - your AI assistant that lives in your terminal and messaging apps.

## Scripts

### 🐦 Twitter/X Automation

Post tweets and replies using Clawdbot's logged-in browser session.

**Usage:**
```bash
# Post a new tweet
./tweet "Hello World! 🌍"

# Reply to a tweet
./tweet -r "https://x.com/user/status/123456" "Nice post!"

# Read from file
./tweet -f tweet.txt

# Preview without posting
./tweet --dry-run "Test content"
```

### 📝 知乎 (Zhihu) Automation

Post articles to Zhihu using Clawdbot's logged-in browser session.

**Usage:**
```bash
# Post an article
./zhihu "文章标题" "文章正文内容"

# Read content from file
./zhihu -t "标题" -f article.md

# Preview without posting
./zhihu --dry-run "标题" "内容"
```

**Notes:**
- Supports Markdown formatting in content
- Make sure you're logged into Zhihu in the Clawdbot browser

## Setup

```bash
# Create venv and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install playwright
playwright install chromium

# Make sure Clawdbot browser is running
clawdbot browser start --profile clawd

# Login to Twitter/X and Zhihu in the browser
```

## Requirements

- [Clawdbot](https://github.com/clawdbot/clawdbot) with browser running
- Python 3.10+
- Playwright

## How it works

These scripts connect to Clawdbot's browser via Chrome DevTools Protocol (CDP). Since you're already logged into the target sites in the Clawdbot browser, the scripts can post on your behalf without needing API keys or OAuth.

## License

MIT

## Author

Created by Albert & Mooer 💕
