#!/usr/bin/env python3
"""
Zhihu Article Post Script using Clawdbot's logged-in browser session.

Usage:
    python zhihu_post.py "标题" "正文内容"
    python zhihu_post.py -t "标题" -f article.md  # Read body from file
    python zhihu_post.py --dry-run "标题" "内容"  # Preview only
    
Requires:
    pip install playwright
    
The script connects to Clawdbot's browser via CDP (Chrome DevTools Protocol).
Make sure the browser is running: clawdbot browser start --profile clawd
And you're logged into Zhihu in that browser.
"""

import argparse
import asyncio
import sys
from playwright.async_api import async_playwright


CDP_URL = "http://127.0.0.1:18800"  # Clawdbot browser CDP endpoint
ZHIHU_WRITE_URL = "https://zhuanlan.zhihu.com/write"


async def post_article(title: str, content: str, dry_run: bool = False) -> str:
    """Post an article to Zhihu using the logged-in browser session.
    
    Args:
        title: Article title (max 100 chars)
        content: Article body (supports Markdown)
        dry_run: If True, just preview without posting
        
    Returns:
        URL of the posted article or status message
    """
    if len(title) > 100:
        print(f"⚠️  Warning: Title is {len(title)} chars (100 limit)")
        title = title[:100]
    
    if dry_run:
        print(f"📝 Preview:")
        print(f"📌 Title: {title}")
        print(f"📊 Title length: {len(title)} chars")
        print(f"📊 Body length: {len(content)} chars")
        print(f"\n--- Content ---\n{content[:500]}{'...' if len(content) > 500 else ''}")
        return "DRY_RUN"
    
    async with async_playwright() as p:
        try:
            # Connect to existing browser via CDP
            browser = await p.chromium.connect_over_cdp(CDP_URL)
            print("✅ Connected to Clawdbot browser")
        except Exception as e:
            return f"❌ Failed to connect to browser: {e}\n💡 Make sure browser is running: clawdbot browser start --profile clawd"
        
        # Get existing context or create new page
        contexts = browser.contexts
        if not contexts:
            return "❌ No browser context found"
        
        context = contexts[0]
        page = await context.new_page()
        
        try:
            # Navigate to Zhihu write page
            print("📝 Opening Zhihu editor...")
            await page.goto(ZHIHU_WRITE_URL, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(5000)  # Wait longer for editor to initialize
            
            # Check if we're on the login page
            if "signin" in page.url:
                return "❌ Not logged in to Zhihu. Please login first in the Clawdbot browser."
            
            # Wait for the editor to be ready
            await page.wait_for_selector('textarea, [contenteditable="true"]', timeout=10000)
            
            # Find title input - try multiple selectors
            print("✍️  Entering title...")
            title_selectors = [
                'textarea[placeholder*="标题"]',
                'input[placeholder*="标题"]', 
                'textarea[placeholder*="100"]',
                '.WriteIndex-titleInput textarea',
                '.PostEditor-titleInput textarea',
            ]
            
            title_input = None
            for selector in title_selectors:
                elem = page.locator(selector).first
                if await elem.count():
                    title_input = elem
                    break
            
            if not title_input:
                # Fallback: first textarea on page
                title_input = page.locator('textarea').first
                
            if not await title_input.count():
                await page.screenshot(path="/tmp/zhihu_debug.png")
                return "❌ Could not find title input. Screenshot saved to /tmp/zhihu_debug.png"
            
            await title_input.click()
            await page.wait_for_timeout(500)
            # Use type() instead of fill() for better reliability
            await page.keyboard.type(title, delay=10)
            await page.wait_for_timeout(1000)
            
            # Move to content area using Tab key (most reliable method)
            print("✍️  Entering content...")
            await page.keyboard.press("Tab")
            await page.wait_for_timeout(1000)
            
            # Type content - split into chunks for reliability
            chunk_size = 50
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i+chunk_size]
                await page.keyboard.type(chunk, delay=3)
                await page.wait_for_timeout(50)
            
            await page.wait_for_timeout(2000)
            
            # Find and click publish button
            print("📤 Publishing...")
            
            # The publish button is a standalone button with exact text "发布"
            # Avoid "发布设置" button by using exact match
            all_buttons = page.locator('button')
            publish_btn = None
            
            for i in range(await all_buttons.count()):
                btn = all_buttons.nth(i)
                text = await btn.inner_text()
                if text.strip() == "发布":
                    publish_btn = btn
                    break
            
            if not publish_btn:
                await page.screenshot(path="/tmp/zhihu_debug.png")
                return "❌ Could not find publish button. Screenshot saved to /tmp/zhihu_debug.png"
            
            # Wait for button to be enabled (content must be entered first)
            await page.wait_for_timeout(1000)
            
            # Scroll button into view and click
            await publish_btn.scroll_into_view_if_needed()
            await page.wait_for_timeout(500)
            
            # Check if button is enabled
            is_disabled = await publish_btn.is_disabled()
            if is_disabled:
                await page.screenshot(path="/tmp/zhihu_debug.png")
                return "❌ Publish button is disabled. Make sure title and content are entered. Screenshot saved."
            
            # Click with force to ensure it works
            await publish_btn.click(force=True)
            print("⏳ Waiting for confirmation...")
            
            # Wait for success dialog to appear
            try:
                await page.wait_for_selector('text="发布成功"', timeout=15000)
                print("✅ Article published successfully!")
                
                # Wait a bit for the publish to fully complete
                await page.wait_for_timeout(3000)
                
                # Extract article URL from current page
                current_url = page.url
                # URL format: https://zhuanlan.zhihu.com/p/XXXXX/edit
                if "/p/" in current_url:
                    article_id = current_url.split("/p/")[1].split("/")[0]
                    article_url = f"https://zhuanlan.zhihu.com/p/{article_id}"
                    
                    # Navigate to the published article (close edit mode)
                    await page.goto(article_url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(2000)
                    
                    return f"✅ Published! URL: {article_url}"
                
                return "✅ Article published successfully!"
                
            except Exception:
                # Check if we're on the published article page
                await page.wait_for_timeout(3000)
                current_url = page.url
                if "/p/" in current_url and "/edit" not in current_url:
                    return f"✅ Published! URL: {current_url}"
                
                await page.screenshot(path="/tmp/zhihu_result.png")
                return f"⚠️  Uncertain if published. Current URL: {current_url}\nScreenshot saved to /tmp/zhihu_result.png"
                
        except Exception as e:
            await page.screenshot(path="/tmp/zhihu_error.png")
            return f"❌ Error: {e}\nScreenshot saved to /tmp/zhihu_error.png"
        # Don't close the page - leave it open for user to see


async def main():
    parser = argparse.ArgumentParser(description="Post article to Zhihu using Clawdbot browser")
    parser.add_argument("title", nargs="?", help="Article title")
    parser.add_argument("content", nargs="?", help="Article content")
    parser.add_argument("-t", "--title-arg", dest="title_opt", help="Article title (alternative)")
    parser.add_argument("-f", "--file", help="Read article content from file")
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    
    args = parser.parse_args()
    
    # Get title
    title = args.title_opt or args.title
    if not title:
        print("❌ Title is required")
        parser.print_help()
        sys.exit(1)
    
    # Get content from args or file
    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
    elif args.content:
        content = args.content
    elif args.title and not args.title_opt:
        # If only positional args, check stdin
        if not sys.stdin.isatty():
            content = sys.stdin.read().strip()
        else:
            print("❌ Content is required")
            parser.print_help()
            sys.exit(1)
    else:
        print("❌ Content is required")
        parser.print_help()
        sys.exit(1)
    
    if not content:
        print("❌ No content provided")
        sys.exit(1)
    
    result = await post_article(title, content, dry_run=args.dry_run)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
