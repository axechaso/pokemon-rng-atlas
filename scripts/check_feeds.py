#!/usr/bin/env python3
"""Find new Hatena RSS/Atom article *candidates*, without reposting source content.
Does not publish candidates automatically: human verification/classification is required.
Run: python scripts/check_feeds.py
"""
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SOURCES = json.loads((BASE/'data/sources.json').read_text(encoding='utf-8'))
ARTICLES = json.loads((BASE/'data/articles.json').read_text(encoding='utf-8'))
CANDIDATES_PATH = BASE/'data/discovery_candidates.json'
CANDIDATES = json.loads(CANDIDATES_PATH.read_text(encoding='utf-8')) if CANDIDATES_PATH.exists() else []
KNOWN = {a['url'].rstrip('/').split('?')[0] for a in ARTICLES}
KNOWN.update((a['url'].rstrip('/').split('?')[0] for a in CANDIDATES))
TERMS = re.compile('乱数|RNG|Seed|シード|孵化|徘徊|ID調整|メソッド|LCG|MT19937|Timer0|色固定|ポケモン.{0,20}解析',re.I)
UA = 'PokemonRNGAtlasSourceIndex/0.1 (RSS titles and links only; contact repository maintainer)'


def txt(element, tag):
    e = element.find(tag)
    return (e.text or '').strip() if e is not None else ''


def entries_from_xml(xml_content):
    root = ET.fromstring(xml_content)
    if root.tag.endswith('feed'):  # Atom
        ns={'a':'http://www.w3.org/2005/Atom'}
        for entry in root.findall('a:entry',ns):
            link = next((e.attrib.get('href','') for e in entry.findall('a:link',ns) if e.attrib.get('rel','alternate')=='alternate'),None)
            if not link:
                link=next((e.attrib.get('href','') for e in entry.findall('a:link',ns)), '')
            yield {'title':txt(entry,'{http://www.w3.org/2005/Atom}title'), 'url':link,
                   'published':txt(entry,'{http://www.w3.org/2005/Atom}published') or txt(entry,'{http://www.w3.org/2005/Atom}updated')}
    else:  # RSS 2
        for entry in root.findall('.//item'):
            yield {'title':txt(entry,'title'),'url':txt(entry,'link'),'published':txt(entry,'pubDate')}


new=[]
for source in SOURCES:
    try:
        request=urllib.request.Request(source['feed'],headers={'User-Agent':UA})
        with urllib.request.urlopen(request,timeout=20) as response:
            feed=response.read(2_000_000)
        n=0
        for item in entries_from_xml(feed):
            url=item['url'].rstrip('/').split('?')[0]
            if not (url.startswith('https://') and TERMS.search(item['title'])) or url in KNOWN:
                continue
            c={'title':item['title'],'url':url,'published_raw':item['published'],
                'source':source['name'],'discovered_on':datetime.now(timezone.utc).date().isoformat(),
                'review_status':'待核实（未公开）'}
            new.append(c)
            KNOWN.add(url)
            n+=1
        print(f"{source['name']}: {n} new candidate(s)")
    except (OSError,urllib.error.URLError,ET.ParseError) as e:
        print(f"[WARN] {source['name']}: unable to inspect feed: {type(e).__name__}: {e}")

if new:
    CANDIDATES.extend(new)
    CANDIDATES.sort(key=lambda item:item['discovered_on'],reverse=True)
    CANDIDATES_PATH.write_text(json.dumps(CANDIDATES,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f'Done. New candidates: {len(new)}. Total pending/listed: {len(CANDIDATES)}.')
