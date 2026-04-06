from PIL import Image
import numpy as np
from collections import deque

def remove_background_smart(input_path, output_path, tolerance=30):
    print(f"Processing: {input_path}")
    
    try:
        img = Image.open(input_path).convert("RGBA")
        width, height = img.size
        data = np.array(img) # (H, W, 4)

        # -------------------------------------------------------------
        # 1. Gemini 로고 (오른쪽 하단) 강제 삭제 [범위 대폭 확대!]
        # 아까 50px가 부족했으니 이번엔 150px로 넉넉하게 잡습니다.
        # -------------------------------------------------------------
        # 로고가 1024x1024 정도라면 150px는 오른쪽 구석에 충분합니다.
        data[height-150:height, width-150:width, 3] = 0

        # 2. Flood Fill로 배경 투명화 (원래 로직)
        visited = np.zeros((height, width), dtype=bool)
        queue = deque()
        
        for x in range(width):
            queue.append((0, x))
            queue.append((height-1, x))
        for y in range(height):
            queue.append((y, 0))
            queue.append((y, width-1))

        bg_sample = data[0, 0, :3]
        
        while queue:
            y, x = queue.popleft()
            if visited[y, x]: continue
            visited[y, x] = True
            
            current_color = data[y, x, :3]
            diff = np.mean(np.abs(current_color - bg_sample))
            brightness = np.mean(current_color)

            if diff < tolerance or brightness < 40:
                data[y, x, 3] = 0 
                for dy, dx in [(-1,0), (1,0), (0,-1), (0,1)]:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < height and 0 <= nx < width and not visited[ny, nx]:
                        queue.append((ny, nx))
        
        new_img = Image.fromarray(data)
        new_img.save(output_path)
        print(f"Restored previous version (with larger corner remove) to: {output_path}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    remove_background_smart(
        "d:/Project/05_regulation_news/web/public/logo_correct.jpg",
        "d:/Project/05_regulation_news/web/public/logo_perfect.png",
        tolerance=40 
    )
