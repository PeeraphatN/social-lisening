"""One anonymous request; extract metadata and matching text for manual review."""

import argparse
import base64
import csv
import json
import re
import time
from datetime import datetime, timezone
from decimal import Decimal
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


DISPLAY_COUNT = r"([0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(\.[0-9]+)?\s*(หมื่น|พัน|แสน|ล้าน|[KkMm])?"


def displayed_count(raw):
    """Return count and its rounding interval; exact notation has no decimals."""
    match = re.fullmatch(DISPLAY_COUNT, raw.strip()) if isinstance(raw, str) else None
    if not match or (match[2] and not match[3]):
        return None
    value = Decimal(match[1].replace(",", "") + (match[2] or ""))
    multiplier = {"k": 1000, "m": 1000000, "พัน": 1000, "หมื่น": 10000,
                  "แสน": 100000, "ล้าน": 1000000}.get((match[3] or "").lower(), 1)
    count = value * multiplier
    half_step = Decimal(multiplier) / (10 ** len((match[2] or "")[1:])) / 2 if match[3] else 0
    return {"count": int(count), "approximate": bool(match[3]),
            "lower": max(0, count - half_step), "upper": count + half_step}


def count_agrees(raw, exact_count):
    value = displayed_count(raw)
    return (value is not None and type(exact_count) is int and exact_count >= 0
            and ((value["lower"] <= exact_count < value["upper"])
                 if value["approximate"] else value["count"] == exact_count))


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
    count = counts.pop()
    return {"count": count, "raw": str(count), "exact_count": count,
            "post_id": post_id, "feedback_id": feedback_id,
            "identity": {"post_id": post_id}, "source": "embedded_comment_summary"}


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
        displayed = displayed_count(raw)
        valid_raw = (count_agrees(raw, count)
                     and (displayed["count"] == 0) == (count == 0))
        candidates["share"].add((raw.strip(), count)
                                if (type(count) is int and count >= 0 and valid_raw
                                    and (not pfbid_path or (type(is_empty) is bool
                                                           and is_empty == (count == 0)))) else None)

    evidence = {}
    for metric, values in candidates.items():
        if len(values) == 1 and None not in values:
            raw, exact_count = values.pop()
            evidence[metric] = {"count": displayed_count(raw)["count"], "raw": raw, "exact_count": exact_count,
                                "post_id": post_id, "feedback_id": feedback_id,
                                "identity": identity, "source": "embedded_ufi_summary"}
    return evidence


def target_identity(url):
    """Recognize only explicit post routes; reject duplicate identity parameters."""
    validate_url(url)
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    path = parsed.path.rstrip("/")
    if path in ("/story.php", "/permalink.php"):
        ids = query.get("story_fbid", [])
        owners = query.get("id", [])
        if len(ids) == 1 and re.fullmatch(r"[0-9]+", ids[0]) and (not owners or
                len(owners) == 1 and re.fullmatch(r"[0-9]+", owners[0])):
            return {"kind": "post", "post_id": ids[0], "owner_id": owners[0] if owners else None}
    group = re.fullmatch(r"/groups/([^/]+)(?:/(?:posts|permalink)/([0-9]+))?", path)
    if group:
        ids = query.get("multi_permalinks", [])
        if group[2] and not ids:
            ids = [group[2]]
        if len(ids) == 1 and re.fullmatch(r"[0-9]+", ids[0]) and (not group[2] or ids[0] == group[2]):
            return {"kind": "group", "group_id": group[1], "post_id": ids[0]}
    if path in ("/photo", "/photo.php"):
        ids = query.get("fbid", [])
        if len(ids) == 1 and re.fullmatch(r"[0-9]+", ids[0]):
            return {"kind": "photo", "photo_id": ids[0]}
    if re.fullmatch(r"/[^/]+/posts/pfbid[A-Za-z0-9]+", path):
        return {"kind": "pfbid", "route": path}
    return None


def identities_match(left, right):
    if left is None or right is None or left["kind"] != right["kind"]:
        return False
    if left["kind"] == "post":
        return (left["post_id"] == right["post_id"] and
                (not left["owner_id"] or not right["owner_id"] or left["owner_id"] == right["owner_id"]))
    return left == right


def inspect_browser_metrics(page, requested_url, *, include_snapshot=False):
    """Capture one rendered snapshot; optionally return it for local evidence."""
    snapshot = page.evaluate(r"""() => {
        const observed_at = new Date().toISOString();
        const blocked = '[data-ad-rendering-role="story_message"], [data-ad-rendering-role="story_attachments"], '
            + '[role="comment"], [role="menu"], [role="dialog"], [role="complementary"], aside';
        const visible = e => e.checkVisibility({checkOpacity:true, checkVisibilityCSS:true});
        const containers = [...document.querySelectorAll('[role="article"]')]
            .filter(a => !a.parentElement.closest('[role="article"]') && visible(a))
            .map(a => {
                const owned = e => e instanceof HTMLElement && e.closest('[role="article"]') === a && visible(e);
                const messages = [...a.querySelectorAll('[data-ad-rendering-role="story_message"]')].filter(owned);
                const message = messages[0];
                const headers = message ? [...a.querySelectorAll('a[href]')].filter(e => owned(e)
                    && !e.closest(blocked) && (e.compareDocumentPosition(message) & Node.DOCUMENT_POSITION_FOLLOWING)) : [];
                const counterNode = e => owned(e) && !e.closest(blocked) && message
                    && !e.querySelector(blocked + ', [role="article"]')
                    && (message.compareDocumentPosition(e) & Node.DOCUMENT_POSITION_FOLLOWING);
                const controls = [...a.querySelectorAll('[role="button"], button')].filter(counterNode);
                const counters = controls.filter(e => !controls.some(c => c !== e && e.contains(c)))
                    .map(e => e.innerText.trim());
                for (const e of a.querySelectorAll('*')) {
                    if (!counterNode(e) || e.children.length || !/^(All reactions|ความรู้สึกทั้งหมด)$/i.test(e.innerText.trim())) continue;
                    const parent = e.parentElement;
                    if (parent !== a && counterNode(parent) && !controls.some(c => c.contains(e))) counters.push(parent.innerText.trim());
                }
                return {permalinks:headers.map(e => e.href), counters, message_count:messages.length,
                        message_has_target_link: !!message?.querySelector('a[href]')};
            });
        const storyLabel = /(?:ดูว่าใครบ้างที่ได้แสดงความรู้สึกต่อเรื่องราวนี้|see who reacted to this story)/i;
        const storyRows = [...document.querySelectorAll('[aria-label]')].filter(e => visible(e) && storyLabel.test(e.getAttribute('aria-label') || ''))
            .map(toolbar => {
                let row = toolbar;
                for (let depth = 0; depth < 5 && row.parentElement; depth++) {
                    const parent = row.parentElement;
                    if (parent.closest('[role="article"]')) break;
                    if ([...parent.querySelectorAll('button,[role="button"]')].filter(visible).length >= 3) { row = parent; break; }
                    row = parent;
                }
                const controls = [...row.querySelectorAll('button,[role="button"]')].filter(e => visible(e) && !e.closest('[role="comment"],[role="article"]'));
                const counters = [];
                let bare = 0;
                for (const control of controls) {
                    const label = control.getAttribute('aria-label') || '';
                    const text = control.innerText.trim();
                    if (/(?:comment|ความคิดเห็น)/i.test(label) && /[0-9]/.test(label)) counters.push(label);
                    else if (/(?:share|แชร์)/i.test(label) && /[0-9]/.test(label)) counters.push(label);
                    else if (storyLabel.test(label)) {
                        if (/[0-9]/.test(text)) { counters.push(`${text} reactions`); bare = 1; }
                    } else if (/^[0-9][0-9.,]*\s*(?:พัน|หมื่น|ล้าน)?$/.test(text)) {
                        counters.push(bare++ === 0 ? `${text} reactions` : bare === 2 ? `${text} comments` : `${text} shares`);
                    }
                }
                return {permalinks:[], counters, message_count:1, message_has_target_link:false, story_row:true};
            });
        const uniqueRows = new Map();
        for (const row of storyRows) uniqueRows.set(JSON.stringify(row.counters), row);
        containers.push(...uniqueRows.values());
        return {containers, html:document.documentElement.outerHTML, resolved_url:location.href,
                body_text:document.body ? document.body.innerText : '', title:document.title, observed_at,
                messages:[...document.querySelectorAll('[data-ad-rendering-role="story_message"]')].map(e => e.innerText)};
    }""")
    metrics = extract_browser_metrics("", snapshot["html"], snapshot["resolved_url"], requested_url=requested_url,
                                      rendered_containers=snapshot["containers"])
    if include_snapshot:
        metrics["snapshot"] = snapshot
    return metrics


def extract_browser_metrics(body_text, html, resolved_url, *, requested_url=None, rendered_containers=None):
    """Accept body counters only from a unique rendered target, then scoped fallbacks.

    body_text remains a compatibility argument and is never used as evidence.
    rendered_containers must come from inspect_browser_metrics' rendered snapshot.
    """
    target = target_identity(resolved_url)
    requested_url = requested_url or resolved_url
    requested = target_identity(requested_url)
    share_redirect = re.fullmatch(r"/share/p/[A-Za-z0-9]+/?", urlparse(requested_url).path)
    consistent = target is not None and (identities_match(requested, target) or share_redirect)
    status = "missing" if consistent else "conflicting"
    candidates = []
    for container in rendered_containers or []:
        identities = []
        malformed_header = False
        for link in container["permalinks"]:
            try:
                identity = target_identity(link)
            except ValueError:
                continue
            if identity is not None:
                identities.append(identity)
            else:
                route = urlparse(link)
                if (route.path.rstrip("/") in ("/story.php", "/permalink.php", "/photo", "/photo.php")
                        or re.search(r"/(?:posts|permalink)/", route.path)
                        or {"story_fbid", "multi_permalinks", "fbid"} & parse_qs(route.query, keep_blank_values=True).keys()):
                    malformed_header = True
        # Resolved/requested identity and the unique post-level message already
        # establish the target; rendered header links may use unrelated aliases.
        if (consistent and not identities and not malformed_header
                and not container.get("message_has_target_link")
                and container["message_count"] == 1 and container.get("counters")):
            candidates.append(container)
        elif any(identities_match(identity, target) for identity in identities):
            candidates.append(container)
            if malformed_header:
                status = "malformed"
            elif not all(identities_match(identity, target) for identity in identities):
                status = "conflicting"
            elif container["message_count"] != 1:
                status = "ambiguous"
    if len(candidates) > 1:
        status = "ambiguous"
    elif len(candidates) == 1 and status == "missing":
        status = "target_scoped"

    metrics = extract_social_metrics("")
    metrics["body_scope_status"] = status
    metrics["comment_counter_evidence"] = extract_comment_counter(html, resolved_url)
    metrics["share_counter_evidence"] = None
    metrics["reaction_counter_evidence"] = None
    zero = metrics["comment_counter_evidence"]
    if consistent and zero is not None and zero["count"] == 0:
        metrics.update(comment_count=0, comment_text_raw="0", comment_count_source=zero["source"])
    for metric, evidence in extract_icon_counters(html, resolved_url).items():
        metrics[f"{metric}_counter_evidence"] = evidence
        if consistent:
            metrics[f"{metric}_count"] = evidence["count"]
            metrics[f"{metric}_text_raw"] = evidence["raw"]
            metrics[f"{metric}_count_source"] = evidence["source"]

    patterns = {"reaction": (rf"(?:All reactions|ความรู้สึกทั้งหมด|reactions?|likes?|ถูกใจ)\s+{DISPLAY_COUNT}",
                             rf"{DISPLAY_COUNT}\s+(?:reactions?|likes?|ถูกใจ)"),
                "comment": (rf"{DISPLAY_COUNT}\s+(?:comments?|ความคิดเห็น)",
                            rf"comments?\s+{DISPLAY_COUNT}", rf"ความคิดเห็น\s+{DISPLAY_COUNT}\s+รายการ"),
                "share": (rf"{DISPLAY_COUNT}\s+shares?", rf"shares?\s+{DISPLAY_COUNT}",
                          rf"แชร์\s+{DISPLAY_COUNT}\s+ครั้ง")}
    for metric, expressions in patterns.items():
        body = []
        malformed = False
        if status == "target_scoped":
            for raw in candidates[0]["counters"]:
                for expression in expressions:
                    match = re.fullmatch(expression, raw.strip(), re.IGNORECASE)
                    if match:
                        number = "".join(part or "" for part in match.groups())
                        value = displayed_count(number)
                        if value is not None:
                            body.append({"count": value["count"], "raw": raw, "number_raw": number,
                                         "approximate": value["approximate"], "identity": target,
                                         "source": "body_text"})
                        else:
                            malformed = True
                        break
                else:
                    if re.search({"reaction": r"reactions?|likes?|ถูกใจ|ความรู้สึกทั้งหมด",
                                  "comment": r"comments?|ความคิดเห็น", "share": r"shares?|แชร์"}[metric], raw, re.I) and re.search(r"[0-9]", raw):
                        malformed = True
        body_evidence = body[0] if len(body) == 1 and not malformed else None
        metrics[f"{metric}_body_evidence"] = body_evidence
        scope_status = status if status != "target_scoped" else "missing"
        if body_evidence:
            metrics[f"{metric}_count"] = body_evidence["count"]
            metrics[f"{metric}_text_raw"] = body_evidence["raw"]
            metrics[f"{metric}_count_source"] = "body_text"
            scope_status = "target_scoped"
        elif malformed or len(body) > 1:
            scope_status = "malformed" if malformed else "ambiguous"
        if metrics[f"{metric}_count"] is not None and not body_evidence:
            scope_status = "identity_scoped_fallback"
        evidence = metrics[f"{metric}_counter_evidence"]
        conflict = body_evidence and evidence and not count_agrees(
            body_evidence["number_raw"], evidence.get("exact_count", evidence["count"]))
        if conflict:
            scope_status = "conflicting"
        verification = "missing"
        if metrics[f"{metric}_count"] is not None:
            approximate = body_evidence["approximate"] if body_evidence else displayed_count(metrics[f"{metric}_text_raw"])["approximate"]
            verification = "unverified" if conflict else "approximate" if approximate else "exact"
        metrics.setdefault(f"{metric}_count_source", None)
        metrics[f"{metric}_scope_status"] = scope_status
        metrics[f"{metric}_verification_status"] = verification
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
