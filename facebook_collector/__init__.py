"""Public Python interface for the Facebook post collector."""

from facebook_collector.collector import CollectionUnavailable, collect_posts


__all__ = ["CollectionUnavailable", "collect_posts"]
