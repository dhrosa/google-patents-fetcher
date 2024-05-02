import json
import logging
from argparse import ArgumentParser

import rich
from bs4 import Tag
from rich import traceback
from rich.logging import RichHandler

from .fetch import fetch_html
from .parse import parse_html


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
        "id_or_url",
        type=str,
        help=(
            "The Google Patent ID to fetch data for. "
            "If a URL is specified instead, then we fetch data from that URL "
            "instead of forming the URLs automatically. "
            "This is useful for debugging (e.g. fetching from a local file:// URL)."
        ),
    )

    args = parser.parse_args()

    url: str
    if "/" in args.id_or_url:
        url = args.id_or_url
    else:
        patent_id = args.id_or_url
        url = f"https://patents.google.com/patent/{patent_id}"

    parsed = parse_html(fetch_html(url))
    print(json.dumps(parsed, indent=2))


if __name__ == "__main__":
    main()
