"""Public channel feed collection is read-only, bounded and not visual review."""
import json
from pathlib import Path
import unittest
from scripts import umbral3_public_feed as feed

CHANNEL="UCu9hVrp6a8i3bdmcWnJDiEw"
XML=f'''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
<yt:channelId>{CHANNEL}</yt:channelId>
<entry><yt:videoId>AaBbCcDdEe1</yt:videoId><yt:channelId>{CHANNEL}</yt:channelId>
<title>Independent original horror</title><published>2026-11-23T18:00:00+00:00</published></entry>
<entry><yt:videoId>AaBbCcDdEe1</yt:videoId><yt:channelId>{CHANNEL}</yt:channelId>
<title>Duplicate entry</title><published>2026-11-23T18:00:00+00:00</published></entry>
<entry><yt:videoId>12345678901</yt:videoId><yt:channelId>UCXvm1kA5S2hWEANxx-0OoIg</yt:channelId>
<title>Untrusted other channel</title><published>2026-11-22T18:00:00+00:00</published></entry>
</feed>'''.encode()

class FeedTests(unittest.TestCase):
    def test_only_direct_official_channels(self):
        self.assertEqual(feed.channel_id("https://www.youtube.com/channel/"+CHANNEL),CHANNEL)
        for source in ("https://evil.youtube.com/channel/"+CHANNEL,
                       "https://www.youtube.com/@somebody",
                       "http://www.youtube.com/channel/"+CHANNEL,
                       "https://www.youtube.com/channel/"+CHANNEL+"?redirect=1"):
            self.assertIsNone(feed.channel_id(source))
    def test_matching_atom_channel_no_fabricated_visual_data(self):
        items=feed.parse_feed(XML,CHANNEL,"2026-11-24")
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]["review_type"],"metadata_only")
        self.assertEqual(items[0]["frames_inspected"],0)
        self.assertFalse(items[0]["verified_vertical"])
        self.assertIsNone(items[0]["follower_count"])
    def test_reject_wrong_feed_or_large_payload(self):
        with self.assertRaisesRegex(ValueError,"identity mismatch"):
            feed.parse_feed(XML,"UCXvm1kA5S2hWEANxx-0OoIg","2026-11-24")
        with self.assertRaises(ValueError):
            feed.parse_feed(XML*1000,CHANNEL,"2026-11-24")
    def test_network_failure_visible_never_empty_success(self):
        discovered=[{"handle":"cultivision","platform":"YouTube",
                     "source":"https://www.youtube.com/channel/"+CHANNEL}]
        good=feed.scan({"accounts":[]},discovered,"2026-11-24",downloader=lambda x:XML)
        self.assertEqual(good["scanned"],1)
        self.assertEqual(good["direct_frame_reviews"],0)
        self.assertEqual(good["newest_public_video_candidates"][0]["creator"],"cultivision")
        def fail(x):
            raise OSError("denied")
        unavailable=feed.scan({"accounts":[]},discovered,"2026-11-24",downloader=fail)
        self.assertEqual(unavailable["scanned"],0)
        self.assertEqual(unavailable["collector_status"],"degraded_external_feed")
        self.assertEqual(unavailable["fallback"],"existing_weekly_web_research")
        self.assertEqual(len(unavailable["unavailable"]),1)
    def test_atom_id_fallback_with_matching_channel(self):
        xml=XML.replace(("<yt:channelId>"+CHANNEL+"</yt:channelId>").encode(),("<id>yt:channel:"+CHANNEL+"</id>").encode(),1)
        self.assertEqual(len(feed.parse_feed(xml,CHANNEL,"2026-11-24")),1)

    def test_discovered_direct_channel_added_without_count_limit(self):
        root=Path(__file__).resolve().parents[1]
        catalog=json.loads((root/"learning/competitors/catalog-2026-11-18.json").read_text())
        discovered=json.loads((root/"learning/visual-radar/accounts_new.json").read_text())
        channels=feed.feed_channels(catalog,discovered)
        self.assertGreaterEqual(len(channels),4)
        self.assertTrue(any(c["channel_id"]==CHANNEL for c in channels))
