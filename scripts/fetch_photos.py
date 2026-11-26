"""Retrieve credited Pexels reference photos and generate optimized WebP/OG."""
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
from PIL import Image, ImageOps, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
SOURCES={
    "room.webp":"https://images.pexels.com/photos/7598366/pexels-photo-7598366.jpeg?auto=compress&w=1200",
    "towels.webp":"https://images.pexels.com/photos/29962514/pexels-photo-29962514.jpeg?auto=compress&w=1200",
}
SOURCES.update({
    "cleansing.webp":"https://images.pexels.com/photos/3985332/pexels-photo-3985332.jpeg?auto=compress&w=1200",
    "facial-massage.webp":"https://images.pexels.com/photos/5240820/pexels-photo-5240820.jpeg?auto=compress&w=1200",
    "hydration.webp":"https://images.pexels.com/photos/5069458/pexels-photo-5069458.jpeg?auto=compress&w=1200",
    "drainage.webp":"https://images.pexels.com/photos/5240640/pexels-photo-5240640.jpeg?auto=compress&w=1200",
    "bodycare.webp":"https://images.pexels.com/photos/6976813/pexels-photo-6976813.jpeg?auto=compress&w=1200",
    "relaxing.webp":"https://images.pexels.com/photos/4599392/pexels-photo-4599392.jpeg?auto=compress&w=1200",
    "about-space.webp":"https://images.pexels.com/photos/6899538/pexels-photo-6899538.jpeg?auto=compress&w=1200",
    "skincare.webp":"https://images.pexels.com/photos/7691167/pexels-photo-7691167.jpeg?auto=compress&w=1200",
    "reception.webp":"https://images.pexels.com/photos/16571736/pexels-photo-16571736.jpeg?auto=compress&w=1200",
    "team-care.webp":"https://images.pexels.com/photos/5659049/pexels-photo-5659049.jpeg?auto=compress&w=1200",
    "experience.webp":"https://images.pexels.com/photos/6899553/pexels-photo-6899553.jpeg?auto=compress&w=1200",
    "cta-room.webp":"https://images.pexels.com/photos/6899549/pexels-photo-6899549.jpeg?auto=compress&w=1200",
})

def make_cover(folder):
    social=ROOT/"assets"/"social"
    social.mkdir(parents=True,exist_ok=True)
    canvas=Image.new("RGB",(1200,630),"#f4efe6")
    with Image.open(folder/"room.webp") as photo:
        canvas.paste(ImageOps.fit(photo.convert("RGB"),(530,630)),(670,0))
    draw=ImageDraw.Draw(canvas)
    try:
        large=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",82)
        small=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",22)
        medium=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",30)
    except OSError:
        large=ImageFont.load_default(size=82)
        small=ImageFont.load_default(size=22)
        medium=ImageFont.load_default(size=30)
    draw.text((65,170),"essenza",font=large,fill="#374c3f")
    draw.text((70,280),"ESTÉTICA AVANÇADA",font=small,fill="#374c3f")
    draw.text((70,340),"A beleza começa",font=medium,fill="#374c3f")
    draw.text((70,386),"na sua essência.",font=medium,fill="#374c3f")
    draw.text((70,550),"PROJETO CONCEITUAL • PORTFÓLIO",font=small,fill="#6d6659")
    canvas.save(social/"og-cover.jpg",quality=85,optimize=True)

def main():
    results={}
    folder=ROOT/"assets"/"photos"
    folder.mkdir(parents=True,exist_ok=True)
    for name,url in SOURCES.items():
        if (folder/name).is_file():
            continue
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
    make_cover(folder)

if __name__=="__main__":
    main()
