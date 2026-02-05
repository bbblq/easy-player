from PIL import Image
import os

def create_icon():
    source = 'assets/banner.png'
    dest = 'assets/icon.ico'
    
    if not os.path.exists(source):
        print(f"Source image {source} not found.")
        return

    print("Generating icon...")
    try:
        img = Image.open(source)
        # Crop to center square
        width, height = img.size
        new_edge = min(width, height)
        left = (width - new_edge) / 2
        top = (height - new_edge) / 2
        right = (width + new_edge) / 2
        bottom = (height + new_edge) / 2
        
        img = img.crop((left, top, right, bottom))
        img.save(dest, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        print(f"Icon saved to {dest}")
    except Exception as e:
        print(f"Failed to create icon: {e}")

if __name__ == "__main__":
    create_icon()
