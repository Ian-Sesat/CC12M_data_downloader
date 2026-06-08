"""
download_cc12m.py
Downloads CC12M images from URLs in the TSV file.
Skips images that cannot be downloaded.
Saves image + caption pairs to disk.

Usage:
    1. Download cc12m.tsv from Google Drive first
    2. Set TSV_PATH to the downloaded file
    3. Run this script
"""

import os
import csv
import requests
import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

BASE_DIR  = '/your/path'
TSV_PATH  = os.path.join(BASE_DIR, 'cc12m.tsv')       # downloaded TSV file
SAVE_DIR  = os.path.join(BASE_DIR, 'cc12m', 'images')
META_PATH = os.path.join(BASE_DIR, 'cc12m', 'captions.tsv')

os.makedirs(SAVE_DIR, exist_ok=True)

# download settings
MAX_WORKERS  = 8     # parallel downloads
TIMEOUT      = 5     # seconds per request
IMAGE_EXTS   = {'.jpg', '.jpeg', '.png', '.webp'}
MAX_SIZE_GB  = 250   # stop when dataset reaches this size


def get_extension(url, content_type=''):
    """Get image extension from URL or content type."""
    url_lower = url.lower()
    for ext in IMAGE_EXTS:
        if url_lower.endswith(ext):
            return ext
    if 'jpeg' in content_type or 'jpg' in content_type:
        return '.jpg'
    if 'png' in content_type:
        return '.png'
    if 'webp' in content_type:
        return '.webp'
    return '.jpg'  # default


def download_image(args):
    """
    Download one image from URL.
    Returns (filename, caption) if successful, None if failed.
    """
    idx, url, caption = args

    # use hash of URL as filename to avoid duplicates
    url_hash  = hashlib.md5(url.encode()).hexdigest()
    filename  = f'{url_hash}.jpg'
    save_path = os.path.join(SAVE_DIR, filename)

    # skip if already downloaded
    if os.path.exists(save_path):
        return filename, caption

    try:
        response = requests.get(url, timeout=TIMEOUT, stream=True)
        if response.status_code != 200:
            return None

        content_type = response.headers.get('Content-Type', '')
        if 'image' not in content_type:
            return None

        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return filename, caption

    except Exception:
        # clean up partial download
        if os.path.exists(save_path):
            os.remove(save_path)
        return None


import random

# load TSV file
print(f"Loading TSV from {TSV_PATH}...")
rows = []
with open(TSV_PATH, 'r', encoding='utf-8') as f:
    reader = csv.reader(f, delimiter='\t')
    for row in reader:
        if len(row) >= 2:
            rows.append((row[0], row[1]))  # url, caption

print(f"Total entries : {len(rows):,}")

# deduplicate by URL first
print("Deduplicating by URL...")
seen_urls = set()
unique_rows = []
for url, caption in rows:
    if url not in seen_urls:
        seen_urls.add(url)
        unique_rows.append((url, caption))
rows = unique_rows
print(f"After dedup : {len(rows):,} unique entries")

# uniform sampling across all sections of the dataset
# split into NUM_SECTIONS equal chunks
# sample equally from each chunk → guaranteed coverage
NUM_SECTIONS = 100
print(f"Applying uniform sampling across {NUM_SECTIONS} sections...")
random.seed(42)

section_size = len(rows) // NUM_SECTIONS
sections     = [rows[i * section_size:(i + 1) * section_size]
                for i in range(NUM_SECTIONS)]

# shuffle within each section
for section in sections:
    random.shuffle(section)

# interleave sections: take one from each section in round-robin
# this guarantees every section is represented even if we stop early
interleaved = []
max_len     = max(len(s) for s in sections)
for i in range(max_len):
    for section in sections:
        if i < len(section):
            interleaved.append(section[i])

rows = interleaved
print(f"Uniform interleaved : {len(rows):,} entries ")
print(f"Each section contributes ~{section_size:,} images")

# check already downloaded
existing = len(list(Path(SAVE_DIR).glob('*.jpg')))
print(f"Already downloaded : {existing:,}")

# download images in parallel
print(f"\nDownloading images with {MAX_WORKERS} workers...")
print(f"Saving to: {SAVE_DIR}")

tasks = [(i, url, caption) for i, (url, caption) in enumerate(rows)]
successful    = []
failed        = 0

meta_file = open(META_PATH, 'w', encoding='utf-8')
meta_file.write('filename\tcaption\n')

def get_dir_size_gb(path):
    total = sum(f.stat().st_size for f in Path(path).glob('*') if f.is_file())
    return total / (1024 ** 3)

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(download_image, task): task for task in tasks}

    with tqdm(total=len(tasks), desc="Downloading") as pbar:
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                filename, caption = result
                meta_file.write(f'{filename}\t{caption}\n')
                successful.append(filename)
            else:
                failed += 1
            pbar.update(1)

            # check size every 1000 images
            if len(successful) % 1000 == 0:
                size_gb = get_dir_size_gb(SAVE_DIR)
                pbar.set_postfix({
                'success': f'{len(successful):,}',
                'failed' : f'{failed:,}',
                'size_gb': f'{size_gb:.1f}GB'
                })
                if size_gb >= MAX_SIZE_GB:
                    print(f"\nReached {MAX_SIZE_GB}GB limit → stopping download")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

meta_file.close()

print(f"\nDownload complete!")
print(f"Successfully downloaded : {len(successful):,}")
print(f"Failed / not found      : {failed:,}")
print(f"Success rate            : {len(successful)/len(tasks)*100:.1f}%")
print(f"Captions saved to       : {META_PATH}")
