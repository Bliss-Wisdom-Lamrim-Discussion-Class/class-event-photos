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
    """將 Commit Message 清理為適合作業系統與網址的乾淨子目錄名稱 (去除 Emoji 與空白)"""
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
    """自動將散落在 photos/ 根目錄的照片移動至『YYYY-MM-DD_CleanFolderTitle』子目錄下"""
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
    
    # 嘗試從 LINE 相簿檔名 (例: LINE_ALBUM_10683-97日幸福與智慧課程_260807_1.jpg) 提取相簿標題
    line_titles = set()
    for photo_name in loose_photos:
        m = re.search(r'LINE_ALBUM_(.+?)_\d+', photo_name, re.IGNORECASE)
        if m:
            raw_title = m.group(1)
            # 整理標題 (例: 10683-97日幸福與智慧課程 -> 106_8_3-9_7日幸福與智慧課程)
            clean_title = re.sub(r'(\d{3})(\d)(\d)-(\d)(\d)', r'\1_\2_\3-\4_\5', raw_title)
            line_titles.add(clean_title)
            
    if line_titles:
        commit_msg = " ".join(sorted(list(line_titles)))
    else:
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
    """直接用 git log --diff-filter=A 找出每個 Commit 新增的相簿資料夾，最新 Commit 排在最上方。"""
    if not os.path.exists(PHOTOS_DIR):
        return []

    # 強制台灣時區 (UTC+8)，使時間顯示正確
    env = os.environ.copy()
    env["TZ"] = "Asia/Taipei"

    # 1. 用 git log 直接找出每個 commit 新增了哪些 photos/ 子目錄
    #    輸出格式: COMMIT行 + 該 commit 新增的檔案/目錄列表
    folder_to_commit = {}  # folder_name -> {hash, short_hash, date, message}

    try:
        cmd = [
            "git", "log",
            "--diff-filter=A",          # 只看有「新增」檔案的 commit
            "--name-only",              # 列出新增的檔案名稱
            "--pretty=format:COMMIT|%H|%h|%cd|%s",
            "--date=format:%Y-%m-%d %H:%M:%S",
            "--", "photos/"             # 只看 photos/ 目錄
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
        lines = res.stdout.strip().split("\n") if res.stdout.strip() else []

        current_commit = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("COMMIT|"):
                parts = line.split("|", 4)
                if len(parts) == 5:
                    _, c_hash, c_short, c_date, c_msg = parts
                    # 跳過自動化 Commit
                    if c_msg.startswith("🤖") or "[skip ci]" in c_msg or "Automated" in c_msg:
                        current_commit = None
                    else:
                        current_commit = {
                            "commit_hash": c_hash,
                            "short_hash": c_short,
                            "date": c_date,
                            "commit_message": c_msg,
                        }
            elif current_commit and line.startswith("photos/"):
                # 路徑格式: photos/<folder_name>/<filename>
                parts = line.split("/")
                if len(parts) >= 2:
                    folder_name = parts[1]
                    if folder_name and folder_name not in folder_to_commit:
                        folder_to_commit[folder_name] = current_commit
    except Exception as e:
        print(f"Error fetching git log: {e}")

    # 2. 取得所有相簿目錄
    albums_dict = {}
    for item in os.listdir(PHOTOS_DIR):
        item_path = os.path.join(PHOTOS_DIR, item)
        if os.path.isdir(item_path):
            albums_dict[item] = item_path

    # 3. 依照 git log 的 commit 順序 (最新→最舊) 重新排列相簿
    #    先建立 commit hash → [folders] 的映射，保留順序
    seen_hashes = []
    hash_to_folders = {}
    for folder_name, commit_info in folder_to_commit.items():
        c_hash = commit_info["commit_hash"]
        if c_hash not in hash_to_folders:
            seen_hashes.append(c_hash)
            hash_to_folders[c_hash] = []
        hash_to_folders[c_hash].append(folder_name)

    commits_list = []
    processed_folders = set()

    for c_hash in seen_hashes:
        commit_info = folder_to_commit[hash_to_folders[c_hash][0]]
        for folder_name in hash_to_folders[c_hash]:
            if folder_name not in albums_dict:
                continue
            processed_folders.add(folder_name)
            folder_path = albums_dict[folder_name]

            valid_photos = []
            for filename in sorted(os.listdir(folder_path)):
                ext = os.path.splitext(filename)[1].lower()
                if ext in ALLOWED_EXTENSIONS and filename != ".gitkeep":
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

            if valid_photos:
                commits_list.append({
                    "commit_hash": commit_info["commit_hash"],
                    "short_hash": commit_info["short_hash"],
                    "author": "Contributor",
                    "date": commit_info["date"],
                    "commit_message": commit_info["commit_message"],
                    "photos": valid_photos
                })

    # 4. 處理尚未被 git log 追蹤到的新目錄 (放最上方)
    for folder_name, folder_path in albums_dict.items():
        if folder_name in processed_folders:
            continue
        parts = folder_name.split("_", 1)
        section_title = parts[1] if len(parts) == 2 else folder_name
        mtime = os.path.getmtime(folder_path)
        section_date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

        valid_photos = []
        for filename in sorted(os.listdir(folder_path)):
            ext = os.path.splitext(filename)[1].lower()
            if ext in ALLOWED_EXTENSIONS and filename != ".gitkeep":
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

        if valid_photos:
            commits_list.insert(0, {
                "commit_hash": folder_name,
                "short_hash": folder_name[:8],
                "author": "Contributor",
                "date": section_date,
                "commit_message": section_title,
                "photos": valid_photos
            })

    return commits_list

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
