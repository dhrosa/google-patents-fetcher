import json
import time
from logging import getLogger

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

logger = getLogger(__name__)


def fetch_html(url: str) -> str:
    """Fetch the source HTML of the given URL."""

    # Client requires that we use content that is exactly identical to a human
    # using "view-source:" as a prefix on a URL in Chrome.
    #
    # We can't use the straightforward WebDriver.page_source property, as this
    # returns the _rendered_ HTML of the page (e.g. this would include all the
    # syntax highlighting and whitespace transformations performed by the
    # browser for pretty-printing). A file created by a human using "Save As" on
    # the view-source: page would produce the correct result. At the time of
    # writing it did not seem possible to cleanly automate that process without
    # using experimental Chrome features, as Selenium doesn't have the ability
    # to interact with the native file dialog.
    #
    # Instead, we intercept the network response by enabling performance logging
    # and using the Chrome Developer Protocol to extract the logged response:
    # https://stackoverflow.com/a/77065745
    options = Options()
    options.add_argument("headless")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = webdriver.Chrome(options=options)
    driver.get(f"view-source:{url}")

    # Wait for page to finish loading
    timeout = 5.0
    start_time = time.time()
    while driver.execute_script("return document.readyState") != "complete":  # type: ignore
        elapsed = time.time() - start_time
        if elapsed >= timeout:
            raise TimeoutError(f"Page did not load within {timeout} seconds.")
        logger.debug(f"Waiting for page to load, elapsed time: {elapsed}")
        time.sleep(0.25)
    logger.info("Page load complete.")

    request_id = ""
    # Find message containing the full response, which happens in the
    # loadingFinished event. We use that message to lookup the request ID for
    # our target response.
    for entry in driver.get_log("performance"):  # type: ignore
        message = json.loads(entry["message"])["message"]
        if message["method"] == "Network.loadingFinished":
            request_id = message["params"]["requestId"]
            break

    if not request_id:
        raise RuntimeError(
            "Could not find 'Network.loadingFinished' message in browser logs."
        )
    # Fetch the response body:
    # https://chromedevtools.github.io/devtools-protocol/tot/Network/#method-getResponseBody
    response = driver.execute_cdp_cmd(
        "Network.getResponseBody", {"requestId": request_id}
    )
    if response["base64Encoded"]:
        # We raise an error because the documentation doesn't specify what kind
        # of base64 is used, and we haven't encountered this situation yet in
        # our manual tests.
        raise NotImplementedError("Encountered base64-encoded content.")

    body = response["body"]
    assert isinstance(body, str)

    return body
