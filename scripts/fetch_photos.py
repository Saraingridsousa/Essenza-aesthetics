"""Retrieve two credited Pexels reference images; generate optimized WebP."""
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
from PIL import Image, ImageOps

ROOT=Path(__file__).resolve().parents[1]
SOURCES={
    "room.webp":"https://images.pexels.com/photos/7598366/pexels-photo-7598366.jpeg?auto=compress&w=1200",
    "towels.webp":"https://images.pexels.com/photos/29962514/pexels-photo-29962514.jpeg?auto=compress&w=1200",
}
def main():
    results={}
    for name,url in SOURCES.items():
        with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=25) as response:
            if not response.headers.get_content_type().startswith("image/"):
                raise ValueError("Expected image")
            data=response.read(8*1024*1024+1)
            if len(data)>8*1024*1024:
                raise ValueError("Image too large")
        with Image.open(BytesIO(data)) as original:
            img=ImageOps.exif_transpose(original).convert("RGB")
            if min(img.size)<350:
                raise ValueError("Insufficient resolution")
            img.thumbnail((1200,1200))
            output=BytesIO()
            img.save(output,format="WEBP",quality=82,method=6)
            results[name]=output.getvalue()
    folder=ROOT/"assets"/"photos"
    folder.mkdir(parents=True,exist_ok=True)
    for name,data in results.items():
        (folder/name).write_bytes(data)
        print(name,len(data))

if __name__=="__main__":
    main()
