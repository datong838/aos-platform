#!/usr/bin/env python3
"""Download article images from Toutiao CDN"""
import subprocess
import os

images = [
    (1, "https://p3-sign.toutiaoimg.com/tos-cn-i-axegupay5k/8e1c44140cdf476eb438da40a7291127~tplv-tt-large.image?_iz=30575&lk3s=06827d14&x-expires=1785422353&x-signature=5u779QeRBwMBHF2u75km2XwCTyo%3D"),
    (2, "https://p3-sign.toutiaoimg.com/tos-cn-i-6w9my0ksvp/9db4ff121c8b43a083b0ce2879bbc11f~tplv-tt-large.image?_iz=30575&lk3s=06827d14&x-expires=1785422353&x-signature=pjbF3qmB6JyH1C%2FMZb003ok2RtA%3D"),
    (3, "https://p3-sign.toutiaoimg.com/tos-cn-i-6w9my0ksvp/b86c9ab6c26d46c89f6163c54d659907~tplv-tt-large.image?_iz=30575&lk3s=06827d14&x-expires=1785422353&x-signature=gbkUghfM1qR8F78z7dz0tmxcU7Y%3D"),
    (4, "https://p3-sign.toutiaoimg.com/tos-cn-i-6w9my0ksvp/b84212a044a24ca5881854ef2a6bc776~tplv-tt-large.image?_iz=30575&lk3s=06827d14&x-expires=1785422353&x-signature=i%2F1mSArriegNGVL3uk7k%2FVWpuwA%3D"),
    (5, "https://p3-sign.toutiaoimg.com/tos-cn-i-6w9my0ksvp/a65ad92cc6b84045b429d436bd5f86f1~tplv-tt-large.image?_iz=30575&lk3s=06827d14&x-expires=1785422353&x-signature=PQkhdbKVhgriKw9IUQCM90aY0HI%3D"),
    (6, "https://p3-sign.toutiaoimg.com/tos-cn-i-6w9my0ksvp/4bb6ea57c5d34f88872a05a8154b5a11~tplv-tt-large.image?_iz=30575&lk3s=06827d14&x-expires=1785422353&x-signature=UH%2B%2B69J2B%2F2A5SpkxYE4q4pKRDU%3D"),
    (7, "https://p3-sign.toutiaoimg.com/tos-cn-i-6w9my0ksvp/c289cb5f56ea4744a8ad609a6b89631b~tplv-tt-large.image?_iz=30575&lk3s=06827d14&x-expires=1785422353&x-signature=f2oplKulAt6q0Vi67DObZaOWG1M%3D"),
    (8, "https://p3-sign.toutiaoimg.com/tos-cn-i-6w9my0ksvp/10dd44e03e73431e961a88a40a8287f3~tplv-tt-large.image?_iz=30575&lk3s=06827d14&x-expires=1785422353&x-signature=TQnLT3cW1asPVizPRCD5cccXN%2Bk%3D"),
    (9, "https://p3-sign.toutiaoimg.com/tos-cn-i-6w9my0ksvp/cb790d4865ea4e86b7d54cc380233b14~tplv-tt-large.image?_iz=30575&lk3s=06827d14&x-expires=1785422353&x-signature=0TuIdv%2BnsfuusgJFvLoj4gQhyr0%3D"),
]

outdir = "/Users/ddt/WorkBuddy/2026-07-21-12-26-10/pptx_images"
for num, url in images:
    outpath = os.path.join(outdir, f"img_{num:02d}.jpg")
    r = subprocess.run(
        ["curl", "-sL", "-H", "User-Agent: Mozilla/5.0", "-o", outpath, url],
        capture_output=True
    )
    size = os.path.getsize(outpath) if os.path.exists(outpath) else 0
    print(f"Image {num}: {size} bytes")
