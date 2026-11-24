"""Collect public YouTube Atom feed metadata for the UMBRAL visual radar.

No video downloads, no private data, no audiovisual review claims.
"""
import argparse
import datetime as dt
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
from scripts.umbral3_visual_radar import CATALOG, RADAR, accounts

ATOM="{http://www.w3.org/2005/Atom}"
YT="{http://www.youtube.com/xml/schemas/2015}"
CHANNEL=re.compile(r"UC[A-Za-z0-9_-]{22}\Z")
VIDEO=re.compile(r"[A-Za-z0-9_-]{11}\Z")
LIMIT=512_000

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def channel_id(source):
    if not isinstance(source,str):
        return None
    p=urlsplit(source)
    if p.scheme!="https" or p.hostname not in ("youtube.com","www.youtube.com") or p.query or p.fragment or p.username or p.password:
        return None
    try:
        if p.port is not None:
            return None
    except ValueError:
        return None
    path=p.path.strip("/").split("/")
    if len(path)!=2 or path[0]!="channel" or not CHANNEL.fullmatch(path[1]):
        return None
    return path[1]

def feed_channels(catalog, discovered):
    result={}
    for row in accounts(catalog,discovered):
        if row["platform"]=="YouTube":
            ident=channel_id(row["source"])
            if ident:
                result[ident]={"channel_id":ident,"creator":row["handle"],
                               "source":"https://www.youtube.com/channel/"+ident}
    return sorted(result.values(),key=lambda x:x["channel_id"])

def parse_feed(payload, expected_channel_id, today, max_age_days=60):
    if not isinstance(payload,bytes) or len(payload)>LIMIT:
        raise ValueError("Feed too large")
    if not CHANNEL.fullmatch(expected_channel_id):
        raise ValueError("Invalid channel")
    today=dt.date.fromisoformat(today)
    root=ET.fromstring(payload)
    if root.tag!=ATOM+"feed" or root.findtext(YT+"channelId")!=expected_channel_id:
        raise ValueError("YouTube feed channel identity mismatch")
    seen=set()
    result=[]
    for entry in root.findall(ATOM+"entry")[:30]:
        vid=entry.findtext(YT+"videoId")
        author=entry.findtext(YT+"channelId")
        raw_date=entry.findtext(ATOM+"published")
        title=entry.findtext(ATOM+"title")
        if not (isinstance(vid,str) and VIDEO.fullmatch(vid)
                and author==expected_channel_id and raw_date
                and isinstance(title,str) and 0<len(title.strip())<=200 and vid not in seen):
            continue
        try:
            published=dt.datetime.fromisoformat(raw_date.replace("Z","+00:00"))
            if published.tzinfo is None:
                continue
            age=(today-published.astimezone(dt.timezone.utc).date()).days
        except ValueError:
            continue
        if age<0 or age>max_age_days:
            continue
        seen.add(vid)
        result.append({"video_id":vid,"url":"https://www.youtube.com/watch?v="+vid,
                       "published_at":published.astimezone(dt.timezone.utc).isoformat(),
                       "title":title.strip(),"review_type":"metadata_only",
                       "frames_inspected":0,"verified_vertical":False,
                       "follower_count":None,"visual_quality_score":None})
    return result

def scan(catalog, discovered, today, limit=8, downloader=None):
    if type(limit) is not int or not 1<=limit<=20:
        raise ValueError("Invalid scan budget")
    civil=dt.date.fromisoformat(today)
    known=feed_channels(catalog,discovered)
    week=civil.isocalendar()
    start=(week.year*53+week.week)%len(known) if known else 0
    selected=(known[start:]+known[:start])[:limit]
    result={"version":1,"date":today,"kind":"public_metadata_discovery",
            "known_public_youtube_channels":len(known),"scanned":0,
            "newest_public_video_candidates":[],"unavailable":[],
            "direct_frame_reviews":0,"automatic_renderer_changes":False}
    opener=urllib.request.build_opener(NoRedirect())
    def fetch(channel):
        url="https://www.youtube.com/feeds/videos.xml?channel_id="+channel["channel_id"]
        req=urllib.request.Request(url,headers={"Accept":"application/atom+xml",
            "User-Agent":"UMBRAL-VisualRadar/1.0 (public Atom metadata only)"})
        with opener.open(req,timeout=20) as response:
            return response.read(LIMIT+1)
    downloader=downloader or fetch
    for channel in selected:
        try:
            items=parse_feed(downloader(channel),channel["channel_id"],today)
            result["scanned"]+=1
            result["newest_public_video_candidates"].extend(
                [{**x,"creator":channel["creator"],"channel_id":channel["channel_id"]}
                 for x in items])
        except (ValueError,OSError,ET.ParseError,urllib.error.URLError) as exc:
            result["unavailable"].append({"channel_id":channel["channel_id"],
                                          "reason":type(exc).__name__})
    result["newest_public_video_candidates"].sort(
        key=lambda x:(x["published_at"],x["video_id"]),reverse=True)
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--today",required=True)
    parser.add_argument("--limit",type=int,default=8)
    args=parser.parse_args()
    result=scan(json.loads(CATALOG.read_text(encoding="utf-8")),
                json.loads((RADAR/"accounts_new.json").read_text(encoding="utf-8")),
                args.today,args.limit)
    print("UMBRAL3_PUBLIC_FEED="+json.dumps(result,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
