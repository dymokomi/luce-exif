#!/usr/bin/env python3
"""luce-exif's gate.

1. The module's own tests (hand-built TIFF and JPEG files, damage), native and C.
2. tests/dump.lucb on tests/fixtures (JPEG, PNG, HEIC) prints tests/fixtures/expected.txt
   exactly, native and C.
3. tests/luce_read.luc: the Metadata crosses into a Luce program.
4. When ExifTool and camera samples are present (luce-raw's build/samples, or --samples):
   every sample's fields agree with ExifTool's. ExifTool is looked for in build/exiftool
   (tools/fetch_exiftool.sh) and on the PATH. CI has neither and skips this part.
"""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--base", type=Path, default=Path(shutil.which("luce-base") or ROOT.parent / "luce-base/build/luce-base"))
parser.add_argument("--luce", type=Path, default=Path(shutil.which("luce") or ROOT.parent / "luce/build/luce"))
parser.add_argument("--samples", type=Path, default=ROOT.parent / "luce-raw/build/samples")
parser.add_argument("--write-expected", action="store_true", help="rewrite tests/fixtures/expected.txt")
args = parser.parse_args()
base = args.base.resolve()
env = dict(os.environ, LUCE_BASE=str(base))
MODES = [["--native"], ["--backend=c"]]


def run(command, **options):
    return subprocess.run([str(part) for part in command], check=True, env=env, cwd=ROOT, timeout=900, **options)


def parse_dump(text):
    """The dump's records: one dict per file, in order."""
    records, current = [], {}
    for line in text.splitlines():
        if not line:
            records.append(current)
            current = {}
            continue
        key, _, value = line.partition("\t")
        current[key] = value
    return records


for flags in MODES:
    run([base, "test", ROOT / "src/exif", *flags])

fixtures = [FIXTURES / name for name in ["camera.jpg", "camera.png", "camera.heic"]]
with tempfile.TemporaryDirectory() as tmp:
    dumps = {}
    for flags in MODES:
        tool = Path(tmp) / ("dump" + flags[0].replace("-", "_").replace("=", "_"))
        run([base, "build", ROOT / "tests/dump.lucb", *flags, "-o", tool])
        dumps[flags[0]] = tool
    expected_path = FIXTURES / "expected.txt"
    for flag, tool in dumps.items():
        found = run([tool, *[f.relative_to(ROOT) for f in fixtures]], capture_output=True, text=True).stdout
        if args.write_expected:
            expected_path.write_text(found)
        if found != expected_path.read_text():
            sys.exit(f"FAIL fixtures {flag}: the dump differs from tests/fixtures/expected.txt")
    run([args.luce, "test", ROOT / "tests/luce_read.luc", "--build"])

    exiftool = ROOT / "build/exiftool/exiftool"
    exiftool = str(exiftool) if exiftool.exists() else shutil.which("exiftool")
    samples = sorted(args.samples.glob("*")) if args.samples.is_dir() else []
    if not exiftool or not samples:
        print("SKIP camera samples: ExifTool or the samples are missing")
    else:
        compared = 0
        found = parse_dump(run([dumps["--native"], *samples], capture_output=True, text=True).stdout)
        tags = ["-IFD0:Make", "-IFD0:Model", "-ExifIFD:LensModel", "-ExifIFD:SerialNumber", "-DateTimeOriginal",
                "-OffsetTimeOriginal", "-SubSecTimeOriginal", "-ExifIFD:ExposureTime", "-ExifIFD:FNumber", "-ExifIFD:ISO",
                "-ExifIFD:FocalLength", "-ExifIFD:FocalLengthIn35mmFormat", "-IFD0:Orientation", "-GPSLatitude",
                "-GPSLongitude", "-GPSLatitudeRef", "-XMP:Rating", "-FujiFilm:FilmMode", "-FujiFilm:Saturation"]
        oracle = json.loads(subprocess.run([exiftool, "-j", "-n", "-G0", "-a", *tags, *map(str, samples)],
                                           check=True, capture_output=True, text=True).stdout)
        films = {0x000: "Provia/Standard", 0x120: "Astia/Soft", 0x200: "Velvia/Vivid", 0x400: "Velvia/Vivid",
                 0x500: "Pro Neg. Std", 0x501: "Pro Neg. Hi", 0x600: "Classic Chrome", 0x700: "Eterna/Cinema",
                 0x800: "Classic Neg.", 0x900: "Eterna Bleach Bypass", 0xa00: "Nostalgic Neg.", 0xb00: "Reala Ace"}
        mono = {0x300: "Monochrome", 0x301: "Monochrome+R Filter", 0x302: "Monochrome+Ye Filter",
                0x303: "Monochrome+G Filter", 0x310: "Sepia", 0x500: "Acros", 0x501: "Acros+R Filter",
                0x502: "Acros+Ye Filter", 0x503: "Acros+G Filter"}
        failures = []
        for sample, ours, theirs in zip(samples, found, oracle):
            def pick(*names):
                for name in names:
                    for key, value in theirs.items():
                        if key.split(":")[-1] == name:
                            return value
                return None

            def same(field, expected, close=False):
                nonlocal_count[0] += 1
                value = ours.get(field, "")
                if expected is None:
                    return
                if close:
                    if abs(float(value or 0) - float(expected)) > 1e-6 * max(1.0, abs(float(expected))):
                        failures.append(f"{sample.name}: {field} {value!r}, ExifTool {expected!r}")
                elif str(value) != str(expected).strip():
                    failures.append(f"{sample.name}: {field} {value!r}, ExifTool {expected!r}")

            nonlocal_count = [0]
            if "error" in ours:
                failures.append(f"{sample.name}: {ours['error']}")
                continue
            same("make", pick("Make"))
            same("model", pick("Model"))
            same("lens", pick("LensModel"))
            same("serial", pick("SerialNumber"))
            original = pick("DateTimeOriginal")
            if original:
                same("captured", original[:10].replace(":", "-") + "T" + original[11:19])
            same("offset", pick("OffsetTimeOriginal"))
            subseconds = pick("SubSecTimeOriginal")
            same("subseconds", None if subseconds is None else str(subseconds))
            same("exposure_time", pick("ExposureTime"), close=True)
            same("f_number", pick("FNumber"), close=True)
            same("iso", pick("ISO"))
            same("focal_length", pick("FocalLength"), close=True)
            same("focal_length_35", pick("FocalLengthIn35mmFormat"))
            same("orientation", pick("Orientation") or 1)
            if pick("GPSLatitudeRef") in ("N", "S") and pick("GPSLatitude"):
                same("latitude", pick("GPSLatitude"), close=True)
                same("longitude", pick("GPSLongitude"), close=True)
            same("rating", pick("Rating"))
            saturation, mode = pick("Saturation"), pick("FilmMode")
            if saturation in mono:
                same("film_simulation", mono[saturation])
            elif mode is not None:
                same("film_simulation", films.get(mode, ""))
            compared += nonlocal_count[0]
        if failures:
            sys.exit("FAIL camera samples:\n  " + "\n  ".join(failures))
        print(f"PASS {len(samples)} camera samples, {compared} fields, agree with ExifTool")
print("PASS luce-exif: module tests, fixtures and the Luce crossing, native and C")
