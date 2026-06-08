Zotero 文献整理与可视化 Skill
这个包给 Codex 增加一套完整的文献整理流程：从一个研究主题出发，检索近年高质量论文，下载或整理 PDF，把新文献加入 Zotero，并生成可交互的中英文可视化 dashboard。

它主要包含两个 skill：

zotero-literature-visualizer：负责文献检索、筛选、分类、总结、Zotero 直读、Zotero 导入和 dashboard 生成。
sciencedirect-live-session-fetcher：负责在你已经合法登录学校/图书馆/出版社账号后，通过真实浏览器会话下载 ScienceDirect/Elsevier 等页面提供的 PDF。
默认目标是：近 1 年、质量优先、顶刊优先、默认 top 30。如果某个方向的高质量强相关论文明显超过 30 篇，也可以让 Codex 不限制数量，全部整理。

一句话说明
你给 Codex 一个领域或关键词，它可以帮你完成：

找论文：检索 OpenAlex、Crossref、Unpaywall、出版社页面等来源。
筛论文：默认优先选择近 1 年、强相关、高影响力期刊论文。
验期刊：需要时会从期刊或出版社官网核对影响因子，默认排除 IF 低于 5 的期刊。
下全文：OA 文章可直接处理；非 OA 文章需要你在浏览器里用学校/图书馆账号合法登录。
入 Zotero：可把下载好的 PDF 自动加入 Zotero 条目，并以本地 linked-file 方式挂载 PDF，不占 Zotero 云端容量。
做 dashboard：自动生成主题分类、方法热度、主题-方法关系图、期刊来源、文章卡片、双语详情总结和本地 PDF/DOI 链接。
安装方法
最简单的安装方式：把这个 GitHub 仓库链接或 zip 链接直接发给 Codex，让 Codex 安装。

可以这样说：

请帮我安装这个文献自动下载、Zotero 导入和可视化综述 skill：
<这里粘贴 GitHub 链接或 zip 链接>
安装完成后，重启 Codex。

重启后可以直接问：

这个文献综述和可视化 skill 安装好了吗？帮我检查一下。
Codex 会检查 skill 是否能被识别、脚本是否能运行、基础 dashboard 是否能生成。

使用方式一：整理一个新研究方向
直接告诉 Codex 你的研究方向或关键词。

示例：

使用 zotero-literature-visualizer skill，帮我整理“……”方向近 1 年的高质量顶刊论文，默认 top 30，生成中英文总结和可视化 dashboard。
把 …… 换成你的研究方向，例如：

建筑，低碳，机器学习，能源优化
或者：

极地建筑，低碳建筑材料，建筑能耗，AI 方法
如果你不想限制 30 篇，可以说：

如果这个方向强相关的高质量论文超过 30 篇，就不要限制数量，全部整理。
Codex 通常会先做一个小样本测试，确认关键词、期刊质量和下载流程能跑通，再扩展到完整结果。

使用方式二：下载非 OA 全文
如果论文不是开放获取，Codex 不能绕过付费墙，也不会要你的账号密码。你需要自己完成合法登录。

你需要做的事：

让 Codex 列出需要下载全文的论文。
Codex 会打开或指导你打开一个专用浏览器窗口。
你在浏览器里登录学校、图书馆或出版社账号。
如果网页出现验证码、学校认证、双重验证，你自己完成。
你打开一篇代表性文章，点一次页面上的 View PDF 或 Download PDF。
登录和 PDF 访问确认成功后，告诉 Codex：“我登录好了，继续下载。”
Codex 会尽量按合规顺序处理：先打开官方文章页，再使用页面可见的 PDF 入口，不把短期签名链接当作长期下载地址。

常用提示词：

我已经在浏览器里登录学校账号了，请继续下载这些文献。下载时先打开文章页，再点击页面上的 PDF 入口。
使用方式三：把新下载的 PDF 放进 Zotero 和 dashboard
如果你已经让 Codex 下载了一批 PDF，可以继续说：

把刚下载好的 PDF 放进 Zotero，新建一个今天日期的 collection，并更新 dashboard。
默认方式是 linked-file：

PDF 文件仍然留在你的电脑本地。
Zotero 条目下面会出现这个 PDF 附件。
不上传 PDF 到 Zotero 云端。
不占 Zotero 云端存储空间。
第一次使用 Zotero 自动导入时，需要设置 Zotero API key。

你需要做的事：

登录 Zotero 官网。
创建一个 API key。
勾选个人文库的 Allow library access 和 Allow write access。
不需要 group 权限，除非你想导入 group library。
不需要把 key 发到公开聊天或 GitHub，放在本地文件里给 Codex 读取即可。
这个 API key 本身不收费。只有你选择把 PDF 上传到 Zotero 云端时，才可能受 Zotero 云端存储容量限制。本 skill 默认使用本地 linked-file，不上传 PDF。

使用方式四：直接读取已有 Zotero 文献库
如果你 Zotero 里已经有很多文献和 PDF，不需要重新搜索或下载，可以让 Codex 直接读取 Zotero 本地库。

提示词：

使用 zotero-literature-visualizer skill 的 Zotero 模式，直接读取我 Zotero 里所有带本地 PDF 的文献，分类总结，并生成中英文可视化 dashboard。
Zotero 直读模式会：

自动寻找本机 Zotero 数据库。
只读方式读取，不修改 Zotero 数据库。
只纳入有本地 PDF 的条目。
没有 PDF 的条目直接跳过。
默认全量读取，不限制 30 篇或 100 篇。
文献超过 100 篇时自动启用大文献库 dashboard。
大文献库 dashboard 会包含：

Overview / 总览：论文数量、主题分布、方法分布、主要期刊。
Explore / 浏览：按主题、方法或期刊浏览文献。
Map / 关系图：主题和方法之间的聚合关系。
文章详情层：点击文章后查看主题、方法、摘要、贡献、局限和相关性。
最终会生成什么
每次运行通常会生成一个新的项目文件夹，例如：

literature-reviews/<你的主题>/
里面通常包含：

metadata/papers.json
metadata/papers.csv
metadata/journal-if-evidence.csv
metadata-repair.md
pdfs/
texts/
manual-download.md
review-bilingual.md
relationship-map.md
dashboard-spec.json
<你的-dashboard>.html
<你的-dashboard>-data.js
<你的-dashboard>-details.js
平时主要打开 <你的-dashboard>.html，就可以看到可视化页面。

需要用户自己做什么
你只需要负责这些事：

提供研究方向或关键词。
对非 OA 文献，自己在浏览器里合法登录学校/图书馆/出版社账号。
手动完成验证码、学校认证或双重验证。
如果要自动导入 Zotero，第一次配置 Zotero API key。
如果要读取 Zotero，确保 Zotero 里有本地 PDF 附件。
Codex 会负责：

搜索和整理候选论文。
生成下载队列。
使用已经登录的浏览器会话下载可访问 PDF。
校验 PDF 文件。
生成 Zotero 导入记录。
更新 dashboard。
写双语总结、分类和关系图。
重要提醒
这个 skill 不能绕过付费墙，只能在你已有合法访问权限的情况下帮你自动化整理流程。
不同学校的数据库权限不同，所以同一个主题在不同人电脑上能下载到的全文数量可能不同。
dashboard 样式和交互可以复现，但具体论文、主题分类、方法分类会随着关键词和文献库变化。
Zotero linked-file PDF 只在本机路径有效。如果把 dashboard 发给别人，对方可能打不开你的本地 PDF 链接。
AI 生成的分类和总结适合快速阅读和综述初稿，正式论文写作前建议人工复核重要文献。
开源许可证
本项目使用 MIT License。开源或二次修改时，请保留 LICENSE 文件和原始版权声明。

Zotero Literature Visualizer
This package gives Codex a complete literature workflow: start from a research topic, discover recent high-quality papers, download or organize PDFs, add new papers to Zotero, and generate an interactive bilingual dashboard.

It includes two skills:

zotero-literature-visualizer: literature search, screening, classification, bilingual synthesis, Zotero direct reading, Zotero import, and dashboard generation.
sciencedirect-live-session-fetcher: PDF downloading through a lawful live browser session after the user has signed in through their school, library, or publisher access.
The default target is recent, quality-first literature: last 1 year, top journals, usually top 30 papers. If a field has more than 30 strongly relevant high-quality papers, you can ask Codex to include all qualified papers.

What It Does
Codex can help you:

Search papers from OpenAlex, Crossref, Unpaywall, DOI and publisher pages.
Select high-quality and strongly relevant papers.
Verify journal Impact Factor from official journal or publisher pages when needed.
Download PDFs when access is available.
Add downloaded PDFs to Zotero as local linked-file attachments.
Generate an interactive dashboard with themes, methods, relationship maps, journal sources, paper cards, bilingual details, DOI links, and local PDF links.
Installation
The easiest way is to give Codex the GitHub or zip link and ask it to install the skill:

Please install this literature auto-download, Zotero import, and visualization skill:
<paste GitHub or zip link here>
Restart Codex after installation.

Then ask:

Is this literature review and visualization skill installed correctly? Please check it for me.
Use Case 1: Review A New Topic
Ask Codex:

Use the zotero-literature-visualizer skill to review recent high-quality top-journal papers on "...", default top 30, and generate a bilingual summary and visualization dashboard.
Replace ... with your topic or keywords.

If you do not want a 30-paper cap, say:

If there are more than 30 strongly relevant high-quality papers, include all qualified papers.
Use Case 2: Download Non-OA Full Texts
Codex will not bypass paywalls or ask for your password. For non-OA papers, you need to sign in yourself.

What you do:

Let Codex prepare the download queue.
Sign in through your school, library, or publisher account in the browser.
Complete any CAPTCHA, SSO, or two-factor verification yourself.
Open one representative article and click the visible View PDF or Download PDF button once if required.
Tell Codex you are ready.
Example:

I have signed in through my school account. Please continue downloading these papers. Open the article page first, then use the visible PDF button.
Use Case 3: Add Downloaded PDFs To Zotero And Dashboard
After PDFs are downloaded, ask:

Add the newly downloaded PDFs to Zotero, create a collection using today's date, and update the dashboard.
By default, the skill uses Zotero linked_file attachments:

PDFs remain on your local computer.
Zotero records point to the local PDF files.
PDF files are not uploaded to Zotero cloud storage.
Zotero cloud storage quota is not used.
For automatic Zotero import, set up a Zotero API key once:

Log in to Zotero.
Create an API key.
Enable personal library access and write access.
Group permissions are not needed unless you want group-library import.
Keep the key local. Do not upload it to GitHub or paste it publicly.
The Zotero API key is free. Zotero cloud storage is only relevant if you choose to upload PDF files. This skill defaults to local linked files.

Use Case 4: Read An Existing Zotero Library
If your Zotero library already contains PDFs, ask:

Use zotero-literature-visualizer Zotero mode to read all Zotero items with local PDFs, classify and summarize them, and generate a bilingual visualization dashboard.
Zotero mode:

Finds the local Zotero database automatically.
Reads Zotero in read-only mode.
Includes only entries with local PDF files.
Skips entries without PDFs.
Uses the full PDF-backed library by default, with no fixed 30 or 100 paper limit.
Switches to a large-library dashboard when there are more than 100 papers.
Outputs
Each run creates a folder like:

literature-reviews/<your-topic>/
Typical outputs include:

metadata/papers.json
metadata/papers.csv
metadata/journal-if-evidence.csv
metadata-repair.md
pdfs/
texts/
manual-download.md
review-bilingual.md
relationship-map.md
dashboard-spec.json
<your-dashboard>.html
<your-dashboard>-data.js
<your-dashboard>-details.js
Open the generated dashboard HTML file to view the interactive report.

What The User Must Do
The user provides:

Research topic or keywords.
Lawful browser login for non-OA papers.
Manual CAPTCHA, SSO, or two-factor verification when needed.
Zotero API key once, if automatic Zotero import is desired.
Existing local PDFs in Zotero, if using Zotero direct mode.
Codex handles:

Search and candidate collection.
Download queue generation.
PDF downloading through the authorized browser session.
PDF validation.
Zotero item and linked-file attachment creation.
Dashboard generation.
Bilingual classification, summaries, and relationship maps.
Notes
This skill does not bypass paywalls. It only works with access the user already has.
Full-text availability depends on each user's institution or publisher access.
The dashboard layout is reproducible, but paper lists and classifications depend on the topic and library.
Zotero linked-file PDF paths work on the local machine. Other people may not be able to open your local PDF links.
AI-generated classifications and summaries are best treated as review aids and first drafts. Important papers should be manually checked before formal academic writing.
License
This project is released under the MIT License. Keep the LICENSE file and copyright notice when reusing or modifying it.
