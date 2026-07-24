#!/usr/bin/env python3
"""
Scrape Palantir AIP documentation pages and images.
Downloads all AIP-related pages from palantir.com/docs/foundry/
and saves them as Markdown + images.
"""
import os
import re
import time
import json
import urllib.request
import urllib.parse
from html.parser import HTMLParser

BASE_URL = "https://www.palantir.com"
OUT_DIR = "/Users/ddt/work/projects/ai_agent/docs/palantier/AIP"
IMG_DIR = os.path.join(OUT_DIR, "images")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

# Collect all AIP-related URLs
SEED_URLS = set()

def fetch_url(url):
    """Fetch a URL and return text content."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()

def extract_links(html_bytes, base_path_filter):
    """Extract all links matching a path filter from HTML."""
    html = html_bytes.decode("utf-8", errors="replace")
    links = set()
    for m in re.finditer(r'href="([^"]+)"', html):
        href = m.group(1)
        if base_path_filter in href and href.startswith("/"):
            links.add(href)
    return links

def discover_all_pages():
    """Discover all AIP-related pages by crawling seed pages."""
    seeds = [
        "/docs/foundry/aip/overview/",
        "/docs/foundry/aip/aip-features/",
        "/docs/foundry/aip-evals/overview/",
        "/docs/foundry/aip-observability/overview/",
        "/docs/foundry/aip-analyst/overview/",
        "/docs/foundry/logic/overview/",
        "/docs/foundry/assist/adding-documentation-to-aip-assist/",
    ]
    
    all_pages = set()
    
    for seed in seeds:
        url = BASE_URL + seed
        print(f"  Discovering from: {seed}")
        try:
            data = fetch_url(url)
            # Extract all /docs/foundry/ links
            links = extract_links(data, "/docs/foundry/")
            for link in links:
                # Only keep AIP-related paths
                if any(kw in link for kw in ["/aip", "/logic", "/assist", "/aip-evals", "/aip-observability", "/aip-analyst"]):
                    # Normalize: remove fragments, ensure trailing slash
                    link = link.split("#")[0]
                    if not link.endswith("/"):
                        link += "/"
                    all_pages.add(link)
        except Exception as e:
            print(f"    Error: {e}")
        time.sleep(0.3)
    
    print(f"\n  Total unique pages discovered: {len(all_pages)}")
    return sorted(all_pages)


class MarkdownExtractor(HTMLParser):
    """Extract Markdown from Palantir docs HTML."""
    
    def __init__(self):
        super().__init__()
        self.result = []
        self.tag_stack = []
        self.in_main = False
        self.in_nav = False
        self.in_script = False
        self.in_style = False
        self.current_href = None
        self.skip_depth = 0
        self.current_list_type = None
        self.in_code_block = False
        self.current_img_src = None
        self.current_img_alt = ""
        self.headings = []
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        if tag in ("script", "style"):
            self.in_script = True
            return
            
        if tag == "nav":
            self.in_nav = True
            return
            
        if tag == "main" or tag == "article":
            self.in_main = True
            
        # Skip if not in main content and not nav
        if not self.in_main and not self.in_nav:
            # Still track to find main
            return
            
        if self.in_script or self.in_style:
            return
            
        if self.in_nav and tag != "a":
            return
            
        self.tag_stack.append(tag)
        
        if tag == "a":
            href = attrs_dict.get("href", "")
            if href and href.startswith("/docs/"):
                self.current_href = BASE_URL + href
            elif href and href.startswith("http"):
                self.current_href = href
            else:
                self.current_href = None
        elif tag == "img":
            src = attrs_dict.get("src", "")
            alt = attrs_dict.get("alt", "")
            if src and ("palantir" in src or src.startswith("/")):
                if src.startswith("/"):
                    src = BASE_URL + src
                self.current_img_src = src
                self.current_img_alt = alt
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            self.result.append(f"\n{'#' * level} ")
            self.headings.append((level, ""))
        elif tag == "p":
            self.result.append("\n")
        elif tag == "br":
            self.result.append("\n")
        elif tag == "li":
            if self.current_list_type == "ul":
                self.result.append("\n- ")
            else:
                self.result.append("\n1. ")
        elif tag == "ul":
            self.current_list_type = "ul"
        elif tag == "ol":
            self.current_list_type = "ol"
        elif tag == "pre":
            self.in_code_block = True
            self.result.append("\n```\n")
        elif tag == "code" and not self.in_code_block:
            self.result.append("`")
        elif tag == "strong" or tag == "b":
            self.result.append("**")
        elif tag == "em" or tag == "i":
            self.result.append("*")
        elif tag == "table":
            self.result.append("\n")
            
    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.in_script = False
            return
            
        if tag == "nav":
            self.in_nav = False
            return
            
        if tag == "main" or tag == "article":
            self.in_main = False
            
        if not self.in_main:
            return
            
        if self.in_script or self.in_style:
            return
            
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()
            
        if tag == "a" and self.current_href:
            self.current_href = None
        elif tag == "img" and self.current_img_src:
            self.result.append(f"\n\n![{self.current_img_alt}]({self.current_img_src})\n")
            self.current_img_src = None
            self.current_img_alt = ""
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.result.append("\n")
        elif tag == "p":
            self.result.append("\n")
        elif tag == "pre":
            self.in_code_block = False
            self.result.append("\n```\n")
        elif tag == "code" and not self.in_code_block:
            self.result.append("`")
        elif tag == "strong" or tag == "b":
            self.result.append("**")
        elif tag == "em" or tag == "i":
            self.result.append("*")
        elif tag == "table":
            self.result.append("\n")
            
    def handle_data(self, data):
        if not self.in_main:
            return
        if self.in_script or self.in_style:
            return
        if data.strip():
            self.result.append(data)
    
    def get_markdown(self):
        text = "".join(self.result)
        # Clean up
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()


def html_to_markdown(html_bytes, page_url):
    """Convert Palantir docs HTML to Markdown, extracting text and image URLs."""
    html = html_bytes.decode("utf-8", errors="replace")
    
    # Try to extract the main content area
    main_match = re.search(r'<main[^>]*>(.*?)</main>', html, re.DOTALL)
    if main_match:
        content_html = main_match.group(1)
    else:
        # Fallback: find article or content div
        article_match = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
        if article_match:
            content_html = article_match.group(1)
        else:
            content_html = html
    
    # Extract images
    images = []
    for m in re.finditer(r'<img[^>]+src="([^"]+)"[^>]*(?:alt="([^"]*)")?', content_html):
        src = m.group(1)
        alt = m.group(2) or ""
        if src.startswith("/"):
            src = BASE_URL + src
        images.append((src, alt))
    
    # Remove script/style tags
    content_html = re.sub(r'<script[^>]*>.*?</script>', '', content_html, flags=re.DOTALL)
    content_html = re.sub(r'<style[^>]*>.*?</style>', '', content_html, flags=re.DOTALL)
    
    # Convert headings
    for i in range(6, 0, -1):
        content_html = re.sub(f'<h{i}[^>]*>', f'\n\n{"#"*i} ', content_html)
        content_html = re.sub(f'</h{i}>', '\n', content_html)
    
    # Convert paragraphs
    content_html = re.sub(r'<p[^>]*>', '\n', content_html)
    content_html = re.sub(r'</p>', '\n', content_html)
    
    # Convert links
    def replace_link(m):
        full = m.group(0)
        href = m.group(1)
        text = m.group(2) if len(m.groups()) > 1 else ""
        # Extract text between tags
        text_match = re.search(r'<a[^>]*>(.*?)</a>', full, re.DOTALL)
        if text_match:
            text = re.sub(r'<[^>]+>', '', text_match.group(1)).strip()
        if href.startswith("/docs/"):
            href = BASE_URL + href
        return f'[{text}]({href})'
    
    content_html = re.sub(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', 
                          lambda m: f'[{re.sub(r"<[^>]+>", "", m.group(2)).strip()}]({m.group(1) if m.group(1).startswith("http") else BASE_URL + m.group(1)})',
                          content_html, flags=re.DOTALL)
    
    # Convert images
    def replace_img(m):
        src = m.group(1)
        alt = m.group(2) if len(m.groups()) > 1 and m.group(2) else ""
        if src.startswith("/"):
            src = BASE_URL + src
        return f'\n\n![{alt}]({src})\n'
    
    content_html = re.sub(r'<img[^>]+src="([^"]+)"[^>]*alt="([^"]*)"[^>]*/?\s*>', replace_img, content_html)
    content_html = re.sub(r'<img[^>]+src="([^"]+)"[^>]*/?\s*>', replace_img, content_html)
    
    # Convert lists
    content_html = re.sub(r'<li[^>]*>', '\n- ', content_html)
    content_html = re.sub(r'</li>', '', content_html)
    
    # Convert code
    content_html = re.sub(r'<pre[^>]*>', '\n```\n', content_html)
    content_html = re.sub(r'</pre>', '\n```\n', content_html)
    content_html = re.sub(r'<code[^>]*>', '`', content_html)
    content_html = re.sub(r'</code>', '`', content_html)
    
    # Convert strong/em
    content_html = re.sub(r'<strong[^>]*>', '**', content_html)
    content_html = re.sub(r'</strong>', '**', content_html)
    content_html = re.sub(r'<em[^>]*>', '*', content_html)
    content_html = re.sub(r'</em>', '*', content_html)
    
    # Remove all remaining HTML tags
    content_html = re.sub(r'<[^>]+>', '', content_html)
    
    # Decode HTML entities
    content_html = content_html.replace('&amp;', '&')
    content_html = content_html.replace('&lt;', '<')
    content_html = content_html.replace('&gt;', '>')
    content_html = content_html.replace('&quot;', '"')
    content_html = content_html.replace('&#39;', "'")
    content_html = content_html.replace('&nbsp;', ' ')
    
    # Clean up whitespace
    content_html = re.sub(r'\n{3,}', '\n\n', content_html)
    content_html = re.sub(r' +', ' ', content_html)
    
    return content_html.strip(), images


def url_to_filepath(url_path):
    """Convert a URL path to a file path."""
    # /docs/foundry/aip/overview/ -> aip/overview.md
    # /docs/foundry/aip-evals/create-suite/ -> aip-evals/create-suite.md
    # /docs/foundry/logic/blocks/ -> logic/blocks.md
    path = url_path.replace("/docs/foundry/", "")
    parts = [p for p in path.split("/") if p]
    
    # Create subdirectory structure
    if len(parts) >= 2:
        subdir = parts[0]
        filename = "_".join(parts[1:]) + ".md"
        return os.path.join(OUT_DIR, subdir, filename)
    else:
        return os.path.join(OUT_DIR, "_".join(parts) + ".md")


def download_image(url, local_path):
    """Download an image to local path."""
    try:
        data = fetch_url(url)
        with open(local_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"    Image download failed: {e}")
        return False


def process_page(page_path):
    """Download and process a single documentation page."""
    url = BASE_URL + page_path
    filepath = url_to_filepath(page_path)
    
    # Skip if already exists
    if os.path.exists(filepath):
        return True, 0
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    try:
        html_bytes = fetch_url(url)
    except Exception as e:
        print(f"    Fetch error: {e}")
        return False, 0
    
    markdown, images = html_to_markdown(html_bytes, url)
    
    # Download images
    img_count = 0
    for img_url, img_alt in images:
        # Skip icons, logos, sprites
        if any(skip in img_url.lower() for skip in ["icon", "logo", "sprite", "favicon", "avatar"]):
            continue
        if not any(ext in img_url.lower() for ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]):
            continue
        
        # Generate local filename
        img_name = img_url.split("/")[-1].split("?")[0]
        if not img_name:
            continue
        
        # Prefix with page name for organization
        page_prefix = os.path.basename(filepath).replace(".md", "")
        local_img_name = f"{page_prefix}_{img_name}"
        local_img_path = os.path.join(IMG_DIR, local_img_name)
        
        # Download
        if download_image(img_url, local_img_path):
            img_count += 1
            # Replace URL in markdown
            relative_path = f"images/{local_img_name}"
            markdown = markdown.replace(img_url, relative_path)
    
    # Add source URL header
    header = f"> Source: {url}\n\n"
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(header + markdown + "\n")
    
    return True, img_count


def main():
    print("=" * 60)
    print("Palantir AIP Documentation Scraper")
    print("=" * 60)
    
    # Step 1: Discover all pages
    print("\n[1/3] Discovering all AIP-related pages...")
    pages = discover_all_pages()
    
    # Also add known pages from the overview
    known_pages = [
        "/docs/foundry/aip/overview/",
        "/docs/foundry/aip/aip-features/",
        "/docs/foundry/aip/aip-compute-usage/",
        "/docs/foundry/aip/aip-observability/",
        "/docs/foundry/aip/aip-security/",
        "/docs/foundry/aip/best-practices-prompt-engineering/",
        "/docs/foundry/aip/bring-your-own-model/",
        "/docs/foundry/aip/build-a-proxy-or-federation-layer/",
        "/docs/foundry/aip/chat-completion-function-interface-quickstart/",
        "/docs/foundry/aip/compute-module-backed-models/",
        "/docs/foundry/aip/enable-aip-features/",
        "/docs/foundry/aip/ethics-governance/",
        "/docs/foundry/aip/getting-started-with-aip/",
        "/docs/foundry/aip/llm-capacity-management/",
        "/docs/foundry/aip/llm-enrollment-rate-limits/",
        "/docs/foundry/aip/llm-provider-compatible-apis/",
        "/docs/foundry/aip/rest-api-backed-models/",
        "/docs/foundry/aip/self-host-models/",
        "/docs/foundry/aip/supported-llms/",
        "/docs/foundry/aip/use-registered-llm/",
        # AIP Logic
        "/docs/foundry/logic/overview/",
        "/docs/foundry/logic/getting-started/",
        "/docs/foundry/logic/core-concepts/",
        "/docs/foundry/logic/blocks/",
        "/docs/foundry/logic/branching-logic/",
        "/docs/foundry/logic/execution-mode-settings/",
        "/docs/foundry/logic/compute-usage/",
        "/docs/foundry/logic/logic-metrics/",
        "/docs/foundry/logic/aip-logic-integration-automate/",
        "/docs/foundry/logic/faq/",
        # AIP Evals
        "/docs/foundry/aip-evals/overview/",
        "/docs/foundry/aip-evals/getting-started/",
        "/docs/foundry/aip-evals/create-suite/",
        "/docs/foundry/aip-evals/run-suite/",
        "/docs/foundry/aip-evals/analyze-run-results/",
        "/docs/foundry/aip-evals/results-dataset/",
        "/docs/foundry/aip-evals/experiments/",
        "/docs/foundry/aip-evals/metrics-dashboard/",
        "/docs/foundry/aip-evals/intermediate-parameters/",
        "/docs/foundry/aip-evals/ontology-edits/",
        # AIP Observability
        "/docs/foundry/aip-observability/overview/",
        # AIP Analyst
        "/docs/foundry/aip-analyst/overview/",
        "/docs/foundry/aip-analyst/capabilities/",
        "/docs/foundry/aip-analyst/using-aip-analyst/",
        "/docs/foundry/aip-analyst/workshop-widget/",
        "/docs/foundry/aip-analyst/analysis-resources/",
        "/docs/foundry/aip-analyst/embed/",
        # Assist
        "/docs/foundry/assist/adding-documentation-to-aip-assist/",
        "/docs/foundry/assist/agents-in-aip-assist/",
        "/docs/foundry/assist/aip-assist-custom-docs-overview/",
        "/docs/foundry/assist/aip-assist-registering-content/",
        "/docs/foundry/assist/aip-assist-suggested-actions/",
        "/docs/foundry/assist/aip-best-practices/",
    ]
    pages = sorted(set(pages + known_pages))
    
    print(f"  Total pages to download: {len(pages)}")
    
    # Step 2: Download all pages
    print("\n[2/3] Downloading pages and images...")
    success = 0
    failed = 0
    total_images = 0
    for i, page in enumerate(pages):
        print(f"  [{i+1}/{len(pages)}] {page}")
        ok, imgs = process_page(page)
        if ok:
            success += 1
            total_images += imgs
            if imgs > 0:
                print(f"    -> OK ({imgs} images)")
        else:
            failed += 1
            print(f"    -> FAILED")
        time.sleep(0.5)  # Be polite
    
    # Step 3: Generate index
    print("\n[3/3] Generating index...")
    index_path = os.path.join(OUT_DIR, "README.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("# Palantir AIP Documentation\n\n")
        f.write(f"> Source: https://www.palantir.com/docs/foundry/aip/overview/\n")
        f.write(f"> Scraped: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"**Total pages: {success} | Images: {total_images}**\n\n")
        
        # Group by section
        sections = {}
        for page in pages:
            parts = [p for p in page.replace("/docs/foundry/", "").split("/") if p]
            if parts:
                section = parts[0]
                if section not in sections:
                    sections[section] = []
                sections[section].append(page)
        
        for section, section_pages in sorted(sections.items()):
            f.write(f"\n## {section}\n\n")
            for p in section_pages:
                # Convert to relative link
                parts = [pp for pp in p.replace("/docs/foundry/", "").split("/") if pp]
                if len(parts) >= 2:
                    rel_path = f"{parts[0]}/" + "_".join(parts[1:]) + ".md"
                else:
                    rel_path = "_".join(parts) + ".md"
                title = parts[-1].replace("-", " ").title()
                f.write(f"- [{title}]({rel_path})\n")
    
    print(f"\n{'=' * 60}")
    print(f"DONE: {success} pages, {failed} failed, {total_images} images")
    print(f"Output: {OUT_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
