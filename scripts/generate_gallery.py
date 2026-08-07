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
    """將 Commit Message 清理為適合作業系統與網址的乾淨子目錄名稱 (去除 Emoji、特殊符號與空白)"""
    if not name:
        return "Album"
    # 移除非英數字、中文以外的特殊符號 (包含 Emoji、標點符號與空白)
    clean = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', name)
    clean = re.sub(r'_+', '_', clean).strip('_')
    if len(clean) > 40:
        clean = clean[:40]
    return clean or "Album"

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
    """自動將散落在 photos/ 根目錄的照片移動至『photos/[YYYY-MM-DD_HH-MM-SS]CleanCommitMessage』目錄下"""
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

    commit_time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    commit_msg = "New Photos"
    
    try:
        cmd = ["git", "log", "-1", "--pretty=format:%cd|%s", "--date=format:%Y-%m-%d_%H-%M-%S"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if result.stdout.strip():
            parts = result.stdout.strip().split("|", 1)
            commit_time_str = parts[0]
            if len(parts) > 1 and parts[1].strip():
                raw_msg = parts[1].strip()
                if not raw_msg.startswith("🤖"):
                    commit_msg = raw_msg
    except Exception as e:
        print(f"Failed to fetch recent git commit info: {e}")

    clean_msg = sanitize_folder_name(commit_msg)
    subfolder_name = f"[{commit_time_str}]{clean_msg}"
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

def process_album_folder(folder_name, folder_path, commit_hash, short_hash, date_str, commit_msg):
    """處理單一相簿目錄：進行增量比對、更新 photos/[folder]/gallery-data.json 並回傳 Header 資訊"""
    sub_json_path = os.path.join(folder_path, "gallery-data.json")
    
    current_files = set()
    for filename in sorted(os.listdir(folder_path)):
        ext = os.path.splitext(filename)[1].lower()
        if ext in ALLOWED_EXTENSIONS and filename != ".gitkeep" and filename != "gallery-data.json":
            current_files.add(filename)

    if not current_files:
        return None

    cached_data = None
    if os.path.exists(sub_json_path):
        try:
            with open(sub_json_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
        except Exception as e:
            print(f"Error reading cached {sub_json_path}: {e}")

    need_rescan = True
    valid_photos = []

    if cached_data:
        cached_files = {p["filename"] for p in cached_data.get("photos", [])}
        if cached_data.get("commit_hash") == commit_hash and cached_files == current_files:
            need_rescan = False
            valid_photos = cached_data.get("photos", [])
            print(f"Album [{folder_name}] commit_hash matches and photos unchanged. Skipping rescan.")

    if need_rescan:
        print(f"Rescanning album [{folder_name}]...")
        valid_photos = []
        for filename in sorted(list(current_files)):
            full_photo_path = os.path.join(folder_path, filename)
            photo_rel_path = os.path.join("photos", folder_name, filename).replace("\\", "/")
            thumb_rel_path = os.path.join("thumbnails", folder_name, filename).replace("\\", "/")
            
            full_thumb_path = os.path.join(THUMBNAILS_DIR, folder_name, filename)
            if not os.path.exists(full_thumb_path):
                generate_thumbnail(full_photo_path, full_thumb_path)
                
            valid_photos.append({
                "filename": filename,
                "photo_url": photo_rel_path,
                "thumbnail_url": thumb_rel_path,
                "caption": filename
            })

        sub_json_data = {
            "commit_hash": commit_hash,
            "short_hash": short_hash,
            "author": "Contributor",
            "date": date_str,
            "commit_message": commit_msg,
            "photos": valid_photos
        }
        with open(sub_json_path, "w", encoding="utf-8") as f:
            json.dump(sub_json_data, f, ensure_ascii=False, indent=2)

    cover_photo = valid_photos[0]["photo_url"] if valid_photos else ""
    cover_thumbnail = valid_photos[0]["thumbnail_url"] if valid_photos else ""
    sub_data_url = os.path.join("photos", folder_name, "gallery-data.json").replace("\\", "/")

    return {
        "commit_hash": commit_hash,
        "short_hash": short_hash,
        "author": "Contributor",
        "date": date_str,
        "commit_message": commit_msg,
        "folder_name": folder_name,
        "sub_data_url": sub_data_url,
        "photo_count": len(valid_photos),
        "cover_photo": cover_photo,
        "cover_thumbnail": cover_thumbnail
    }

def build_gallery_data():
    """解析 git log 取得真實 Commit 歷史順序，比對並拆解 JSON 到各個相簿目錄下"""
    if not os.path.exists(PHOTOS_DIR):
        return []

    # 1. 取得所有相簿目錄 (folder_name -> full_path)
    albums_dict = {}
    if os.path.exists(PHOTOS_DIR):
        for item in os.listdir(PHOTOS_DIR):
            item_path = os.path.join(PHOTOS_DIR, item)
            if os.path.isdir(item_path):
                albums_dict[item] = item_path

    if not albums_dict:
        return []

    # 2. 透過 git log 取得真實 Commit 歷史 (從最新到最舊)
    root_commits_headers = []
    processed_folders = set()

    git_commits = []
    try:
        # 取得 commit hash, commit date, commit message
        cmd = ["git", "log", "--pretty=format:%H|%h|%cd|%s", "--date=format:%Y-%m-%d %H:%M:%S"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log_lines = res.stdout.strip().split("\n") if res.stdout.strip() else []

        for line in log_lines:
            if not line.strip():
                continue
            parts = line.strip().split("|", 3)
            if len(parts) < 4:
                continue

            c_hash, c_short, c_date, c_msg = parts[0], parts[1], parts[2], parts[3]
            
            # 跳過自動化腳本Commit
            if c_msg.startswith("🤖") or "[skip ci]" in c_msg or "Automated" in c_msg:
                continue

            git_commits.append({
                "hash": c_hash,
                "short_hash": c_short,
                "date": c_date,
                "msg": c_msg
            })
    except Exception as e:
        print(f"Error fetching git log: {e}")

    # 比對這筆 Commit 對應的相簿資料夾
    for c_info in git_commits:
        c_hash, c_short, c_date, c_msg = c_info["hash"], c_info["short_hash"], c_info["date"], c_info["msg"]
        clean_msg = sanitize_folder_name(c_msg)
        matched_folder = None

        for folder_name in albums_dict.keys():
            if folder_name in processed_folders:
                continue
            # 比對資料夾名稱是否包含乾淨的 commit message 或反向包含
            if clean_msg in folder_name or folder_name in c_msg or re.sub(r'[^\w\u4e00-\u9fff]', '', c_msg) in re.sub(r'[^\w\u4e00-\u9fff]', '', folder_name):
                matched_folder = folder_name
                break

        if matched_folder:
            processed_folders.add(matched_folder)
            header_info = process_album_folder(matched_folder, albums_dict[matched_folder], c_hash, c_short, c_date, c_msg)
            if header_info:
                root_commits_headers.append(header_info)

    # 3. 處理尚未在 git log 匹配到的新目錄 (依修改時間倒序，最新在最前)
    unmatched_folders = [f for f in albums_dict.keys() if f not in processed_folders]
    unmatched_folders.sort(key=lambda f: os.path.getmtime(albums_dict[f]), reverse=True)

    for folder_name in unmatched_folders:
        folder_path = albums_dict[folder_name]
        mtime = os.path.getmtime(folder_path)
        section_date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

        # 擷取標題：若資料夾包含日期時間字首 [YYYY-MM-DD_HH-MM-SS]，取後面部分作為標題
        parts = folder_name.split("]", 1)
        if len(parts) == 2 and parts[0].startswith("["):
            section_title = parts[1]
        else:
            parts_two = folder_name.split("_", 1)
            section_title = parts_two[1] if len(parts_two) == 2 else folder_name

        header_info = process_album_folder(
            folder_name, folder_path,
            f"local_{int(mtime)}", "local",
            section_date, section_title
        )
        if header_info:
            root_commits_headers.insert(0, header_info)

    return root_commits_headers

def main():
    ensure_dirs()
    organize_loose_photos()
    commits_headers = build_gallery_data()
    
    data = {
        "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_commits": len(commits_headers),
        "commits": commits_headers
    }
    
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully generated root {OUTPUT_JSON} with {len(commits_headers)} album sections.")

if __name__ == "__main__":
    main()
