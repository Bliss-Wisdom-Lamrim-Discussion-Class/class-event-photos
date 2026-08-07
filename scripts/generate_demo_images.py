import os
from PIL import Image, ImageDraw, ImageFont

photos_dir = "photos"
thumbnails_dir = "thumbnails"

os.makedirs(photos_dir, exist_ok=True)
os.makedirs(thumbnails_dir, exist_ok=True)

demo_photos = [
    ("calla_lily.jpg", "海芋花海特寫", (76, 175, 80), (232, 245, 233)),
    ("yangmingshan_sunset.jpg", "擎天崗日落餘暉", (255, 87, 34), (255, 235, 238)),
    ("mountain_fog.jpg", "山間晨霧景致", (96, 125, 139), (236, 239, 241)),
    ("old_street.jpg", "大稻埕歷史街景", (141, 110, 99), (239, 235, 233)),
    ("drip_coffee.jpg", "手沖單品咖啡", (93, 64, 55), (239, 235, 233)),
    ("taipei101_night.jpg", "台北101與城市夜芒", (103, 58, 183), (237, 231, 246)),
    ("neon_lights.jpg", "街頭霓虹光影流動", (233, 30, 99), (252, 228, 236))
]

for filename, text, main_color, bg_color in demo_photos:
    photo_path = os.path.join(photos_dir, filename)
    thumb_path = os.path.join(thumbnails_dir, filename)
    
    # 建立 1200x800 高清範例照片
    img = Image.new("RGB", (1200, 800), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # 畫出美觀樣式塊
    draw.rectangle([50, 50, 1150, 750], outline=main_color, width=8)
    draw.rectangle([80, 80, 1120, 720], fill=main_color)
    
    # 儲存原圖
    img.save(photo_path, quality=90)
    
    # 建立 400x267 縮圖
    img_thumb = img.resize((400, 267), Image.Resampling.LANCZOS)
    img_thumb.save(thumb_path, quality=85)
    print(f"Generated photo: {photo_path} and thumbnail: {thumb_path}")

print("Demo images generation complete!")
