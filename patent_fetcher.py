import json
import logging
import re
from argparse import ArgumentParser
from collections.abc import Iterator
from typing import Any, TypeAlias, cast

from bs4 import BeautifulSoup, Tag
from rich import print
from rich.logging import RichHandler
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

logger = logging.getLogger(__name__)

Field: TypeAlias = tuple[str, Any]
FieldIterator: TypeAlias = Iterator[Field]


def fetch_html(url: str) -> str:
    options = Options()
    options.add_argument("headless")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = webdriver.Chrome(options=options)
    driver.get(f"view-source:{url}")
    request_id = ""
    for entry in driver.get_log("performance"):  # type: ignore
        message = json.loads(entry["message"])["message"]
        if message["method"] == "Network.loadingFinished":
            request_id = message["params"]["requestId"]
            break

    if not request_id:
        raise RuntimeError(
            "Could not find 'Network.loadingFinished' message in browser logs."
        )
    # Documentation for getResponseBody command:
    # https://chromedevtools.github.io/devtools-protocol/tot/Network/#method-getResponseBody
    response = driver.execute_cdp_cmd(
        "Network.getResponseBody", {"requestId": request_id}
    )
    if response["base64Encoded"]:
        # We raise an error because the documentation doesn't specify what form
        # of base64 is used, and we haven't encountered this situation yet.
        raise NotImplementedError("Encountered base64-encoded content.")
    return cast(str, response["body"])


def parse(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, features="html.parser")
    root = soup.html
    assert root

    data = dict[str, Any]()
    data.update(parse_head(root))
    data.update(parse_body(root))
    return data


def parse_head(root: Tag) -> FieldIterator:
    head = root.head
    assert head

    def meta_tag(name: str) -> Tag:
        return cast(Tag, head.find("meta", attrs={"name": name}))

    def meta_content(name: str) -> str:
        return cast(str, meta_tag(name)["content"])

    # These fields can just be copied over in a straightforward way without extra processing.
    for name in (
        "DC.title",
        "DC.description",
        "citation_patent_application_number",
        "citation_pdf_url",
        "citation_patent_publication_number",
    ):
        yield name.removeprefix("DC."), meta_content(name)

    dates = list[dict[str, Any]]()
    for meta in head.find_all("meta", attrs={"name": "DC.date"}):
        dates.append(dict(value=meta.get("content"), type=meta.get("scheme")))
    yield "dates", dates

    contributors = list[dict[str, Any]]()
    for meta in head.find_all("meta", attrs={"name": "DC.contributor"}):
        contributors.append(dict(value=meta.get("content"), type=meta.get("scheme")))
    yield "contributors", contributors


Node: TypeAlias = dict[str, Any]


def parse_body(root: Tag) -> FieldIterator:
    body = root.body
    assert body

    # yield "publicationNumber", dict(parse_publication_number(body))
    yield "", []
    for dt in body.find_all("dt"):
        assert isinstance(dt, Tag)
        yield parse_dt_tag(dt)


def parse_dt_tag(dt: Tag) -> Field:
    node: Node = {}
    for sibling in dt.find_next_siblings():
        assert isinstance(sibling, Tag)
        if sibling.name == "dt":
            break
        parse_property_tree(sibling, node)

    return parse_dt_label(dt), node


def parse_dt_label(dt: Tag) -> str:
    raw = dt.string
    assert isinstance(raw, str)
    raw = raw.strip()

    parts = list[str]()
    for i, part in enumerate(raw.split()):
        if not part[0].isalnum():
            break
        if i == 0:
            parts.append(part.lower())
        else:
            parts.append(part.capitalize())
    return "".join(parts)


def find_dt_tag(root: Tag, contents: str) -> Tag:
    dt = root.find("dt", string=re.compile(contents))
    assert isinstance(dt, Tag)
    return dt


def parse_property_tree(tag: Tag, current_node: Node) -> None:
    name = tag.get("itemprop")
    if not name:
        # This tag itself is not a property, but its descendants might be
        for child in tag.children:
            if not isinstance(child, Tag):
                continue
            parse_property_tree(child, current_node)
        return
    assert isinstance(name, str)

    if tag.has_attr("itemscope"):
        logging.debug(f"Skipping nested tag: {tag.name}")
        return

    value: str
    if content := tag.get("content"):
        assert isinstance(content, str)
        value = content
    else:
        text = tag.string
        assert isinstance(text, str)
        value = text.strip()

    if tag.has_attr("repeat"):
        if name not in current_node:
            current_node[name] = []
        current_node[name].append(value)
    else:
        current_node[name] = value


# def parse_publication_number(body: Tag) -> FieldIterator:
#     publication_number = find_dt_tag(body, "Publication number")

#     # Parse all of the publication number values
#     values = list[str]()
#     for span in publication_number.find_next_siblings("span"):
#         assert isinstance(span, Tag)
#         if value := cast(str, span.string).strip():
#             values.append(value)
#     yield "values", values


def main() -> None:
    logging.basicConfig(
        level="NOTSET",
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )

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

    print(parse(fetch_html(url)))

    # with err_console.pager(styles=True):
    #     print
    #     err_console.print(fetch_html(url))


if __name__ == "__main__":
    pass
