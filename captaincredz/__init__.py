import argparse
from .lib.engine import Engine
from importlib.util import find_spec

RICH_INSTALLED = find_spec("rich") is not None
if RICH_INSTALLED:
    from rich.progress import Progress


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        required=True,
        help="Configure CaptainCredz using config file config.json",
    )
    parser.add_argument(
        "-w",
        "--weekday_warrior",
        type=str,
        default=None,
        required=False,
        help="Weekday Warrior config file. Only active when specified",
    )

    args = parser.parse_args()
    e = Engine(args)
    if RICH_INSTALLED:
        from rich.progress import Progress

        with Progress() as pb:
            e.start(pb)
    else:
        e.start()


if __name__ == "__main__":
    main()
