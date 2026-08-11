#!/usr/bin/env python3
"""
Universal web content extractor (Scrapling + html2text).
Returns clean Markdown with headings, links, images, lists, and code blocks.

Usage:
  python3 fetch.py <url> [max_chars] [--stealth]

Modes:
  (default)   Fast HTTP fetch via Fetcher — works for most sites (~1-3s)
  --stealth   Headless browser via StealthyFetcher — for JS-rendered or
              anti-scraping sites like WeChat, Zhihu, Juejin (~5-15s)

Examples:
  python3 fetch.py https://sspai.com/post/73145
  python3 fetch.py https://mp.weixin.qq.com/s/xxx 30000 --stealth
  python3 fetch.py https://zhuanlan.zhihu.com/p/12345 --stealth
"""

import sys
import re
import json
import logging
from datetime import datetime, timedelta, timezone


def check_dependencies():
    """Check if required packages are installed and provide install instructions."""
    missing = []
    try:
        import scrapling  # noqa: F401
    except ImportError:
        missing.append("scrapling")
    try:
        import html2text  # noqa: F401
    except ImportError:
        missing.append("html2text")

    if missing:
        print(
            f"Error: missing dependencies: {', '.join(missing)}\n"
            f"Install with:\n"
            f"  pip install {' '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)


def fix_lazy_images(html_raw):
    """
    Promote data-src to src for lazy-loaded images (WeChat, Zhihu, etc.).
    Many Chinese platforms use data-src for the real image URL while src
    holds a tiny placeholder. html2text only reads src, so we swap them.
    """
    return re.sub(
        r'<img([^>]*?)\sdata-src="([^"]+)"([^>]*?)>',
        lambda m: f'<img{m.group(1)} src="{m.group(2)}"{m.group(3)}>',
        html_raw,
    )


# CSS selectors in priority order — the first match with enough content wins.
# Covers most blog/article platforms without needing per-site customization.
CONTENT_SELECTORS = [
    "article",
    "main",
    ".post-content",
    ".entry-content",
    ".article-content",
    ".article-body",
    ".article-detail",         # 36kr
    ".article-holder",         # InfoQ
    ".post_body",              # 163.com (NetEase)
    ".markdown-body",          # GitHub
    ".Post-RichText",          # Zhihu
    "#article_content",        # CSDN
    ".article-area",           # Juejin
    ".ssa-article",            # Toutiao
    '[role="article"]',
    '[itemprop="articleBody"]',
]

# WeChat has a unique DOM structure — try these first for mp.weixin.qq.com
WECHAT_SELECTORS = [
    "div#js_content",
    "div.rich_media_content",
]

# Minimum characters for a selector match to be considered "real content"
MIN_CONTENT_LENGTH = 200


def html_to_markdown(html_raw, max_chars=30000):
    """Convert raw HTML to clean Markdown."""
    import html2text

    html_raw = fix_lazy_images(html_raw)

    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.body_width = 0       # No line wrapping
    h.skip_internal_links = True
    h.ignore_emphasis = False

    md = h.handle(html_raw)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return md[:max_chars]


def extract_content(page, url, max_chars=30000):
    """
    Try content selectors to find the article body.
    Returns (markdown_text, matched_selector).
    """
    is_wechat = "mp.weixin.qq.com" in url
    selectors = (WECHAT_SELECTORS + CONTENT_SELECTORS) if is_wechat else CONTENT_SELECTORS

    for selector in selectors:
        els = page.css(selector)
        if els:
            md = html_to_markdown(els[0].html_content, max_chars)
            if len(md) >= MIN_CONTENT_LENGTH:
                return md, selector

    # Fallback: convert the entire page
    md = html_to_markdown(page.html_content, max_chars)
    return md, "body(fallback)"


def extract_metadata(page, url):
    """Extract stable metadata exposed by supported article pages."""
    if "mp.weixin.qq.com" not in url:
        return {}

    selectors = {
        "title": ("#activity-name", "meta[property='og:title']"),
        "author": ("#js_name", ".rich_media_meta_nickname"),
        "published_at": ("#publish_time", "em#publish_time"),
    }
    metadata = {}
    for key, candidates in selectors.items():
        for selector in candidates:
            elements = page.css(selector)
            if not elements:
                continue
            element = elements[0]
            if selector.startswith("meta"):
                value = element.attrib.get("content", "")
            else:
                value = element.get_all_text()
            value = re.sub(r"\s+", " ", str(value)).strip()
            if value:
                if key == "published_at":
                    value = normalize_wechat_published_at(value)
                metadata[key] = value
                break
    if "published_at" not in metadata:
        timestamp = re.search(r"\bct\s*=\s*['\"](\d{10})", page.html_content)
        if timestamp is not None:
            china_time = timezone(timedelta(hours=8))
            metadata["published_at"] = datetime.fromtimestamp(
                int(timestamp.group(1)), china_time
            ).isoformat()
    return metadata


def normalize_wechat_published_at(value):
    """Normalize WeChat's visible Chinese timestamp when possible."""
    try:
        parsed = datetime.strptime(value, "%Y年%m月%d日 %H:%M")
    except ValueError:
        return value
    return parsed.replace(tzinfo=timezone(timedelta(hours=8))).isoformat()


def _suppress_scrapling_logs():
    """Scrapling's logger is noisy (deprecation warnings, fetch info). Silence it."""
    logging.getLogger("scrapling").setLevel(logging.CRITICAL)


def fetch_fast_document(url, max_chars=30000, timeout=15):
    """
    Fast HTTP fetch — no JavaScript execution.
    Works for most blogs and static sites.
    """
    from scrapling.fetchers import Fetcher
    _suppress_scrapling_logs()

    page = Fetcher().get(url, timeout=timeout, stealthy_headers=True)
    md, selector = extract_content(page, url, max_chars)
    return md, selector, extract_metadata(page, url)


def fetch_fast(url, max_chars=30000, timeout=15):
    md, selector, _metadata = fetch_fast_document(url, max_chars, timeout)
    return md, selector


def fetch_stealth_document(url, max_chars=30000, timeout=30000):
    """
    Headless browser fetch — executes JavaScript, bypasses anti-scraping.
    Required for: WeChat articles, Zhihu, Juejin, and other JS-rendered pages.
    Slower (~5-15s) but more reliable for protected content.
    """
    from scrapling.fetchers import StealthyFetcher
    _suppress_scrapling_logs()

    page = StealthyFetcher().fetch(
        url,
        headless=True,
        network_idle=True,
        timeout=timeout,
    )
    md, selector = extract_content(page, url, max_chars)
    return md, selector, extract_metadata(page, url)


def fetch_stealth(url, max_chars=30000, timeout=30000):
    md, selector, _metadata = fetch_stealth_document(url, max_chars, timeout)
    return md, selector


def fetch_document(url, max_chars=30000, stealth=False):
    """Fetch content plus page metadata for Adapter consumers."""
    if stealth:
        md, selector, metadata = fetch_stealth_document(url, max_chars)
        return md, selector, "stealth", metadata

    md, selector, metadata = fetch_fast_document(url, max_chars)
    if len(md) < MIN_CONTENT_LENGTH:
        try:
            md_stealth, sel_stealth, metadata_stealth = fetch_stealth_document(
                url, max_chars
            )
            if len(md_stealth) > len(md):
                return (
                    md_stealth,
                    sel_stealth,
                    "stealth(auto-fallback)",
                    metadata_stealth,
                )
        except Exception:
            pass
    return md, selector, "fast", metadata


def fetch(url, max_chars=30000, stealth=False):
    """
    Main entry point. Fetches URL and returns (markdown, selector, mode).
    If stealth=False, tries fast mode first and falls back to stealth
    when the result is too short (likely a JS-rendered page).
    """
    md, selector, mode, _metadata = fetch_document(url, max_chars, stealth)
    return md, selector, mode


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python3 fetch.py <url> [max_chars] [--stealth]\n"
            "\n"
            "Options:\n"
            "  max_chars   Maximum output characters (default: 30000)\n"
            "  --stealth   Use headless browser for JS-rendered pages\n"
            "  --json      Output as JSON with metadata\n",
            file=sys.stderr,
        )
        sys.exit(1)

    url = sys.argv[1]
    args = sys.argv[2:]

    stealth = "--stealth" in args
    json_output = "--json" in args
    args = [a for a in args if not a.startswith("--")]
    max_chars = int(args[0]) if args else 30000

    try:
        md, selector, mode, metadata = fetch_document(
            url, max_chars, stealth=stealth
        )

        if json_output:
            result = {
                "url": url,
                "mode": mode,
                "selector": selector,
                "content_length": len(md),
                "metadata": metadata,
                "content": md,
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(md)

    except Exception as e:
        error_msg = f"Error fetching {url}: {type(e).__name__}: {e}"
        if json_output:
            print(json.dumps({"url": url, "error": error_msg}, ensure_ascii=False))
        else:
            print(error_msg, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    check_dependencies()
    main()
