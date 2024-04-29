import json
from argparse import ArgumentParser
from typing import cast

from rich import print
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


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


def main() -> None:
    parser = ArgumentParser(
        description="Fetch JSON-encoded information about a patent."
    )
    parser.add_argument(
        "patent_id", type=str, help="The Google Patent ID to fetch data for."
    )
    args = parser.parse_args()

    print(fetch_html(f"https://patents.google.com/patent/{args.patent_id}/"))


if __name__ == "__main__":
    pass
