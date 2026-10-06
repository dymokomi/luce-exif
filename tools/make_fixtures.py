#!/usr/bin/env python3
"""Make tests/fixtures: small JPEG, PNG and HEIC files with EXIF (camera, exposure, dates,
offset, lens, GPS) and an XMP packet carrying a rating and a label. Run once on macOS
(HEIC comes from `sips`); the files are checked in, with their expected dump."""
from pathlib import Path
import subprocess
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests/fixtures"
XMP = (b"http://ns.adobe.com/xap/1.0/\x00"
       b"<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?><x:xmpmeta xmlns:x='adobe:ns:meta/'>"
       b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
       b"<rdf:Description rdf:about='' xmlns:xmp='http://ns.adobe.com/xap/1.0/'>"
       b"<xmp:Rating>3</xmp:Rating><xmp:Label>Green</xmp:Label>"
       b"</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end='w'?>")


def exif():
    image = Image.new("RGB", (64, 48), (90, 140, 200))
    data = image.getexif()
    data[0x010F] = "FUJIFILM"
    data[0x0110] = "X100VI"
    data[0x0112] = 8
    data[0x0131] = "luce-exif fixtures"
    ifd = data.get_ifd(0x8769)
    ifd[0x829A] = 1 / 500
    ifd[0x829D] = 5.6
    ifd[0x8827] = 160
    ifd[0x9003] = "2025:03:09 08:15:02"
    ifd[0x9011] = "-05:00"
    ifd[0x9291] = "50"
    ifd[0x9204] = -0.7
    ifd[0x920A] = 23.0
    ifd[0xA405] = 35
    ifd[0xA434] = "FUJINON 23mm F2"
    gps = data.get_ifd(0x8825)
    gps[1] = "S"
    gps[2] = (33.0, 51.0, 54.0)
    gps[3] = "E"
    gps[4] = (151.0, 12.0, 36.0)
    gps[5] = b"\x00"
    gps[6] = 58.0
    return image, data


def insert_app1(jpeg: bytes, payload: bytes) -> bytes:
    segment = b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload
    return jpeg[:2] + segment + jpeg[2:]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    image, data = exif()
    jpeg = OUT / "camera.jpg"
    image.save(jpeg, exif=data, quality=80)
    jpeg.write_bytes(insert_app1(jpeg.read_bytes(), XMP))
    image.save(OUT / "camera.png", exif=data)
    subprocess.run(["sips", "-s", "format", "heic", str(jpeg), "--out", str(OUT / "camera.heic")], check=True, capture_output=True)


main()
