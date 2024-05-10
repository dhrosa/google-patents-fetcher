import json
import logging
from argparse import ArgumentParser

import rich
from bs4 import Tag
from rich import traceback
from rich.logging import RichHandler

from .scrape import scrape


def main() -> None:
    rich.reconfigure(stderr=True)
    log_handler = RichHandler(rich_tracebacks=True)
    traceback.install(show_locals=True)
    # Monkeypatch BS4 Tag to not take huge amounts of screen space in
    # rich tracebacks.
    setattr(Tag, "__repr__", lambda s: str(type(s)))

    file_handler = logging.FileHandler("log.txt", mode="w")
    logging.basicConfig(
        level="NOTSET",
        format="%(message)s",
        datefmt="[%X]",
        handlers=[log_handler, file_handler],
    )
    # for handler in logging.getLogger().handlers:
    #     handler.addFilter(logging.Filter("patent"))

    parser = ArgumentParser(
        description="Fetch JSON-encoded information about a patent."
    )
    parser.add_argument(
        "id",
        type=str,
        help=("The Google Patent ID to fetch data for. "),
    )
    args = parser.parse_args()

    scraped = scrape(args.id)
    print(json.dumps(scraped, indent=2))


if __name__ == "__main__":
    main()
