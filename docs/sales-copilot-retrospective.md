# Sales Copilot 项目复盘

## 范围

这份说明总结了当前分支中 `Sales Copilot` 项目的主要设计、实现、评测与 benchmark 方面的经验。

它的定位是供后续迭代参考的实践文档，而不是一份对外发布的正式报告。

## 我们构建了什么

`Sales Copilot` 最初只是一个以 parse 为中心的 workflow demo，后续逐步演化成一个更完整的 LLM 应用原型，主要包括：

- 基于 `LangGraph` 的有状态 workflow 编排
- 面向销售与客服场景的结构化解析能力
- 本地 `CRM/Tasks` 的 MCP 风格工具层，以及 `stdio MCP server` 支持
- 面向 `MiniMind` 的 OpenAI 兼容本地推理接口
- 带有 `hybrid retrieval` 与 `reranker` 实验的检索增强上下文能力
- 用于 parse、retrieval 和 workflow 的离线 benchmark 流水线

## Parse 主线：什么最稳

目前最像“可生产化基线”的方案，仍然是**不经过二次重写的 direct parse 路径**。

在校准过的 100 条子集上，当前 baseline 依然强于各种二次 refinement 变体。这说明现阶段最可靠的主路径，仍然是主 parse prompt 与 schema 本身。

主要原因有三点：

- baseline 在 `confirmed_needs` 上已经足够强
- 二次处理会在 `budget_signals`、`timeline_signals` 和 `next_steps` 上引入额外语义歧义
- 额外的 refinement 逻辑目前还没有证明自己能持续带来稳定净收益

## RAG 主线：我们加了什么

检索栈是分阶段增强的：

1. 关键词检索
2. embedding + 关键词的 `hybrid retrieval`
3. `cross-encoder reranker` 实验
4. retrieval benchmark、hard benchmark 和 dual-path benchmark

我们从中得到的经验是：

- 当 query 表达更接近真实输入时，`hybrid retrieval` 相比纯关键词检索有明显优势
- `reranker` 的工程接入已经完成，但当前的 reranker 选择和融合策略，还没有稳定超过最强的 hybrid baseline
- 即便当前还不是最主要的提分来源，retrieval 基础设施本身已经足够成熟，能支撑后续迭代

简而言之：

- RAG 基础设施进步很大
- RAG 的评测质量也进步很大
- RAG 已经成为项目里一个真实的工程子系统
- 但和 parse 质量相比，它还不是当前最强的用户侧差异化来源

## Benchmark 经验

最初的 `full-CSDS 800` parse benchmark 最终被证明是“有用，但有限”的。

最关键的经验是：

- 这套 800 条 benchmark 是基于 CSDS 摘要字段加适配规则生成出来的
- 所以它本质上是一个 weak benchmark，而不是完全独立的人工 gold benchmark

我们发现的主要问题包括：

- `budget_signals`、`timeline_signals` 和 `next_steps` 在适配后的 gold 中经常重叠
- 有些规则会把整句客服回复吸进字段，而不是提取干净的字段信号
- 当 benchmark 奖励的是另一种写法时，模型行为变好并不一定会带来分数提升

因此，这套 800 条 benchmark 更适合被用来做：

- 趋势跟踪
- 回归检查
- schema 稳定性检查

而不应该被当成模型质量的唯一最终裁判。

## AI-Calibrated 100

为了补一层更可信的 benchmark，我们构建了 `AI-calibrated 100` 子集：

- 来源：从完整的 CSDS test split 中抽样
- 目的：得到一套更便于复核、弱适配程度更低的 benchmark draft
- 角色：作为模型迭代时的主对比集

它依然不等同于完全人工复核的 benchmark，但已经比只依赖那套 800 条 weak auto-gold 更有用。

推荐的定位方式是：

- `full-CSDS 800`：用于大规模趋势跟踪的 weak benchmark
- `AI-calibrated 100`：用于模型比较的更优 benchmark draft

## 二次 Refinement：我们学到了什么

我们探索过多种二次 refinement 策略：

- freeform JSON reclassification
- tool-call reclassification
- 基于 confidence gate 的 merging
- 候选 span 生成 + 本地过滤

核心结论是：

- 二次 refinement 在工程上已经稳定
- 但它目前仍然没有在校准 benchmark 上稳定超过 direct baseline

这不是失败，反而是一个有用的结果。它告诉我们当前最实用的策略是：

- baseline parse 继续作为主线
- 二次 refinement 保留为实验线

## Semantic Metrics

我们还补了一套 semantic list-field metrics，让评测不再只依赖字面字符串重叠。

现在这套指标会和旧指标并行运行：

- 旧指标：更保守、更稳定、更适合回归
- semantic 指标：更接近“语义正确即可”

同时我们也发现，semantic scoring 对下面这些因素非常敏感：

- field guards
- 阈值选择
- 哪些字段允许绕过 guard 检查

这意味着 semantic metrics 很有价值，但它们应该被当作“需要调参的评测仪器”，而不是自动真理。

## 当前最务实的结论

在当前这个项目状态下：

- direct baseline parse 路径仍然是最强的主方案
- RAG 和 retrieval 基础设施已经比之前成熟得多
- benchmark 质量和评测严谨性有了明显提升
- 二次 refinement 对研究依然有价值，但还不适合作为默认生产路径

## 建议的下一步

最务实的下一步是：

1. 继续把 baseline parse 作为默认主线
2. 使用 `AI-calibrated 100` 作为主对比 benchmark
3. 只把 `full-CSDS 800` 当作 weak 的大规模趋势 benchmark
4. 按字段逐步、小心地继续调 semantic metrics
5. 如果还要继续做二次 refinement，只聚焦最差的字段，而不是再次重构整条链路

## 最终结论

这一阶段最大的收获，并不是每一条实验线都把分数提上去了。

真正最大的收获是，这个项目现在已经具备了：

- 更强的 parse baseline
- 一个真实可用的 retrieval 子系统
- 更诚实的 benchmark 结构
- 更清楚的主线方案与实验线分离

这让后续工作有了明显更可靠的基础。

## 人工销售 Workflow Benchmark

我们还额外加入了一套由 AI 编写的 50 条销售 workflow benchmark draft，用来覆盖 `CSDS` 衍生数据集无法很好体现的电商商家 / 平台销售场景。这套 benchmark 首先用于 workflow 级评测，尤其关注 route 选择、CRM 写回质量、任务生成质量，以及未来在真正销售场景下的 with-RAG vs without-RAG 对比。
