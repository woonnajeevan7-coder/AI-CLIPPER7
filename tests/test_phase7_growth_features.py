"""
Phase 7 Verification Tests: Growth Features
Tests multi-language support (Hindi, Telugu, Tamil), channel watcher, and official OAuth auto-publisher payloads.
"""

from datetime import datetime, timezone
import pytest
from agents.growth import (
    SUPPORTED_LANGUAGES,
    MultiLanguageEngine,
    ChannelWatcherAgent,
    OfficialPublisherAgent
)


def test_supported_languages_indic_and_global():
    assert "hi" in SUPPORTED_LANGUAGES
    assert "te" in SUPPORTED_LANGUAGES
    assert "ta" in SUPPORTED_LANGUAGES
    assert "en" in SUPPORTED_LANGUAGES
    assert SUPPORTED_LANGUAGES["hi"]["name"] == "Hindi (हिन्दी)"
    assert SUPPORTED_LANGUAGES["te"]["name"] == "Telugu (తెలుగు)"
    assert SUPPORTED_LANGUAGES["ta"]["name"] == "Tamil (தமிழ்)"


def test_youtube_shorts_payload_creation():
    pub = OfficialPublisherAgent()
    payload = pub.create_youtube_shorts_payload(
        title="Unleash 10X Speed",
        description="The secret method",
        tags=["coding", "speed"]
    )
    assert "#Shorts" in payload["body"]["snippet"]["title"]
    assert payload["body"]["snippet"]["categoryId"] == "22"
    assert payload["body"]["status"]["privacyStatus"] == "public"

    # Test scheduled publishing
    scheduled_time = datetime(2026, 12, 1, 15, 0, 0)
    scheduled_payload = pub.create_youtube_shorts_payload(
        title="Scheduled Release",
        description="Coming soon",
        scheduled_at=scheduled_time
    )
    assert scheduled_payload["body"]["status"]["privacyStatus"] == "private"
    assert "publishAt" in scheduled_payload["body"]["status"]


def test_tiktok_publisher_payload():
    payload = OfficialPublisherAgent.create_tiktok_payload(
        caption="Stop making this mistake"
    )
    assert "source_info" in payload
    assert payload["source_info"]["source"] == "PULL_FROM_URL"
    assert "post_info" in payload
    assert "#fyp" in payload["post_info"]["title"]


def test_instagram_reels_payload():
    payload = OfficialPublisherAgent.create_instagram_reels_payload(
        caption="The hidden mindset",
        video_url="https://r2.storage.com/clip1.mp4",
        share_to_feed=True
    )
    assert payload["media_type"] == "REELS"
    assert payload["video_url"] == "https://r2.storage.com/clip1.mp4"
    assert payload["share_to_feed"] is True
