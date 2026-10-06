#!/usr/bin/env python3
"""Mutation fuzzing (local, not in CI): flip and truncate the metadata-bearing heads of
the fixtures and camera samples and require the dump driver never to trap.
Usage: tests/fuzz.py DUMP_BINARY [ROUNDS]"""
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
dump, rounds = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 300
sources = sorted((ROOT / "tests/fixtures").glob("camera.*")) + sorted((ROOT.parent / "luce-raw/build/samples").glob("*"))
random.seed(7)
with tempfile.TemporaryDirectory() as tmp:
    for source in sources:
        head = bytearray(source.read_bytes()[:262144])
        for round_ in range(rounds // 10 if source.stat().st_size > 1e6 else rounds):
            data = bytearray(head)
            for _ in range(random.randint(1, 8)):
                at = random.randrange(min(len(data), 4096 if random.random() < 0.7 else len(data)))
                data[at] = random.randrange(256)
            if random.random() < 0.2:
                data = data[:random.randrange(len(data))]
            path = Path(tmp) / "case"
            path.write_bytes(data)
            done = subprocess.run([dump, str(path)], capture_output=True, text=True, timeout=30)
            if "trap" in done.stderr or done.returncode not in (0, 1):
                (ROOT / "build/crash.bin").write_bytes(data)
                sys.exit(f"FAIL {source.name} round {round_}: {done.stderr.strip()} (build/crash.bin)")
print(f"PASS fuzz: {len(sources)} sources, no traps")
