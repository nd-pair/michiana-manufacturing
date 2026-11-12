#!/usr/bin/env python3
"""Make the Main Building textures from a frontal photograph on Wikimedia Commons.

    python3 scripts/make_landmark_textures.py      # writes site/img/landmark-*.webp

Source: "Golden Dome frontal.jpg" by Eccekevin, 2016, Wikimedia Commons, CC BY-SA 4.0
https://commons.wikimedia.org/wiki/File:Golden_Dome_frontal.jpg
The textures are adaptations of that photograph and are released under the same license
(CC BY-SA 4.0); see site/img/LICENSE-landmark.txt.

What is cut out (coordinates below are in a 1500-pixel-wide version of the photo):
- facade: the central block from the gable apex to the ground. Trees cover its right third, so the
  left third is mirrored onto the right (the facade is symmetric about the entrance); sky is keyed
  out above the roofline, and the drum that rises behind the gable is masked away.
- drum: the south face of the octagonal drum below the dome, mirrored about its axis, sky keyed out.
- bay: one window bay, four stories, for the sides and the wings.
- roof: a strip of the striped slate roof.
Needs Pillow with WebP support.
"""
import io, os, urllib.request
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "site", "img")
SRC = "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2d/Golden_Dome_frontal.jpg/3840px-Golden_Dome_frontal.jpg"
UA = {"User-Agent": "michiana-manufacturing/1.0 (github.com/nd-pair/michiana-manufacturing)"}
AXIS = 745            # the entrance and the dome sit on this vertical axis
APEX = (745, 375)     # gable apex
GABLE_SLOPE = 0.61    # the gable's roof edges fall about 0.61 px per px from the apex

def fetch():
    cache = os.path.join(OUT, ".source-frontal.jpg")
    if os.path.exists(cache):
        return Image.open(cache).convert("RGB")
    api = "https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo&iiprop=url&iiurlwidth=3840&titles=File:Golden%20Dome%20frontal.jpg"
    import json
    with urllib.request.urlopen(urllib.request.Request(api, headers=UA), timeout=60) as r:
        url = list(json.load(r)["query"]["pages"].values())[0]["imageinfo"][0]["thumburl"]
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        data = r.read()
    with open(cache, "wb") as fh:
        fh.write(data)
    return Image.open(io.BytesIO(data)).convert("RGB")

def is_sky(p):
    r, g, b = p[:3]
    return b > 140 and b > r + 60 and b > g + 25

def clear_sky(img, extra=lambda x, y: False):
    """Make transparent the sky that is connected to the top edge (so blue reflections in windows stay),
    plus any pixel for which extra(x, y) is true."""
    px = img.load(); W, H = img.size; seen = bytearray(W * H); stack = [(x, 0) for x in range(W)]
    while stack:
        x, y = stack.pop()
        if x < 0 or y < 0 or x >= W or y >= H or seen[y * W + x]:
            continue
        seen[y * W + x] = 1
        if not is_sky(px[x, y]):
            continue
        px[x, y] = (0, 0, 0, 0)
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    for y in range(H):
        for x in range(W):
            if extra(x, y):
                px[x, y] = (0, 0, 0, 0)

def main():
    im = fetch(); k = im.width / 1500
    box = lambda x0, y0, x1, y1: im.crop(tuple(round(v * k) for v in (x0, y0, x1, y1)))
    os.makedirs(OUT, exist_ok=True)

    # facade: left third, center column, mirrored left third; then alpha above the roofline
    # (the left edge starts at 455 to stay clear of the tree that touches the corner)
    top, bottom, x0 = APEX[1], 858, 455
    left = box(x0, top, 665, bottom); center = box(665, top, 825, bottom); right = ImageOps.mirror(left)
    fac = Image.new("RGBA", (left.width + center.width + right.width, left.height))
    fac.paste(left, (0, 0)); fac.paste(center, (left.width, 0)); fac.paste(right, (left.width + center.width, 0))
    W, H = fac.size
    def behind_gable(x, y):                                   # the drum, above the gable's edges
        X, Y = x0 + x / k, top + y / k
        dx = abs(X - AXIS)
        return dx < 160 and Y < APEX[1] + dx * GABLE_SLOPE
    clear_sky(fac, behind_gable)
    fac = fac.resize((1024, round(1024 * H / W)), Image.LANCZOS)
    fac.save(os.path.join(OUT, "landmark-facade.webp"), quality=86, method=6)

    # drum: the face of the octagonal drum that looks south, mirrored about its axis, sky keyed;
    # the model repeats it once per face. Repeated textures are cut to power-of-two sizes.
    half = box(697, 296, AXIS, 372); drum = Image.new("RGBA", (half.width * 2, half.height))
    drum.paste(half, (0, 0)); drum.paste(ImageOps.mirror(half), (half.width, 0))
    clear_sky(drum)
    drum.resize((128, 128), Image.LANCZOS).save(os.path.join(OUT, "landmark-drum.webp"), quality=86, method=6)

    # one window bay between the tree on the left and the passers-by below, and a strip of slate roof
    box(465, 500, 517, 828).resize((128, 1024), Image.LANCZOS).save(os.path.join(OUT, "landmark-bay.webp"), quality=84, method=6)
    box(602, 437, 682, 462).resize((256, 64), Image.LANCZOS).save(os.path.join(OUT, "landmark-roof.webp"), quality=84, method=6)
    with open(os.path.join(OUT, "LICENSE-landmark.txt"), "w") as fh:
        fh.write("The landmark-*.webp textures are adapted from \"Golden Dome frontal.jpg\" by Eccekevin (2016),\n"
                 "https://commons.wikimedia.org/wiki/File:Golden_Dome_frontal.jpg, licensed CC BY-SA 4.0\n"
                 "(https://creativecommons.org/licenses/by-sa/4.0/). Changes: cropped, the facade's left third mirrored\n"
                 "onto its right third, the drum mirrored about its axis, sky and the drum behind the gable made\n"
                 "transparent, resized. These adaptations are released under CC BY-SA 4.0.\n")
    for f in sorted(os.listdir(OUT)):
        if f.startswith("landmark-"):
            print(f, os.path.getsize(os.path.join(OUT, f)), "bytes", Image.open(os.path.join(OUT, f)).size)

if __name__ == "__main__":
    main()
