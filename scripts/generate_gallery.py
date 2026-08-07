import os
import json
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

def generate_thumbnail(photo_path, thumb_path):
    if Image is None:
        print("Pillow not installed, skipping thumbnail generation.")
        return
    try:
        with Image.open(photo_path) as img:
            # 自動處理 EXIF 旋轉問題
            img = ImageOps.exif_transpose(img)
            img.thumbnail(MAX_THUMB_SIZE, Image.Resampling.LANCZOS)
            # 如果是 RGBA 轉成 RGB
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(thumb_path, quality=85, optimize=True)
            print(f"Generated thumbnail: {thumb_path}")
    except Exception as e:
        print(f"Error generating thumbnail for {photo_path}: {e}")

def get_git_commits():
    """解析 git log 取得 commit 資訊與該 commit 修改/新增的照片"""
    try:
        cmd = ["git", "log", "--name-only", "--pretty=format:COMMIT_START|%H|%h|%an|%ad|%s", "--date=format:%Y-%m-%d %H:%M:%S"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.split("\n")
        
        commits = []
        current_commit = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("COMMIT_START|"):
                parts = line.split("|")
                if len(parts) >= 6:
                    if current_commit and current_commit["photos"]:
                        commits.append(current_commit)
                    current_commit = {
                        "commit_hash": parts[1],
                        "short_hash": parts[2],
                        "author": parts[3],
                        "date": parts[4],
                        "commit_message": parts[5],
                        "photos": []
                    }
            elif current_commit and line.startswith("photos/"):
                filename = os.path.basename(line)
                ext = os.path.splitext(filename)[1].lower()
                if ext in ALLOWED_EXTENSIONS:
                    photo_path = line.replace("\\", "/")
                    thumb_filename = filename
                    thumb_path = f"thumbnails/{thumb_filename}"
                    
                    # 確保縮圖存在
                    full_photo_path = os.path.join(PHOTOS_DIR, filename)
                    full_thumb_path = os.path.join(THUMBNAILS_DIR, thumb_filename)
                    if os.path.exists(full_photo_path) and not os.path.exists(full_thumb_path):
                        generate_thumbnail(full_photo_path, full_thumb_path)
                        
                    current_commit["photos"].append({
                        "filename": filename,
                        "photo_url": photo_path,
                        "thumbnail_url": thumb_path,
                        "caption": filename
                    })
                    
        if current_commit and current_commit["photos"]:
            commits.append(current_commit)
            
        return commits
    except Exception as e:
        print(f"Git log failed: {e}. Falling back to directory scan.")
        return []

def fallback_directory_scan():
    """無 Git 歷史或 Git 失敗時備用：掃描 photos 目錄"""
    if not os.path.exists(PHOTOS_DIR):
        return []
    
    photos = []
    for filename in sorted(os.listdir(PHOTOS_DIR)):
        ext = os.path.splitext(filename)[1].lower()
        if ext in ALLOWED_EXTENSIONS:
            full_photo = os.path.join(PHOTOS_DIR, filename)
            full_thumb = os.path.join(THUMBNAILS_DIR, filename)
            if not os.path.exists(full_thumb):
                generate_thumbnail(full_photo, full_thumb)
            photos.append({
                "filename": filename,
                "photo_url": f"photos/{filename}",
                "thumbnail_url": f"thumbnails/{filename}",
                "caption": filename
            })
            
    if not photos:
        return []
        
    return [{
        "commit_hash": "local_import",
        "short_hash": "local",
        "author": "System",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "commit_message": "📸 上傳相片總集錦",
        "photos": photos
    }]

def main():
    ensure_dirs()
    
    # 遍歷 photos/ 確保所有照片均生成縮圖
    if os.path.exists(PHOTOS_DIR):
        for filename in os.listdir(PHOTOS_DIR):
            ext = os.path.splitext(filename)[1].lower()
            if ext in ALLOWED_EXTENSIONS:
                p_path = os.path.join(PHOTOS_DIR, filename)
                t_path = os.path.join(THUMBNAILS_DIR, filename)
                if not os.path.exists(t_path):
                    generate_thumbnail(p_path, t_path)
                    
    commits = get_git_commits()
    if not commits:
        commits = fallback_directory_scan()
        
    data = {
        "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_commits": len(commits),
        "commits": commits
    }
    
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully generated {OUTPUT_JSON} with {len(commits)} commits.")

if __name__ == "__main__":
    main()
