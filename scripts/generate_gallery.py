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
    """
    透過 git log 找出每個照片最初被加入 photos/ 根目錄的 user commit，
    再透過檔名對應到目前的相簿資料夾，確保順序與使用者上傳的 commit 順序一致。
    """
    if not os.path.exists(PHOTOS_DIR):
        return []

    # 強制台灣時區 (UTC+8)
    env = os.environ.copy()
    env["TZ"] = "Asia/Taipei"

    # Step 1: 掃描現有相簿資料夾及其照片檔名
    albums_dict = {}
    file_to_folder = {}  # filename -> folder_name
    for item in os.listdir(PHOTOS_DIR):
        item_path = os.path.join(PHOTOS_DIR, item)
        if os.path.isdir(item_path):
            albums_dict[item] = item_path
            for fname in os.listdir(item_path):
                ext = os.path.splitext(fname)[1].lower()
                if ext in ALLOWED_EXTENSIONS and fname != ".gitkeep":
                    file_to_folder[fname] = item

    if not albums_dict:
        return []

    # Step 2: 用 git log 找出每個照片被加入 photos/ 根目錄的原始 user commit
    #         (排除 Actions 自動化 commit，只找使用者的手動 commit)
    try:
        cmd = [
            "git", "log",
            "--diff-filter=A",              # 只看新增檔案
            "--name-only",                  # 列出新增的檔案
            "--pretty=format:COMMIT|%H|%h|%cd|%s",
            "--date=format:%Y-%m-%d %H:%M:%S",
            "--", "photos/"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
        lines = res.stdout.strip().split("\n") if res.stdout.strip() else []
    except Exception as e:
        print(f"Error fetching git log: {e}")
        lines = []

    # Step 3: 解析 git log 輸出，將每個照片檔名對應到 commit_index (0=最新)
    folder_to_commit = {}  # folder_name -> commit_info dict
    current_commit = None
    commit_index = 0  # git log 從最新到最舊，所以 index 0 是最新

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("COMMIT|"):
            parts = line.split("|", 4)
            if len(parts) == 5:
                _, c_hash, c_short, c_date, c_msg = parts
                if c_msg.startswith("🤖") or "[skip ci]" in c_msg or "Automated" in c_msg:
                    current_commit = None  # 跳過自動化 commit
                else:
                    current_commit = {
                        "commit_hash": c_hash,
                        "short_hash": c_short,
                        "date": c_date,
                        "commit_message": c_msg,
                        "index": commit_index,
                    }
                    commit_index += 1
        elif line.startswith("photos/") and current_commit:
            path_parts = line.split("/")
            if len(path_parts) == 2:
                # 直接在 photos/ 根目錄的檔案 (使用者上傳的原始位置)
                filename = path_parts[1]
                if filename in file_to_folder:
                    folder_name = file_to_folder[filename]
                    if folder_name not in folder_to_commit:
                        folder_to_commit[folder_name] = current_commit
            # 忽略 photos/<subfolder>/<file> (Actions 移動後的位置)

    # Step 4: 依 commit_index 排序相簿資料夾 (index 0 = 最新 = 排最上面)
    def sort_key(folder_name):
        info = folder_to_commit.get(folder_name)
        return info["index"] if info else -1  # 未比對到的放最前面

    sorted_folders = sorted(albums_dict.keys(), key=sort_key)

    # Step 5: 生成 commits_list
    commits_list = []
    for folder_name in sorted_folders:
        folder_path = albums_dict[folder_name]
        commit_info = folder_to_commit.get(folder_name)

        # 從資料夾名稱取得顯示標題
        parts = folder_name.split("_", 1)
        section_title = parts[1] if len(parts) == 2 else folder_name

        if commit_info:
            display_date = commit_info["date"]
            display_hash = commit_info["commit_hash"]
            display_short = commit_info["short_hash"]
        else:
            mtime = os.path.getmtime(folder_path)
            display_date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            display_hash = folder_name
            display_short = folder_name[:8]

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
                "commit_hash": display_hash,
                "short_hash": display_short,
                "author": "Contributor",
                "date": display_date,
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

