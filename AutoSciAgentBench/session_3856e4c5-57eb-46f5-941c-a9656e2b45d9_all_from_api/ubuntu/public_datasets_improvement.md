# 公开数据集分析 — SciEval-Bench 改进点清单

## 一、可用的高价值数据源

从公开数据集中识别出以下可直接集成到 SciEval-Bench 的数据源，按优先级排序：

### 1.1 PeerRead（高优先级，直接可用）

**规模：** 14,700+篇论文草稿，10,700+条评审意见。**覆盖：** 计算机科学（AI/ML/NLP）。**关键标签：** 接受/拒绝标签（核心价值）、文本评审意见、部分评分。**集成方式：** 通过 HuggingFace datasets API 直接加载，提取接受/拒绝标签和评审文本，将评审意见对齐到 SciEval-Bench 的九维度评分框架。

### 1.2 ICLR Open Reviews（高优先级，直接可用）

**规模：** 10,000+篇论文，40,000+条评审。**覆盖：** AI/ML。**关键标签：** 接受/拒绝标签、详细评审意见、多轮讨论（评审-作者反驳-评审修订）。**集成方式：** 从 OpenReview API 批量下载，提取官方接受/拒绝决策作为论文质量标签（对应 SciEval-Bench 的 paper_quality_grade），将评审评分映射到九维度。

### 1.3 MOPRD（中优先级，跨学科扩展）

**规模：** 6,578篇论文，617种期刊。**覆盖：** 多学科（计算机科学、工程、生命科学、医学）。**关键标签：** 元评审、作者反驳、编辑决定、多版本手稿。**集成方式：** 用于扩展 SciEval-Bench 的学科覆盖——MOPRD 是唯一覆盖多学科且包含完整评审流程数据的数据集。

### 1.4 Re²（中优先级，全阶段评审数据）

**规模：** 19,926篇提交，70,668条评审，120,000+条对话。**覆盖：** 计算机科学24个会议+21个研讨会。**关键标签：** 多轮对话、作者反驳、最终决策。**集成方式：** 用于增强 SciEval-Bench 的评审校准——将 Re² 的多轮评审数据用于验证评审器的一致性。

---

## 二、可集成的标签维度

基于公开数据集中的标签信息，建议在 SciEval-Bench 的 `metadata.json` 中新增以下标签维度：

### 2.1 接受状态标签（来源：PeerRead、ICLR、Re²）

```json
"acceptance_status": {
    "decision": "accepted" | "rejected" | "withdrawn",
    "venue": "ICLR 2024",
    "acceptance_rate": "27%",
    "decision_confidence": "high" | "medium" | "low"
}
```

**用途：** 直接作为 `paper_quality_grade`（A/B/C）的校准基准。已接收论文→A级，接近接收的拒稿→B级，明确拒稿→C级。

### 2.2 评审分数标签（来源：ICLR、Kaggle、PeerRead）

```json
"review_scores": {
    "overall_score": 6.5,
    "confidence_score": 4,
    "dimension_scores": {
        "novelty": 3,
        "soundness": 3,
        "presentation": 3,
        "contribution": 3
    },
    "num_reviews": 3,
    "inter_reviewer_agreement": 0.72
}
```

**用途：** 作为 SciEval-Bench 九维度评分的校准数据——将人类评审评分与AI评审评分进行相关性分析。

### 2.3 引用影响力标签（来源：Semantic Scholar、Crossref API）

```json
"citation_impact": {
    "total_citations": 45,
    "citations_per_year": 15.2,
    "h_index_context": 12,
    "influential_citations": 8
}
```

**用途：** 增强 `citation_depth` 标注——从模糊的 low/medium/high 升级为量化指标。

### 2.4 评审过程完整性标签（来源：Re²、MOPRD）

```json
"review_process": {
    "has_rebuttal": true,
    "rebuttal_rounds": 1,
    "has_meta_review": true,
    "reviewer_identities": "anonymous" | "open" | "partially_open",
    "review_timeline_days": 45
}
```

**用途：** 标注论文的评审完整性——经历过完整评审流程的论文比仅基于预印本的论文有更高的质量置信度。

### 2.5 开放获取与复现性标签

```json
"accessibility": {
    "is_open_access": true,
    "has_code": true,
    "code_repository_url": "https://github.com/...",
    "has_data": true,
    "has_appendix": true
}
```

**用途：** 直接关联 Code-Aware 子类型的判定——有代码仓库的论文天然适合 Code-Aware。

---

## 三、数据集构建改进方案

### 3.1 丰富标注维度（基于 PeerRead/ICLR 标签）

当前 SciEval-Bench 的 `paper_quality_grade`（A/B/C）基于摘要中的关键词推断，精度有限。改进方案：对于有 PeerRead 或 ICLR 评审数据的论文，直接使用 **官方接受/拒绝决策** 作为质量标签。这是比关键词推断更准确、更权威的质量信号。

### 3.2 新增评审校准数据集（基于 ICLR/Re² 评审分数）

在 SciEval-Bench 的数据集中新增一个 **评审校准子集** ——选取200-500篇已有真实人类评审分数和接受/拒绝决策的论文，不用于AI科研工具的任务评估，而专门用于验证评审器的准确性。这直接对标 AI-Researcher 使用32对 ICLR 论文验证评审器的做法，但规模扩大5-10倍。

### 3.3 引入跨学科评审数据（基于 MOPRD）

MOPRD 是唯一覆盖多学科（CS、工程、生命科学、医学）且包含完整评审流程的数据集。将其评审数据用于扩展 SciEval-Bench 的非CS学科——自然科学和医学的论文可以从 MOPRD 中提取评审意见和质量标签。

### 3.4 引用标签升级（基于 Semantic Scholar + Crossref API）

将引用标注从模糊的 `citation_depth: low/medium/high` 升级为量化指标——通过 Semantic Scholar API 批量查询引用次数、引用密度和引用影响力，为每篇论文自动标注 `citation_impact` 对象。

### 3.5 集成开放评审平台动态数据（基于 OpenReview API + F1000Research API）

SciEval-Bench 的 "可扩展生态"（任务三）设计可以具体化为：定期（每月）从 OpenReview 和 F1000Research 获取最新的评审数据和接受论文列表，自动更新数据集的评审校准子集，确保校准数据随领域发展而更新。

---

## 四、实施优先级

| 优先级 | 改进项 | 数据源 | 工作量 | 预期收益 |
|--------|--------|--------|--------|----------|
| **P0** | 接受状态标签集成 | PeerRead + ICLR | 2天 | 质量标签精度从关键词推断升级为权威决策 |
| **P0** | 评审校准子集 | ICLR + Re² | 3天 | 评审器验证从32对→200-500篇 |
| **P1** | 量化引用标签 | Semantic Scholar API | 1天 | 引用标注从模糊三级→量化指标 |
| **P1** | 开放获取/代码标签 | Crossref + GitHub API | 1天 | 直接关联 Code-Aware 判定 |
| **P2** | MOPRD 跨学科数据 | MOPRD | 3天 | 非CS学科的质量标签覆盖 |
| **P2** | 动态评审数据更新 | OpenReview API | 2天 | 校准数据随领域发展持续更新 |
