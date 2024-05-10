from logging import getLogger

from .fetch import fetch_html
from .parse import Node, parse_html

logger = getLogger(__name__)


def patent_url(patent_id: str, language: str) -> str:
    """language may be empty string to fetch the patent in its original language."""
    return f"https://patents.google.com/patent/{patent_id}/{language}"


def scrape(patent_id: str) -> list[Node]:
    """Scrape information for the given patent ID.

    We produce one element for every language the patent is available in.
    """
    original_url = patent_url(patent_id, "")
    logger.info(f"Parsing patent in its original language: {original_url}")
    # Fetch patent HTML for the original language.
    original_html = fetch_html(original_url)
    original = parse_html(original_html)
    try:
        original_language = original["abstract"]["lang"].lower()
    except KeyError:
        original_language = "<unknown>"
    logger.info(f"Original language is {original_language!r}")

    # Figure out what translations are available. Single-language patents won't
    # have an 'otherLanguages' attribute.
    other_languages = list[str]()
    for other in original.get("otherLanguages", {}).get("otherLanguages", []):
        other_languages.append(other["code"])

    logger.info(f"Other languages available: {other_languages}")

    parsed = list[Node]()
    parsed.append(
        {"language": original_language, "data": original, "html": original_html}
    )

    for language in other_languages:
        url = patent_url(patent_id, language)
        logger.info(f"Fetching {language!r} translation: {url}")
        html = fetch_html(url)
        parsed.append({"language": language, "data": parse_html(html), "html": html})

    logger.info("Scrape completed.")
    return parsed
