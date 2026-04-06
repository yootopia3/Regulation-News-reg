from PIL import Image
import numpy as np

def remove_checkered_background(input_path, output_path):
    print(f"Processing: {input_path}")
    
    try:
        img = Image.open(input_path).convert("RGBA")
        data = np.array(img)

        # RGB 분리
        r, g, b, a = data.T

        # 체크무늬 특성: 무채색(R, G, B가 거의 비슷함)이고 밝은 색(회색/흰색)
        # Saturation(채도) 기반으로 접근: |R-G| + |G-B| + |B-R| 이 작으면 무채색
        # 밝기는 높아야 함
        
        diff = np.abs(r - g) + np.abs(g - b) + np.abs(b - r)
        brightness = (r.astype(int) + g.astype(int) + b.astype(int)) / 3

        # 조건: 무채색(diff < 20)이면서 밝은 배경(brightness > 200)
        # 로고(파랑/보라)는 채도가 높으므로 diff가 큼.
        
        mask = (diff < 30) & (brightness > 180)
        
        # 해당 픽셀 투명화
        data[..., 3][mask.T] = 0

        # 저장
        new_img = Image.fromarray(data)
        new_img.save(output_path)
        print(f"Saved transparent logo to: {output_path}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # 웹 서버의 public 폴더에 있는 로고 대상
    remove_checkered_background(
        "d:/Project/05_regulation_news/web/public/logo.png",
        "d:/Project/05_regulation_news/web/public/logo_transparent.png"
    )
