"""One anonymous request; extract metadata and matching text for manual review."""

import argparse
import base64
import csv
import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
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


def parse_count(text):
    match = re.search(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(หมื่น|พัน|แสน|ล้าน|[KkMm])?", text)
    if not match:
        return None
    raw = match.group(1).replace(",", "")
    unit = (match.group(2) or "").lower()
    multiplier = {"k": 1_000, "m": 1_000_000, "พัน": 1_000,
                  "หมื่น": 10_000, "แสน": 100_000, "ล้าน": 1_000_000}.get(unit, 1)
    return int(float(raw) * multiplier)


def extract_social_metrics(body_text):
    metrics = {"reaction_count": None, "comment_count": None, "share_count": None,
               "reaction_text_raw": None, "comment_text_raw": None, "share_text_raw": None}
    keys = (("reaction", ("reaction", "like", "ถูกใจ")),
            ("comment", ("comment", "ความคิดเห็น")),
            ("share", ("share", "แชร์")))
    lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        lowered = line.lower()
        if metrics["reaction_count"] is None and ("ความรู้สึกทั้งหมด" in line or "all reactions" in lowered):
            next_line = lines[index + 1] if index + 1 < len(lines) else ""
            metrics["reaction_count"] = parse_count(next_line)
            metrics["reaction_text_raw"] = f"{line} {next_line}".strip()
            continue
        count = parse_count(line)
        if count is None or len(line) > 80:
            continue
        if not (line[0].isdigit() or any(lowered.startswith(word) for _, words in keys for word in words)):
            continue
        for name, words in keys:
            if metrics[f"{name}_text_raw"] is None and any(word in lowered for word in words):
                metrics[f"{name}_text_raw"] = line
                metrics[f"{name}_count"] = count
    return metrics


def extract_comment_counter(html, resolved_url):
    """Read a comment summary only when both feedback IDs match the URL's post ID.

    Currently supports resolved story.php URLs with a single numeric story_fbid.
    Missing data or conflicting summaries are not evidence of zero.
    """
    validate_url(resolved_url)
    parsed = urlparse(resolved_url)
    ids = parse_qs(parsed.query).get("story_fbid", [])
    if parsed.path != "/story.php" or len(ids) != 1 or not ids[0].isascii() or not ids[0].isdigit():
        return None
    post_id = ids[0]
    feedback_id = base64.b64encode(f"feedback:{post_id}".encode()).decode()
    page = PageData()
    page.feed(html)
    counts = set()
    for script in page.scripts:
        try:
            pending = [json.loads(script)]
        except json.JSONDecodeError:
            continue
        while pending:
            node = pending.pop()
            if isinstance(node, dict):
                renderer = node.get("comet_ufi_summary_and_actions_renderer")
                feedback = renderer.get("feedback") if isinstance(renderer, dict) else None
                if isinstance(feedback, dict) and feedback.get("id") == feedback_id:
                    summary = feedback.get("comments_count_summary_renderer")
                    inner = summary.get("feedback") if isinstance(summary, dict) else None
                    count = None
                    if isinstance(inner, dict) and inner.get("id") == feedback_id:
                        instance = inner.get("comment_rendering_instance")
                        comments = instance.get("comments") if isinstance(instance, dict) else None
                        count = comments.get("total_count") if isinstance(comments, dict) else None
                    counts.add(count if type(count) is int and count >= 0 else None)
                pending.extend(node.values())
            elif isinstance(node, list):
                pending.extend(node)
    if len(counts) != 1 or None in counts:
        return None
    return {"count": counts.pop(), "post_id": post_id, "feedback_id": feedback_id,
            "source": "embedded_comment_summary"}


def extract_icon_counters(html, resolved_url):
    """Read icon counters from an explicitly matched UFI summary.

    Photo IDs identify media, so map the selected media to its owning story.
    Group pages can contain other posts; their feedback must never be used.
    Opaque pfbid pages require a complete route-to-feedback identity chain.
    """
    validate_url(resolved_url)
    parsed = urlparse(resolved_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    photo_ids = query.get("fbid", []) if parsed.path.rstrip("/") in ("/photo", "/photo.php") else []
    group_path = re.fullmatch(r"/groups/[^/]+/(?:posts|permalink)/(\d+)/?", parsed.path)
    group_ids = query.get("multi_permalinks", []) if re.fullmatch(r"/groups/[^/]+/?", parsed.path) else []
    pfbid_path = re.fullmatch(r"/[^/]+/posts/pfbid[^/]+/?", parsed.path)
    ids = photo_ids or ([group_path.group(1)] if group_path else group_ids)
    if not pfbid_path and (len(ids) != 1 or not re.fullmatch(r"[0-9]+", ids[0])):
        return {}

    page = PageData()
    page.feed(html)
    nodes = []
    for script in page.scripts:
        try:
            pending = [json.loads(script)]
        except json.JSONDecodeError:
            continue
        while pending:
            node = pending.pop()
            if isinstance(node, dict):
                nodes.append(node)
                pending.extend(node.values())
            elif isinstance(node, list):
                pending.extend(node)

    if pfbid_path:
        route_story_ids = set()
        for node in nodes:
            route_info = node.get("initialRouteInfo")
            route = route_info.get("route") if isinstance(route_info, dict) else None
            if not isinstance(route, dict) or route.get("url") != parsed.path:
                continue
            root_view = route.get("rootView")
            props = root_view.get("props") if isinstance(root_view, dict) else None
            story_id = props.get("storyID") if isinstance(props, dict) else None
            route_story_ids.add(story_id if isinstance(story_id, str) and story_id else None)
        if len(route_story_ids) != 1 or None in route_story_ids:
            return {}
        story_id = route_story_ids.pop()

        matched_summaries = []
        post_ids = set()
        for node in nodes:
            story = node.get("node_v2")
            if not isinstance(story, dict) or story.get("id") != story_id:
                continue
            post_id = story.get("post_id")
            sections = story.get("comet_sections")
            feedback_section = sections.get("feedback") if isinstance(sections, dict) else None
            story_wrapper = feedback_section.get("story") if isinstance(feedback_section, dict) else None
            container = story_wrapper.get("story_ufi_container") if isinstance(story_wrapper, dict) else None
            nested_story = container.get("story") if isinstance(container, dict) else None
            if (not isinstance(post_id, str) or not re.fullmatch(r"[0-9]+", post_id)
                    or not isinstance(nested_story, dict)
                    or nested_story.get("id") != story_id
                    or nested_story.get("post_id") != post_id):
                continue
            context = nested_story.get("feedback_context")
            summary = context.get("feedback_target_with_context") if isinstance(context, dict) else None
            renderer = summary.get("comet_ufi_summary_and_actions_renderer") if isinstance(summary, dict) else None
            feedback = renderer.get("feedback") if isinstance(renderer, dict) else None
            feedback_id = base64.b64encode(f"feedback:{post_id}".encode()).decode()
            comments = feedback.get("comments_count_summary_renderer") if isinstance(feedback, dict) else None
            inner = comments.get("feedback") if isinstance(comments, dict) else None
            if (not isinstance(feedback, dict) or feedback.get("id") != feedback_id
                    or feedback.get("subscription_target_id") != post_id
                    or not isinstance(inner, dict) or inner.get("id") != feedback_id):
                continue
            post_ids.add(post_id)
            matched_summaries.append(summary)
        if len(post_ids) != 1 or not matched_summaries:
            return {}
        post_id = post_ids.pop()
        nodes = matched_summaries
        identity = {"route": parsed.path, "story_id": story_id, "post_id": post_id}
    else:
        post_id = ids[0]
        identity = {"post_id": post_id}
        if photo_ids:
            stories = set()
            for node in nodes:
                media = node.get("currMedia")
                if not isinstance(media, dict) or media.get("id") != ids[0]:
                    continue
                for key in ("creation_story", "container_story"):
                    story = media.get(key)
                    if isinstance(story, dict) and "post_id" in story:
                        value = story["post_id"]
                        stories.add(value if isinstance(value, str) and re.fullmatch(r"[0-9]+", value) else None)
            if len(stories) != 1 or None in stories:
                return {}
            post_id = stories.pop()
            identity = {"photo_id": ids[0], "post_id": post_id}

    feedback_id = base64.b64encode(f"feedback:{post_id}".encode()).decode()
    candidates = {"comment": set(), "share": set()}
    for node in nodes:
        renderer = node.get("comet_ufi_summary_and_actions_renderer")
        feedback = renderer.get("feedback") if isinstance(renderer, dict) else None
        if not isinstance(feedback, dict) or feedback.get("id") != feedback_id:
            continue
        if feedback.get("subscription_target_id", post_id) != post_id:
            candidates["comment"].add(None)
            candidates["share"].add(None)
            continue
        summary = feedback.get("comments_count_summary_renderer")
        inner = summary.get("feedback") if isinstance(summary, dict) else None
        instance = (inner.get("comment_rendering_instance")
                    if isinstance(inner, dict) and inner.get("id") == feedback_id else None)
        comments = instance.get("comments") if isinstance(instance, dict) else None
        count = comments.get("total_count") if isinstance(comments, dict) else None
        candidates["comment"].add((str(count), count) if type(count) is int and count >= 0 else None)
        shares = feedback.get("share_count")
        count = shares.get("count") if isinstance(shares, dict) else None
        is_empty = shares.get("is_empty") if isinstance(shares, dict) else None
        raw = feedback.get("i18n_share_count")
        match = (re.fullmatch(r"([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(หมื่น|พัน|แสน|ล้าน|[KkMm])?",
                              raw.strip()) if isinstance(raw, str) else None)
        displayed = parse_count(raw) if match else None
        valid_raw = (match and (match.group(2) or ("." not in match.group(1) and displayed == count))
                     and (displayed == 0) == (count == 0))
        candidates["share"].add((raw.strip(), count)
                                if (type(count) is int and count >= 0 and valid_raw
                                    and (not pfbid_path or (type(is_empty) is bool
                                                           and is_empty == (count == 0)))) else None)

    evidence = {}
    for metric, values in candidates.items():
        if len(values) == 1 and None not in values:
            raw, exact_count = values.pop()
            evidence[metric] = {"count": parse_count(raw), "raw": raw, "exact_count": exact_count,
                                "post_id": post_id, "feedback_id": feedback_id,
                                "identity": identity, "source": "embedded_ufi_summary"}
    return evidence


def extract_browser_metrics(body_text, html, resolved_url):
    """Keep browser counter semantics; fill missing identity-scoped icon counters."""
    metrics = extract_social_metrics(body_text)
    for metric in ("reaction", "comment", "share"):
        metrics[f"{metric}_count_source"] = "body_text" if metrics[f"{metric}_count"] is not None else None
    metrics["comment_counter_evidence"] = extract_comment_counter(html, resolved_url)
    metrics["share_counter_evidence"] = None
    zero = metrics["comment_counter_evidence"]
    if metrics["comment_count"] is None and zero is not None and zero["count"] == 0:
        metrics.update(comment_count=0, comment_text_raw="0", comment_count_source=zero["source"])
    for metric, evidence in extract_icon_counters(html, resolved_url).items():
        metrics[f"{metric}_counter_evidence"] = evidence
        if metrics[f"{metric}_count"] is None:
            metrics[f"{metric}_count"] = evidence["count"]
            metrics[f"{metric}_text_raw"] = evidence["raw"]
            metrics[f"{metric}_count_source"] = evidence["source"]
    return metrics


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
