from collections.abc import Iterator
from logging import getLogger
from typing import Any, TypeAlias

from bs4 import BeautifulSoup, NavigableString, Tag

Field: TypeAlias = tuple[str, Any]
FieldIterator: TypeAlias = Iterator[Field]
Node: TypeAlias = dict[str, Any]

logger = getLogger(__name__)

# We define a 'property' as an HTML tag with an 'itemprop' attribute.


def tag_string(tag: Tag) -> str:
    """Human-readable tag information for logging."""
    return f"{tag.name=} {tag.attrs=} {tag.sourceline=}"


def has_class(tag: Tag, class_name: str) -> bool:
    """True if 'class_name' is one of tag's classes"""
    classes = tag.get("class") or []
    return class_name in classes


def hyphenated_to_camel(hyphenated: str) -> str:
    """Convert hyphenated-string to camelCased string."""
    parts = list[str]()
    for i, part in enumerate(hyphenated.split("-")):
        if i != 0:
            part = part.capitalize()
        parts.append(part)
    return "".join(parts)


def parse_html(html: str) -> Node:
    """Parse HTML string"""
    soup = BeautifulSoup(html, features="html.parser")
    article = soup.find("article")
    if not isinstance(article, Tag):
        raise ValueError("Could not find <article> tag. Maybe the URL is wrong?")

    data: Node = {}
    parse_properties(article, data)

    hack.clear()
    # Special sections get incorrectly nested under the "links" property. Remove
    # these properties to move them to the proper location, and also to
    # specialize their handling.
    #
    # TODO(dhrosa): Figure out how to avoid these nesting under "links". Perhaps
    # pre-process the HTML to nest the special sections under a new synthethic
    # property.
    links = data["links"]
    for name in SPECIAL_SECTION_NAMES:
        if name in links:
            del links[name]
    parse_special_sections(article, data)

    data["info"]["publicationNumber"]["values"] = list(
        parse_publication_numbers(article)
    )
    return data


hack = set[int]()

START_TAGS = ("dt", "h2")


def parse_properties(tag: Tag, current_node: Node) -> None:  # noqa: C901
    """Recursively parse properties.

    We skip over tags that are not related to a property.

    <dt> and <h2> tags are used as labels that delineate properties. Nodes
    between these tags relate to the previous label.
    """
    if id(tag) in hack:
        return
    hack.add(id(tag))
    child_node: Node
    if tag.name in START_TAGS:
        # New label found; begin a new nested node
        label = parse_label(tag)
        child_node = {}
        parse_siblings_properties(tag, child_node)
        current_node[label] = child_node
        return

    property_name = tag.get("itemprop")
    if not property_name:
        # This tag itself is not a property, but its descendants might be
        parse_children_properties(tag, current_node)
        return
    assert isinstance(property_name, str)

    value = property_value(tag)

    if tag.has_attr("repeat"):
        # "repeat" attribute indicate list-valued properties
        if property_name not in current_node:
            current_node[property_name] = []
        current_node[property_name].append(value)
    else:
        # Scalar property
        current_node[property_name] = value


def property_value(tag: Tag) -> Any:
    """Parse value of a property tag.

    Dependent on the type of tag, the interesting content of the tag"""
    if tag.has_attr("itemscope"):
        # Nested property
        child_node: Node = {}
        parse_children_properties(tag, child_node)
        return child_node
    if (content := tag.get("content")) is not None:
        # <meta> tags
        return content
    if (href := tag.get("href")) is not None:
        # <a> tags
        return href
    if (src := tag.get("src")) is not None:
        # <img> tags
        return src
    # Otherwise, the text within the node is considered the value
    text = tag.string
    if not isinstance(text, str):
        #
        logger.warning(
            f"Omitting property value for tag with nested content: {tag_string(tag)}"
        )
        return None
    return text.strip()


def attrs_to_fields(tag: Tag) -> FieldIterator:
    """Convert all HTML attributes of a tag into fields except for 'class'."""
    for key, value in tag.attrs.items():
        if key != "class":
            yield hyphenated_to_camel(key), value


def parse_label(tag: Tag) -> str:
    """Convert a label (e.g. an h2 tag) into camel case."""
    raw = tag.string
    if not isinstance(raw, str):
        logger.warning("Label tag has no string")
        return ""
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


def parse_children_properties(tag: Tag, current_node: Node) -> None:
    """Parse properties from all child tags"""
    for child in tag.children:
        if not isinstance(child, Tag):
            continue
        parse_properties(child, current_node)


def parse_siblings_properties(tag: Tag, current_node: Node) -> None:
    """Parse properties from all sibling tags"""
    for sibling in tag.next_siblings:
        if not isinstance(sibling, Tag):
            continue
        if sibling.name in START_TAGS:
            return
        parse_properties(sibling, current_node)


def parse_publication_numbers(article: Tag) -> Iterator[str]:
    start = article.find(attrs={"itemprop": "publicationNumber"})
    if not isinstance(start, Tag):
        logger.warning("Could not find publication numbers.")
        return

    for sibling in start.next_siblings:
        if not isinstance(sibling, Tag):
            continue
        if sibling.name in START_TAGS:
            return
        if sibling.name != "span":
            continue
        text = sibling.get_text(strip=True)
        if text:
            yield text


SPECIAL_SECTION_NAMES = (
    "abstract",
    "description",
    "claims",
    "application",
    "family",
)
"""itemprop value of <section> tags that need specialized handling."""


def is_special_section(tag: Tag) -> bool:
    """True if this is a <section> tag that needs specialized handling."""
    return (
        tag.name == "section"
        and tag.has_attr("itemscope")
        and (tag.get("itemprop") in SPECIAL_SECTION_NAMES)
    )


def parse_special_sections(article: Tag, current_node: Node) -> None:
    """Parse section tags that are also properties.

    These tags have special structure that is not represented as properties."""
    for section in article.find_all(is_special_section):
        property_name = section["itemprop"]
        assert isinstance(property_name, str)
        value: Any
        match property_name:
            case "abstract":
                value = dict(parse_abstract(section))
            case "description":
                value = dict(parse_description(section))
            case "claims":
                value = dict(parse_claims(section))
            case "application":
                value = dict(parse_application(section))
            case "family":
                value = dict(parse_family(section))
            case _:
                logger.warning(f"Unhandled section: {section.attrs=}")
                value = None
        current_node[property_name] = value


def parse_abstract(section: Tag) -> FieldIterator:
    """Parse abstract section"""
    abstract = section.find("abstract")
    if not isinstance(abstract, Tag):
        return

    yield from attrs_to_fields(abstract)
    yield "text", abstract.get_text(strip=True)


def parse_description(section: Tag) -> FieldIterator:
    """Parse description section"""

    def is_description(tag: Tag) -> bool:
        return has_class(tag, "description") or (tag.name == "description")

    description = section.find(is_description)
    if not isinstance(description, Tag):
        return

    yield from attrs_to_fields(description)

    yield "lines", list(parse_description_lines(description))


def descendant_navigable_strings(tag: Tag) -> Iterator[NavigableString]:
    """Iterates through NavigableString descendants of the given tag."""
    for d in tag.descendants:
        if isinstance(d, NavigableString):
            yield d


def parse_description_lines(description: Tag) -> Iterator[Node]:
    """Parse individual text elements inside the description section."""

    def get_line_num(s: NavigableString) -> str:
        """Fetches the "num" attribute of the nearest ancestor."""
        for parent in s.parents:
            if num := parent.get("num"):
                assert isinstance(num, str)
                return num
        return ""

    for d in descendant_navigable_strings(description):
        text = str(d).strip()
        if not text:
            continue
        yield {"num": get_line_num(d), "text": text}


def parse_claims(section: Tag) -> FieldIterator:
    """Parse claims section"""

    def is_claims(tag: Tag) -> bool:
        return has_class(tag, "claims") or tag.name == "claims"

    claims_tag = section.find(is_claims)
    if not isinstance(claims_tag, Tag):
        return

    yield from attrs_to_fields(claims_tag)

    parsed_claims = list[Node]()

    def is_claim(tag: Tag) -> bool:
        return (has_class(tag, "claim") or tag.name == "claim") and tag.has_attr("num")

    for claim in claims_tag.find_all(is_claim):
        assert isinstance(claim, Tag)
        parsed_claims.append(dict(parse_claim(claim)))

    yield "claims", parsed_claims


def parse_claim(claim: Tag) -> FieldIterator:
    """Parse a single claim"""
    yield from attrs_to_fields(claim)
    yield "text", list(claim.stripped_strings)


def parse_application(application: Tag) -> FieldIterator:
    """Parse application section."""
    node: Node = {}
    parse_children_properties(application, node)
    yield from node.items()


def parse_family(family: Tag) -> FieldIterator:
    """Parse family section."""
    # The ID of the family is contained in its first h2 tag.
    id_tag = family.find("h2")
    if not isinstance(id_tag, Tag):
        return
    yield "id", id_tag.get_text(strip=True).split("=")[-1]

    content_start = id_tag.find_next_sibling("h2")
    if not isinstance(content_start, Tag):
        return

    node: Node = {}
    parse_properties(content_start, node)
    yield from node.items()
