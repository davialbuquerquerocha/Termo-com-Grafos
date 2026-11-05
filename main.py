import argparse
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Launcher central dos algoritmos do Termo."
    )
    commands = parser.add_subparsers(dest="algorithm")
    commands.add_parser(
        "partition",
        add_help=False,
        help="encaminhar argumentos para a avaliação do algoritmo de partição",
    )
    commands.add_parser(
        "entropy",
        add_help=False,
        help="encaminhar argumentos para a CLI de algorithm/entropy",
    )
    commands.add_parser(
        "inclusive",
        add_help=False,
        help="encaminhar argumentos para a avaliação do algoritmo inclusivo",
    )

    args, forwarded_args = parser.parse_known_args(argv)
    if args.algorithm == "entropy":
        from algorithm.entropy.algorithm import main as algorithm_main
    elif args.algorithm == "inclusive":
        from algorithm.inclusive.evaluation import main as algorithm_main
    elif args.algorithm in (None, "partition"):
        from algorithm.partition.evaluation import main as algorithm_main

        if args.algorithm == "partition" and forwarded_args[:1] == ["evaluate"]:
            forwarded_args = forwarded_args[1:]
    else:
        parser.error(f"algoritmo não reconhecido: {args.algorithm}")
        return

    algorithm_main(forwarded_args)


if __name__ == "__main__":
    main()
