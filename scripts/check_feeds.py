#!/usr/bin/env python3
"""Bounded Hatena discovery and revision monitoring; never publishes articles."""
import argparse
import hashlib
import html
import http.client
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
UA = 'PokemonRNGAtlasMonitor/1.0 (+https://github.com/axechaso/pokemon-rng-atlas)'
EXTRACTOR = 'hatena-entry-v1'
RNG = re.compile(r'乱数調整|乱数消費|乱数解析|初期.?seed|ID調整|裏ID|Timer0|LCG|MT19937|RNG|メソッド|(?:固定|孵化|徘徊|野生|捕獲).{0,16}乱数|乱数.{0,16}(?:固定|孵化|徘徊|野生|捕獲)', re.I)
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
BLOCKS = {'p', 'div', 'section', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'pre', 'tr', 'blockquote', 'br', 'hr'}
IGNORE = {'script', 'style', 'noscript', 'iframe', 'nav', 'footer', 'form', 'button', 'ins'}
IGNORE_CLASS = re.compile(r'(?:^|[\s_-])(?:ads?|adsbygoogle|share|social|comments?|entry-footer|table-of-contents)(?:$|[\s_-])', re.I)
FETCH_ERRORS = (OSError, ValueError, ET.ParseError, http.client.HTTPException)


def load(relative, default):
    path = BASE / relative
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def save(relative, value):
    path = BASE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def normalize(value):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', value)).strip()


def hatena_host(host):
    return bool(host and (re.fullmatch(r'[a-z0-9_-]+\.(?:hatenablog\.(?:com|jp)|hatenadiary\.(?:com|jp|org))', host) or host == 'd.hatena.ne.jp'))


def allowed_url(url):
    parts = urllib.parse.urlsplit(url)
    return parts.scheme == 'https' and not parts.username and not parts.password and parts.port in (None, 443) and (hatena_host(parts.hostname) or parts.hostname == 'b.hatena.ne.jp')


def canonical(url):
    try:
        parts = urllib.parse.urlsplit(html.unescape(url))
        host = (parts.hostname or '').lower()
        if not hatena_host(host) or parts.scheme not in ('http', 'https') or parts.username or parts.password or parts.port not in (None, 80, 443):
            return ''
        path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe='/~:@!$&\'()*+,;=-._')
        query = urllib.parse.urlencode([(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in {'fbclid', 'gclid', 'ref', 'referrer'}])
        return urllib.parse.urlunsplit(('https', host, path.rstrip('/') or '/', query, ''))
    except ValueError:
        return ''


def article_url(url):
    url = canonical(url)
    if not url:
        return ''
    parts = urllib.parse.urlsplit(url)
    if parts.hostname == 'd.hatena.ne.jp':
        return url if re.match(r'^/[^/]+/\d{8}(?:/[^/]+)?$', parts.path) else ''
    return url if parts.path.startswith('/entry/') else ''


def homepage(url):
    parts = urllib.parse.urlsplit(canonical(url))
    suffix = parts.path.strip('/').split('/')[0] + '/' if parts.hostname == 'd.hatena.ne.jp' else ''
    return f'https://{parts.netloc}/' + suffix


def entries_from_xml(data):
    """Atom, RSS2 and RSS1/RDF; a bookmark's dc:date is not publication time."""
    root = ET.fromstring(data)
    if root.tag.rsplit('}', 1)[-1].lower() not in ('feed', 'rss', 'rdf'):
        raise ValueError('response is not an Atom/RSS feed')
    for item in root.iter():
        if item.tag.rsplit('}', 1)[-1] not in ('entry', 'item'):
            continue
        values = {}
        for child in item:
            key = child.tag.rsplit('}', 1)[-1]
            value = normalize(''.join(child.itertext()))
            if key == 'link':
                if child.attrib.get('rel', 'alternate') == 'alternate':
                    values['url'] = child.attrib.get('href') or value
            elif key in ('title', 'published', 'updated', 'pubDate', 'date'):
                values[key] = value
        yield {'title': values.get('title', ''), 'url': values.get('url', ''),
               'published_raw': values.get('published') or values.get('pubDate', ''),
               'source_updated_raw': values.get('updated', ''), 'index_date_raw': values.get('date', '')}


class EntryParser(HTMLParser):
    """Extract entry-content only. Keep hashes, never store the article text."""
    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url = url
        self.stack = []
        self.body_depth = None
        self.title_depth = None
        self.title_bits = []
        self.blocks = []
        self.bits = []
        self.links = []
        self.media = []
        self.metadata = {}
        self.json_bits = None
        self.anchor = None
        self.anchors = []
        self.body_roots = 0

    def flush(self):
        raw = ''.join(self.bits)
        if any(tag == 'pre' for tag, ignored in self.stack):
            value = '\n'.join(line.rstrip() for line in unicodedata.normalize('NFC', raw).splitlines()).strip('\n')
        else:
            value = normalize(raw)
        if value:
            self.blocks.append(value)
        self.bits = []

    def active(self):
        return self.body_depth is not None and not any(ignored for tag, ignored in self.stack[self.body_depth - 1:])

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get('class', '')
        if tag == 'meta':
            name = attrs.get('property', attrs.get('name', ''))
            if name in ('article:published_time', 'article:modified_time', 'og:title'):
                self.metadata[name] = attrs.get('content', '')
        if tag == 'script' and attrs.get('type') == 'application/ld+json':
            self.json_bits = []
        if tag == 'h1' and 'entry-title' in classes.split():
            self.title_depth = len(self.stack) + 1
        # Hatena's dormant-blog ad also uses entry-content, without hatenablog-entry.
        if {'entry-content', 'hatenablog-entry'} <= set(classes.split()) and self.body_depth is None:
            self.body_depth = len(self.stack) + 1
            self.body_roots += 1
        if self.active() and tag in BLOCKS:
            self.flush()
        ignored = tag in IGNORE or bool(IGNORE_CLASS.search(classes))
        if tag not in VOID:
            self.stack.append((tag, ignored))
        if tag == 'a':
            self.anchor = {'url': urllib.parse.urljoin(self.url, attrs.get('href', '')), 'bits': [], 'in_body': self.active()}
            if self.active():
                target = self.anchor['url']
                if urllib.parse.urlsplit(target).scheme in ('http', 'https') and not attrs.get('href', '').startswith('#'):
                    self.links.append(target)
        if self.active() and tag in ('img', 'video', 'audio', 'source'):
            target = attrs.get('src') or attrs.get('data-src')
            if target:
                self.media.append(urllib.parse.urljoin(self.url, target))
            if attrs.get('alt'):
                self.bits.append(' [image: ' + attrs['alt'] + '] ')

    def handle_endtag(self, tag):
        if tag == 'script' and self.json_bits is not None:
            try:
                self.read_metadata(json.loads(''.join(self.json_bits)))
            except (ValueError, TypeError):
                pass
            self.json_bits = None
        if tag == 'a' and self.anchor:
            self.anchors.append({'url': self.anchor['url'], 'title': normalize(''.join(self.anchor['bits'])), 'in_body': self.anchor['in_body']})
            self.anchor = None
        index = next((i for i in range(len(self.stack) - 1, -1, -1) if self.stack[i][0] == tag), None)
        if index is None:
            return
        if self.active() and tag in BLOCKS:
            self.flush()
        if self.body_depth is not None and index < self.body_depth:
            self.flush()
            self.body_depth = None
        if self.title_depth is not None and index < self.title_depth:
            self.title_depth = None
        del self.stack[index:]

    def handle_data(self, data):
        if self.json_bits is not None:
            self.json_bits.append(data)
        if self.title_depth is not None:
            self.title_bits.append(data)
        if self.anchor:
            self.anchor['bits'].append(data)
        if self.active():
            self.bits.append(data)

    def read_metadata(self, data):
        if isinstance(data, list):
            for item in data:
                self.read_metadata(item)
        if isinstance(data, dict):
            if data.get('@type') in ('Article', 'BlogPosting'):
                for name in ('datePublished', 'dateModified', 'headline'):
                    if isinstance(data.get(name), str):
                        self.metadata[name] = data[name]
            if '@graph' in data:
                self.read_metadata(data['@graph'])

    def snapshot(self, now):
        self.flush()
        title = normalize(''.join(self.title_bits)) or self.metadata.get('headline') or self.metadata.get('og:title', '')
        length = sum(map(len, self.blocks))
        if self.body_roots != 1 or length < 100 or not title:
            raise ValueError(f'no unambiguous article body (roots={self.body_roots}, characters={length})')
        block_hashes = [digest(block) for block in self.blocks]
        links, media = sorted(set(self.links)), sorted(set(self.media))
        return {'observed_at': now, 'extractor': EXTRACTOR, 'title': title,
                'published_raw': self.metadata.get('datePublished') or self.metadata.get('article:published_time', ''),
                'source_updated_raw': self.metadata.get('dateModified') or self.metadata.get('article:modified_time', ''),
                'text_length': length, 'body_sha256': digest('\n'.join(block_hashes)), 'block_hashes': block_hashes,
                'links_sha256': digest('\n'.join(links)), 'link_hashes': [digest(link) for link in links],
                'media_sha256': digest('\n'.join(media)), 'media_hashes': [digest(link) for link in media]}


def signature(snapshot):
    fields = ('extractor', 'title', 'body_sha256', 'links_sha256', 'media_sha256', 'published_raw', 'source_updated_raw')
    return digest(json.dumps({key: snapshot.get(key, '') for key in fields}, sort_keys=True, ensure_ascii=False))


class LimitReached(Exception):
    pass


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise ValueError('redirect outside allowed public Hatena hosts')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Fetcher:
    def __init__(self, limit, delay):
        self.limit, self.delay = limit, delay
        self.count = 0
        self.deadline = time.monotonic() + 14 * 60
        self.last, self.robots, self.robot_errors = {}, {}, {}
        self.host_delays = {}
        self.events = []
        self.opener = urllib.request.build_opener(SafeRedirect())

    def request(self, url, headers=None):
        if not allowed_url(url):
            raise ValueError('URL outside allowed public Hatena hosts')
        if self.count >= self.limit or time.monotonic() >= self.deadline:
            raise LimitReached('request/time budget reached')
        host = urllib.parse.urlsplit(url).netloc
        delay = max(0, self.host_delays.get(host, self.delay) - (time.monotonic() - self.last.get(host, 0)))
        if delay > 30:
            raise ValueError('robots crawl delay exceeds this run\'s per-request wait budget')
        if time.monotonic() + delay >= self.deadline:
            raise LimitReached('time budget reached before host crawl delay')
        if delay:
            time.sleep(delay)
        self.count += 1
        self.last[host] = time.monotonic()
        request = urllib.request.Request(url, headers={'User-Agent': UA, **(headers or {})})
        try:
            with self.opener.open(request, timeout=20) as response:
                data = response.read(3_000_001)
                if len(data) > 3_000_000:
                    raise ValueError('response exceeds 3 MB limit')
                return data, response.headers, response.url
        except urllib.error.HTTPError as error:
            if error.code == 304:
                return None, error.headers, url
            raise

    def get(self, url, headers=None):
        parts = urllib.parse.urlsplit(url)
        origin = f'{parts.scheme}://{parts.netloc}'
        if origin in self.robot_errors:
            raise ValueError(self.robot_errors[origin])
        if origin not in self.robots:
            try:
                robot_data, _, _ = self.request(origin + '/robots.txt')
            except urllib.error.HTTPError as error:
                if error.code in (404, 410):
                    robot_data = b''
                else:
                    self.robot_errors[origin] = f'robots.txt unavailable: HTTP {error.code}'
                    raise
            except (OSError, ValueError) as error:
                self.robot_errors[origin] = f'robots.txt unavailable: {error}'[:350]
                raise
            robot = urllib.robotparser.RobotFileParser()
            robot.parse(robot_data.decode('utf-8', 'replace').splitlines())
            self.robots[origin] = robot
            self.host_delays[parts.netloc] = max(self.delay, robot.crawl_delay(UA) or 0)
        if not self.robots[origin].can_fetch(UA, url):
            raise ValueError('robots.txt disallows this path')
        return self.request(url, headers)

    def record(self, channel, url, count=0, error=None):
        event = {'channel': channel, 'url': url, 'status': 'error' if error else 'ok', 'items': count}
        if error:
            event['error'] = f'{type(error).__name__}: {error}'[:350]
        self.events.append(event)
        print(f"[{event['status']}] {channel}: {url} ({event.get('error', count)})", flush=True)


def report(now, candidates, revisions, state, fetcher, articles):
    pending = [item for item in candidates if item['review_status'] == 'pending']
    changes = [item for item in revisions if item['review_status'] == 'pending']
    supported = [item for item in articles if article_url(item['url'])]
    good = sum(bool(state['pages'].get(canonical(item['url']), {}).get('baseline')) for item in supported)
    errors = [event for event in fetcher.events if event['status'] == 'error']
    unresolved = []
    for channel, records in [('revision', state['pages']), ('blog-feed', state['feeds']), ('blog-archive', state['archives'])]:
        for url, record in records.items():
            if record.get('last_error'):
                unresolved.append({'channel': channel, 'url': url, **record['last_error']})
    for candidate in pending:
        if candidate.get('last_error'):
            unresolved.append({'channel': 'candidate-verify', 'url': candidate['url'], **candidate['last_error']})
    summary = {'generated_at': now, 'scope': 'Hatena only; cross-blog queries and bounded crawling, not an exhaustive index',
               'requests': fetcher.count, 'request_limit': fetcher.limit, 'pending_articles': len(pending),
               'pending_revisions': len(changes), 'hatena_articles': len(supported), 'baselines': good,
               'outside_revision_scope': len(articles) - len(supported), 'errors': len(errors),
               'channels': fetcher.events, 'unresolved_errors': unresolved, 'limits_reached': state['run']['limits_reached']}
    save('reports/discovery-run.json', summary)
    def label(value):
        return normalize(str(value)).replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]').replace('|', '\\|').replace('<', '&lt;').replace('>', '&gt;')
    def link(value, url):
        return f'[{label(value)}](<{url}>)'
    lines = ['# Hatena 待审核更新清单', '', f'抓取时间（UTC）：{now}', '',
             '> 自动发现的线索，尚未核实语言、主题、作者和日期。只有人工写入 articles.json 才会公开为资料卡。', '',
             f'- 待审新来源：{len(pending)}；待审原文变化：{len(changes)}。',
             f'- 已收录 Hatena 原文：{len(supported)}；已有正文基线：{good}。首次基线不算修订。',
             f'- 其他 {len(articles) - len(supported)} 条来源暂不监测正文修订（含其他网站、GitHub、YouTube、X）。',
             f'- 本次请求：{fetcher.count}/{fetcher.limit}；获取或解析失败：{len(errors)}。',
             '- 发现通道：Hatena Bookmark 跨博客搜索（近期／历史热门）、博客 Feed、正文引用、轮换归档页。',
             '- 搜索索引、排名、Feed 留存和请求预算限制覆盖范围，不能穷尽整个平台；未抓到不代表没有更新。',
             '- 原站 updated、HTTP Last-Modified 与发现时间分别保留，均不冒充发表时间；书签日期只记索引时间。', '',
             '## 本次覆盖与失败', '', '| 通道 | 成功请求 | 失败请求 |', '| --- | ---: | ---: |']
    for channel in sorted({event['channel'] for event in fetcher.events}):
        events = [event for event in fetcher.events if event['channel'] == channel]
        lines.append(f"| {channel} | {sum(event['status'] == 'ok' for event in events)} | {sum(event['status'] == 'error' for event in events)} |")
    if summary['limits_reached']:
        lines += ['', '**达到预算，未处理的项目将在后续轮次继续：** ' + label(', '.join(summary['limits_reached']))]
    for event in errors:
        lines += ['', f"- {link(event['channel'], event['url'])}：{label(event['error'])}"]
    if unresolved:
        lines += ['', '### 尚未恢复的获取问题（含之前轮次）', '']
        for event in unresolved:
            lines.append(f"- {link(event['channel'], event['url'])} · {label(event['at'])}：{label(event['message'])}")
    lines += ['', '## 原文变化（需核实，不等于技术结论已修正）', '']
    if not changes:
        lines.append('暂无待审变化。首次抓取仅建立基线；失败页面保留已有基线。')
    for item in changes:
        lines += [f"### {label(item['id'])} · {label(item['after']['title'])}", '', link('原文', item['url']), '',
                  f"- 首次检测：{item['first_detected_at']}；最近确认：{item['last_seen_at']}。",
                  f"- 变化字段：{label(', '.join(item['changed_fields']))}；段落增／删 {item['delta']['blocks_added']}/{item['delta']['blocks_removed']}。",
                  f"- 正文链接增／删 {item['delta']['links_added']}/{item['delta']['links_removed']}；图片等媒体地址增／删 {item['delta']['media_added']}/{item['delta']['media_removed']}。",
                  f"- 标题：{label(item['before']['title'])} → {label(item['after']['title'])}。",
                  f"- 字符数：{item['before']['text_length']} → {item['after']['text_length']}。",
                  f"- 原站更新时间：{label(item['before'].get('source_updated_raw') or '未注明')} → {label(item['after'].get('source_updated_raw') or '未注明')}。",
                  f"- 正文 SHA-256：`{item['before']['body_sha256']}` → `{item['after']['body_sha256']}`。",
                  '- 核对原文与本站摘要、工具条件和相关研究后，用 README 中的审核命令确认。重复运行不会清除待审变化。', '']
    lines += ['', '## 新来源候选', '']
    if not pending:
        lines.append('暂无待审新来源。')
    for item in pending:
        lines += [f"### {label(item['title'])}", '', link('原文', item['url']), '',
                  f"- 首次发现：{item['discovered_on']}；来源博客：{label(item['source'])}。",
                  f"- 发现依据：{label('; '.join(v['channel'] + ' · ' + v['url'] for v in item['discovered_via']))}。",
                  f"- 原文发表元数据：{label(item.get('published_raw') or '尚未取得')}；原站更新时间：{label(item.get('source_updated_raw') or '尚未取得')}。",
                  f"- 状态：{label(item.get('verification', '未抓取正文；待核实'))}。", '']
        if re.match(r'^\d{4}-\d{2}-\d{2}', item.get('published_raw', '')) and item['published_raw'][:10] > now[:10]:
            lines += ['- **原站使用未来置顶日期，真实发表日期待核实。**', '']
    lines += ['## 审核规则', '',
              '1. 打开原文确认宝可梦 RNG 相关性、非中文原文、作者、版本、实机／模拟器条件与发布日期。未来置顶日期不能当作真实发表日期。',
              '2. 检查是否已收录、工具迁移或原作者后续修正；独立撰写中文摘要并指定四级分类。未经授权不发布全文译文。',
              '3. 收录后编辑 data/articles.json；不合适的候选在 discovery_candidates.json 将 review_status 改为 dismissed 并填写 review_note，保留去重记录。',
              '4. 正文指纹不含原文全文，不提供逐字差异；哈希变化只触发复核，不能证明作者修改了技术结论。', '']
    (BASE / 'reports/discovery-review.md').write_text('\n'.join(lines), encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backfill', action='store_true', help='inspect additional rotating archives and candidates')
    parser.add_argument('--request-limit', type=int, default=180)
    parser.add_argument('--accept-revision', metavar='ID', help='acknowledge a pending revision; does not edit the article index')
    parser.add_argument('--note', default='')
    args = parser.parse_args()
    if not 20 <= args.request_limit <= 300:
        parser.error('--request-limit must be between 20 and 300')
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    config = load('data/discovery_config.json', {})
    articles = load('data/articles.json', [])
    sources = load('data/sources.json', [])
    candidates = load('data/discovery_candidates.json', [])
    revisions = load('data/revision_candidates.json', [])
    state = load('data/source_watch_state.json', {'version': 1, 'pages': {}, 'feeds': {}, 'archives': {}})
    registry = load('data/discovery_sources.json', {})
    if args.accept_revision:
        item = next((item for item in revisions if item['id'] == args.accept_revision), None)
        if not item or item['review_status'] != 'pending' or not args.note.strip():
            parser.error('a pending revision ID and a nonempty --note are required')
        item.update(review_status='reviewed', reviewed_at=now, review_note=args.note.strip())
        page = state['pages'].get(item['url'], {})
        if page.get('latest') and signature(page['latest']) == signature(item['after']):
            page['baseline'] = page['latest']
        save('data/revision_candidates.json', revisions)
        save('data/source_watch_state.json', state)
        print('Revision acknowledged. Re-run discovery to refresh the report; update articles.json separately if needed.')
        return 0
    known = {canonical(item['url']): item for item in articles if article_url(item['url'])}
    known_aliases = {url: url for url in known}
    for url, page in state['pages'].items():
        if url in known and article_url(page.get('final_url', '')):
            known_aliases[canonical(page['final_url'])] = url
    by_url = {canonical(item['url']): item for item in candidates}
    fetcher = Fetcher(args.request_limit, config.get('host_delay_seconds', 1.0))
    state['run'] = {'started_at': now, 'limits_reached': []}
    stats = Counter()

    def register(url, via, name=''):
        home = homepage(url)
        if home not in registry:
            registry[home] = {'name': name or urllib.parse.urlsplit(home).hostname, 'homepage': home,
                              'feed': home + ('rss' if urllib.parse.urlsplit(home).hostname == 'd.hatena.ne.jp' else 'feed'),
                              'discovered_at': now, 'discovered_via': via}

    def offer(item, channel, via):
        url = article_url(item.get('url', ''))
        title = normalize(item.get('title', ''))
        if not url or (channel != 'article-reference' and not RNG.search(title)):
            return
        title = title or '原标题待核实（正文引用线索）'
        register(url, via)
        if url in known_aliases:
            return
        evidence = {'channel': channel, 'url': via}
        if url in by_url:
            candidate = by_url[url]
            if evidence not in candidate['discovered_via']:
                candidate['discovered_via'].append(evidence)
            candidate['last_seen_at'] = now
            return
        candidate = {'title': title, 'url': url, 'source': urllib.parse.urlsplit(url).hostname,
                     'published_raw': item.get('published_raw', ''), 'source_updated_raw': item.get('source_updated_raw', ''),
                     'discovered_on': now[:10], 'last_seen_at': now, 'discovered_via': [evidence],
                     'review_status': 'pending', 'verification': '仅标题线索；语言、主题、作者和日期待核实'}
        if channel == 'bookmark-search':
            candidate['published_raw'] = ''
            candidate['bookmark_indexed_raw'] = item.get('index_date_raw', '')
        by_url[url] = candidate
        candidates.append(candidate)
        stats['new_candidates'] += 1

    for source in sources:
        register(source['homepage'], 'data/sources.json', source['name'])
        registry[homepage(source['homepage'])]['feed'] = source['feed']
    for url in known:
        register(url, 'data/articles.json')
    for candidate in candidates:
        candidate.setdefault('discovered_via', [{'channel': 'legacy-feed', 'url': candidate.get('source', '')}])
        if candidate.get('review_status', '').startswith('待核实'):
            candidate['review_status'] = 'pending'
        if canonical(candidate['url']) in known:
            candidate['review_status'] = 'published'

    def inspect(url, monitor):
        page = state['pages'].setdefault(url, {}) if monitor else by_url[url]
        page['last_attempt_at'] = now
        headers = {}
        if monitor and page.get('latest', {}).get('extractor') == EXTRACTOR:
            for field, header in [('etag', 'If-None-Match'), ('last_modified', 'If-Modified-Since')]:
                if page.get(field):
                    headers[header] = page[field]
        channel = 'revision' if monitor else 'candidate-verify'
        try:
            data, response_headers, final_url = fetcher.get(url, headers)
            if data is None:
                page['checked_at'] = now
                page.pop('last_error', None)
                fetcher.record(channel, url)
                return
            if not article_url(final_url):
                raise ValueError('redirected to a non-article page')
            document = EntryParser(final_url)
            document.feed(data.decode(response_headers.get_content_charset() or 'utf-8', 'replace'))
            snapshot = document.snapshot(now)
            for anchor in document.anchors:
                if anchor['in_body'] and article_url(anchor['url']):
                    offer(anchor, 'article-reference', url)
            if monitor:
                known_aliases[canonical(final_url)] = url
                previous = page.get('latest')
                if not previous or previous.get('extractor') != EXTRACTOR:
                    page['baseline'] = snapshot
                    stats['new_baselines'] += 1
                elif signature(previous) != signature(snapshot):
                    changed = [name for name in ('title', 'body_sha256', 'links_sha256', 'media_sha256', 'published_raw', 'source_updated_raw') if previous.get(name) != snapshot.get(name)]
                    delta = {}
                    for name, field in [('blocks', 'block_hashes'), ('links', 'link_hashes'), ('media', 'media_hashes')]:
                        before, after = Counter(previous[field]), Counter(snapshot[field])
                        delta[name + '_added'] = sum((after - before).values())
                        delta[name + '_removed'] = sum((before - after).values())
                    revision_id = digest(url + signature(previous) + signature(snapshot) + previous['observed_at'])[:16]
                    revisions.append({'id': revision_id, 'url': url, 'article_id': known[url]['id'],
                                      'first_detected_at': now, 'last_seen_at': now, 'review_status': 'pending',
                                      'changed_fields': changed, 'delta': delta, 'before': previous, 'after': snapshot})
                    stats['new_revisions'] += 1
                for revision in revisions:
                    if revision['url'] == url and signature(revision['after']) == signature(snapshot):
                        revision['last_seen_at'] = now
                page.update(latest=snapshot, checked_at=now, final_url=final_url,
                            etag=response_headers.get('ETag', ''), last_modified=response_headers.get('Last-Modified', ''))
                page.pop('last_error', None)
            else:
                page.update(title=snapshot['title'], published_raw=snapshot['published_raw'],
                            source_updated_raw=snapshot['source_updated_raw'], verified_at=now,
                            final_url=canonical(final_url),
                            verification='已获取原站正文与日期元数据；语言、相关性与技术结论仍待人工核实')
                if canonical(final_url) in known_aliases:
                    page.update(review_status='published', duplicate_of=known_aliases[canonical(final_url)],
                                verification='已收录原文的跳转别名；保留发现记录，不重复收录')
                else:
                    duplicate = next((candidate for candidate in candidates if candidate is not page and
                                      (candidate['url'] == canonical(final_url) or candidate.get('final_url') == canonical(final_url)) and
                                      candidate['review_status'] != 'duplicate'), None)
                    if duplicate:
                        page.update(review_status='duplicate', duplicate_of=duplicate['url'])
                page.pop('last_error', None)
                if snapshot['published_raw'][:10] > now[:10]:
                    page['verification'] += '；原站使用未来日期，需查明真实发表时间'
            fetcher.record(channel, url, len(document.blocks))
        except LimitReached:
            raise
        except FETCH_ERRORS as error:
            page['last_error'] = {'at': now, 'message': f'{type(error).__name__}: {error}'[:350]}
            fetcher.record(channel, url, error=error)

    # Published articles have priority; rotate by last attempt to avoid starvation.
    try:
        for url in sorted(known, key=lambda url: (state['pages'].get(url, {}).get('last_attempt_at', ''), url)):
            inspect(url, True)
    except LimitReached:
        state['run']['limits_reached'].append('revision')

    for query in config.get('searches', []):
        url = 'https://b.hatena.ne.jp/q/' + urllib.parse.quote(query['query'], safe='') + '?' + urllib.parse.urlencode({'mode': 'rss', 'target': 'title', 'sort': query['sort'], 'users': '1', 'date_range': 'all', 'safe': 'on'})
        try:
            data, _, _ = fetcher.get(url)
            items = list(entries_from_xml(data))
            for item in items:
                offer(item, 'bookmark-search', url)
            fetcher.record('bookmark-search', url, len(items))
        except LimitReached:
            state['run']['limits_reached'].append('bookmark-search')
            break
        except FETCH_ERRORS as error:
            fetcher.record('bookmark-search', url, error=error)

    feeds = sorted((source for source in registry.values() if source.get('enabled', True)), key=lambda source: (state['feeds'].get(source['homepage'], {}).get('last_attempt_at', ''), source['homepage']))
    for source in feeds[:config.get('feeds_per_run', 24)]:
        home, url = source['homepage'], source['feed']
        record = state['feeds'].setdefault(home, {})
        try:
            record['last_attempt_at'] = now
            data, _, _ = fetcher.get(url)
            items = list(entries_from_xml(data))
            for item in items:
                offer(item, 'blog-feed', url)
            record['checked_at'] = now
            record.pop('last_error', None)
            fetcher.record('blog-feed', url, len(items))
        except LimitReached:
            state['run']['limits_reached'].append('blog-feed')
            break
        except FETCH_ERRORS as error:
            record['last_error'] = {'at': now, 'message': str(error)[:350]}
            fetcher.record('blog-feed', url, error=error)

    # Crawl archive titles, not every sitemap URL. One page per blog per run.
    archives = sorted((source for source in registry.values() if source.get('enabled', True)), key=lambda source: (state['archives'].get(source['homepage'], {}).get('last_attempt_at', ''), source['homepage']))
    for source in archives[:config.get('archive_pages_per_run', 8) * (2 if args.backfill else 1)]:
        home = source['homepage']
        record = state['archives'].setdefault(home, {'next_page': 1})
        page_number = record['next_page']
        url = home + 'archive?page=' + str(page_number)
        try:
            record['last_attempt_at'] = now
            data, headers, final = fetcher.get(url)
            if homepage(final) != home:
                raise ValueError('archive redirected to a different blog')
            document = EntryParser(final)
            document.feed(data.decode(headers.get_content_charset() or 'utf-8', 'replace'))
            links = [anchor for anchor in document.anchors if article_url(anchor['url']) and homepage(anchor['url']) == home]
            for item in links:
                offer(item, 'blog-archive', url)
            page_hash = digest('\n'.join(sorted(set(article_url(item['url']) for item in links))))
            record['next_page'] = page_number + 1 if links and page_hash != record.get('last_page_hash') else 1
            record.update(checked_at=now, last_page_hash=page_hash)
            record.pop('last_error', None)
            fetcher.record('blog-archive', url, len(links))
        except LimitReached:
            state['run']['limits_reached'].append('blog-archive')
            break
        except FETCH_ERRORS as error:
            record['last_error'] = {'at': now, 'message': str(error)[:350]}
            fetcher.record('blog-archive', url, error=error)

    pending = sorted([item for item in candidates if item['review_status'] == 'pending'], key=lambda item: (item.get('last_attempt_at', ''), item['url']))
    candidate_limit = config.get('candidate_pages_per_run', 12) * (2 if args.backfill else 1)
    retries = sorted((item for item in pending if item.get('last_error')), key=lambda item: item.get('last_attempt_at', ''))[:candidate_limit // 3]
    selected = (retries + [item for item in pending if item not in retries])[:candidate_limit]
    for item in selected:
        try:
            inspect(item['url'], False)
        except LimitReached:
            state['run']['limits_reached'].append('candidate-verify')
            break
    state['run'].update(finished_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(), **stats)
    candidates.sort(key=lambda item: (item['discovered_on'], item['url']), reverse=True)
    summary = report(now, candidates, revisions, state, fetcher, articles)
    save('data/discovery_candidates.json', candidates)
    save('data/revision_candidates.json', revisions)
    save('data/source_watch_state.json', state)
    save('data/discovery_sources.json', dict(sorted(registry.items())))
    print(json.dumps({**stats, 'requests': fetcher.count, 'errors': summary['errors'], 'pending': summary['pending_articles']}, ensure_ascii=False), flush=True)
    # Partial failures remain visible; an unavailable critical channel fails CI.
    for channel in ('revision', 'bookmark-search'):
        if not any(event['channel'] == channel and event['status'] == 'ok' for event in fetcher.events):
            print(f'ERROR: no successful {channel} requests; preserved state and report.', file=sys.stderr)
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
