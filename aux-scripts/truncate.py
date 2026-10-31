#!/usr/bin/env python3
"""Write N randomly selected words from the accepted-words dataset."""

import random
import sys
from pathlib import Path

SEED = 7

def main():
	if len(sys.argv) != 3:
		raise SystemExit(f"Usage: {Path(sys.argv[0]).name} <N> <output.txt>")

	try:
		count = int(sys.argv[1])
	except ValueError:
		raise SystemExit("N must be a non-negative integer")
	if count < 0:
		raise SystemExit("N must be a non-negative integer")

	dataset = Path(__file__).resolve().parent.parent / "dataset" / "termo_palavras_aceitas.txt"
	words = dataset.read_text(encoding="utf-8").split()
	if count > len(words):
		raise SystemExit(f"Requested {count} words, but the dataset contains only {len(words)}")

	selected = random.Random(SEED).sample(words, count)
	Path(sys.argv[2]).write_text("\n".join(selected) + ("\n" if selected else ""), encoding="utf-8")


if __name__ == "__main__":
	main()
