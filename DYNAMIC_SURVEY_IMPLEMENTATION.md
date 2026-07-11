# 动态综述主页实现全流程

本文档用于指导你把当前静态综述主页改造成一个可以定期自动更新的动态综述主页。

目标是：自动发现微信公众号文章里推荐的 arXiv 论文，提取论文信息，自动分类，然后更新 GitHub Pages 主页。

推荐架构不是让前端实时爬取微信公众号，而是使用定时后台任务更新静态数据文件：

```text
GitHub Actions 定时触发
  -> 通过 Tavily / SerpAPI 搜索微信公众号相关文章
  -> 提取 arXiv ID 或疑似论文标题
  -> 调用 arXiv API 校验论文元数据
  -> 自动分类到综述 taxonomy
  -> 更新 docs/data 下的 JSON 数据
  -> GitHub Pages 自动部署最新主页
```

## 1. 最终效果

实现完成后，主页可以支持：

- 定期自动发现新论文
- 记录论文来自哪些微信公众号文章推荐
- 使用 arXiv 官方元数据校验标题、作者、摘要、发布时间
- 按 arXiv ID 自动去重
- 自动分类到 OCR、Layout、Table、RAG、VLM、Eval
- 高置信度论文自动发布
- 低置信度论文进入待审核列表
- 主页展示动态模块：
  - 最新发现论文
  - 本周新增论文
  - 微信推荐来源
  - 分类统计
  - 待审核数量
  - 最后更新时间

前端仍然是静态 GitHub Pages。所谓“动态”，是指定时任务自动更新 JSON 数据，页面再读取最新 JSON 渲染。

## 2. 哪些步骤可以全自动，哪些建议人工审核

可以全自动的步骤：

- GitHub Actions 定时执行
- Tavily / SerpAPI 搜索微信公众号相关文章
- 收集微信文章链接、标题、摘要片段
- 从文章或搜索摘要中提取 arXiv ID
- 调用 arXiv API 获取论文标准元数据
- 根据 arXiv ID 去重
- 根据标题和摘要自动分类
- 写入 `docs/data/dynamic_papers.json`
- 自动提交数据更新
- GitHub Pages 自动部署

建议人工审核的情况：

- 没有 arXiv ID，只能靠标题猜测论文
- 分类置信度太低
- 疑似重复论文
- 微信文章正文提取失败
- 来源不在白名单
- 搜索结果明显不相关

推荐上线策略：

```text
有效 arXiv ID + 元数据完整 + 分类置信度 >= 0.75
  -> 自动发布到主页

没有 arXiv ID / 分类置信度低 / 疑似重复 / 抓取失败
  -> 写入 pending_updates.json 等待人工确认
```

这样既能自动更新，又不会让低质量结果污染主页。

## 3. 在新 clone 的项目中准备环境

假设你已经把仓库 clone 到：

```text
G:\document-intelligence-survey-github-new
```

进入项目根目录：

```powershell
cd G:\document-intelligence-survey-github-new
git status
```

如果 `git status` 正常显示分支和文件状态，说明仓库是正常的。

本地预览当前静态页面：

```powershell
cd docs
python -m http.server 8080
```

浏览器打开：

```text
http://localhost:8080
```

预览结束后回到项目根目录：

```powershell
cd ..
```

## 4. 推荐新增文件结构

建议新增或修改这些文件：

```text
configs/
  dynamic_sources.json

scripts/
  update_dynamic_papers.py

docs/data/
  dynamic_papers.json
  pending_updates.json
  update_log.json

.github/workflows/
  update-papers.yml

requirements.txt
```

如果后面代码变复杂，可以再拆分成：

```text
scripts/lib/
  arxiv_client.py
  classify.py
  dedupe.py
  search_providers.py
  wechat_extract.py
```

第一版 MVP 不需要拆太细。建议先用一个 `scripts/update_dynamic_papers.py` 跑通完整流程。

## 5. 数据文件设计

不要一开始就直接覆盖现有的 `paper_index.json`。建议先新增一个动态数据文件：

```text
docs/data/dynamic_papers.json
```

示例结构：

```json
{
  "lastUpdated": "2026-07-09T00:00:00Z",
  "source": "scheduled-wechat-arxiv-pipeline",
  "papers": [
    {
      "id": "arxiv:2607.01234",
      "arxiv": "2607.01234",
      "title": "Example Paper Title",
      "authors": "Alice Zhang, Bob Wang",
      "abstract": "Short abstract from arXiv.",
      "year": 2026,
      "published": "2026-07-08",
      "updated": "2026-07-08",
      "venue": "arXiv 2026",
      "category": "vlm",
      "categories": ["vlm"],
      "subcategory": "Document VLM",
      "tags": ["Document VLM", "OCR-free", "Multimodal QA"],
      "classificationConfidence": 0.86,
      "status": "auto",
      "firstSeen": "2026-07-09",
      "lastSeen": "2026-07-09",
      "sourceMentions": [
        {
          "platform": "wechat",
          "provider": "tavily",
          "account": "Unknown",
          "articleTitle": "A weekly arXiv paper recommendation article",
          "url": "https://mp.weixin.qq.com/s/example",
          "foundAt": "2026-07-09"
        }
      ]
    }
  ]
}
```

低置信度候选论文写入：

```text
docs/data/pending_updates.json
```

示例结构：

```json
{
  "lastUpdated": "2026-07-09T00:00:00Z",
  "items": [
    {
      "reason": "no_arxiv_id",
      "candidateTitle": "Possible Paper Title",
      "sourceUrl": "https://mp.weixin.qq.com/s/example",
      "sourceTitle": "WeChat article title",
      "foundAt": "2026-07-09"
    }
  ]
}
```

运行日志写入：

```text
docs/data/update_log.json
```

示例：

```json
{
  "lastRun": "2026-07-09T00:00:00Z",
  "searchedQueries": 7,
  "candidateArticles": 32,
  "arxivIdsFound": 18,
  "autoPublished": 10,
  "pendingReview": 4,
  "duplicates": 4
}
```

## 6. 搜索源配置

创建：

```text
configs/dynamic_sources.json
```

建议第一版内容：

```json
{
  "enabledProviders": ["tavily", "serpapi"],
  "autoPublishConfidence": 0.75,
  "maxResultsPerQuery": 10,
  "queries": [
    "site:mp.weixin.qq.com/s arxiv 文档智能",
    "site:mp.weixin.qq.com/s arxiv OCR VLM",
    "site:mp.weixin.qq.com/s arxiv 多模态 文档理解",
    "site:mp.weixin.qq.com/s arxiv Document AI",
    "site:mp.weixin.qq.com/s arxiv RAG 文档问答",
    "site:mp.weixin.qq.com/s arxiv 表格理解",
    "site:mp.weixin.qq.com/s arxiv 版面分析"
  ],
  "trustedSourceHints": [
    "机器之心",
    "量子位",
    "PaperWeekly",
    "AI科技评论",
    "arXiv每日学术速递"
  ],
  "taxonomy": [
    {
      "id": "ocr",
      "title": "OCR & Text Recognition",
      "keywords": ["ocr", "text recognition", "scene text", "handwriting", "document parsing", "paddleocr"]
    },
    {
      "id": "layout",
      "title": "Layout Analysis",
      "keywords": ["layout", "reading order", "document structure", "region detection", "doclaynet", "publaynet"]
    },
    {
      "id": "table",
      "title": "Table Understanding",
      "keywords": ["table", "spreadsheet", "tabular", "table qa", "table structure", "chart"]
    },
    {
      "id": "rag",
      "title": "Retrieval-Augmented Generation",
      "keywords": ["rag", "retrieval", "long context", "knowledge graph", "document qa", "multi-hop"]
    },
    {
      "id": "vlm",
      "title": "Vision-Language Models",
      "keywords": ["vlm", "vision-language", "multimodal", "document vqa", "ocr-free", "high-resolution"]
    },
    {
      "id": "eval",
      "title": "Evaluation & Benchmarks",
      "keywords": ["benchmark", "evaluation", "dataset", "leaderboard", "metric", "test set"]
    }
  ]
}
```

后续你可以逐步增加更精确的公众号白名单、关键词和分类规则。

## 7. API Key 和 GitHub Secrets

不要把 API Key 写进前端 JS，也不要提交到 GitHub。

在 GitHub 仓库中配置：

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

建议配置：

```text
TAVILY_API_KEY
SERPAPI_API_KEY
OPENAI_API_KEY
```

其中：

- `TAVILY_API_KEY`：用于 Tavily 搜索和网页内容提取
- `SERPAPI_API_KEY`：用于 SerpAPI 搜索
- `OPENAI_API_KEY`：可选，用于低置信度论文的智能分类

第一版可以不用 OpenAI，先用关键词分类跑通。

本地测试时可以临时设置环境变量：

```powershell
$env:TAVILY_API_KEY="your_key_here"
$env:SERPAPI_API_KEY="your_key_here"
python scripts/update_dynamic_papers.py --dry-run
```

## 8. Python 依赖

创建或更新：

```text
requirements.txt
```

第一版建议：

```text
requests>=2.32.0
python-dateutil>=2.9.0
feedparser>=6.0.11
```

如果后续使用 OpenAI 做分类，再加：

```text
openai>=1.0.0
```

本地安装：

```powershell
pip install -r requirements.txt
```

## 9. 主更新脚本职责

创建：

```text
scripts/update_dynamic_papers.py
```

这个脚本负责完整自动更新流程：

```text
1. 读取 configs/dynamic_sources.json
2. 读取已有 docs/data/dynamic_papers.json
3. 读取已有 docs/data/paper_index.json，避免和人工整理的论文重复
4. 通过 Tavily / SerpAPI 搜索微信公众号相关文章
5. 从搜索结果和文章内容中提取 arXiv ID
6. 调用 arXiv API 获取标准论文元数据
7. 自动分类
8. 按 arXiv ID 去重
9. 高置信度论文写入 dynamic_papers.json
10. 低置信度候选写入 pending_updates.json
11. 写入 update_log.json
```

建议支持这些命令：

```powershell
python scripts/update_dynamic_papers.py --dry-run
python scripts/update_dynamic_papers.py --provider tavily
python scripts/update_dynamic_papers.py --provider serpapi
python scripts/update_dynamic_papers.py --max-results 20
```

`--dry-run` 只打印将要更新什么，不实际写文件。这个参数对调试很重要。

## 10. arXiv ID 提取规则

需要识别这些格式：

```text
https://arxiv.org/abs/2607.01234
https://arxiv.org/pdf/2607.01234
arXiv:2607.01234
arxiv 2607.01234
```

推荐正则：

```python
ARXIV_ID_RE = re.compile(
    r"(?:arxiv(?:\.org)?/(?:abs|pdf)/|arxiv\s*:\s*|arxiv\s+)?"
    r"([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)",
    re.IGNORECASE,
)
```

建议统一去掉版本号：

```python
def normalize_arxiv_id(value: str) -> str:
    return re.sub(r"v\d+$", "", value.strip())
```

例如：

```text
2607.01234v2 -> 2607.01234
```

## 11. 调用 arXiv API 获取论文元数据

提取 arXiv ID 后，使用 arXiv 官方 API 获取标准信息。

请求格式：

```text
https://export.arxiv.org/api/query?id_list=2607.01234
```

返回结果是 Atom XML，可以用 `feedparser` 解析：

```python
import feedparser
import requests

def fetch_arxiv_metadata(arxiv_ids):
    if not arxiv_ids:
        return {}

    query = ",".join(arxiv_ids)
    url = f"https://export.arxiv.org/api/query?id_list={query}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    feed = feedparser.parse(response.text)
    result = {}

    for entry in feed.entries:
        arxiv_id = entry.id.rsplit("/", 1)[-1].split("v")[0]
        result[arxiv_id] = {
            "arxiv": arxiv_id,
            "title": " ".join(entry.title.split()),
            "authors": ", ".join(author.name for author in entry.authors),
            "abstract": " ".join(entry.summary.split()),
            "published": entry.published[:10],
            "updated": entry.updated[:10],
            "year": int(entry.published[:4]),
            "venue": f"arXiv {entry.published[:4]}",
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdfUrl": f"https://arxiv.org/pdf/{arxiv_id}",
            "primaryArxivCategory": entry.tags[0]["term"] if getattr(entry, "tags", None) else ""
        }

    return result
```

注意：不要对 arXiv API 做高频请求。尽量批量请求 ID，并避免短时间循环请求。

## 12. Tavily / SerpAPI 搜索逻辑

建议把搜索结果统一成一种结构：

```python
{
    "provider": "tavily",
    "title": "...",
    "url": "...",
    "snippet": "...",
    "publishedDate": "2026-07-09"
}
```

搜索 query 示例：

```text
site:mp.weixin.qq.com/s arxiv 文档智能
site:mp.weixin.qq.com/s arxiv OCR VLM
site:mp.weixin.qq.com/s arxiv Document AI
site:mp.weixin.qq.com/s arxiv table understanding
site:mp.weixin.qq.com/s arxiv RAG 文档问答
```

第一版建议：

```text
先用 Tavily 搜索
如果 Tavily 结果少，再用 SerpAPI 补充
```

重要规则：

不要用浏览器自动化绕过登录、验证码、付费墙或反爬机制。只使用搜索 API、公开摘要、允许提取的公开页面内容，并且最终以 arXiv 元数据为准。

## 13. 自动分类策略

第一版建议用关键词分类，不要一开始就依赖大模型。

分类输入：

```text
论文标题
论文摘要
arXiv category
微信文章标题
搜索摘要 snippet
```

分类输出：

```json
{
  "category": "vlm",
  "categories": ["vlm"],
  "subcategory": "Document VLM",
  "tags": ["Document VLM", "OCR-free"],
  "confidence": 0.82
}
```

简单计算方式：

```text
统计每个分类命中的关键词数量
最高分分类作为主分类
confidence = 最高分类分数 / 所有分类总分
```

推荐规则：

```text
confidence >= 0.75 -> 自动发布
confidence < 0.75 -> pending_updates.json
没有关键词命中 -> pending_updates.json
多个分类分数接近 -> pending_updates.json
```

后续增强：

只对低置信度论文调用 LLM 分类，节省成本。

## 14. 去重规则

去重优先级：

```text
1. arXiv ID
2. DOI
3. 标准化后的标题
```

标题标准化示例：

```python
def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
```

如果发现同一 arXiv ID 已存在：

- 不新增论文条目
- 只追加 `sourceMentions`
- 更新 `lastSeen`

这样同一篇论文被多个公众号推荐时，主页可以显示多个来源，但论文本身只出现一次。

## 15. 前端主页改造

当前主页需要额外读取动态数据：

```text
docs/data/paper_index.json
docs/data/dynamic_papers.json
docs/data/pending_updates.json
docs/data/update_log.json
```

推荐新增模块：

```text
Dynamic Overview
  - 人工整理论文数量
  - 自动发现论文数量
  - 本周新增数量
  - 待审核数量
  - 最后更新时间

Latest From WeChat
  - 最新自动发现论文
  - arXiv 链接
  - 微信来源文章链接
  - 分类标签

Category Growth
  - 动态论文按分类统计

Pending Review
  - 只展示数量，不一定公开展示所有候选细节
```

搜索页也建议支持动态论文：

- 搜索人工整理论文
- 搜索动态发现论文
- 按分类筛选
- 按来源筛选
- 按状态筛选：curated / auto / pending

## 16. 主页文案建议

建议使用中性表述：

```text
Dynamic Paper Tracker
Recently discovered arXiv papers mentioned by public WeChat articles and verified against arXiv metadata.
```

如果要中文：

```text
动态论文追踪
自动发现公开微信公众号文章中提及的 arXiv 论文，并使用 arXiv 元数据进行校验。
```

来源处建议写：

```text
Mentioned by public article
```

或：

```text
公开文章提及
```

不要写成“官方推荐”或“权威推荐”，除非原文明确这样表达。

## 17. GitHub Actions 定时更新

创建：

```text
.github/workflows/update-papers.yml
```

推荐内容：

```yaml
name: Update Dynamic Papers

on:
  schedule:
    - cron: "0 18 * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Update dynamic paper data
        run: python scripts/update_dynamic_papers.py
        env:
          TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}
          SERPAPI_API_KEY: ${{ secrets.SERPAPI_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}

      - name: Commit data updates
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add docs/data
          git commit -m "Update dynamic paper data" || exit 0
          git push
```

说明：

```text
"0 18 * * *" 是 UTC 时间
对应北京时间第二天凌晨 2 点
```

如果想每周执行一次，例如每周一北京时间凌晨 2 点：

```yaml
schedule:
  - cron: "0 18 * * 0"
```

## 18. GitHub Pages 部署

如果项目已有：

```text
.github/workflows/deploy.yml
```

可以保留。数据更新 workflow 提交 JSON 后，部署 workflow 会重新发布 `docs/`。

GitHub Pages 设置位置：

```text
Repository -> Settings -> Pages -> Build and deployment
```

推荐设置：

```text
Source: GitHub Actions
```

如果数据更新后页面没有重新部署，需要检查：

- `deploy.yml` 是否监听 `push`
- GitHub Pages 是否启用
- Actions 是否有权限部署 Pages
- `update-papers.yml` 是否成功 push 了 JSON 变更

## 19. 本地测试流程

先测试 dry run：

```powershell
python scripts/update_dynamic_papers.py --dry-run
```

期望看到类似输出：

```text
Loaded config
Found candidate articles
Extracted arXiv IDs
Fetched arXiv metadata
Classified papers
Would publish N papers
Would send M items to pending review
```

再执行真实更新：

```powershell
python scripts/update_dynamic_papers.py
```

查看变更：

```powershell
git status
```

本地预览页面：

```powershell
cd docs
python -m http.server 8080
```

打开：

```text
http://localhost:8080
```

确认：

- 首页能看到动态论文模块
- 最新论文能显示 arXiv 链接
- 来源文章链接正常
- 分类标签正确
- 最后更新时间正确

## 20. 提交和推送

本地验证通过后：

```powershell
git add configs scripts docs .github requirements.txt
git commit -m "Add dynamic paper update pipeline"
git push
```

然后去 GitHub 手动触发一次：

```text
Actions -> Update Dynamic Papers -> Run workflow
```

检查：

- Actions 是否成功
- `docs/data/dynamic_papers.json` 是否被更新
- 是否有自动 commit
- GitHub Pages 是否重新部署
- 公开主页是否显示最新数据

## 21. 建议实现顺序

不要一口气做完整系统。建议按这个顺序：

```text
第 1 步：修复现有 paper_index 生成脚本路径
第 2 步：新增 configs/dynamic_sources.json
第 3 步：写 update_dynamic_papers.py，但先用固定 arXiv ID 测试
第 4 步：生成 docs/data/dynamic_papers.json
第 5 步：让首页读取 dynamic_papers.json 并展示
第 6 步：接入 Tavily 搜索
第 7 步：接入 SerpAPI 作为补充
第 8 步：加入关键词分类
第 9 步：加入 pending_updates.json
第 10 步：加入 GitHub Actions 定时任务
第 11 步：低置信度结果再考虑接入 LLM 分类
```

这样可以先跑通“自动更新主页”的闭环，再逐步提高采集和分类质量。

## 22. 第一版 MVP 应该做到什么

第一版不要太复杂，只需要做到：

```text
1. Tavily 搜索微信公众号相关文章
2. 从搜索结果和文章内容里提取 arXiv ID
3. 调 arXiv API 获取论文元数据
4. 根据关键词分类
5. 高置信度写入 dynamic_papers.json
6. 低置信度写入 pending_updates.json
7. 主页展示最新动态论文
8. GitHub Actions 每天或每周自动执行
```

这已经可以证明完整动态更新流程是可行的。

## 23. 自动发布质量规则

建议满足以下条件才自动发布：

```text
必须有 arXiv ID
必须能从 arXiv API 获取标题
必须能从 arXiv API 获取作者
必须能从 arXiv API 获取摘要
不能已存在于 paper_index.json
不能已存在于 dynamic_papers.json
分类置信度必须 >= 0.75
来源 URL 必须是公开搜索结果中的 URL
```

任一条件失败：

```text
写入 pending_updates.json
```

## 24. 公开页面安全规则

公开页面可以展示：

- 论文标题
- 作者
- arXiv 链接
- arXiv 摘要或简短摘要
- 分类标签
- 来源文章标题
- 来源文章 URL
- 发现日期

公开页面不建议保存或展示：

- 微信公众号全文
- 登录后可见内容
- 付费内容
- 绕过验证码或反爬获得的内容
- API Key

## 25. 推荐最终架构

```text
configs/dynamic_sources.json
  控制搜索 query、可信来源、taxonomy、自动发布阈值

scripts/update_dynamic_papers.py
  执行完整更新任务

docs/data/paper_index.json
  现有人工整理论文库

docs/data/dynamic_papers.json
  自动发现的新论文

docs/data/pending_updates.json
  需要人工确认的候选论文

docs/data/update_log.json
  最近一次更新日志

docs/js/app.js
  首页渲染逻辑

docs/js/search.js
  搜索页渲染逻辑

.github/workflows/update-papers.yml
  定时更新数据

.github/workflows/deploy.yml
  GitHub Pages 部署
```

## 26. 完成检查清单

上线前逐项检查：

- [ ] 新 clone 的仓库中 `git status` 正常
- [ ] 本地静态页面可以打开
- [ ] `configs/dynamic_sources.json` 已创建
- [ ] `requirements.txt` 已创建
- [ ] `scripts/update_dynamic_papers.py` 已创建
- [ ] 脚本支持 `--dry-run`
- [ ] 脚本能写入 `docs/data/dynamic_papers.json`
- [ ] 脚本能写入 `docs/data/pending_updates.json`
- [ ] 脚本能写入 `docs/data/update_log.json`
- [ ] 首页能读取动态论文数据
- [ ] 搜索页能检索动态论文
- [ ] 重复 arXiv ID 会合并
- [ ] 低置信度项目不会自动发布
- [ ] API Key 只放在 GitHub Secrets
- [ ] `.github/workflows/update-papers.yml` 已创建
- [ ] workflow 可以手动运行
- [ ] workflow 可以自动提交 JSON 变更
- [ ] GitHub Pages 会在数据变更后重新部署
- [ ] 公开主页显示最后更新时间

## 27. 最推荐的落地方案

最稳妥的方案是：

```text
自动采集
自动校验 arXiv 元数据
自动分类
高置信度自动发布
低置信度进入待审核
GitHub Actions 定时运行
GitHub Pages 自动展示最新 JSON
```

不要一开始就追求完全无人审核所有结果。对于长期维护的综述主页，质量比数量更重要。

第一版只要能做到：

```text
每周自动新增若干篇高置信度 arXiv 论文
主页自动显示最新论文和来源
低质量候选不自动上线
```

这个动态综述主页就已经具备可用价值。
