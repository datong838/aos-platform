#!/usr/bin/env python3
"""Reorder sidebar sections and rename menu item across all HTML files."""
import re
import os

HTML_DIR = "/Users/ddt/work/projects/ai_agent/docs/palantier/foundry/html"

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # 1. Rename "数据连接" to "数据链接器" in sidebar
    content = content.replace('<span>数据连接</span>', '<span>数据链接器</span>')
    
    # 2. Swap "数据源与同步" and "管道与数据治理" sections
    # Match the two section blocks and swap them
    # Pattern: title div + section div (with all content until closing </div>)
    # We need to be careful with nested divs
    
    # Find the two blocks using regex with the title markers
    # Block A: from "数据源与同步" title to "管道与数据治理" title
    # Block B: from "管道与数据治理" title to next title (运维交付) or end
    
    # Strategy: extract the full blocks by tracking div nesting
    pattern = re.compile(
        r'(<div class="p-sidebar-section-title">数据源与同步</div>\s*<div class="p-sidebar-section">.*?</div>\s*)'
        r'(<div class="p-sidebar-section-title">管道与数据治理</div>\s*<div class="p-sidebar-section">.*?</div>\s*)',
        re.DOTALL
    )
    
    match = pattern.search(content)
    if match:
        block_a = match.group(1)  # 数据源与同步
        block_b = match.group(2)  # 管道与数据治理
        # Swap: B first, then A
        content = content[:match.start()] + block_b + block_a + content[match.end():]
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

# Process all HTML files
changed = []
unchanged = []

for filename in sorted(os.listdir(HTML_DIR)):
    if filename.endswith('.html'):
        filepath = os.path.join(HTML_DIR, filename)
        if process_file(filepath):
            changed.append(filename)
        else:
            unchanged.append(filename)

print(f"Changed: {len(changed)} files")
print(f"Unchanged: {len(unchanged)} files")
if unchanged:
    print("Unchanged files:")
    for f in unchanged:
        print(f"  {f}")

# Verify: check section order in a sample file
print("\n=== Verification (index.html) ===")
with open(os.path.join(HTML_DIR, "index.html"), 'r', encoding='utf-8') as f:
    content = f.read()
for line in content.split('\n'):
    if 'p-sidebar-section-title' in line:
        print(line.strip())
