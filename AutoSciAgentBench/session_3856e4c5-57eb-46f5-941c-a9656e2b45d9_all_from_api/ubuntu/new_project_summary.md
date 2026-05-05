# SciEval-Bench 项目汇总（v0.3.0 富标签升级版）

## 一、六阶段构建流程（新增富标签采集）

### 阶段一：原始论文采集（第1-2周）
`scieval_collector.py` — 从 arXiv 和 Semantic Scholar 双 API 批量采集论文元数据。167个关键词覆盖六大学科。`--dry-run` 预览覆盖，`--papers-per-keyword 10` 正式采集，目标2000-3000条。

### 阶段二：论文筛选与预处理（第2-3周）
四步筛选：去重（arXiv ID）→ 全文可获取性过滤 → 时间窗口（2022+）→ 最终统计，目标保留1500-1800条。

### 阶段二-bis：富标签自动采集（第3周，v0.3.0新增）
`scieval_enrichment.py` — 对筛选后的论文批量采集四类富标签。SemanticScholarEnricher 获取引用数据（total_citations/citations_per_year/citation_velocity）和出处信息。OpenReviewEnricher 获取论文接受/拒绝状态和评审信息（评分、评语、推荐）。DBLPEnricher 补充会议/期刊出处。自动填充默认值（API不可用时 status=preprint、has_reviews=false）。

### 阶段三：结构化标注（第3-6周）
`scieval_annotator.py` — LLM辅助标注 + 人工交叉校验。标注内容：四层级学科路径、任务类型、难度级别、五维元数据、Code-Aware编造检测清单。两人盲法独立标注，Kappa<0.7触发仲裁。标注完成后自动填充阶段二-bis采集的富标签。

### 阶段四：质量控制（第6-8周）
`scieval_qc.py`（三级：格式→去污染→多样性）+ `scieval_qc_v1.1_upgrade.py`（第四级：富标签完整性）。四级验证覆盖：publication_status枚举值、review_information一致性（has_reviews与num_reviews匹配）、citation_impact合理性、provenance完整性、跨标签一致性（已接受论文应有评审、有代码应审核Code-Aware标记）。评分升级为100分制（格式30+一致性25+多样性25+富标签20），目标≥85/100。

### 阶段五：发布打包（第8周）
`scieval_packager.py`（v0.2.0）或 `scieval_packager_v0.3.0.py`（富标签版）。生成语义化版本发布包，包含 README/CHANGELOG/VERSION/MANIFEST/SHA256。v0.3.0新增 `data/sample_enriched.json` 含完整富标签示例。

---

## 二、核心文档清单（12篇）

| # | 文档 | 行数 | 内容概要 |
|---|------|:---:|------|
| 1 | `detailed_design_document.md` | 95 | 完整叙述性设计说明：动机→需求→调研→架构→决策→原创性 |
| 2 | `design_rationale.md` | 79 | 七个设计决策各一段：为什么、解决什么、比现有方法好在哪 |
| 3 | `construction_steps_detail.md` | 530 | 每步精确命令、参数、预期输出和注意事项 |
| 4 | `scieval_evaluation_guide.md` | 354 | 六系统评估流程+纯理论Code-Aware补充+适配器 |
| 5 | `evaluation_input_spec.md` | 398 | 每阶段输入参数详细规格（必要性、格式、示例） |
| 6 | `dataset_spec_v1.1_upgrade.md` | 236 | 四类富标签完整JSON Schema定义（v0.3.0核心） |
| 7 | `public_datasets_improvement.md` | 137 | 公开数据集分析+六项改进清单（v0.3.0基础） |
| 8 | `system_interface_comparison.md` | 131 | 六系统接口对比与适配方案 |
| 9 | `research_arena_dataset_construction.md` | 127 | Research Arena 数据集构建方法分析 |
| 10 | `research_arena_implementation_analysis.md` | 121 | Research Arena 代码分析+五问题+优化方案 |
| 11 | `integrated_summary_report.md` | 57 | 三部分整合：构建+复现+迭代验证结论 |
| 12 | `project_summary.md` | 79 | 本文件（原版） |

---

## 三、工具脚本清单（9个）

| # | 脚本 | 行数 | 功能 | 版本 |
|---|------|:---:|------|:---:|
| 1 | `scieval_collector.py` | 752 | 多源数据采集（arXiv+S2，167关键词） | v1.0 |
| 2 | `scieval_enrichment.py` | 652 | 富标签采集（OpenReview/S2/DBLP/Crossref） | **v0.3.0新增** |
| 3 | `scieval_annotator.py` | 1112 | LLM辅助标注+人工校验+编造检测清单 | v1.0 |
| 4 | `scieval_qc.py` | 630 | 三级质量控制（格式→去污染→多样性） | v1.0 |
| 5 | `scieval_qc_v1.1_upgrade.py` | 368 | 第四级富标签验证+100分制评分 | **v0.3.0新增** |
| 6 | `scieval_packager.py` | 200 | 语义化版本打包（v0.2.0） | v1.0 |
| 7 | `scieval_packager_v0.3.0.py` | 209 | 富标签版打包器 | **v0.3.0新增** |
| 8 | `iterative_self_review_prototype.py` | 473 | 迭代式自评审生成原型 | Research Arena验证 |
| 9 | `run_evaluation.py` | - | 评估集成脚本 | v1.0 |

---

## 四、发布包版本

| 版本 | 文件数 | 新增内容 |
|------|:---:|------|
| v0.1.0 | - | 初始原型（13条，4学科） |
| v0.2.0 | 18 | 标注管线+QC引擎+Code-Aware+编造检测清单 |
| v0.3.0 | 12 | 富标签（4类）+采集模块+四级QC+示例数据 |

---

## 五、阅读路径

| 目的 | 路径 | 用时 |
|------|------|:---:|
| 理解设计 | `design_rationale.md` → `detailed_design_document.md` | 15分钟 |
| 动手构建 | `construction_steps_detail.md` + 执行脚本1-7 | 8周 |
| 评估系统 | `scieval_evaluation_guide.md` + `evaluation_input_spec.md` | 20分钟 |
| 富标签升级 | `public_datasets_improvement.md` → `dataset_spec_v1.1_upgrade.md` → 脚本2+5 | 15分钟 |
| Research Arena | `research_arena_dataset_construction.md` → `research_arena_implementation_analysis.md` → 脚本8 | 20分钟 |
