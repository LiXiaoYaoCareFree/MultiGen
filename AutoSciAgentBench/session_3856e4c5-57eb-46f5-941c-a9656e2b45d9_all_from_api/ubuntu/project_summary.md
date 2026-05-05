# SciEval-Bench 构建流程总结与文件清单

## 一、五阶段构建流程

### 阶段一：原始论文采集（第1-2周）
使用 `scieval_collector.py` 从 arXiv 和 Semantic Scholar 双 API 批量采集论文元数据。167个关键词覆盖六大学科，目标2000-3000条原始数据。
```
python3 scieval_collector.py --dry-run          # 预览关键词
python3 scieval_collector.py --papers-per-keyword 10  # 正式采集
```

### 阶段二：论文筛选与预处理（第2-3周）
四步筛选：去重（arXiv ID）→ 全文可获取性过滤 → 时间窗口（2022+）→ 最终统计。目标保留1500-1800条。
使用 `scieval_enrichment.py` 同步从 OpenReview/Semantic Scholar/DBLP 采集论文状态、评审信息、引用数据和出处标签。

### 阶段三：结构化标注（第3-6周）
使用 `scieval_annotator.py` 进行 LLM 辅助标注 + 人工交叉校验。标注内容包括四层级学科路径、任务类型、难度级别、五维元数据、Code-Aware 编造检测清单。两人盲法独立标注，Kappa<0.7触发仲裁。

### 阶段四：质量控制（第6-8周）
使用 `scieval_qc.py`（三级）和 `scieval_qc_v1.1_upgrade.py`（四级）执行递进验证：格式合规 → 去污染一致性 → 难度多样性平衡 → 富标签完整性。目标综合评分≥85/100。

### 阶段五：发布打包（第8周）
使用 `scieval_packager.py`（v0.2.0）或 `scieval_packager_v0.3.0.py`（富标签版）生成语义化版本发布包，包含 README/CHANGELOG/VERSION/MANIFEST/SHA256。

---

## 二、核心文档清单（12篇）

| 文档 | 行数 | 内容 |
|------|:---:|------|
| `detailed_design_document.md` | 95 | 完整叙述性设计说明（动机→需求→调研→架构→决策→原创性） |
| `design_rationale.md` | 79 | 七个设计决策的动机与优势 |
| `construction_steps_detail.md` | 530 | 每步精确命令、参数、预期输出和注意事项 |
| `scieval_evaluation_guide.md` | 354 | 六系统评估+纯理论Code-Aware补充+适配器 |
| `evaluation_input_spec.md` | 398 | 每阶段输入参数详细规格（必要性、格式、示例） |
| `dataset_spec_v1.1_upgrade.md` | 236 | 四类富标签的完整JSON Schema定义 |
| `public_datasets_improvement.md` | 137 | 公开数据集分析与改进清单 |
| `system_interface_comparison.md` | 131 | 六系统接口对比与适配方案 |
| `research_arena_dataset_construction.md` | 127 | Research Arena 数据集构建方法分析 |
| `research_arena_implementation_analysis.md` | 121 | Research Arena 代码分析与优化方案 |
| `integrated_summary_report.md` | 57 | 三部分整合总结（构建+复现+迭代验证） |
| `dataset_purpose_explanation.md` | - | 数据集用途与目的说明 |

---

## 三、工具脚本清单（4个核心 + 2个升级模块）

| 脚本 | 行数 | 功能 |
|------|:---:|------|
| `scieval_collector.py` | 752 | 多源数据采集（arXiv+Semantic Scholar，167关键词×6学科） |
| `scieval_annotator.py` | 1112 | LLM辅助标注+人工校验+编造检测清单生成 |
| `scieval_qc.py` | 630 | 三级质量控制（格式→去污染→多样性） |
| `scieval_packager.py` | 200 | 语义化版本打包（README+CHANGELOG+SHA256） |
| `scieval_enrichment.py` | 652 | **新增**：富标签采集（OpenReview/S2/DBLP/Crossref API） |
| `scieval_qc_v1.1_upgrade.py` | 368 | **新增**：第四级富标签验证+100分制评分 |
| `scieval_packager_v0.3.0.py` | 209 | **新增**：v0.3.0富标签版打包器 |
| `iterative_self_review_prototype.py` | 473 | 迭代式自评审生成原型（Research Arena验证） |
| `run_evaluation.py` | - | 评估集成脚本 |

---

## 四、发布包版本

| 版本 | 位置 | 说明 |
|------|------|------|
| v0.2.0 | `SciEval-Bench-v0.2.0/` | 标注管线+QC引擎+Code-Aware（18文件） |
| v0.3.0 | `SciEval-Bench-v0.3.0/` | 富标签升级版（12文件，含示例数据和新增工具） |

---

## 五、阅读路径推荐

**快速理解设计 →** `design_rationale.md`（5分钟）→ `detailed_design_document.md`（10分钟）

**动手构建 →** `construction_steps_detail.md`（参考命令）→ 执行4个核心脚本

**评估系统 →** `scieval_evaluation_guide.md` + `evaluation_input_spec.md`

**升级到富标签 →** `dataset_spec_v1.1_upgrade.md` → `scieval_enrichment.py` → `scieval_qc_v1.1_upgrade.py`
