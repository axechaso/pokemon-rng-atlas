#!/usr/bin/env python3
"""Dependency-free static-site builder. One canonical article record, many navigation paths."""
import json
import shutil
from collections import Counter, defaultdict
from datetime import date
from html import escape as esc
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
ARTICLES = json.loads((ROOT / 'data/articles.json').read_text(encoding='utf-8'))
OUT = ROOT / 'dist'
GEN_ORDER = ['第一世代','第二世代','第三世代','第四世代','第五世代','第六世代','第七世代','第八世代','第九世代']
ENVS = ['实机','模拟器']


def text(value):
    return esc(str(value), quote=True)


def path_url(parts):
    return '/'.join(quote(p, safe='') for p in parts) + ('/' if parts else '')


def prefix_for(parts):
    return '../' * len(parts) if parts else './'


def article_link(article, prefix):
    return prefix + path_url(['文章', article['id']])


def valid(article):
    required = ['id','title','original_title','author','date','url','summary','routes','tags']
    assert all(article.get(field) for field in required), f'Missing article field: {article}'
    assert article['url'].startswith('https://'), article['id']
    assert len(article['routes']) == len({tuple(r) for r in article['routes']}), article['id']
    assert all(len(r) == 4 and r[0] in ENVS and r[1] in GEN_ORDER for r in article['routes'])

assert len({a['id'] for a in ARTICLES}) == len(ARTICLES), 'Duplicate IDs'
assert len({a['url'].rstrip('/') for a in ARTICLES}) == len(ARTICLES), 'Duplicate sources: merge routes instead'
for a in ARTICLES: valid(a)

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
        tiles.append(f'<a class="scope-tile" href="{base}{path_url(route)}"><span class="folder-icon">▣</span><span class="scope-tile-name">{text(route[-1])}</span><span class="scope-tile-num">{num} 篇</span><span class="arrow">↗</span></a>')
    return '<section class="folders"><div class="section-head"><h2>下级目录</h2><span>依照你的四级分类逐层浏览</span></div><div class="folder-grid">' + ''.join(tiles) + '</div></section>'


def breadcrumbs(parts, base):
    crumbs = ['<a href="'+base+'">首页</a>']
    for i, item in enumerate(parts):
        if i == len(parts)-1: crumbs.append('<span aria-current="page">'+text(item)+'</span>')
        else: crumbs.append('<a href="'+base+path_url(parts[:i+1])+'">'+text(item)+'</a>')
    return '<nav class="crumbs" aria-label="面包屑">' + '<span class="crumb-sep">/</span>'.join(crumbs) + '</nav>'


def article_card(a, base, scope=()):
    envs = list(dict.fromkeys(r[0] for r in a['routes']))
    game_names = list(dict.fromkeys(r[2] for r in a['routes']))
    labels = [f'<span class="chip">{text(a["date"])}</span>', '<span class="chip">'+text(' / '.join(envs))+'</span>', '<span class="chip chip-evidence">'+text(a['evidence'])+'</span>']
    tags = ''.join(f'<span class="tag">#{text(tag)}</span>' for tag in a['tags'][:4])
    hierarchy = ' · '.join(game_names)
    search_blob = (' '.join([a['title'],a['original_title'],a['author'],a['summary'],hierarchy] + a['tags'])).lower()
    return f'''<article class="article-card" data-search="{text(search_blob)}" data-date="{text(a['date'])}">
      <div class="article-top">{''.join(labels)}</div>
      <h3><a href="{article_link(a,base)}">{text(a['title'])}</a></h3>
      <p class="jptitle">原题：{text(a['original_title'])}</p>
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
    return '<aside class="sidebar"><div class="sidebar-kicker">资料目录 / INDEX</div>' + ''.join(sections) + '<p class="sidebar-note">一篇资料可同时归入不同目录，文章记录仅维护一份。</p></aside>'


def page_frame(title, main, parts=(), description='宝可梦乱数调整中文技术资料库，按实机/模拟器、世代、游戏和乱数项目分类。'):
    base = prefix_for(parts)
    count = len(ARTICLES)
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <meta name="color-scheme" content="light"><meta name="description" content="{text(description)}"><title>{text(title)} · Pokémon RNG Atlas</title>
    <link rel="stylesheet" href="{base}assets/styles.css"><script src="{base}assets/search.js" defer></script></head>
    <body><header class="site-header"><a class="brand" href="{base}"><span class="brand-symbol">◈</span><span><strong>RNG <i>ATLAS</i></strong><small>宝可梦乱数研究中文资料库</small></span></a><nav class="head-nav"><a href="{base}">资料库</a><a href="{base}更新记录/">更新记录</a><a href="{base}关于/">关于项目</a><a class="source-link" href="{base}关于/">项目说明 ↗</a></nav></header>
    <div class="layout">{side_nav(base,parts if len(parts)<=4 else ())}<main id="main" class="main">{main}</main></div>
    <footer class="footer"><span>POKÉMON RNG ATLAS · 社区资料整理项目</span><span>当前收录 {count} 篇文章 · 只提供原创摘要与外部原文链接</span></footer></body></html>'''


def write_page(parts, title, content, description=''):
    directory = OUT.joinpath(*parts)
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'index.html').write_text(page_frame(title,content,parts,description or title), encoding='utf-8')


def listing_page(scope):
    base = prefix_for(scope)
    subset = sorted([a for a in ARTICLES if matches(a,scope)],key=lambda x: x['date'],reverse=True)
    label = '全部资料' if not scope else scope[-1]
    hierarchy = ' / '.join(scope)
    intro = ('浏览所有已核实原文链接和中文技术摘要。按“实机 / 模拟器 → 世代 → 游戏 → 乱数项目”进入对应目录。' if not scope else '当前位置：'+hierarchy+'。下方列出适用此分类的资料。')
    folders = scope_cards(scope,base) if len(scope)<4 else ''
    env_tabs = ''
    if not scope:
        env_tabs = '<div class="env-tabs"><a href="实机/"><span>◇</span><strong>实机乱数</strong><small>手动校准、实机验证、硬件自动化</small>↗</a><a href="模拟器/"><span>▣</span><strong>模拟器乱数</strong><small>Lua、内存读取、调试器与复现</small>↗</a></div>'
    lead = f'''{breadcrumbs(scope,base)}<div class="hero"><div class="eyebrow"><span class="small-dot"></span> OPEN RESEARCH LIBRARY · 目录初版</div><h1>{text(label) if scope else '让散落各处的 RNG 研究<br><em>变得可检索、可追溯。</em>'}</h1><p>{text(intro)}</p>{'' if scope else f'<div class="hero-stats"><span><b>{len(ARTICLES):02}</b> 条文章记录</span><span><b>{len({a["author"] for a in ARTICLES}):02}</b> 个资料来源</span><span><b>{len({tuple(r) for a in ARTICLES for r in a["routes"]}):02}</b> 个项目目录</span></div>'}</div>'''
    listing = f'''<section class="listing" id="articles"><div class="section-head"><h2>{'相关资料' if scope else '全部文章'}</h2><span id="resultCount">{len(subset)} 篇</span></div><div class="list-toolbar"><label class="search-box"><span>⌕</span><input id="articleSearch" type="search" placeholder="搜索中文标题、日文原题、作者、Seed、PID…" autocomplete="off"></label><select id="sortOrder" aria-label="排序方式"><option value="newest">发表日期 · 最新优先</option><option value="oldest">发表日期 · 最早优先</option><option value="title">标题 · A-Z</option></select></div><div class="article-list" id="articleList">{''.join(article_card(a,base,scope) for a in subset)}</div><div id="noResults" class="no-results" hidden>没有符合搜索条件的文章，可以尝试更短的关键词。</div></section>'''
    write_page(scope,label,lead+env_tabs+folders+listing)


def article_page(a):
    parts = ['文章',a['id']]
    base = prefix_for(parts)
    route_links = ''.join(f'<a href="{base}{path_url(r)}">'+ ' <span> / </span> '.join(map(text,r)) + '</a>' for r in a['routes'])
    tags = ''.join(f'<span class="tag">#{text(tag)}</span>' for tag in a['tags'])
    body = f'''{breadcrumbs(parts,base)}<div class="doc-header"><span class="eyebrow">ARTICLE PROFILE · 研究资料卡</span><h1>{text(a['title'])}</h1><p class="doc-origin">{text(a['original_title'])}</p><div class="article-top"><span class="chip">{text(a['date'])}</span><span class="chip">{text(a['evidence'])}</span><span class="chip">{text(a['status'])}</span></div></div><div class="doc-layout"><article class="doc-copy"><h2>中文技术摘要</h2><p>{text(a['summary'])}</p><p>这里仅收录自主编写的技术摘要和索引信息。完整内容、图表、程序及原作者更新，请访问原文。</p><h2>所属分类</h2><div class="route-list">{route_links}</div><h2>主题关键词</h2><div class="card-tags">{tags}</div><div class="doc-alert"><strong>翻译状态</strong><p>尚未公开完整译文。未经授权不会直接转载原文的完整机器翻译。</p></div></article><aside class="source-card"><h3>原始文献</h3><dl><dt>作者 / 博客</dt><dd>{text(a['author'])}</dd><dt>发表日期</dt><dd>{text(a['date'])}</dd><dt>资料性质</dt><dd>{text(a['evidence'])}</dd><dt>中文整理</dt><dd>{text(a['status'])}</dd></dl><a class="source-cta" href="{text(a['url'])}" target="_blank" rel="noopener noreferrer">阅读日文原文 ↗</a><p class="smallprint">请以原作者最新内容为准。资料卡仅用于发现、归档和理解研究线索。</p></aside></div>'''
    write_page(parts,a['title'],body,a['summary'])


def simple_page(parts, headline, body):
    base = prefix_for(parts)
    content = breadcrumbs(parts,base)+f'<div class="hero hero-narrow"><span class="eyebrow">POKÉMON RNG ATLAS</span><h1>{text(headline)}</h1></div><div class="simple-content">{body}</div>'
    write_page(parts,headline,content)

if OUT.exists(): shutil.rmtree(OUT)
OUT.mkdir(parents=True)
(OUT/'assets').mkdir()
for filename in ('styles.css','search.js'):
    shutil.copy(ROOT/'assets'/filename,OUT/'assets'/filename)
listing_page(())
article_index_parts = ('文章',)
article_index_base = prefix_for(article_index_parts)
write_page(article_index_parts, '文章索引', breadcrumbs(article_index_parts,article_index_base) + '<div class="hero hero-narrow"><span class="eyebrow">ALL ARTICLES</span><h1>文章索引</h1></div><div class="article-list">' + ''.join(article_card(a,article_index_base) for a in sorted(ARTICLES,key=lambda a:a['date'],reverse=True)) + '</div>')
for route in routes: listing_page(route)
for a in ARTICLES: article_page(a)
simple_page(['关于'],'关于这个资料库','''<h2>四级分类</h2><p><strong>实机／模拟器 → 世代 → 游戏 → 乱数项目</strong>。每篇文章保留唯一记录；同一文章适用于多个场景时，出现在多个目录，但维护一份中文摘要和来源信息。</p><h2>内容原则</h2><p>保留原文、作者、发布时间、资料性质和中文原创技术摘要；对未确定的机制明确保留“推测/待验证”等标记。未经许可不公开完整翻译转载。</p><h2>关于自动更新</h2><p>项目带有可配置的 Hatena RSS 候选发现脚本。候选需人工核实和分类后，才会进入公开目录；RSS 检查与 ChatGPT 的定时巡检是两个独立的系统。</p><h2>目录演进</h2><p>目前只是结构验证版，收录少量核实链接用于示例。后续可以扩展更多博客、其他网站、工具源码以及完整授权译文。</p>''')
simple_page(['更新记录'],'更新记录',f'''<div class="timeline"><div class="timeline-item"><span>2026-10-16</span><h2>网站目录初版</h2><p>建立四级目录架构、中文原创摘要、来源链接、搜索和文章资料卡，首次整理 {len(ARTICLES)} 篇示例文章。这是网站初版的整理日期，<strong>不代表这些文章都在当天发布</strong>。</p></div></div>''')
shutil.copy(ROOT/'data/articles.json',OUT/'articles.json')
print(f'Generated {len(list(OUT.rglob("index.html")))} HTML pages; {len(ARTICLES)} canonical sources; {len(routes)} navigation categories')
