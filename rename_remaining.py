#!/usr/bin/env python3
"""Rename remaining '数据连接' references to '数据链接器' across all HTML files."""
import os
import re

HTML_DIR = "/Users/ddt/work/projects/ai_agent/docs/palantier/foundry/html"

changed = []
for filename in sorted(os.listdir(HTML_DIR)):
    if not filename.endswith('.html'):
        continue
    filepath = os.path.join(HTML_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Replace all remaining "数据连接" with "数据链接器"
    # But preserve "数据连接代理" -> "数据链接器代理"
    content = content.replace('数据连接代理', '数据链接器代理')
    content = content.replace('数据连接', '数据链接器')
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        changed.append(filename)

print(f"Changed: {len(changed)} files")
for f in changed:
    print(f"  {f}")

# Final verify
print("\n=== Final check ===")
remaining = 0
for filename in sorted(os.listdir(HTML_DIR)):
    if not filename.endswith('.html'):
        continue
    filepath = os.path.join(HTML_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    count = content.count('数据连接')
    if count > 0:
        remaining += count
        print(f"  Still has '数据连接' x{count}: {filename}")

if remaining == 0:
    print("All '数据连接' have been renamed to '数据链接器'")
