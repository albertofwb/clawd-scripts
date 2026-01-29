#!/usr/bin/env python3
"""
Twitter/X Post Script using Clawdbot's logged-in browser session.

Usage:
    python twitter_post.py "Your tweet content here"
    python twitter_post.py -f tweet.txt  # Read from file
    python twitter_post.py --reply URL "Reply content"  # Reply to a tweet
    
Requires:
    pip install playwright
    
The script connects to Clawdbot's browser via CDP (Chrome DevTools Protocol).
Make sure the browser is running: clawdbot browser start --profile clawd
"""

import argparse
import asyncio
import re
import sys
from playwright.async_api import async_playwright


CDP_URL = "http://127.0.0.1:18800"  # Clawdbot browser CDP endpoint


async def post_tweet(content: str, reply_to: str = None, dry_run: bool = False) -> str:
    """Post a tweet or reply using the logged-in browser session.
    
    Args:
        content: Tweet content (max 280 chars for regular accounts)
        reply_to: URL of tweet to reply to (optional)
        dry_run: If True, just preview without posting
        
    Returns:
        URL of the posted tweet or error message
    """
    if len(content) > 280:
        print(f"⚠️  Warning: Tweet is {len(content)} chars (280 limit for free accounts)")
    
    if dry_run:
        print(f"📝 Preview:\n{content}\n")
        print(f"📊 Length: {len(content)} chars")
        if reply_to:
            print(f"↩️  Reply to: {reply_to}")
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
            if reply_to:
                # === REPLY MODE ===
                print(f"↩️  Replying to: {reply_to}")
                await page.goto(reply_to, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(3000)
                
                # Click the reply button on the tweet
                reply_button = page.locator('[data-testid="reply"]').first
                if not await reply_button.count():
                    # Try alternative selector
                    reply_button = page.locator('button[aria-label*="Reply"]').first
                
                if await reply_button.count():
                    print("💬 Opening reply dialog...")
                    await reply_button.click()
                    await page.wait_for_timeout(1500)
                else:
                    return "❌ Could not find reply button"
                
                # Find the reply textbox in the dialog
                textbox = page.locator('[data-testid="tweetTextarea_0"]').first
                if not await textbox.count():
                    textbox = page.locator('div[role="dialog"] [data-testid="tweetTextarea_0"]').first
                if not await textbox.count():
                    textbox = page.locator('[aria-label="Post text"]').first
                    
            else:
                # === NEW TWEET MODE ===
                print("📝 Opening compose dialog...")
                await page.goto("https://twitter.com/compose/tweet", wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(3000)
                
                # Find and fill the text box
                textbox = page.locator('[data-testid="tweetTextarea_0"]').first
                if not await textbox.count():
                    textbox = page.locator('[aria-label="Post text"]').first
            
            if not await textbox.count():
                await page.screenshot(path="/tmp/twitter_debug.png")
                return "❌ Could not find tweet textbox. Screenshot saved to /tmp/twitter_debug.png"
            
            print("✍️  Typing content...")
            await textbox.click()
            await page.wait_for_timeout(300)
            await textbox.fill(content)
            await page.wait_for_timeout(500)
            
            # Post using Ctrl+Enter (most reliable method)
            print("📤 Posting via Ctrl+Enter...")
            await page.keyboard.press("Control+Enter")
            
            # Wait for success
            print("⏳ Waiting for confirmation...")
            await page.wait_for_timeout(3000)
            
            # Check for success - look for the alert
            alert = page.locator('text="Your post was sent."')
            reply_alert = page.locator('text="Your reply was sent."')
            
            if await alert.count() or await reply_alert.count():
                action = "Reply" if reply_to else "Tweet"
                print(f"✅ {action} posted successfully!")
                return f"✅ {action} posted!"
            
            # If Ctrl+Enter didn't work, try clicking the button
            print("🔄 Trying button click...")
            selectors = [
                'div[role="dialog"] button[data-testid="tweetButton"]',
                'button[data-testid="tweetButton"]',
                'button[data-testid="tweetButtonInline"]',
                'div[role="dialog"] button:has-text("Reply")',
                'div[role="dialog"] button:has-text("Post")',
            ]
            for selector in selectors:
                btn = page.locator(selector).first
                if await btn.count():
                    try:
                        is_disabled = await btn.get_attribute("disabled")
                        if is_disabled:
                            continue
                        await btn.click(force=True)
                        print(f"✅ Clicked: {selector}")
                        await page.wait_for_timeout(3000)
                        break
                    except Exception as e:
                        print(f"⚠️  Failed {selector}: {e}")
                        continue
            
            # Final check
            await page.wait_for_timeout(2000)
            if await alert.count() or await reply_alert.count():
                action = "Reply" if reply_to else "Tweet"
                return f"✅ {action} posted!"
            
            await page.screenshot(path="/tmp/twitter_debug.png")
            return "⚠️  Uncertain if posted. Screenshot saved to /tmp/twitter_debug.png"
                
        except Exception as e:
            await page.screenshot(path="/tmp/twitter_error.png")
            return f"❌ Error: {e}\nScreenshot saved to /tmp/twitter_error.png"
        finally:
            await page.close()


async def main():
    parser = argparse.ArgumentParser(description="Post to Twitter/X using Clawdbot browser")
    parser.add_argument("content", nargs="?", help="Tweet content")
    parser.add_argument("-f", "--file", help="Read tweet content from file")
    parser.add_argument("-r", "--reply", help="URL of tweet to reply to")
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    
    args = parser.parse_args()
    
    # Get content from args or file
    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
    elif args.content:
        content = args.content
    else:
        # Read from stdin if piped
        if not sys.stdin.isatty():
            content = sys.stdin.read().strip()
        else:
            parser.print_help()
            sys.exit(1)
    
    if not content:
        print("❌ No content provided")
        sys.exit(1)
    
    result = await post_tweet(content, reply_to=args.reply, dry_run=args.dry_run)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
