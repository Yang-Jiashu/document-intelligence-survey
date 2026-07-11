# 动态综述主页修改流程

本文档记录本仓库从静态综述主页改造成“静态页面 + 定时更新 JSON 数据”的动态综述主页的最终实施流程。

## 已确认约束

- 第一版只使用 Tavily，不接入 SerpAPI。
- 本地和 GitHub Actions 至少需要 `TAVILY_API_KEY`；如果启用大模型分类，还需要 `DMX_API_KEY`。
- 搜索范围只限微信公众号文章，即 `site:mp.weixin.qq.com/s`。
- 自动发布只允许白名单公众号来源：
  - 机器之心
  - 量子位
  - PaperWeekly
  - AI科技评论
  - arXiv每日学术速递
- 必须能从搜索结果标题、摘要或提取后的文章正文中识别白名单公众号；不能仅凭命中的搜索 query 判定来源可信。
- 已经存在于人工论文库 `docs/data/paper_index.json` 的论文不重复写入动态论文列表，但会在 `curatedSourceMentions` 中保留对应公众号文章。
- 首页不展示动态论文列表，不修改 `Recent Papers`。
- 首页新增小型 `Dynamic Overview`，只显示自动发现总数、分类数量、待审核数量、最后更新时间。
- 首页 Taxonomy 分类卡片数量等于人工论文数量加自动发现论文数量。
- 搜索页支持搜索动态论文，并显示 `Auto-discovered` 标签。
- 搜索页同时显示 arXiv 链接和对应公众号文章链接；同一论文可关联多篇公众号文章。
- 严格验证为白名单来源的文章即使暂时没有抽出 arXiv ID，也写入 `verifiedWechatArticles` 并在搜索页展示。
- 动态论文长期保存在 `docs/data/dynamic_papers.json`。
- 动态待审核结果长期保存在 `docs/data/pending_dynamic_papers.json`。
- 现有 `docs/data/pending_updates.json` 保留给 SOTA 更新脚本使用。
- GitHub Actions 每周运行一次。
- 自动发布阈值为 `classificationConfidence >= 0.75`。
- 文档智能相关性不再作为来源链接的展示门槛；不相关论文以 `source-only` 状态和 `other` 分类展示，但不进入主页文档智能分类统计。
- 分类策略使用“大模型优先 + 关键词兜底”：
  - 有可用 `DMX_API_KEY` 时，调用 OpenAI-compatible Chat Completions 接口判断是否属于文档智能，并输出分类。
  - 大模型不可用或调用失败时，回退到规则关键词分类。
  - 规则兜底的文档智能相关性只看 arXiv 标题、摘要和 arXiv 类别，不使用公众号正文，避免公众号集合文章造成误判。
- 搜索摘要中找不到 arXiv ID 时，使用 Tavily Extract 提取公开文章正文，再从正文中识别 arXiv ID。
- 每次运行会重新检查已保存的动态论文，发现不再满足文档智能相关性的论文会移出 `dynamic_papers.json`，并写入 `pending_dynamic_papers.json`。

## 修改步骤

1. 修复人工论文索引脚本路径
   - 修改 `scripts/build_paper_index.py`。
   - 将旧路径 `paper_latex/latex/custom.bib` 和 `paper_latex/latex/sections` 改为当前仓库的 `custom.bib` 和 `sections/`。
   - 输出继续写入 `docs/data/paper_index.json`。

2. 新增动态配置文件
   - 创建 `configs/dynamic_sources.json`。
   - 配置 Tavily、搜索 query、白名单、分类 taxonomy、自动发布阈值和每个 query 的最大结果数。
   - 配置 `documentRelevance` 文档智能相关性关键词门槛。
   - 配置 `llmClassification`，默认读取本地或 GitHub Secret 中的 `DMX_API_KEY`。

3. 新增 Python 依赖
   - 创建或更新 `requirements.txt`。
   - 第一版依赖为 `requests`、`feedparser`、`python-dateutil`。

4. 新增动态更新脚本
   - 创建 `scripts/update_dynamic_papers.py`。
   - 支持 `--dry-run`、`--max-results`、`--config`。
   - 读取配置、人工论文库、动态论文库、动态待审核库。
   - 调用 Tavily 搜索微信公众号文章。
   - 对搜索到的微信文章 URL 调用 Tavily Extract 提取公开正文。
   - 从搜索结果和可公开提取正文中识别 arXiv ID。
   - 调用 arXiv API 获取标准元数据。
   - 已存在于人工论文库的 arXiv ID 只合并公众号来源映射，不重复创建论文。
   - 已存在于动态论文库的 arXiv ID 合并新的 `sourceMentions`，并更新 `lastSeen`。
   - 对 arXiv 元数据执行大模型分类；大模型失败时使用关键词兜底。
   - 对候选论文执行文档智能相关性判断，用于分类和标注，不用于隐藏已验证的白名单公众号来源。
   - 只自动发布白名单来源、元数据完整、分类置信度达标的论文。
   - 白名单来源必须来自搜索结果或文章正文内容，不能只来自命中的白名单 query。
   - 其他候选写入 `docs/data/pending_dynamic_papers.json`。
   - 写入 `docs/data/update_log.json`。
   - 每次运行前检查现有动态论文，不相关论文移入待审核。

5. 首页改造
   - 修改 `docs/index.html`，新增 `Dynamic Overview` 容器。
   - 修改 `docs/js/app.js`：
     - 加载 `dynamic_papers.json`、`pending_dynamic_papers.json`、`update_log.json`。
     - 渲染动态总数、分类数量、待审核数量、最后更新时间。
     - Taxonomy 数量改为人工论文数量加动态论文数量。
     - 不改变 `Recent Papers` 数据来源。

6. 搜索页改造
   - 修改 `docs/js/search.js`：
     - 同时加载 `paper_index.json` 和 `dynamic_papers.json`。
     - 合并搜索人工论文和动态论文。
     - 动态论文显示 `Auto-discovered` 标签。
     - 从论文的 `sourceMentions` 或 `curatedSourceMentions` 读取公众号来源。
     - 在 arXiv 按钮旁显示一个或多个公众号文章按钮。
   - 修改 `docs/search.html`，移除或修复不存在的 `index.html#reading` 导航。

7. 新增 GitHub Actions
   - 创建 `.github/workflows/update-papers.yml`。
   - 每周运行一次，同时支持手动触发。
   - 安装 `requirements.txt`。
   - 运行 `python scripts/update_dynamic_papers.py`。
   - 使用 secret `TAVILY_API_KEY`。
   - 使用 secret `DMX_API_KEY`；可选配置 `DMX_BASE_URL` secret 和 `DMX_MODEL` variable。
   - 使用 `stefanzweifel/git-auto-commit-action@v5` 提交动态 JSON 数据。

8. 验证
   - 运行 `python scripts/build_paper_index.py`。
   - 运行 `python -m py_compile scripts/update_dynamic_papers.py scripts/build_paper_index.py`。
   - 运行 `python scripts/update_dynamic_papers.py --dry-run`。
   - 启动 `docs` 静态服务，确认首页和搜索页可加载。
   - 检查 `git status`，确认只包含预期变更。
