#!/usr/bin/env python3
"""Convert Python-tuple text lines into CSV.

Usage:
    python3 program.py input.txt output.csv
    python3 program.py -i input.txt -o output.csv

Input (one tuple per line):
    ('a', '1ª', 92)

Output CSV (no header):
    a,1,92

The second column is normalized by stripping ordinal markers (ª / º).
Standard library only — no external dependencies.
"""
import argparse
import ast
import csv
import sys
from pathlib import Path

# Characters stripped from the ordinal column (Portuguese ordinals)
ORDINAL_STRIP = str.maketrans("", "", "ªº")


def parse_line(line: str):
    """Parse one input line into a list of string fields, or None to skip."""
    line = line.strip().rstrip(",")
    if not line:
        return None
    try:
        value = ast.literal_eval(line)
    except (ValueError, SyntaxError):
        # Fallback: tolerate already-plain CSV-ish lines
        parts = [p.strip().strip("'\"") for p in line.split(",")]
        return parts if len(parts) >= 2 else None
    if isinstance(value, (tuple, list)):
        return [str(v) for v in value]
    return [str(value)]


def convert(input_path: Path, output_path: Path, encoding: str) -> int:
    """Read tuples from input_path, write CSV to output_path. Returns row count."""
    text = input_path.read_text(encoding="utf-8")
    rows = []
    for raw in text.splitlines():
        parsed = parse_line(raw)
        if not parsed:
            continue
        if len(parsed) >= 2:
            # '1ª' -> '1'
            parsed[1] = parsed[1].translate(ORDINAL_STRIP).strip()
        rows.append(parsed)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding=encoding) as f:
        csv.writer(f).writerows(rows)
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert tuple lines like ('a', '1ª', 92) into CSV rows like a,1,92."
    )
    parser.add_argument("input", nargs="?", help="input file with one tuple per line")
    parser.add_argument("output", nargs="?", help="output CSV file")
    parser.add_argument("-i", "--input-file", dest="in_flag",
                        help="input file (flag form)")
    parser.add_argument("-o", "--output-file", dest="out_flag",
                        help="output file (flag form)")
    parser.add_argument("--encoding", default="utf-8-sig",
                        help="output encoding (default: utf-8-sig, Excel-friendly)")
    args = parser.parse_args()

    input_file = args.input or args.in_flag
    output_file = args.output or args.out_flag

    if not input_file or not output_file:
        parser.error("both INPUT and OUTPUT are required "
                     "(positional or via -i / -o)")

    input_path = Path(input_file)
    if not input_path.exists():
        print(f"error: input file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        n_rows = convert(input_path, Path(output_file), args.encoding)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"OK: wrote {n_rows} rows to {output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
