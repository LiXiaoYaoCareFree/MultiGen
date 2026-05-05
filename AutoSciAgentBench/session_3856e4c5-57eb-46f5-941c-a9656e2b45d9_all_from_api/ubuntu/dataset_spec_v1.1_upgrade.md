# SciEval-Bench 数据集规范 v1.1 — 元数据升级版

## 变更概要

v1.0 → v1.1 的核心升级：基于 PeerRead、ICLR Open Reviews、MOPRD、Re² 等公开数据集的分析，在 `metadata.json` 中新增四类富标签——论文状态、评审信息、引用影响力和出处信息。这些标签将质量标注从模糊关键词推断升级为权威数据驱动的精准标注。

---

## 新增字段一：论文状态标签 `publication_status`

### 字段定义

```json
"publication_status": {
    "status": "accepted" | "rejected" | "preprint" | "published" | "withdrawn",
    "venue": "ICLR 2024",
    "venue_type": "conference" | "journal" | "workshop" | "preprint_server",
    "acceptance_rate": 0.27,
    "decision_date": "2024-01-15",
    "decision_source": "openreview_api" | "peerread" | "moprd" | "manual" | "unknown"
}
```

### 字段说明

| 字段 | 类型 | 必要性 | 来源 | 说明 |
|------|------|:---:|------|------|
| `status` | enum | **必填** | PeerRead/ICLR/手动 | accepted/rejected/preprint/published/withdrawn |
| `venue` | string | 条件必填 | 论文元数据 | 如 "ICLR 2024"，preprint时可为空 |
| `venue_type` | enum | 条件必填 | 数据库分类 | conference/journal/workshop/preprint_server |
| `acceptance_rate` | float | 可选 | 会议官网 | 该venue的接受率（如27%），用于校准难度 |
| `decision_date` | string | 可选 | OpenReview API | 格式 YYYY-MM-DD |
| `decision_source` | enum | **必填** | 标注记录 | 标签的数据来源，确保可追溯性 |

### 与原有 paper_quality_grade 的校准关系

- `status=accepted` + 顶会(NeurIPS/ICML/ICLR) → `paper_quality_grade: A`
- `status=accepted` + 好会(ACL/CVPR/AAAI) → `paper_quality_grade: B`
- `status=rejected` + 顶会 → `paper_quality_grade: B`
- `status=preprint` → `paper_quality_grade` 由标注者根据内容判定
- `status=rejected` + workshop → `paper_quality_grade: C`

---

## 新增字段二：评审信息标签 `review_information`

### 字段定义

```json
"review_information": {
    "has_reviews": true,
    "num_reviews": 3,
    "review_scores": {
        "overall": 6.5,
        "confidence": 4,
        "dimensions": {
            "novelty": 3,
            "soundness": 3,
            "presentation": 3,
            "contribution": 3
        }
    },
    "review_texts": [
        {
            "reviewer_id": "reviewer_1",
            "summary": "This paper presents a novel approach...",
            "strengths": ["Strong theoretical foundation", "Comprehensive experiments"],
            "weaknesses": ["Missing key baseline comparison", "Limited ablation study"],
            "recommendation": "weak_accept"
        }
    ],
    "has_rebuttal": true,
    "rebuttal_rounds": 1,
    "has_meta_review": true,
    "inter_reviewer_agreement": 0.72,
    "review_source": "openreview_api" | "peerread" | "moprd" | "re2" | "none"
}
```

### 字段说明

| 字段 | 类型 | 必要性 | 用途 |
|------|------|:---:|------|
| `has_reviews` | bool | **必填** | 是否有评审数据（快速筛选） |
| `num_reviews` | int | 条件必填 | 评审数量，用于评审可靠性评估 |
| `review_scores` | object | 条件必填 | 人类评审的维度评分——**直接作为AI评审器校准基准** |
| `review_texts` | array | 可选 | 评审全文/摘要——用于评审质量分析和LLM评审比较 |
| `has_rebuttal` | bool | 可选 | 是否有作者反驳——经历反驳的论文质量置信度更高 |
| `has_meta_review` | bool | 可选 | 是否有元评审——元评审是更权威的质量信号 |
| `inter_reviewer_agreement` | float | 可选 | 评审者间一致性——用于验证人类评审本身的可信度 |
| `review_source` | enum | **必填** | 评审数据来源，确保可追溯 |

### 评审校准子集

从数据集中选取 `has_reviews=true` 且 `review_scores` 完整的200-500篇论文，构建评审校准子集。该子集不用于AI工具的任务评估，专门用于：验证AI评审器的评分与人类评审的一致性（Spearman ρ），检测AI评审器的系统性偏差（偏高/偏低），分析AI评审在不同维度上的准确性差异。

---

## 新增字段三：引用影响力标签 `citation_impact`

### 字段定义

```json
"citation_impact": {
    "total_citations": 45,
    "citations_per_year": 15.2,
    "h_index_context": 12,
    "influential_citations": 8,
    "citation_velocity": "high" | "medium" | "low",
    "citation_source": "semantic_scholar_api",
    "retrieved_at": "2026-04-29"
}
```

### 字段说明

| 字段 | 类型 | 必要性 | 说明 |
|------|------|:---:|------|
| `total_citations` | int | **必填** | 总引用次数，从Semantic Scholar API获取 |
| `citations_per_year` | float | **必填** | 年均引用数 = total_citations / (当前年份 - 发表年份 + 1) |
| `h_index_context` | int | 可选 | 该论文作者的h-index（如有） |
| `influential_citations` | int | 可选 | 高影响力引用数（被高引论文引用） |
| `citation_velocity` | enum | 可选 | 引用增长速度——high(年均>20)/medium(5-20)/low(<5) |
| `citation_source` | string | **必填** | 数据来源API |
| `retrieved_at` | string | **必填** | 数据获取时间（引用数据会随时间变化） |

### 与原有 citation_depth 的校准关系

- `total_citations ≥ 50` → `citation_depth: high`
- `total_citations 10-49` → `citation_depth: medium`
- `total_citations < 10` → `citation_depth: low`

---

## 新增字段四：出处与可复现性标签 `provenance`

### 字段定义

```json
"provenance": {
    "conference": "ICLR",
    "conference_year": 2024,
    "journal": null,
    "publisher": "OpenReview",
    "is_open_access": true,
    "license": "CC BY 4.0",
    "has_code": true,
    "code_repository_url": "https://github.com/author/paper-code",
    "code_license": "MIT",
    "has_data": true,
    "data_url": "https://github.com/author/paper-data",
    "has_appendix": true,
    "is_preprint_of_published": true,
    "published_doi": "10.xxxx/xxxxx"
}
```

### 字段说明

| 字段 | 类型 | 必要性 | 说明 |
|------|------|:---:|------|
| `conference` | string | 条件必填 | 会议名称（如已知） |
| `conference_year` | int | 条件必填 | 会议年份 |
| `journal` | string | 条件必填 | 期刊名称（如已知） |
| `is_open_access` | bool | **必填** | 是否开放获取 |
| `has_code` | bool | **必填** | 是否有代码仓库——**直接触发 Code-Aware 判定** |
| `code_repository_url` | string | 条件必填 | 代码仓库URL |
| `has_data` | bool | 可选 | 是否有公开数据集 |
| `has_appendix` | bool | 可选 | 是否有附录（补充材料） |
| `is_preprint_of_published` | bool | 可选 | 该预印本是否已有正式出版版本 |

---

## 五、升级后的完整 metadata.json Schema

升级后的 `metadata.json` 包含五个顶层对象（原有两个 + 新增三个）：

```json
{
    "paper_id": "CS-AI-001",
    
    "discipline_annotations": { ... },      // 原有：四层级学科路径
    "content_annotations": { ... },         // 原有：研究类型/论证类型/数学密集度
    "quality_annotations": { ... },         // 原有：引用深度/论证复杂度/创新程度/质量等级
    "source_annotations": { ... },          // 原有：数据库/出版日期/许可
    "decontamination": { ... },             // 原有：去污染标注
    
    "publication_status": { ... },          // **新增**：论文状态
    "review_information": { ... },          // **新增**：评审信息
    "citation_impact": { ... },             // **新增**：引用影响力
    "provenance": { ... }                   // **新增**：出处与可复现性
}
```

### 字段必要性汇总

| 字段组 | 有公开数据时 | 无公开数据时（如arXiv预印本） |
|--------|:----------:|:--------------------------:|
| `publication_status` | 全部必填 | status=preprint，decision_source=unknown |
| `review_information` | 全部必填 | has_reviews=false，review_source=none |
| `citation_impact` | 全部必填（通过API自动获取） | total_citations/citations_per_year 必填 |
| `provenance` | 全部必填 | is_open_access/has_code 必填，其余可选 |

---

## 六、实施路径

### 6.1 自动填充（通过API）

对现有1200条数据执行以下批量更新（约半天）：

```bash
# 1. 从 PeerRead/ICLR 匹配接受状态
python3 tools/enrich_publication_status.py --source peerread,iclr

# 2. 从 Semantic Scholar API 批量获取引用数据
python3 tools/enrich_citation_impact.py --api semantic_scholar

# 3. 从 Crossref API 获取出处和许可信息
python3 tools/enrich_provenance.py --api crossref

# 4. 从 GitHub API 检测代码仓库
python3 tools/enrich_code_availability.py
```

### 6.2 人工标注（无法自动获取的字段）

- `review_information.review_texts`：从 PeerRead/ICLR/Re² 的评审文本中提取摘要
- `review_information.inter_reviewer_agreement`：从多评审评分中计算
- `provenance.has_appendix`：检查论文PDF是否有附录

### 6.3 版本计划

- v1.1.0：新增四个字段组，批量回填已有1200条数据
- v1.2.0：构建评审校准子集（200-500篇），验证AI评审器准确性
- v2.0.0：所有新实例默认携带完整富标签
