# 免费优先的文档智能更新

网站默认不调用付费搜索或模型服务。GitHub Pages 前端只读取静态 JSON，访问者搜索不会触发模型请求。

## 已启用的流程

- 每日北京时间 11:16，`Update Research Progress` 读取 arXiv 和 PaddleOCR、MinerU、Docling 的官方 Releases。按文档主题筛选、稳定 ID 去重，保留首次发表、修订和最后核验日期。
- 从已验证记录选取少量候选；摘要按来源内容指纹缓存。同一版本不会反复生成。没有模型账号时，展示明确标注的原始摘要节选。
- 预计算主题/意图检索索引；浏览器本地进行关键词、中英概念和潜在语义匹配。不提供无依据的实时问答。
- 旧周更任务改为免费兼容维护；不读取或调用 Tavily、DMX 的密钥和接口。历史公众号资料保留原核验时间。
- 每日 SOTA 更新继续独立运行。来源失败会保留旧数据及其真实时间，不能把任务运行时间当成新核验。

## 可选：启用免费中文 AI 摘要

这一步需要仓库所有者自己的 Cloudflare Free 账号。代码已经接好，但**不配置就不会请求模型**，也不影响抓取和检索。

1. 在 Cloudflare 确认使用 Free 计划；不要升级 Workers Paid，也不要添加付费回退。当前默认模型为 Free 计划可用的 `@cf/zai-org/glm-4.7-flash`。
2. 创建限定到相应账号的 Workers AI API token，权限按 [Cloudflare REST 设置文档](https://developers.cloudflare.com/workers-ai/get-started/rest-api/) 配置。不要把 token 发到聊天、提交进仓库或填进网页。
3. 打开本仓库 **Settings → Secrets and variables → Actions**，新增两个 Repository secrets：
   - `CLOUDFLARE_ACCOUNT_ID`：账号 ID。
   - `CLOUDFLARE_API_TOKEN`：上述 token。
4. 在同处 **Variables** 新增 `FREE_AI_PLAN_CONFIRMED=true`。这是账号仍处于免费计划的人工确认；程序不会替你核验套餐。没有这项确认，即使有密钥也不会调用。
5. 在 Actions 手动运行 **Update Research Progress**，检查摘要步骤状态和网页上的摘要标签。

默认限额以 `configs/free_intelligence.json` 为准。程序在请求前保存当日预算预留；达到上限、认证失败或遇到 429/额度错误时停止本批，剩余候选等待下次运行。不会切换服务商、模型或计费方案。只有摘要内容与来源一致、字段及证据检查通过的结果才会作为 AI 摘要显示；摘要只基于 arXiv 摘要或官方发布说明，不声称阅读全文。

Cloudflare 当前提供每日 10,000 Neurons 免费额度；请求数限制不等于 token/Neurons 精确估算，实际处理量取决于文本长度和模型。严格零额外费用的前提是账号保持 Free。参见 [官方价格与免费额度](https://developers.cloudflare.com/workers-ai/platform/pricing/) 和 [模型页面](https://developers.cloudflare.com/workers-ai/models/glm-4.7-flash/)。模型及免费政策变化时需复核配置。

## 维护与本地验证

```bash
python -m unittest discover -s tests -p 'test_*.py'
node tests/test_research_ui.js
node tests/test_sota_deployment.js
node tests/test_semantic_search.js
node tests/test_research_digest.js
node tests/test_search_sources.js
python scripts/enrich_research.py
python scripts/build_semantic_index.py
```

最后两条命令在没有 Cloudflare 三项配置时不请求任何模型。`research_intelligence_cache.json` 只包含公开来源、摘要、指纹和预算状态，不含账号 ID 或 token。
