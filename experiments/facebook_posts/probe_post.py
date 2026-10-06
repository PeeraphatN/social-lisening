"""One anonymous request; extract metadata and matching text for manual review."""

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, build_opener


def validate_url(url):
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname not in
            {"facebook.com", "www.facebook.com", "m.facebook.com"}
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("Only HTTPS Facebook URLs without credentials are accepted")
    return url


class FacebookRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PageData(HTMLParser):
    def __init__(self):
        super().__init__()
        self.metadata = {}
        self.scripts = []
        self.script = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            self.metadata[attrs.get("property", attrs.get("name"))] = attrs.get("content", "")
        if tag == "script" and attrs.get("type") == "application/json":
            self.script = []

    def handle_data(self, data):
        if self.script is not None:
            self.script.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.script is not None:
            self.scripts.append("".join(self.script))
            self.script = None


def extract_post(html):
    page = PageData()
    page.feed(html)
    preview = page.metadata.get("og:description", page.metadata.get("description", ""))
    prefix = " ".join(preview.rstrip(".… ").split())[:80]
    matches = {}
    for script in page.scripts:
        try:
            pending = [json.loads(script)]
        except json.JSONDecodeError:
            continue
        while pending:
            node = pending.pop()
            if isinstance(node, dict):
                message = node.get("message")
                text = message.get("text") if isinstance(message, dict) else None
                if isinstance(text, str):
                    normalized = " ".join(text.split())
                    if prefix and normalized.startswith(prefix):
                        matches[normalized] = text
                pending.extend(node.values())
            elif isinstance(node, list):
                pending.extend(node)
    candidates = list(matches.values())
    status = "preview_only" if preview else "no_post_data"
    if candidates:
        status = "candidate_text_unverified" if len(candidates) == 1 else "ambiguous"
    return {
        "status": status,
        "publisher_metadata": page.metadata.get("og:title"),
        "preview_text": preview or None,
        "text": candidates[0] if len(candidates) == 1 else None,
        "candidate_count": len(candidates),
        "text_source": "embedded_json_message" if len(candidates) == 1 else None,
        "manual_match": None,
        "published_at": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", type=validate_url)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {"sample_id": "P01", "input_url": args.url,
              "collected_at": datetime.now(timezone.utc).isoformat(),
              "method": "anonymous_http_stdlib", "authenticated": False}
    started = time.monotonic()
    try:
        with build_opener(FacebookRedirects()).open(args.url, timeout=30) as response:
            content = response.read(5_000_001)
            if len(content) > 5_000_000:
                raise ValueError("Response exceeds the 5 MB experiment limit")
            result.update(http_status=response.status, resolved_url=response.url,
                          html_bytes=len(content))
            result.update(extract_post(content.decode("utf-8")))
            if urlparse(response.url).path.startswith("/login"):
                result.update(status="login_required", text=None)
    except (HTTPError, URLError, TimeoutError, UnicodeError, ValueError, OSError) as error:
        result.update(status="request_failed", error_reason=str(error), text=None)
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with args.output.with_suffix(".csv").open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(result))
        writer.writeheader()
        writer.writerow(result)
    print(json.dumps({key: result.get(key) for key in
                      ("status", "http_status", "resolved_url", "candidate_count",
                       "html_bytes", "duration_seconds")}, ensure_ascii=True))


if __name__ == "__main__":
    main()
