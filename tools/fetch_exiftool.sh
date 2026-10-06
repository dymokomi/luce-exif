#!/bin/sh
# Fetch ExifTool (Phil Harvey's, Perl) into build/exiftool for tests/run.py's sample
# comparison. CPAN keeps every release; exiftool.org only the newest.
set -eu
cd "$(dirname "$0")/.."
version=${1:-13.59}
mkdir -p build
curl -fsSL -o build/exiftool.tar.gz "https://cpan.metacpan.org/authors/id/E/EX/EXIFTOOL/Image-ExifTool-$version.tar.gz"
rm -rf build/exiftool
tar xzf build/exiftool.tar.gz -C build
mv "build/Image-ExifTool-$version" build/exiftool
rm build/exiftool.tar.gz
build/exiftool/exiftool -ver
