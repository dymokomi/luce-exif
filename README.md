# luce-exif

Photo metadata for Luce and Luce Base. It reads what a photo library shows and sorts
by: the camera and lens, when the picture was taken, how it was exposed, where it was
taken, the orientation and size, and the rating and color label an editor stored in
XMP. Fujifilm files also report their film simulation. It is written in pure Luce
Base with no platform libraries.

```luce
from luce_exif import exif
from luce_std import files

let m = exif.read(files.read(path))     # a Luce value; its texts are its own
print(f"{m.make} {m.model}, {m.lens}: {m.shutter} f/{m.f_number} ISO {m.iso}")
print(f"taken {m.captured}{m.offset}, rated {m.rating}")
```

From Base, `read` returns an `interop.Owned[Metadata]`. Read `.value`, then call
`release()` when you are done with it.

## API (module `luce_exif.exif`)

`read(data: const u8[]) -> interop.Owned[Metadata]!`: the metadata of the file
`data`. It fails with `exif.unrecognized` when the bytes are not a supported
container, and with `exif.truncated` when the file ends before its first metadata
directory. Anything damaged after that point is skipped, and the affected fields
keep their zero values. Every offset is checked, so no input can make it trap
(`tests/fuzz.py`).

`Metadata`. Texts are `""` and numbers `0` when the file does not say:

| field | meaning |
| --- | --- |
| `format` | `"DNG"`, `"TIFF"`, `"NEF"`, `"ARW"`, `"CR2"`, `"CR3"`, `"ORF"`, `"RW2"`, `"PEF"`, `"RAF"`, `"JPEG"`, `"HEIF"`, `"AVIF"`, `"PNG"` |
| `make`, `model` | as the camera writes them, trimmed |
| `lens` | LensModel; otherwise built from the lens's range (DNG LensInfo, EXIF LensSpecification): `"35mm f/1.4"`, `"18-55mm f/2.8-4"` |
| `serial`, `software` | BodySerialNumber (or DNG CameraSerialNumber), Software |
| `captured` | `"YYYY-MM-DDTHH:MM:SS"`, local time, from DateTimeOriginal, else DateTimeDigitized, else DateTime |
| `subseconds`, `offset` | SubSecTimeOriginal digits; OffsetTimeOriginal `"+02:00"` (or OffsetTime) |
| `captured_unix` | seconds since 1970 UTC when the offset is known, otherwise the local time read as UTC; 0 without a date |
| `exposure_time`, `shutter` | seconds, and `"1/250"`, `"0.3s"`, `"30s"` |
| `f_number`, `iso`, `exposure_bias`, `focal_length`, `focal_length_35` | as EXIF states them; APEX values stand in for a missing exposure time or f-number |
| `flash` | whether the flash fired |
| `metering`, `exposure_program` | the EXIF codes (`5` multi-segment, `3` aperture priority, ...) |
| `orientation` | 1–8, defaulting to 1 |
| `width`, `height` | the main image's size: a DNG's default crop, a RAF's cropped raw size, a JPEG's frame, otherwise the largest full-resolution directory or PixelX/YDimension |
| `has_gps`, `latitude`, `longitude`, `altitude` | signed degrees and metres; a GPS directory without a fix (void status, no hemisphere, 0/0) does not count |
| `rating`, `label` | XMP `xmp:Rating` (−1 rejected, 0–5) and `xmp:Label` (also IFD0 Rating) |
| `film_simulation` | Fujifilm's menu name: `"Classic Chrome"`, `"Acros+R Filter"`, `"Provia/Standard"`, ... |

## Containers

| container | where the metadata is |
| --- | --- |
| TIFF and TIFF raws (DNG, NEF, ARW, CR2, PEF, ORF, RW2, TIFF) | the TIFF stream from byte 0; IFD0, its chain and SubIFDs; the EXIF and GPS directories; RW2's embedded JpgFromRaw |
| JPEG | the APP1 `Exif` segment and the APP1 XMP packet; the frame header for the size |
| Fujifilm RAF | the embedded JPEG's EXIF and maker note; the RAF header's model and the RAF directory's raw size |
| Canon CR3 | Canon's uuid box in `moov`: CMT1 (IFD0), CMT2 (EXIF), CMT4 (GPS); the XMP uuid box |
| HEIF / HEIC / AVIF | the `Exif` item and an `application/rdf+xml` mime item, located by `meta/iinf` and `meta/iloc` (construction method 0, first extent) |
| PNG | the `eXIf` chunk and the `XML:com.adobe.xmp` iTXt chunk (uncompressed) |

Not read yet:
- maker notes other than Fujifilm's, so no lens name from Canon, Nikon or Sony maker
  notes when the EXIF LensModel is missing;
- XMP that writes the `xmp` namespace under another prefix, or compressed PNG iTXt;
- HEIF items split over several extents or stored in `idat`;
- Sigma X3F, Canon CRW and other non-TIFF legacy raws.

## Tests

```sh
luc test                     # module tests and the test programs in tests/<name>/
tools/fetch_exiftool.sh      # optional: ExifTool into build/, for the sample comparison
```

The module's own tests cover hand-built TIFF and JPEG files, every truncation and
byte flip of a TIFF, and the date, shutter and lens texts. `tests/dump` dumps
`tests/fixtures` (a JPEG, a PNG and a HEIC made by `tools/make_fixtures.py`), and
luc test holds its output to `tests/dump/expected`. `tests/luce_read` is a Luce
program that reads a fixture. `tests/exiftool` checks every one of luce-raw's camera
samples against ExifTool, and is skipped when ExifTool or the samples are not
there: make, model, lens, serial, date, offset, subseconds,
exposure time, f-number, ISO, focal lengths, orientation, GPS, rating and film
simulation. That covers 32 samples: Leica M240 DNG, five Fujifilm RAFs (X-Trans
and Bayer, GFX), Canon CR2/CR3, Nikon, Sony, Olympus, Panasonic, Pentax, and
iPhone/Pixel DNGs. `tests/fuzz.py DUMP` mutates their metadata heads and requires
that nothing traps.

Licensed MIT or Apache-2.0, at your option.
