import os
import re
import json
import shutil
import subprocess
from datetime import datetime

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None

PHOTOS_DIR = "photos"
THUMBNAILS_DIR = "thumbnails"
OUTPUT_JSON = "gallery-data.json"
MAX_THUMB_SIZE = (400, 400)
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

def ensure_dirs():
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    os.makedirs(THUMBNAILS_DIR, exist_ok=True)

def sanitize_folder_name(name):
    """將 Commit Message 清理為安全合法之子目錄名稱"""
    if not name:
        return "Uncategorized"
    clean = re.sub(r'[\/\\\:\*\?\"<>\|]', '_', name)
    clean = clean.strip().strip('.')
    if len(clean) > 50:
        clean = clean[:50]
    return clean or "Uncategorized"

def generate_thumbnail(photo_path, thumb_path):
    if Image is None:
        return
    try:
        thumb_dir = os.path.dirname(thumb_path)
        os.makedirs(thumb_dir, exist_ok=True)
        
        with Image.open(photo_path) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail(MAX_THUMB_SIZE, Image.Resampling.LANCZOS)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(thumb_path, quality=85, optimize=True)
            print(f"Generated thumbnail: {thumb_path}")
    except Exception as e:
        print(f"Error generating thumbnail for {photo_path}: {e}")

def organize_loose_photos():
    """自動將散落在 photos/ 根目錄的照片移動至『YYYY-MM-DD_CommitMessage』子目錄下"""
    if not os.path.exists(PHOTOS_DIR):
        return

    loose_photos = []
    for item in os.listdir(PHOTOS_DIR):
        item_path = os.path.join(PHOTOS_DIR, item)
        if os.path.isfile(item_path):
            ext = os.path.splitext(item)[1].lower()
            if ext in ALLOWED_EXTENSIONS and item != ".gitkeep":
                loose_photos.append(item)

    if not loose_photos:
        print("No loose photos in photos/ root directory.")
        return

    commit_date = datetime.now().strftime("%Y-%m-%d")
    commit_msg = "New Photos"
    
    try:
        cmd = ["git", "log", "-1", "--pretty=format:%cd|%s", "--date=format:%Y-%m-%d"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if result.stdout.strip():
            parts = result.stdout.strip().split("|", 1)
            commit_date = parts[0]
            if len(parts) > 1 and parts[1].strip():
                raw_msg = parts[1].strip()
                if not raw_msg.startswith("🤖"):
                    commit_msg = raw_msg
    except Exception as e:
        print(f"Failed to fetch recent git commit info: {e}")

    clean_msg = sanitize_folder_name(commit_msg)
    subfolder_name = f"{commit_date}_{clean_msg}"
    target_dir = os.path.join(PHOTOS_DIR, subfolder_name)
    os.makedirs(target_dir, exist_ok=True)

    print(f"Organizing {len(loose_photos)} photos into subfolder: {target_dir}")

    for photo_name in loose_photos:
        src_path = os.path.join(PHOTOS_DIR, photo_name)
        dst_path = os.path.join(target_dir, photo_name)
        
        if os.path.exists(dst_path):
            base, ext = os.path.splitext(photo_name)
            dst_path = os.path.join(target_dir, f"{base}_{int(datetime.now().timestamp())}{ext}")
            
        shutil.move(src_path, dst_path)
        print(f"Moved: {src_path} -> {dst_path}")

def build_gallery_data():
    """掃描 photos/ 目錄及其子目錄，生成 gallery-data.json"""
    if not os.path.exists(PHOTOS_DIR):
        return []

    commits_map = {}
    
    for root, dirs, files in os.walk(PHOTOS_DIR):
        rel_root = os.path.relpath(root, PHOTOS_DIR)
        
        if rel_root == ".":
            section_title = "📸 未歸類相片集錦"
            section_key = "root"
            section_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            folder_name = os.path.basename(root)
            parts = folder_name.split("_", 1)
            if len(parts) == 2 and re.match(r'^\d{4}-\d{2}-\d{2}$', parts[0]):
                section_date = f"{parts[0]} 00:00:00"
                section_title = parts[1]
            else:
                section_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                section_title = folder_name
            section_key = folder_name

        valid_photos = []
        for filename in sorted(files):
            ext = os.path.splitext(filename)[1].lower()
            if ext in ALLOWED_EXTENSIONS and filename != ".gitkeep":
                photo_rel_path = os.path.join("photos", rel_root, filename).replace("\\", "/")
                thumb_rel_path = os.path.join("thumbnails", rel_root, filename).replace("\\", "/")
                
                full_photo_path = os.path.join(root, filename)
                full_thumb_path = os.path.join(THUMBNAILS_DIR, rel_root, filename)
                if not os.path.exists(full_thumb_path):
                    generate_thumbnail(full_photo_path, full_thumb_path)
                    
                valid_photos.append({
                    "filename": filename,
                    "photo_url": photo_rel_path,
                    "thumbnail_url": thumb_rel_path,
                    "caption": filename
                })

        if valid_photos:
            commits_map[section_key] = {
                "commit_hash": section_key,
                "short_hash": section_key[:8] if len(section_key) >= 8 else section_key,
                "author": "Contributor",
                "date": section_date,
                "commit_message": section_title,
                "photos": valid_photos
            }

    sorted_keys = sorted(commits_map.keys(), reverse=True)
    sorted_commits = [commits_map[k] for k in sorted_keys]
    
    return sorted_commits

def main():
    ensure_dirs()
    organize_loose_photos()
    commits = build_gallery_data()
    
    data = {
        "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_commits": len(commits),
        "commits": commits
    }
    
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully generated {OUTPUT_JSON} with {len(commits)} album sections.")

if __name__ == "__main__":
    main()
