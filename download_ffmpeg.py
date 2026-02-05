import os
import io
import zipfile
import urllib.request
import shutil

def download_ffmpeg():
    # Stable release URL
    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    print(f"Downloading FFmpeg from {url}...\nThis may take a minute depending on your connection.")

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            content = response.read()
    except Exception as e:
        print(f"Download failed: {e}")
        return

    print("Download complete. Extracting binaries...")

    found_ffmpeg = False
    found_ffprobe = False

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            for file in z.namelist():
                # The zip structure usually has a root folder, look for bin/ffmpeg.exe anywhere
                lower_name = file.lower()
                if "bin/ffmpeg.exe" in lower_name:
                    print(f"Extracting {file} -> ffmpeg.exe")
                    with z.open(file) as source, open("ffmpeg.exe", "wb") as target:
                        shutil.copyfileobj(source, target)
                    found_ffmpeg = True
                elif "bin/ffprobe.exe" in lower_name:
                    print(f"Extracting {file} -> ffprobe.exe")
                    with z.open(file) as source, open("ffprobe.exe", "wb") as target:
                        shutil.copyfileobj(source, target)
                    found_ffprobe = True
        
        if found_ffmpeg and found_ffprobe:
            print("Successfully downloaded and extracted ffmpeg.exe and ffprobe.exe")
        else:
            print(f"Warning: Extracted {found_ffmpeg=} {found_ffprobe=}. Check zip structure.")

    except Exception as e:
        print(f"Extraction failed: {e}")

if __name__ == "__main__":
    download_ffmpeg()
