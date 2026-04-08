from PIL import Image
import numpy as np

def remove_black_background(input_path, output_path):
    print(f"Processing: {input_path}")
    
    try:
        img = Image.open(input_path).convert("RGBA")
        data = np.array(img)

        # RGB 분리
        r, g, b, a = data.T

        # 검은색 배경 감지 (밝기가 매우 낮은 픽셀)
        # Threshold: RGB 합이 50 이하 (매우 어두운 색)
        brightness = (r.astype(int) + g.astype(int) + b.astype(int))
        
        # 조건: 매우 어두운 픽셀 (배경)
        mask = brightness < 60 
        
        # 어두운 픽셀을 투명하게
        data[..., 3][mask.T] = 0

        # 저장
        new_img = Image.fromarray(data)
        new_img.save(output_path)
        print(f"Saved transparent logo to: {output_path}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    remove_black_background(
        "d:/Project/05_regulation_news/web/public/logo_correct.jpg",
        "d:/Project/05_regulation_news/web/public/logo_final.png"
    )
