# Codex-Zotero 文献可视化 Skill

## 中文说明

`zotero-literature-visualizer` 是面向 Codex 的学术文献工作流 skill。它可从研究主题或已有 Zotero 文献库出发，完成文献检索、期刊质量核查、合规的全文获取流程、Zotero 条目整理、中英文研究摘要，以及交互式文献 dashboard 的生成。

Dashboard 会包含主题分类、方法热点、主题—方法关系图、发表时间线、期刊来源、文章卡片与本地 PDF 打开入口。时间线按年份排列，以主题颜色区分文献；文章卡片可显示中文研究摘要，并将英文证据折叠为可选参考。
<img width="1302" height="751" alt="Screenshot 2026-08-02 121211" src="https://github.com/user-attachments/assets/827da0cd-4922-40e1-98ad-9cc9116c38ca" />
<img width="1243" height="751" alt="Screenshot 2026-08-02 121236" src="https://github.com/user-attachments/assets/96a27132-5cf9-4b7d-b53c-6a667e0547a1" />



### 安装

1. 下载或获得此 skill 的 `.skill` 或 `.zip` 文件。
2. 将文件拖入 Codex，或在对话中附上文件并说：

   ```text
   请安装这个 zotero-literature-visualizer skill。
   ```

3. 安装后重启 Codex，或刷新插件/skills 列表。
4. 在新对话中用下面的提示词开始工作。

### 使用方式 1：直接整理已有 Zotero 文献库

适用于 Zotero 中已经有论文条目和本地 PDF 的情况。

```text
使用 zotero-literature-visualizer skill，读取我 Zotero 中所有带本地 PDF 的文献，
按主题和方法分类，生成中英文摘要与交互式 dashboard。
```

也可以限制到一个 collection：

```text
使用 zotero-literature-visualizer skill，只整理 Zotero 中“某个文件夹”内带本地 PDF 的文献，
生成交互式 dashboard。
```

Zotero 直读模式会以只读方式读取本地数据库，不移动 PDF，也不会修改原有条目。只有已解析到本地的 PDF 会被纳入全文可视化；没有本地 PDF 的条目会被明确标记为未纳入全文分析。

### 使用方式 2：检索一个新研究方向

```text
使用 zotero-literature-visualizer skill，整理“关键词***”相关的近年高质量论文。
请给出筛选逻辑、期刊质量核查、双语研究摘要和可视化 dashboard。
```

可补充限定条件，例如时间范围、目标数量、主题词、地区或方法：

```text
近 5 年；不限制篇数；重点关注关键词***、研究对象***与研究方法***。
```

默认流程优先关注相关性、研究质量与期刊证据，不会因为论文是否开放获取而改变纳入排序。

### 使用方式 3：获取全文 PDF

对于受订阅限制的论文，Codex 不会绕过付费墙或索取账号密码。请先在出版社、学校或图书馆网页中自行完成登录，然后说：

```text
我已在浏览器中合法登录，请继续下载这些论文的全文。
```

下载流程会从可见的出版社文章页开始，并使用页面上的 `View PDF`、`Open PDF` 或 `Download PDF` 等入口。遇到验证码、双重验证或下载确认时，由用户自行完成。

### 使用方式 4：把论文及 PDF 添加到 Zotero

如果希望把新文献写回 Zotero，可以说：

```text
将已下载的论文加入 Zotero 的“某个文件夹”，并把本地 PDF 作为对应条目的附件。
```

需要通过 Zotero Web API 写入时，请自行在 Zotero 创建仅限个人文库的 API key，并授予需要的 library/write 权限。不要把 API key 放入 README、代码仓库或公开聊天记录。

### 使用方式 5：生成或改进 dashboard

```text
为这个文献库生成 dashboard，并加入：主题分类、方法分布、发表时间线、主题—方法关系图、期刊来源与本地 PDF 链接。
```

如需针对某个文献库做更深入的解释，可继续要求：

```text
请根据 PDF 全文，逐篇补充中文的研究主题、方法、数据或案例、主要结果、局限与研究启示。
```

### 典型输出

运行目录通常包含：

- `metadata/papers.json`：规范化的论文元数据；
- `texts/`：从本地 PDF 提取的文本；
- `review-bilingual.md`：双语综述；
- `relationship-map.md`：主题与方法关系说明；
- `dashboard-spec.json`：可人工调整的分类与卡片语义；
- `literature-dashboard.html`：离线打开的交互式 dashboard。

### 隐私与数据边界

- 不要把姓名、邮箱、学校账号、API key、Cookie、浏览器配置或本地绝对路径写入 skill、README 或公开仓库。
- Zotero 直读模式默认只读取本机数据；不会复制或上传 PDF。
- 下载付费文献时只使用用户已经合法登录的可见浏览器流程。

---

## English Description

`zotero-literature-visualizer` is a Codex skill for academic literature workflows. Starting from either a research topic or an existing Zotero library, it supports literature discovery, journal-quality checks, compliant full-text access workflows, Zotero organization, bilingual research summaries, and interactive literature dashboards.

The dashboard includes theme taxonomy, method hotspots, theme–method maps, a theme-coloured publication timeline, journal sources, paper cards, and local PDF launchers. Timeline nodes are grouped by publication year and colour-coded by theme. Paper cards can present curated Chinese research notes while keeping English evidence collapsed as optional reference.

### Installation

1. Download the `.skill` or `.zip` package.
2. Drag it into Codex, or attach it in a conversation and say:

   ```text
   Install this zotero-literature-visualizer skill.
   ```

3. Restart Codex or refresh the plugins/skills list.
4. Start a new chat and use one of the prompts below.

### Workflow 1: Read an existing Zotero library

Use this when Zotero already contains article records and local PDF files.

```text
Use the zotero-literature-visualizer skill to read all Zotero items with local PDFs,
classify them by theme and method, and generate bilingual summaries and an interactive dashboard.
```

To focus on one collection:

```text
Use the zotero-literature-visualizer skill to analyze only the local-PDF items in my Zotero collection named “Collection name” and generate an interactive dashboard.
```

Zotero direct-import mode reads a local database snapshot without moving PDFs or modifying existing Zotero records. Only records with resolved local PDFs are included in full-text visualization; records without local PDFs are kept out of full-text analysis.

### Workflow 2: Search a new research topic

```text
Use the zotero-literature-visualizer skill to review recent high-quality literature on
“keyword ***”.
Provide the screening logic, journal-quality checks, bilingual research notes, and a dashboard.
```

You can add constraints such as year range, target count, geographic scope, keywords, or methods:

```text
Last 5 years; no paper limit; focus on keyword ***, research context ***, and research method ***.
```

The workflow prioritizes relevance, research quality, and journal evidence. Open-access status is not used as a ranking criterion.

### Workflow 3: Obtain full-text PDFs

Codex does not bypass paywalls or request credentials. For subscription content, sign in yourself through your publisher, library, or institutional access page, then say:

```text
I have completed an authorized browser login. Continue downloading the full texts for these papers.
```

The workflow starts from a visible publisher article page and uses the page’s visible `View PDF`, `Open PDF`, or `Download PDF` control. Users complete CAPTCHAs, two-factor verification, and download confirmations themselves.

### Workflow 4: Add papers and PDFs to Zotero

```text
Add the downloaded papers to my Zotero collection named “Collection name” and attach each local PDF to its matching article record.
```

When Zotero Web API writing is needed, create a personal-library API key yourself and grant only the required library/write permissions. Never place an API key in a README, public repository, or public chat.

### Workflow 5: Generate or refine a dashboard

```text
Create a dashboard for this library with theme taxonomy, method distribution,
a publication timeline, a theme–method map, journal sources, and local PDF links.
```

For deeper literature notes, ask:

```text
Read the local PDFs and add paper-specific Chinese notes for research topic, method,
data or case, findings, limitations, and implications.
```

### Typical outputs

A run folder commonly contains:

- `metadata/papers.json`: normalized paper metadata;
- `texts/`: extracted text from local PDFs;
- `review-bilingual.md`: bilingual review;
- `relationship-map.md`: theme and method relationships;
- `dashboard-spec.json`: editable taxonomy and paper-card semantics;
- `literature-dashboard.html`: an offline interactive dashboard.

### Privacy and data boundaries

- Do not put names, email addresses, institutional accounts, API keys, cookies, browser profiles, or absolute local paths in the skill, README, or a public repository.
- Zotero direct-import mode reads local data by default and does not copy or upload PDFs.
- For paywalled content, use only an authorized, visible browser workflow after the user has completed login.
