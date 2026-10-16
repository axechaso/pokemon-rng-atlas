# Pokémon RNG Atlas — 宝可梦乱数资料库（网站初版）

一个可以离线打开、无需 Node.js / npm 的静态网站初版，以 **实机 / 模拟器 → 世代 → 游戏 → 乱数项目** 为唯一主导航结构。

## 在线访问

- 网站：<https://axechaso.github.io/pokemon-rng-atlas/>
- 源码：<https://github.com/axechaso/pokemon-rng-atlas>

推送到 `main` 的网站内容变更会通过 GitHub Actions 自动构建并部署到 GitHub Pages。

## 立即预览

直接打开 `dist/index.html` 即可浏览。内容采用相对链接，因此子目录与文章页同样可以离线打开。若要本地服务器预览，运行：

```bash
cd dist
python -m http.server 8000
```

在浏览器访问 `http://localhost:8000/`。

## 更新文章

唯一文章数据库为 `data/articles.json`，每一条记录包含：

- `id`：全站唯一 ID
- `title` 和 `original_title`：中文标题与日文原标题
- `url`、`author`、`date`：原始来源信息
- `summary`：本站自行编写的中文技术摘要
- `evidence`：证据类别，如“实机实践”或“机制实验”；这不是准确性担保
- `status`：译文/摘要状态
- `tags`：关键词
- `routes`：一个或多个 `[环境, 世代, 游戏, 乱数项目]` 四级目录

同一原文只能存在一条文章记录，但可被多个 `routes` 收录。例如同一篇 DPt 游戏厅文章同时包含实机调整与 DeSmuME Lua 实验，因而可以分别进入实机和模拟器栏目。

录入后执行：

```bash
python scripts/build.py
```

`dist/` 会自动重新生成网站所有目录和文章资料卡。注意：**不要编辑 `dist/` 内的生成页面**，这些会被覆盖。

## 自动发现（候选不等于公开发表）

`scripts/check_feeds.py` 会读取 `data/sources.json` 中的 Hatena 博客 Atom/RSS，只获取标题、链接和日期并筛选 RNG 关键词；新发现保存到 `data/discovery_candidates.json`，**不会未经审核直接发布到网站**。

```bash
python scripts/check_feeds.py
```

仓库附带 `.github/workflows/check-new-articles.yml`，当你把本目录推送到 GitHub 并启用 Actions 后，可每天定期收集候选。它只监控已经录入 `sources.json` 的博客，**不是全 Hatena 平台的完整搜索引擎**；平台范围的历史文章发现仍需人工或独立巡检任务扩展来源。RSS 只能覆盖博客 Feed 目前保留的条目，旧文需要另行回溯归档。GitHub Actions 计划任务可能延迟。

ChatGPT 里的“Hatena 宝可梦乱数资料巡检”定时任务与此 GitHub 工作流相互独立，**不会自动把 ChatGPT 报告写入这个网站**。

## 发布到 GitHub Pages

1. 新建一个 GitHub 仓库并把项目文件推送到 `main`。
2. 在 Settings → Pages → Build and deployment → Source 中选择 **GitHub Actions**。
3. 在 Settings → Actions → General 中确认工作流具备必要权限（候选发现工作流会尝试写入仓库）。
4. 在 Actions 手动运行 `Deploy static archive` 一次，之后代码更改将自动构建并发布网站。

网站通过上面的 GitHub Pages 地址发布，HTML 为纯静态页面，没有后端服务。新版可继续迁移到 Astro，但当前版本为零依赖静态生成器，更便于修改验证。

## 版权与质量原则

- 保留作者、原文标题、日期、原文 URL。
- 只公开自行撰写的简要索引与摘要；未经作者许可不直接公开原文完整机器翻译。
- 不把文章的发表日期误写成网站发现日期；不把猜想冒充已证实机制。
- 注明实机与模拟器的适用差异。

## 当前范围

首批 **14 篇来源文章**，分布在第三、第四、第五、第七世代。只是用于验证四级目录的精简样例，未声称全站 Hatena 完成穷举。
