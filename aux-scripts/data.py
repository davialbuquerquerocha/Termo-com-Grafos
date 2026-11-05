from pathlib import Path


dataset = (
    Path(__file__).resolve().parent.parent
    / "dataset"
    / "statistics"
    / "letters_position.txt"
)
arquivo = dataset.open(encoding="utf-8")
for line in arquivo:
    print(line)

arquivo.close()
"[a, b, c]"