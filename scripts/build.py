#!/usr/bin/env python3
"""Dependency-free static-site builder. One canonical article record, many navigation paths."""
import json
import shutil
from collections import Counter, defaultdict
from datetime import date
from html import escape as esc
from pathlib import Path
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ARTICLES = json.loads((ROOT / 'data/articles.json').read_text(encoding='utf-8'))
OUT = ROOT / 'dist'
GEN_ORDER = ['第一世代','第二世代','第三世代','第四世代','第五世代','第六世代','第七世代','第八世代','第九世代']
ENVS = ['实机','模拟器']
LANGUAGES = {'ja': '日文', 'en': '英文', 'it': '意大利语'}
LANGUAGE_KEYWORDS = {'ja': 'Japanese ja', 'en': 'English en', 'it': 'Italian Italiano it'}
SOURCE_TYPES = {'article': '图文指南', 'wiki': 'GitHub Wiki', 'tool': '工具／插件', 'video': 'YouTube 视频', 'post': 'X 帖文'}
SOURCE_KEYWORDS = {'article': 'article guide 图文 教程', 'wiki': 'GitHub Wiki 维基', 'tool': 'GitHub README tool plugin overlay 工具 插件', 'video': 'YouTube video 视频 油管', 'post': 'X Twitter tweet 推特 帖文'}


def source_type(article):
    if article.get('source_type'):
        return article['source_type']
    url = urlsplit(article['url'])
    if url.hostname == 'github.com':
        parts = url.path.strip('/').split('/')
        if len(parts) > 2 and parts[2] == 'wiki':
            return 'wiki'
        if len(parts) == 2:
            return 'tool'
    return 'article'


def text(value):
    return esc(str(value), quote=True)


def path_url(parts):
    return '/'.join(quote(p, safe='') for p in parts) + ('/' if parts else '')


def prefix_for(parts):
    return '../' * len(parts) if parts else './'


def article_link(article, prefix):
    return prefix + path_url(['文章', article['id']])


def date_label(article):
    return article['date'] or '发布日期未注明'


def newest_first(article):
    return article['date'] or ''


def valid(article):
    required = ['id','title','original_title','author','language','url','summary','routes','tags']
    assert all(article.get(field) for field in required), f'Missing article field: {article}'
    assert article['language'] in LANGUAGES, article['id']
    assert source_type(article) in SOURCE_TYPES, article['id']
    assert 'date' in article, article['id']
    if article['date'] is not None:
        assert date.fromisoformat(article['date']).isoformat() == article['date'], article['id']
    assert article['url'].startswith('https://'), article['id']
    assert len(article['routes']) == len({tuple(r) for r in article['routes']}), article['id']
    assert all(len(r) == 4 and r[0] in ENVS and r[1] in GEN_ORDER for r in article['routes'])
    related = article.get('related_sources', [])
    assert isinstance(related, list) and len(related) == len(set(related)), article['id']
    assert all(r in ARTICLE_BY_ID and r != article['id'] for r in related), article['id']

assert len({a['id'] for a in ARTICLES}) == len(ARTICLES), 'Duplicate IDs'
assert len({a['url'].rstrip('/') for a in ARTICLES}) == len(ARTICLES), 'Duplicate sources: merge routes instead'
ARTICLE_BY_ID = {a['id']: a for a in ARTICLES}
for a in ARTICLES: valid(a)
LANGUAGE_COUNTS = Counter(a['language'] for a in ARTICLES)
TYPE_COUNTS = Counter(source_type(a) for a in ARTICLES)
RELATED = defaultdict(set)
for a in ARTICLES:
    for other in a.get('related_sources', []):
        RELATED[a['id']].add(other)
        RELATED[other].add(a['id'])

routes = sorted({tuple(r[:i]) for a in ARTICLES for r in a['routes'] for i in range(1, 5)}, key=lambda x: (ENVS.index(x[0]), GEN_ORDER.index(x[1]) if len(x) > 1 else -1, x[2:]))
counts = Counter(tuple(route) for a in ARTICLES for route in a['routes'])


def matches(article, scope):
    return any(tuple(path[:len(scope)]) == tuple(scope) for path in article['routes'])


def scope_cards(scope, base):
    children = sorted({tuple(r[:len(scope)+1]) for r in routes if len(r) == len(scope)+1 and tuple(r[:len(scope)]) == tuple(scope)}, key=lambda r: (GEN_ORDER.index(r[-1]) if len(r) == 2 else 999, r[-1]))
    if not children: return ''
    tiles = []
    for route in children:
        num = sum(matches(article, route) for article in ARTICLES)
        tiles.append(f'<a class="scope-tile" href="{base}{path_url(route)}"><span class="folder-icon">▣</span><span class="scope-tile-name">{text(route[-1])}</span><span class="scope-tile-num">{num} 条</span><span class="arrow">↗</span></a>')
    return '<section class="folders"><div class="section-head"><h2>下级目录</h2><span>依照你的四级分类逐层浏览</span></div><div class="folder-grid">' + ''.join(tiles) + '</div></section>'


def breadcrumbs(parts, base):
    crumbs = ['<a href="'+base+'">首页</a>']
    for i, item in enumerate(parts):
        if i == len(parts)-1: crumbs.append('<span aria-current="page">'+text(item)+'</span>')
        else: crumbs.append('<a href="'+base+path_url(parts[:i+1])+'">'+text(item)+'</a>')
    return '<nav class="crumbs" aria-label="面包屑">' + '<span class="crumb-sep">/</span>'.join(crumbs) + '</nav>'


def article_card(a, base, scope=()):
    kind = source_type(a)
    envs = list(dict.fromkeys(r[0] for r in a['routes']))
    game_names = list(dict.fromkeys(r[2] for r in a['routes']))
    labels = [f'<span class="chip chip-source">{SOURCE_TYPES[kind]}</span>', f'<span class="chip">{text(date_label(a))}</span>', f'<span class="chip">{LANGUAGES[a["language"]]}原文</span>', '<span class="chip">'+text(' / '.join(envs))+'</span>', '<span class="chip chip-evidence">'+text(a['evidence'])+'</span>']
    tags = ''.join(f'<span class="tag">#{text(tag)}</span>' for tag in a['tags'][:4])
    hierarchy = ' · '.join(game_names)
    language_keywords = LANGUAGES[a['language']] + ' ' + LANGUAGE_KEYWORDS[a['language']]
    search_blob = (' '.join([a['title'],a['original_title'],a['author'],a['summary'],hierarchy,language_keywords,SOURCE_KEYWORDS[kind]] + a['tags'])).lower()
    return f'''<article class="article-card" data-type="{kind}" data-search="{text(search_blob)}" data-date="{text(a['date'] or '')}">
      <div class="article-top">{''.join(labels)}</div>
      <h3><a href="{article_link(a,base)}">{text(a['title'])}</a></h3>
      <p class="jptitle">原题：<span lang="{a['language']}">{text(a['original_title'])}</span></p>
      <p class="summary">{text(a['summary'])}</p>
      <div class="card-tags">{tags}</div>
      <div class="card-foot"><span><strong>{text(a['author'])}</strong> · {text(hierarchy)}</span><a href="{article_link(a,base)}" aria-label="查看中文资料卡">查看资料卡 →</a></div>
    </article>'''


def side_nav(base, active=()):
    sections = []
    for env in ENVS:
        generations = sorted({r[1] for r in routes if len(r)>1 and r[0]==env}, key=lambda g: GEN_ORDER.index(g))
        generation_html=[]
        for generation in generations:
            games = sorted({r[2] for r in routes if len(r)>2 and r[:2]==(env,generation)})
            game_html=[]
            for game in games:
                projects = sorted({r[3] for r in routes if len(r)>3 and r[:3]==(env,generation,game)})
                project_html=''.join(f'<a class="nav-leaf {"selected" if tuple(active)==(env,generation,game,p) else ""}" href="{base}{path_url((env,generation,game,p))}">{text(p)}</a>' for p in projects)
                game_html.append(f'<details {"open" if active[:3]==(env,generation,game) else ""}><summary>{text(game)}</summary><div class="nav-nest">{project_html}</div></details>')
            generation_html.append(f'<details {"open" if active[:2]==(env,generation) else ""}><summary><a href="{base}{path_url((env,generation))}">{text(generation)}</a></summary><div class="nav-nest">{"".join(game_html)}</div></details>')
        sections.append(f'<div class="nav-section"><a class="nav-root {"selected" if active[:1]==(env,) else ""}" href="{base}{path_url((env,))}"><span class="nav-root-icon">{"◇" if env=="实机" else "▣"}</span>{env}<span class="nav-count">{sum(matches(a,(env,)) for a in ARTICLES)}</span></a><div class="nav-nest">{"".join(generation_html)}</div></div>')
    return '<aside class="sidebar"><div class="sidebar-kicker">资料目录 / INDEX</div>' + ''.join(sections) + '<p class="sidebar-note">一条资料可同时归入不同目录，来源记录仅维护一份。</p></aside>'


def page_frame(title, main, parts=(), description='宝可梦乱数调整中文技术资料库，按实机/模拟器、世代、游戏和乱数项目分类。'):
    base = prefix_for(parts)
    count = len(ARTICLES)
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <meta name="color-scheme" content="light"><meta name="description" content="{text(description)}"><title>{text(title)} · Pokémon RNG Atlas</title>
    <link rel="stylesheet" href="{base}assets/styles.css"><script src="{base}assets/search.js" defer></script></head>
    <body><header class="site-header"><a class="brand" href="{base}"><span class="brand-symbol">◈</span><span><strong>RNG <i>ATLAS</i></strong><small>宝可梦乱数研究中文资料库</small></span></a><nav class="head-nav"><a href="{base}">资料库</a><a href="{base}更新记录/">更新记录</a><a href="{base}资料巡检/">资料巡检</a><a href="{base}关于/">关于项目</a><a class="source-link" href="{base}关于/">项目说明 ↗</a></nav></header>
    <div class="layout">{side_nav(base,parts if len(parts)<=4 else ())}<main id="main" class="main">{main}</main></div>
    <footer class="footer"><span>POKÉMON RNG ATLAS · 社区资料整理项目</span><span>当前收录 {count} 条资料 · 原创摘要与原始来源链接</span></footer></body></html>'''


def write_page(parts, title, content, description=''):
    directory = OUT.joinpath(*parts)
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'index.html').write_text(page_frame(title,content,parts,description or title), encoding='utf-8')


def listing_page(scope):
    base = prefix_for(scope)
    subset = sorted([a for a in ARTICLES if matches(a,scope)],key=newest_first,reverse=True)
    label = '全部资料' if not scope else scope[-1]
    hierarchy = ' / '.join(scope)
    intro = ('收录日文、英文和意大利语原始资料，提供中文技术摘要。按“实机 / 模拟器 → 世代 → 游戏 → 乱数项目”浏览，或按图文、GitHub Wiki、工具插件、YouTube 和 X 筛选。' if not scope else '当前位置：'+hierarchy+'。下方列出适用此分类的资料。')
    folders = scope_cards(scope,base) if len(scope)<4 else ''
    env_tabs = ''
    if not scope:
        env_tabs = '<div class="env-tabs"><a href="实机/"><span>◇</span><strong>实机乱数</strong><small>手动校准、破解读取、硬件自动化</small>↗</a><a href="模拟器/"><span>▣</span><strong>模拟器乱数</strong><small>Lua、内存读取、调试器与复现</small>↗</a></div>'
    lead = f'''{breadcrumbs(scope,base)}<div class="hero"><div class="eyebrow"><span class="small-dot"></span> OPEN RESEARCH LIBRARY · 日文 / 英文 / 意大利语原始资料</div><h1>{text(label) if scope else '让散落各处的 RNG 研究<br><em>变得可检索、可追溯。</em>'}</h1><p>{text(intro)}</p>{'' if scope else f'<div class="hero-stats"><span><b>{len(ARTICLES):02}</b> 条来源资料</span><span><b>{len({a["author"] for a in ARTICLES}):02}</b> 个作者／项目</span><span><b>{len({tuple(r) for a in ARTICLES for r in a["routes"]}):02}</b> 个项目目录</span></div>'}</div>'''
    subset_types = Counter(source_type(a) for a in subset)
    type_options = ''.join(f'<option value="{kind}">{label}（{subset_types[kind]}）</option>' for kind, label in SOURCE_TYPES.items() if subset_types[kind])
    listing = f'''<section class="listing" id="articles"><div class="section-head"><h2>{'相关资料' if scope else '全部资料'}</h2><span id="resultCount">{len(subset)} 条</span></div><div class="list-toolbar"><label class="search-box"><span>⌕</span><input id="articleSearch" type="search" aria-label="搜索资料" placeholder="搜索标题、作者、语言、Seed、PID…" autocomplete="off"></label><select id="sourceType" aria-label="资料形式"><option value="all">全部形式</option>{type_options}</select><select id="sortOrder" aria-label="排序方式"><option value="newest">发表日期 · 最新优先</option><option value="oldest">发表日期 · 最早优先</option><option value="title">标题 · A-Z</option></select></div><div class="article-list" id="articleList">{''.join(article_card(a,base,scope) for a in subset)}</div><div id="noResults" class="no-results" hidden>没有符合条件的资料，可以调整形式或尝试更短的关键词。</div></section>'''
    write_page(scope,label,lead+env_tabs+folders+listing)


def article_page(a):
    parts = ['文章',a['id']]
    base = prefix_for(parts)
    route_links = ''.join(f'<a href="{base}{path_url(r)}">'+ ' <span> / </span> '.join(map(text,r)) + '</a>' for r in a['routes'])
    tags = ''.join(f'<span class="tag">#{text(tag)}</span>' for tag in a['tags'])
    language = LANGUAGES[a['language']]
    kind = source_type(a)
    action = {'article': f'阅读{language}原文', 'wiki': '阅读 Wiki 原文', 'tool': '查看工具／插件说明', 'video': '观看 YouTube 视频', 'post': '查看 X 原帖'}[kind]
    review = f'<h2>核对说明</h2><p>{text(a["review_notes"])}</p>' if a.get('review_notes') else ''
    related = sorted((ARTICLE_BY_ID[id] for id in RELATED[a['id']]), key=lambda item: (list(SOURCE_TYPES).index(source_type(item)), item['title']))
    related_html = '<h2>配套教程与相关资料</h2><ul class="related-list">' + ''.join(f'<li><a href="{article_link(item,base)}">{text(item["title"])}</a><small>{SOURCE_TYPES[source_type(item)]} · {text(item["author"])}</small></li>' for item in related) + '</ul>' if related else ''
    body = f'''{breadcrumbs(parts,base)}<div class="doc-header"><span class="eyebrow">SOURCE PROFILE · 研究资料卡</span><h1>{text(a['title'])}</h1><p class="doc-origin" lang="{a['language']}">{text(a['original_title'])}</p><div class="article-top"><span class="chip chip-source">{SOURCE_TYPES[kind]}</span><span class="chip">{text(date_label(a))}</span><span class="chip">{language}原文</span><span class="chip">{text(a['evidence'])}</span><span class="chip">{text(a['status'])}</span></div></div><div class="doc-layout"><article class="doc-copy"><h2>中文技术摘要</h2><p>{text(a['summary'])}</p><p>这里收录自主编写的技术摘要和索引信息。完整内容、图表、程序及原作者更新，请访问原始来源。</p>{review}{related_html}<h2>所属分类</h2><div class="route-list">{route_links}</div><h2>主题关键词</h2><div class="card-tags">{tags}</div><div class="doc-alert"><strong>中文整理</strong><p>本站提供摘要与来源索引，尚未公开完整译文。</p></div></article><aside class="source-card"><h3>原始来源</h3><dl><dt>作者 / 项目</dt><dd>{text(a['author'])}</dd><dt>发表日期</dt><dd>{text(date_label(a))}</dd><dt>原文语言</dt><dd>{language}</dd><dt>资料形式</dt><dd>{SOURCE_TYPES[kind]}</dd><dt>资料性质</dt><dd>{text(a['evidence'])}</dd><dt>中文整理</dt><dd>{text(a['status'])}</dd></dl><a class="source-cta" href="{text(a['url'])}" target="_blank" rel="noopener noreferrer">{action} ↗</a><p class="smallprint">请以原作者最新内容为准。资料卡用于发现、归档和理解研究线索。</p></aside></div>'''
    write_page(parts,a['title'],body,a['summary'])


def simple_page(parts, headline, body):
    base = prefix_for(parts)
    content = breadcrumbs(parts,base)+f'<div class="hero hero-narrow"><span class="eyebrow">POKÉMON RNG ATLAS</span><h1>{text(headline)}</h1></div><div class="simple-content">{body}</div>'
    write_page(parts,headline,content)

assert OUT.resolve().parent == ROOT and OUT.resolve().name == 'dist', 'Unexpected output directory'
if OUT.exists(): shutil.rmtree(OUT)
OUT.mkdir(parents=True)
(OUT/'assets').mkdir()
for filename in ('styles.css','search.js'):
    shutil.copy(ROOT/'assets'/filename,OUT/'assets'/filename)
listing_page(())
article_index_parts = ('文章',)
article_index_base = prefix_for(article_index_parts)
write_page(article_index_parts, '资料索引', breadcrumbs(article_index_parts,article_index_base) + '<div class="hero hero-narrow"><span class="eyebrow">ALL SOURCES</span><h1>资料索引</h1></div><div class="article-list">' + ''.join(article_card(a,article_index_base) for a in sorted(ARTICLES,key=newest_first,reverse=True)) + '</div>')
for route in routes: listing_page(route)
for a in ARTICLES: article_page(a)
simple_page(['资料巡检'],'发现与修订巡检','''<h2>持续寻找散落的研究</h2><p>从 Hatena Bookmark 的跨博客搜索、博客 Feed、文章正文引用和轮换归档中寻找候选，兼顾近期文章与历史资料。新发现的博客会加入后续巡检范围，摆脱只检查固定博客的限制。公开搜索索引、关键词和抓取预算仍会造成遗漏，不能把它视为 Hatena 全平台的完整档案。</p><h2>复核原作者的变化</h2><p>巡检覆盖已收录的 Hatena 原文，比较文章标题、正文、正文链接、图片地址和日期元数据。首次读取仅建立基线；之后发现的变化进入人工复核清单。获取失败时保留已有记录，并说明失败原因。导航、广告和评论不参与正文比较，日期变化也不等于技术结论改变。</p><p>Hatena 以外的其他网站、GitHub 文档、YouTube 和 X 来源，目前尚未监测正文修订。相同地址下的图片文件替换与嵌入视频变化也无法识别；请结合原作者的后续说明判断。</p><h2>查看最新待审核清单</h2><p><a href="https://github.com/axechaso/pokemon-rng-atlas/blob/main/reports/discovery-review.md" target="_blank" rel="noopener noreferrer">打开最新待审核更新清单 ↗</a></p><p>清单列出新来源、原文变化、发现依据和获取失败，随 GitHub 每日巡检更新。<a href="https://github.com/axechaso/pokemon-rng-atlas/actions/workflows/check-new-articles.yml" target="_blank" rel="noopener noreferrer">查看巡检运行记录 ↗</a>。计划时间为北京时间每天约 08:17，实际执行可能延迟。</p><h2>候选如何成为资料卡</h2><p>候选还需核实宝可梦 RNG 相关性、原文语言、作者、发表日期、适用版本与操作环境。确认后才撰写中文摘要、关联工具和其他研究，并加入四级目录。待审线索不计入正式资料数量。只保留元数据和变化指纹，未经授权不公开原文全文或完整译文。</p>''')
simple_page(['关于'],'关于这个资料库',f'''<h2>四级分类</h2><p><strong>实机／模拟器 → 世代 → 游戏 → 乱数项目</strong>。每篇文章保留唯一记录；同一文章适用于多个场景时，出现在多个目录，但维护一份中文摘要和来源信息。实机栏目同时包含普通硬件、破解读取与硬件自动化方法，具体要求请查看各资料卡；离线计算参考与种子编辑文档会注明用途和条件。</p><h2>内容原则</h2><p>收录日文、英文和意大利语原始资料，不收录中文来源或中文翻译页；提供中文原创技术摘要，并保留原标题、作者、来源链接和资料性质。语言按正文标注，不根据英文标题或网站标签推断。来源未注明发表日期时如实标记，日期排序将其置于末尾；网站收录时间与原文更新时间不替代发表日期。对草稿、实验性方法及未验证机制明确标记。未经许可不公开完整翻译转载。</p><h2>关于自动更新</h2><p>通过 Hatena Bookmark 跨博客搜索、博客 Feed、正文引用与轮换归档发现日文研究线索，并检测已收录 Hatena 原文的变化。候选和修订均进入待审核清单，经人工核实后更新资料卡。查看<a href="../资料巡检/">资料巡检说明与最新审核清单</a>。自动发现受公开索引和抓取预算限制，无法穷尽整个平台；其他网站、GitHub、YouTube 与 X 的正文修订暂未自动监测。GitHub 巡检与 ChatGPT 定时任务相互独立。</p><h2>收录范围</h2><p>目前共有 {len(ARTICLES)} 条来源：日文 {LANGUAGE_COUNTS["ja"]} 条、英文 {LANGUAGE_COUNTS["en"]} 条、意大利语 {LANGUAGE_COUNTS["it"]} 条，包含第一至第九世代的代表性资料。已索引本次核对到的全部 79 篇 Devon Studios 官网教程及 4 份官方英文工具说明，覆盖基础捕获、孵化、ID、特殊遭遇与配信。其他来源包括日文作者博客、Admiral-Fish、Smogon 的第三至第五世代机制与实机指南、SM／USUM 孵化和剑盾团体战指南、3DSRNGTool、Real96 的 PokeLua、BDSP 参考实现和 Tera Finder，以及此前收录的 9 篇 PokemonRNG.com 指南。本轮未新增 PokemonRNG.com 来源。</p><p>按形式分为图文 {TYPE_COUNTS["article"]} 条、GitHub Wiki {TYPE_COUNTS["wiki"]} 条、工具／插件 {TYPE_COUNTS["tool"]} 条、YouTube 视频 {TYPE_COUNTS["video"]} 条、X 公开帖文 {TYPE_COUNTS["post"]} 条，可在各级资料列表筛选。配套教程、工具和演示通过关联来源互相连接；同一 URL 只维护一份记录。视频保留原题与频道，未逐段核对的内容在资料卡明确标注，未确认的发布日期填空；公开短帖只概括当前可读正文，不将其当作完整教程或完整讨论串。</p><p>继续沿作者的其他仓库、贡献者和引用追溯 Ten Lines、Pokémon RNG Docs、Real96 的每日遭遇与道具工具、RBY／GSC Lua、KnownUnown，以及 Anubis 的野生生成研究。主动扩展 Smogon、作者资料站、Billo 的 GRASS／PickyUppy 指南与日文实机研究，补充日版 N64 礼物、BDSP 蛋尺寸和 ORAS 能量方块等项目。Switch 版 FRLG 单独归类；日版《ポケモンスタジアム2》对应欧美版 Pokémon Stadium，归入第一世代。普通实机、破解读取、自动搜索、预测与补丁／存档编辑条件均按原文注明；简短工具说明不作为完整教程。</p><p>新增的视频资料串联红蓝黄 DV 与状况复现、水晶初始伙伴、GBA／Switch 版 FRLG、GameCube 初始伙伴与 Poké Spot、Channel／WISHMKR 基拉祈、梦境雷达及第六／七世代特殊遭遇。继续从视频追溯 Retail Pokémon RNG 的实机指南、夜綱的原作者工具说明、ChatotTool 和 CoSearch 操作。新收录视频的发表日期按 YouTube 发布元数据保留源端日期；未逐段观看或实机验证。破解读取、画面采集、外接自动化硬件、存档回写和 ACE 条件分别注明；旧工具和外部服务入口不代表当前仍可用。</p><p>旧模拟器、破解插件、工具迁移与游戏版本限制请查看资料卡。朱紫太晶团体战计算器收录为种子枚举与编辑研究，其每日 Seed 使用加密安全随机数，无法据此预测自然调日期推进。各游戏与乱数项目仍会持续补充，尚未完成所有资料的穷举。</p>''')
simple_page(['更新记录'],'更新记录','''<div class="timeline"><div class="timeline-item"><span>2026-10-27</span><h2>周计划维护：审核原文修订与 Hatena 候选</h2><p>按周计划完成一次带回溯巡检并人工处理 12 条候选：新增 8 条日文资料，4 条候选保留为明确排除记录；处理 TinyMT、HGSS ID、BW2 PWT、WISHMKR／CHANNEL、彩票 SID、蒼玉玛纳霏和 HGSS 狩猎地带资料。朱紫道具打印机原文确认发生正文变化，但因基线只保留哈希，未确认技术结论改变；旧地址迁移、404 和正文提取失败保留原始记录。<a href="https://github.com/axechaso/pokemon-rng-atlas/blob/main/reports/weekly-maintenance-2026-10-27.md" target="_blank" rel="noopener noreferrer">查看周维护记录 ↗</a>。</p></div><div class="timeline-item"><span>2026-10-26</span><h2>同步 Blastoise-X 资料挖掘与历史机制研究</h2><p><a href="../?q=Blastoise-X资料挖掘#articles">浏览本次补录的 40 条资料 →</a>。核对 10 月 21–26 日报告的原始来源后，新增 40 条日文资料：29 份图文研究／指南、11 份历史工具或源码说明，全站共 388 条。补充聒噪鸟 64 位 Seed 恢复、彩票 SID、BW2 孵化、对战地铁、迷人之躯、FRLG／绿宝石速通、GameCube 与 WISHMKR 校验和研究，并关联配套工具与既有教程。保留历史停用、推测、失败实验和未运行程序的限定；活动日期不代替未注明的发表日期。<a href="https://github.com/axechaso/pokemon-rng-atlas/blob/main/reports/blastoise-sync-2026-10-26.md" target="_blank" rel="noopener noreferrer">查看本次核对与保留线索 ↗</a>。</p></div><div class="timeline-item"><span>2026-10-16</span><h2>扩充视频并追溯配套实机指南与原作者工具</h2><p>新增 96 条来源（英文 84 条、日文 12 条）：75 支 YouTube 视频、14 份图文指南、7 份工具说明，全站共 348 条、其中视频 93 条。覆盖早期世代 DV／状况复现、GBA 与 Switch 版 FRLG、GameCube Poké Spot／基拉祈、梦境雷达、第六／七世代特殊遭遇、BDSP 和道具打印机。新增 Retail Pokémon RNG 实机指南、夜綱工具页及 Scrapbox 说明，并补充计时、读种、校准与硬件自动化工具，视频与图文互相关联。新视频日期按发布元数据核对；明确未逐段观看、工具历史差异、破解／模拟器／硬件／ACE 与存档回写条件。未新增 PokemonRNG.com 来源。</p></div><div class="timeline-item"><span>2026-10-16</span><h2>建立 Hatena 跨博客发现与原文修订巡检</h2><p>增加近期与历史搜索、文章引用追溯、新博客 Feed 和轮换归档回溯；为已收录 Hatena 原文建立正文基线，后续变化自动生成待审核清单。清单保留发现依据、日期元数据、变化指纹及获取失败，候选经人工核实后再发布。新增资料巡检入口，正式资料仍为 252 条。平台发现受公开索引与请求预算限制，其他网站及视频、帖子暂未监测正文修订。</p></div><div class="timeline-item"><span>2026-10-16</span><h2>沿作者与引用扩展原始研究和操作指南</h2><p>新增 55 条来源（英文 49 条、日文 6 条），全站共 252 条：19 份工具说明、33 份图文教程与机制文档、1 支配套 YouTube 演示及 2 条 X 研究者原帖。沿 GitHub 作者、贡献者和引用补充 GB／GSC、第四世代每日物种与道具、Switch 版 FRLG、LGPE 隐藏道具及旧世代机制，并主动扩展 Smogon、独立资料站和博客。工具、研究、操作教程与演示互相关联；明确环境、补丁、历史结论与未确认范围，未新增 PokemonRNG.com 来源。</p></div><div class="timeline-item"><span>2026-10-16</span><h2>补充 GitHub 插件、Wiki、视频与研究者原帖</h2><p>新增 55 条来源（英文 49 条、日文 6 条），全站共 197 条。本轮包括 13 份 GitHub Wiki、5 份工具／插件说明、17 份图文教程与研究索引、17 支 YouTube 视频及 3 条 X 公开帖文。补充第六世代野生、群战、图鉴导航，剑盾道具项目和 BDSP 工具环境；增加资料形式筛选与配套来源互链。公开视频元数据、未确认日期、SysBot 依赖、编辑用途与可预测范围均在资料卡注明，未新增 PokemonRNG.com 来源。</p></div><div class="timeline-item"><span>2026-10-16</span><h2>补齐 Devon 基础教程并扩充英文资料</h2><p>新增 38 条来源（意大利语 29 条、英文 9 条），全站共 142 条。完成本次核对的 Devon 官网 79 篇教程索引，补充第三至第五世代捕获、孵化、ID、配信，以及 CitraRNG 与 GameCube／GBA 联机配置。新增 Smogon 的 SM／USUM 孵化系列、TinyMT 参数表、3DSRNGTool、PokeLua、BDSP 参考实现及朱紫太晶团体战种子研究文档。按原文核对语言、作者、发表日期、游戏与工具条件，并区分种子编辑和自然推进。本轮未新增 PokemonRNG.com 来源。</p></div><div class="timeline-item"><span>2026-10-16</span><h2>补充 Devon Studios 专题与英文工具文档</h2><p>新增 54 条 Devon Studios 来源：50 篇意大利语专题、4 份官方英文工具说明，全站共 104 条。扩展 Channel 与 WISHMKR 基拉祈、BOX 礼物蛋、GameCube 赠送和交换、头锤树、涂蜜树、狩猎地带、连入之森、白森林，以及第六、第七世代校准和配信。加入意大利语显示与 Italian／Italiano 关键词搜索，并注明旧 Lua 仓库已迁移。本轮未新增 PokemonRNG.com 来源。</p></div><div class="timeline-item"><span>2026-10-16</span><h2>补充日文与英文资料</h2><p>新增 36 篇资料（日文 26 篇、英文 10 篇），总计 50 篇；补上第一、第二、第六、第八、第九世代，并扩展红蓝宝石、绿宝石、圆形竞技场、梦境雷达、Let's Go 与传说 阿尔宙斯等游戏。加入原文语言标记、语言关键词搜索和未注明发布日期的显示，扩充 4 个 RSS 来源。</p></div><div class="timeline-item"><span>2026-10-16</span><h2>网站目录初版</h2><p>建立四级目录架构、中文原创摘要、来源链接、搜索和文章资料卡，首次整理 14 篇示例文章。这是网站初版的整理日期，<strong>不代表这些文章都在当天发布</strong>。</p></div></div>''')
shutil.copy(ROOT/'data/articles.json',OUT/'articles.json')
print(f'Generated {len(list(OUT.rglob("index.html")))} HTML pages; {len(ARTICLES)} canonical sources; {len(routes)} navigation categories')
