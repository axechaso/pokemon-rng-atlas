# Pokémon RNG Atlas — 宝可梦乱数资料库

一个可以离线打开、无需 Node.js / npm 的静态网站，以 **实机 / 模拟器 → 世代 → 游戏 → 乱数项目** 为唯一主导航结构。收录日文、英文和意大利语原始资料，提供中文索引与原创摘要。

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
- `title` 和 `original_title`：中文标题与原文标题
- `url`、`author`：原始来源信息；个人作者未明确时注明来源社区，方法或工具贡献不等同于文章作者
- `language`：原文语言，`ja` 为日文，`en` 为英文，`it` 为意大利语；按正文判断，不以英文标题或网站标签判断。不收录中文来源或中文翻译页
- `date`：原文发表日期（`YYYY-MM-DD`）；来源未注明时填 `null`，页面显示“发布日期未注明”，日期排序始终将其放在末尾。不要用收录时间、提交时间或更新时间代替发表日期
- `summary`：本站自行编写的中文技术摘要
- `evidence`：证据类别，如“实机实践”或“机制实验”；这不是准确性担保
- `status`：译文/摘要状态
- `tags`：关键词
- `routes`：一个或多个 `[环境, 世代, 游戏, 乱数项目]` 四级目录

同一原文只能存在一条文章记录，但可被多个 `routes` 收录。例如同一篇 DPt 游戏厅文章同时包含实机调整与 DeSmuME Lua 实验，因而可以分别进入实机和模拟器栏目。

资料卡和列表均标记原文语言。首页搜索“英文”或“English”可筛选英文来源，搜索“意大利语”“Italian”或“Italiano”可筛选意大利语来源，也可直接搜索原标题。搜索“DevonStudios”或“DevonStudio”可查看已收录的 Devon Studios 资料，搜索“Smogon”可查看第七世代孵化指南。实机栏目包含普通硬件、破解读取和硬件自动化方法，各篇摘要会注明相应条件；离线计算参考与种子编辑文档也会单独标明用途。

录入后执行：

```bash
python scripts/build.py
```

`dist/` 会自动重新生成网站所有目录和文章资料卡。注意：**不要编辑 `dist/` 内的生成页面**，这些会被覆盖。

## 自动发现（候选不等于公开发表）

`scripts/check_feeds.py` 会读取 `data/sources.json` 中的 Hatena 博客 Atom/RSS，只获取标题、链接和日期并筛选 RNG 关键词；新发现保存到 `data/discovery_candidates.json`，**不会未经审核直接发布到网站**。

当前配置 11 个日文博客 Feed。其他来源包括 [Devon Studios](https://devonstudios.it/) 的意大利语专题、[官方 GitHub](https://github.com/DevonStudios) 的英文工具说明、[Admiral-Fish / RNGWriteups](https://github.com/Admiral-Fish/RNGWriteups) 的英文机制文档，以及 [Smogon](https://www.smogon.com/ingame/rng/)、[3DSRNGTool](https://github.com/wwwwwwzx/3DSRNGTool)、[PokeLua](https://github.com/Real96/PokeLua)、[BDSP RNG Reference](https://github.com/zaksabeast/BDSP-RNG-Reference) 和 [Tera Finder](https://github.com/Manu098vm/Tera-Finder) 的英文指南与工具文档。此前已收录 [PokemonRNG.com](https://www.pokemonrng.com/) 及其[原始指南仓库](https://github.com/zaksabeast/PokemonRNGGuides) 的 9 篇指南，后续两轮按要求未新增该站来源。这些来源目前人工核对后收录，未配置 RSS 自动发现。

Devon Studios 的作者与发表日期按官网文章元数据核对；其部分英文标题、English 标签对应的正文实际为意大利语，均按正文标注。官方工具 README 未注明发表日期，记为 `null`。旧版 [LuaScripts](https://github.com/DevonStudios/LuaScripts) 已停止维护，维护者指向 [Real96/PokeLua](https://github.com/Real96/PokeLua)；教程依赖的旧模拟器、插件及存档工具条件在各资料卡中注明。

已索引本次核对到的全部 **79 篇 Devon 官网教程**及 4 份官方英文工具说明。PokeLua 归属 Real96，第二世代在其 README 中仍标记为 `soon`。Tera Finder 文档用于朱紫种子枚举和编辑研究：每日 Seed 使用加密安全随机数，不能将计算器描述成可预测自然调日期推进的乱数流程。

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

- 仅使用日文、英文和意大利语原始资料，保留作者、原文标题、已注明的发表日期、原文 URL 与语言。
- 只公开自行撰写的简要索引与摘要；未经作者许可不直接公开原文完整机器翻译。
- 不把文章的发表日期误写成网站发现日期；不把猜想冒充已证实机制。
- 注明实机与模拟器的适用差异，以及 CFW、硬件自动化、旧版工具、草稿和实验性方法等条件。

## 当前范围

当前 **142 条来源资料：日文 40 条、英文 23 条、意大利语 79 条**，已包含第一至第九世代的代表性资料。覆盖水晶、红蓝宝石、绿宝石、FRLG、Pokémon BOX RS、Pokémon Channel、圆形竞技场及 Bonus Disc、XD、DPt、HGSS、BW／BW2、白森林、梦境雷达、XY／ORAS、SM／USUM、虚拟控制台传送、Let's Go、剑盾、BDSP、传说 阿尔宙斯及朱紫等游戏与场景。

2026-10-16：新增 **38 条来源**（意大利语 29 条、英文 9 条），补齐 Devon 官网当前 79 篇教程的索引，重点补充第三至第五世代捕获、孵化、ID 与配信基础流程，以及 CitraRNG 环境和 GameCube／GBA 联机配置。新增 Smogon 的 SM／USUM 孵化系列、TinyMT 参数表、3DSRNGTool、PokeLua、BDSP 参考实现与朱紫太晶团体战种子研究文档；核对旧工具限制、游戏范围与发布日期，未新增 PokemonRNG.com 来源。

2026-10-16：新增 **54 条 Devon Studios 来源**，包括 50 篇意大利语专题及 4 份英文工具说明。重点补充 GameCube 配信、礼物蛋、赠送与交换，第三至第五世代特殊遭遇，以及 3DS 校准、配信和动态 PID 孵化；扩展意大利语显示与语言关键词搜索。公开内容为原创摘要和来源索引，未转载完整正文。

2026-10-16：在首批 14 篇的基础上新增 36 篇（日文 26、英文 10），补充缺少的世代与游戏。收录范围尚未穷尽所有游戏和资料。
