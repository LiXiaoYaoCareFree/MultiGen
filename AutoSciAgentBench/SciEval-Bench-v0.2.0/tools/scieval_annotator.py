#!/usr/bin/env python3
"""
SciEval-Bench 标注管线
=======================
LLM辅助 + 人工校验的标注流程，支持：

阶段一：自动标注 (LLM-assisted)
  - 四层级学科路径标注
  - 任务类型分配
  - 难度级别判定
  - 五维元数据标注 (研究类型/论证类型/数学密集度/图表依赖/创新程度等)
  - 输入输出配对构建

阶段二：Code-Aware标注
  - 可验证声明提取
  - 编造检测清单生成 (符合 dataset_final_spec.md 格式)

阶段三：人工校验
  - 标注审核界面
  - 分歧标记与解决
  - 交叉验证统计 (Kappa)
"""
import json
import os
import re
import hashlib
import random
import argparse
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT_PATH = os.path.join(PROJECT_ROOT, "scieval_annotations", "to_annotate.json")
DEFAULT_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "scieval_annotations")


# ============================================================
# 数据模型
# ============================================================

@dataclass
class DisciplineAnnotation:
    """学科标注"""
    primary_path: List[str]       # 四层级主路径
    cross_discipline_tags: List[str] = field(default_factory=list)
    confidence: float = 0.0       # 标注置信度 [0, 1]
    annotator: str = "auto"       # "auto" | "human_reviewed"
    human_review_notes: str = ""


@dataclass
class ContentAnnotation:
    """内容标注"""
    research_type: str = ""       # theoretical/empirical/methodological/survey/application
    argumentation_type: str = ""  # deductive/inductive/analogical/empirical
    math_density: str = ""        # none/low/medium/high
    figure_dependency: str = ""   # none/low/medium/high
    section_boundaries: Dict[str, Tuple[int, int]] = field(default_factory=dict)


@dataclass
class QualityAnnotation:
    """质量标注"""
    citation_depth: str = ""      # low/medium/high
    argument_complexity: str = "" # low/medium/high
    innovation_level: str = ""    # incremental_improvement/significant_improvement/breakthrough/survey
    paper_quality_grade: str = "" # A/B/C (对应顶会/好会议/workshop)


@dataclass
class SourceAnnotation:
    """来源标注"""
    database: str = ""
    publication_date: str = ""
    license_type: str = ""
    is_preprint: bool = True


@dataclass
class DecontaminationAnnotation:
    """去污染标注"""
    risk_level: str = "suspicious"
    gpt4_cutoff_safe: bool = False
    gpt4o_cutoff_safe: bool = False
    claude_cutoff_safe: bool = False
    gemini_cutoff_safe: bool = False
    notes: str = ""


@dataclass
class TaskAnnotation:
    """任务标注"""
    task_type: str = ""             # 六种任务类型之一
    difficulty_level: int = 1       # 1-3
    is_code_aware: bool = False
    rationale: str = ""


@dataclass
class FabricationClaim:
    """编造检测声明"""
    claim_id: str
    claim_type: str            # numerical_result/method_description/comparison_claim/citation_dependency
    claim_location: Dict       # {"section": str, "paragraph": int}
    claim_text: str
    verification_method: str   # results_json/code_inspection/crossref_api/log_analysis
    tolerance: Optional[Dict]  # {"absolute": float, "relative": float} or None
    required_evidence: str


@dataclass
class FabricationChecklist:
    """编造检测清单"""
    paper_id: str
    checklist_version: str = "1.0.0"
    verifiable_claims: List[FabricationClaim] = field(default_factory=list)

    def validate(self) -> Tuple[bool, List[str]]:
        """验证清单质量"""
        issues = []
        if len(self.verifiable_claims) < 5:
            issues.append("至少需要5条声明")
        if len(self.verifiable_claims) > 15:
            issues.append("最多15条声明")

        sections_covered = set()
        type_counts = {}
        for c in self.verifiable_claims:
            sections_covered.add(c.claim_location.get("section", ""))
            type_counts[c.claim_type] = type_counts.get(c.claim_type, 0) + 1

        if len(sections_covered) < 3:
            issues.append("声明需覆盖至少3个不同章节")

        total = len(self.verifiable_claims)
        numerical_pct = type_counts.get("numerical_result", 0) / total if total else 0
        method_pct = type_counts.get("method_description", 0) / total if total else 0
        if numerical_pct < 0.3:
            issues.append(f"numerical_result占比过低({numerical_pct:.0%}, 需要≥30%)")
        if method_pct < 0.15:
            issues.append(f"method_description占比过低({method_pct:.0%}, 需要≥15%)")

        return len(issues) == 0, issues


@dataclass
class AnnotationRecord:
    """完整标注记录"""
    paper_id: str
    discipline: DisciplineAnnotation
    content: ContentAnnotation
    quality: QualityAnnotation
    source: SourceAnnotation
    decontamination: DecontaminationAnnotation
    task: TaskAnnotation
    fabrication_checklist: Optional[FabricationChecklist] = None
    annotated_at: str = ""
    human_reviewed: bool = False
    human_reviewer: str = ""
    inter_annotator_agreement: Optional[Dict] = None


# ============================================================
# 学科分类学 (taxonomy.json 内容)
# ============================================================

TAXONOMY = {
    "formal_sciences": {
        "name_zh": "形式科学",
        "sub_disciplines": {
            "computer_science": {
                "name_zh": "计算机科学",
                "research_areas": ["人工智能", "自然语言处理", "计算机视觉",
                                  "机器学习系统", "理论计算机科学", "机器人学"]
            },
            "mathematics": {
                "name_zh": "数学",
                "research_areas": ["优化理论", "数值分析", "概率论与统计"]
            },
            "logic": {"name_zh": "逻辑学", "research_areas": ["形式逻辑", "计算逻辑"]}
        }
    },
    "natural_sciences": {
        "name_zh": "自然科学",
        "sub_disciplines": {
            "physics": {"name_zh": "物理学", "research_areas": ["量子计算", "凝聚态物理", "高能物理"]},
            "chemistry": {"name_zh": "化学", "research_areas": ["有机合成", "催化设计", "计算化学"]},
            "earth_science": {"name_zh": "地球科学", "research_areas": ["气候科学", "地质学"]}
        }
    },
    "engineering": {
        "name_zh": "工程与技术科学",
        "sub_disciplines": {
            "electrical_engineering": {"name_zh": "电子工程", "research_areas": ["信号处理", "通信系统"]},
            "materials_science": {"name_zh": "材料科学", "research_areas": ["新型材料", "纳米材料"]},
            "mechanical_engineering": {"name_zh": "机械工程", "research_areas": ["机器人控制", "流体动力学"]}
        }
    },
    "medical_life_sciences": {
        "name_zh": "医学与生命科学",
        "sub_disciplines": {
            "biology": {"name_zh": "生物学", "research_areas": ["基因编辑", "蛋白质工程", "生物信息学"]},
            "clinical_medicine": {"name_zh": "临床医学", "research_areas": ["诊断方法", "治疗策略"]}
        }
    },
    "social_sciences": {
        "name_zh": "社会科学",
        "sub_disciplines": {
            "economics": {"name_zh": "经济学", "research_areas": ["因果推断", "计量经济学"]},
            "psychology": {"name_zh": "心理学", "research_areas": ["认知心理学", "社会心理学"]},
            "sociology": {"name_zh": "社会学", "research_areas": ["社会网络分析", "组织行为"]}
        }
    },
    "humanities": {
        "name_zh": "人文学科",
        "sub_disciplines": {
            "philosophy": {"name_zh": "哲学", "research_areas": ["认识论", "伦理学", "科学哲学"]},
            "linguistics": {"name_zh": "语言学", "research_areas": ["理论语言学", "计算语言学"]},
            "history": {"name_zh": "历史学", "research_areas": ["数字人文", "史学方法论"]}
        }
    }
}


# ============================================================
# LLM 提示词模板
# ============================================================

ANNOTATION_PROMPTS = {
    "discipline": """你是一位学术论文分类专家。请根据以下论文信息，标注其完整的四层级学科路径。

## 论文信息
标题: {title}
摘要: {abstract}
arXiv分类: {categories}

## 学科分类学
{taxonomy_summary}

## 输出要求
请以JSON格式输出：
{{
    "primary_path": ["学科大类", "学科门类", "子学科", "研究方向"],
    "cross_discipline_tags": ["跨学科标签1", "跨学科标签2"],
    "confidence": 0.0-1.0,
    "rationale": "标注理由（50字以内）"
}}

注意：
1. 学科大类必须从以下选择：形式科学、自然科学、工程与技术科学、医学与生命科学、社会科学、人文学科
2. 四层级路径必须完整（四个元素）
3. 如果论文涉及多个学科，在cross_discipline_tags中标注""",

    "task_type": """你是一位AI科研评估专家。请根据论文信息，确定最适合的评估任务类型和难度级别。

## 论文信息
标题: {title}
摘要: {abstract}

## 可选任务类型
1. full_paper_generation - 完整论文生成（需要有清晰的方法和实验）
2. literature_review - 文献综述生成（综述类论文）
3. experiment_design - 实验方案设计（需要有可分离的假设和实验设计）
4. research_proposal - 研究提案生成（有明确的研究方向和创新点）
5. paper_extension - 论文扩展与改写（可作为草稿扩展的论文）
6. peer_review - 同行评审生成（适合被评审的完整论文）

## 难度级别
1. Level-1（引导式）：可提供明确研究指令和实验数据
2. Level-2（半自主）：仅提供主题和参考文献
3. Level-3（全自主）：仅提供学科领域方向

## 输出要求
{{
    "task_type": "任务类型代码",
    "difficulty_level": 1-3,
    "is_code_aware": true/false,
    "rationale": "分配理由（50字以内）"
}}

注意：is_code_aware为true仅当task_type为full_paper_generation或experiment_design且论文包含可执行实验代码时。""",

    "content_metadata": """你是一位学术论文分析专家。请根据论文信息标注内容维度的元数据。

## 论文信息
标题: {title}
摘要: {abstract}

## 标注维度

1. research_type（研究类型）：
   - theoretical: 以数学证明、理论推导为核心
   - empirical: 以实验观察和数据分析为核心
   - methodological: 以提出新算法、新工具或新框架为核心
   - survey: 以系统梳理归纳已有工作为核心
   - application: 以在特定场景中应用已有方法为核心

2. argumentation_type（论证类型）：
   - deductive: 从一般原理推导特定结论
   - inductive: 从特定观察归纳一般规律
   - analogical: 通过与已知事物类比论证
   - empirical: 以实验数据作为主要论证手段

3. math_density（数学密集度）：
   - none: 无公式
   - low: ≤5个独立公式
   - medium: 6-20个独立公式
   - high: >20个独立公式

4. figure_dependency（图表依赖度）：
   - none: 无图表
   - low: 1-2个图表
   - medium: 3-8个图表
   - high: >8个图表

## 输出要求
{{
    "research_type": "类型代码",
    "argumentation_type": "类型代码",
    "math_density": "级别代码",
    "figure_dependency": "级别代码",
    "confidence": 0.0-1.0
}}""",

    "quality_metadata": """标注论文的质量维度元数据。

## 论文信息
标题: {title}
摘要: {abstract}

## 标注维度
1. citation_depth: low/medium/high（基于参考文献数量和引用方式）
2. argument_complexity: low/medium/high（论点数量和逻辑链条长度）
3. innovation_level: incremental_improvement/significant_improvement/breakthrough/survey
4. paper_quality_grade: A/B/C（顶会级/好会议级/workshop级）

## 输出要求
{{
    "citation_depth": "级别",
    "argument_complexity": "级别",
    "innovation_level": "级别",
    "paper_quality_grade": "等级"
}}""",

    "fabrication_checklist": """为这篇论文生成编造检测清单。你需要识别论文中可以通过实验代码验证的关键声明。

## 论文信息
标题: {title}
摘要: {abstract}

## 声明类型
1. numerical_result: 论文中报告的数值结果（准确率、F1、运行时间等）
2. method_description: 声称实现的方法组件（优化器、架构、超参数等）
3. comparison_claim: 声称的相对性能（"优于""达到SOTA"等）
4. citation_dependency: 引用并依赖其结论的外部工作

## 输出要求
生成5-10条可验证声明，每条包含：
- claim_type: 声明类型
- claim_location: {{"section": "章节名", "paragraph": 段落索引(0-based)}}
- claim_text: 精确的原文引用
- verification_method: results_json/code_inspection/crossref_api/log_analysis
- tolerance: {{"absolute": 绝对容差, "relative": 相对容差}} (仅numerical_result)
- required_evidence: 验证时需要的具体证据描述

JSON格式：
{{
    "verifiable_claims": [
        {{
            "claim_type": "...",
            "claim_location": {{"section": "...", "paragraph": 0}},
            "claim_text": "...",
            "verification_method": "...",
            "tolerance": null,
            "required_evidence": "..."
        }}
    ]
}}

注意：
1. 声明必须覆盖至少3个不同章节
2. numerical_result占比40-60%
3. method_description占比20-30%
4. claim_text必须像是论文中实际会出现的表述""",
}


# ============================================================
# LLM 标注器（模拟LLM的规则+启发式标注）
# ============================================================

class LLMAnnotator:
    """
    LLM辅助标注器
    生产环境中替换为真实的LLM API调用
    当前使用规则+启发式方法模拟LLM标注行为
    """

    def __init__(self, taxonomy: Dict = None):
        self.taxonomy = taxonomy or TAXONOMY

    def annotate_discipline(self, paper: Dict) -> DisciplineAnnotation:
        """根据论文元数据进行学科标注"""
        title = (paper.get("title") or "").lower()
        abstract = (paper.get("abstract") or "").lower()
        categories = paper.get("categories", [])
        text = title + " " + abstract

        # 规则匹配
        rules = [
            (["形式科学", "计算机科学", "人工智能", "深度学习"],
             ["deep learning", "neural network", "reinforcement learning", "transformer",
              "attention mechanism", "graph neural", "diffusion model"]),
            (["形式科学", "计算机科学", "自然语言处理", "文本生成"],
             ["language model", "machine translation", "text generation", "nlp",
              "sentiment analysis", "named entity", "question answering"]),
            (["形式科学", "计算机科学", "计算机视觉", "图像识别"],
             ["object detection", "image segmentation", "computer vision",
              "visual recognition", "video understanding"]),
            (["自然科学", "物理学", "量子计算", "量子算法"],
             ["quantum computing", "quantum algorithm", "qubit", "quantum error"]),
            (["自然科学", "化学", "有机合成", "逆合成分析"],
             ["organic synthesis", "retrosynthetic", "catalysis", "cross-coupling"]),
            (["自然科学", "地球科学", "气候科学", "气候模型"],
             ["climate", "atmospheric", "ocean", "carbon cycle"]),
            (["工程与技术科学", "材料科学", "新型材料", "纳米材料"],
             ["material", "alloy", "perovskite", "nanomaterial", "metamaterial"]),
            (["工程与技术科学", "电子工程", "信号处理", "通信系统"],
             ["signal processing", "MIMO", "beamforming", "wireless communication"]),
            (["工程与技术科学", "机械工程", "机器人控制", "动力学"],
             ["robotics", "manipulation", "actuator", "finite element"]),
            (["医学与生命科学", "生物学", "基因编辑", "CRISPR"],
             ["crispr", "gene editing", "genome", "base editing", "protein engineering"]),
            (["医学与生命科学", "生物学", "蛋白质工程", "计算生物学"],
             ["protein structure", "enzyme design", "AlphaFold", "directed evolution"]),
            (["社会科学", "经济学", "因果推断", "计量方法"],
             ["causal inference", "difference-in-differences", "instrumental variable",
              "treatment effect", "econometric"]),
            (["社会科学", "心理学", "认知心理学", "实验心理学"],
             ["cognitive", "psychology", "behavioral", "mental", "emotion regulation"]),
            (["社会科学", "社会学", "社会网络分析", "组织行为"],
             ["social network", "inequality", "urban", "migration", "collective action"]),
            (["人文学科", "哲学", "科学哲学", "认识论"],
             ["philosophy", "epistemology", "ethics", "metaphysics", "ontology"]),
            (["人文学科", "语言学", "理论语言学", "句法学"],
             ["linguistics", "syntax", "semantics", "phonology", "morphology"]),
            (["人文学科", "历史学", "史学方法论", "数字人文"],
             ["history", "historiography", "digital humanities", "archival"]),
        ]

        best_path = ["形式科学", "计算机科学", "人工智能", "深度学习"]
        best_score = 0
        cross_tags = []

        for path, keywords in rules:
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best_path = path
                # 添加跨学科标签
                if len(path) >= 2:
                    cross_tags = [f"{path[0]}-交叉"]

        confidence = min(0.5 + best_score * 0.1, 0.95)

        # arXiv分类增强
        for cat in categories:
            cat_lower = cat.lower()
            if "cs." in cat_lower and best_path[0] != "形式科学":
                confidence += 0.1
            if "q-bio" in cat_lower and best_path[0] != "医学与生命科学":
                cross_tags.append("生物信息学交叉")

        return DisciplineAnnotation(
            primary_path=best_path,
            cross_discipline_tags=list(set(cross_tags)),
            confidence=round(min(confidence, 1.0), 2),
            annotator="auto"
        )

    def annotate_task(self, paper: Dict) -> TaskAnnotation:
        """分配任务类型和难度级别"""
        title = (paper.get("title") or "").lower()
        abstract = (paper.get("abstract") or "").lower()
        text = title + " " + abstract

        # 规则匹配
        survey_kw = ["survey", "review", "comprehensive overview", "systematic review"]
        proposal_kw = ["propose", "novel", "new method", "we introduce", "we present"]
        experiment_kw = ["experiment", "empirical", "evaluation", "benchmark", "dataset"]
        theory_kw = ["theorem", "proof", "lemma", "theoretical", "bound"]

        is_survey = any(kw in text for kw in survey_kw)
        has_proposal = any(kw in text for kw in proposal_kw)
        has_experiment = any(kw in text for kw in experiment_kw)
        has_theory = any(kw in text for kw in theory_kw)

        if is_survey:
            task_type = "literature_review"
            difficulty = random.choice([1, 2])
            is_code_aware = False
        elif has_experiment and has_proposal:
            task_type = "full_paper_generation"
            difficulty = random.choice([1, 2, 3])
            is_code_aware = difficulty <= 2  # Level-1和Level-2支持Code-Aware
        elif has_experiment and not has_proposal:
            task_type = "experiment_design"
            difficulty = random.choice([1, 2])
            is_code_aware = True
        elif has_theory:
            task_type = "research_proposal"
            difficulty = random.choice([2, 3])
            is_code_aware = False
        else:
            task_type = random.choice(["paper_extension", "peer_review"])
            difficulty = 1
            is_code_aware = False

        return TaskAnnotation(
            task_type=task_type,
            difficulty_level=difficulty,
            is_code_aware=is_code_aware,
            rationale=f"基于关键词匹配: survey={is_survey}, proposal={has_proposal}, experiment={has_experiment}, theory={has_theory}"
        )

    def annotate_content(self, paper: Dict) -> ContentAnnotation:
        """标注内容维度元数据"""
        text = (paper.get("abstract") or "").lower()

        # 研究类型
        if any(kw in text for kw in ["theorem", "proof", "lemma", "bound", "theoretical"]):
            research_type = "theoretical"
        elif any(kw in text for kw in ["survey", "review", "overview"]):
            research_type = "survey"
        elif any(kw in text for kw in ["experiment", "evaluate", "benchmark", "dataset"]):
            research_type = "empirical"
        elif any(kw in text for kw in ["propose", "novel", "new method", "framework"]):
            research_type = "methodological"
        else:
            research_type = "application"

        # 论证类型
        has_math = any(kw in text for kw in ["equation", "formula", "theorem", "lemma"])
        has_data = any(kw in text for kw in ["result", "accuracy", "performance", "%"])
        argumentation_type = "empirical" if has_data else ("deductive" if has_math else "inductive")

        # 数学密集度（基于摘要估算）
        eq_count = text.count("equation") + text.count("formula") + text.count("\\frac")
        if eq_count == 0:
            math_density = "none"
        elif eq_count <= 2:
            math_density = "low"
        elif eq_count <= 6:
            math_density = "medium"
        else:
            math_density = "high"

        # 图表依赖度
        fig_count = text.count("figure") + text.count("fig.") + text.count("table")
        if fig_count == 0:
            figure_dependency = "none"
        elif fig_count <= 2:
            figure_dependency = "low"
        elif fig_count <= 5:
            figure_dependency = "medium"
        else:
            figure_dependency = "high"

        return ContentAnnotation(
            research_type=research_type,
            argumentation_type=argumentation_type,
            math_density=math_density,
            figure_dependency=figure_dependency
        )

    def annotate_quality(self, paper: Dict) -> QualityAnnotation:
        """标注质量维度元数据"""
        abstract = (paper.get("abstract") or "").lower()
        title = (paper.get("title") or "").lower()

        # 引用深度
        ref_indicators = sum(1 for kw in ["prior work", "previous", "existing", "state-of-the-art",
                                          "related work", "compared to", "outperform"] if kw in abstract)
        citation_depth = "high" if ref_indicators >= 3 else ("medium" if ref_indicators >= 1 else "low")

        # 论证复杂度
        complexity_indicators = sum(1 for kw in ["furthermore", "moreover", "however", "therefore",
                                                  "consequently", "in contrast", "specifically",
                                                  "notably"] if kw in abstract)
        argument_complexity = "high" if complexity_indicators >= 3 else ("medium" if complexity_indicators >= 1 else "low")

        # 创新程度
        novelty_indicators = sum(1 for kw in ["novel", "first", "new", "state-of-the-art",
                                               "breakthrough", "significant", "unprecedented"] if kw in abstract)
        if novelty_indicators >= 3:
            innovation_level = "significant_improvement"
        elif novelty_indicators >= 1:
            innovation_level = "incremental_improvement"
        else:
            innovation_level = "incremental_improvement"

        # 论文质量等级
        quality_indicators = sum(1 for kw in ["novel", "comprehensive", "rigorous", "extensive",
                                               "significant", "robust"] if kw in abstract)
        paper_quality_grade = "A" if quality_indicators >= 3 else ("B" if quality_indicators >= 1 else "C")

        return QualityAnnotation(
            citation_depth=citation_depth,
            argument_complexity=argument_complexity,
            innovation_level=innovation_level,
            paper_quality_grade=paper_quality_grade
        )

    def annotate_source(self, paper: Dict) -> SourceAnnotation:
        """标注来源信息"""
        return SourceAnnotation(
            database=paper.get("source", "arxiv"),
            publication_date=paper.get("publication_date", ""),
            license_type=paper.get("license_type", "CC BY"),
            is_preprint=paper.get("source", "") == "arxiv"
        )

    def annotate_decontamination(self, paper: Dict) -> DecontaminationAnnotation:
        """去污染标注"""
        pub_date = paper.get("publication_date", "")
        year = int(pub_date[:4]) if pub_date and len(pub_date) >= 4 else 2022

        # LLM训练截止日期参考
        gpt4_safe = year >= 2024
        gpt4o_safe = year >= 2024 and (int(pub_date[5:7]) if len(pub_date) >= 7 else 1) >= 7
        claude_safe = year >= 2024 and (int(pub_date[5:7]) if len(pub_date) >= 7 else 1) >= 5
        gemini_safe = year >= 2024 and (int(pub_date[5:7]) if len(pub_date) >= 7 else 1) >= 6

        safe_count = sum([gpt4_safe, gpt4o_safe, claude_safe, gemini_safe])
        if safe_count == 4:
            risk_level = "safe"
        elif safe_count >= 2:
            risk_level = "suspicious"
        else:
            risk_level = "high_risk"

        return DecontaminationAnnotation(
            risk_level=risk_level,
            gpt4_cutoff_safe=gpt4_safe,
            gpt4o_cutoff_safe=gpt4o_safe,
            claude_cutoff_safe=claude_safe,
            gemini_cutoff_safe=gemini_safe,
            notes=f"基于出版日期{paper.get('publication_date', 'unknown')}与各LLM截止日期比较"
        )

    def generate_fabrication_checklist(self, paper: Dict) -> FabricationChecklist:
        """为Code-Aware任务生成编造检测清单"""
        abstract = paper.get("abstract", "")
        title = paper.get("title", "")
        paper_id = paper.get("paper_id", "unknown")

        claims = []
        idx = 1

        # 从摘要中提取数值型声明
        percentage_pattern = re.findall(
            r'(\d+\.?\d*)\s*%', abstract
        )
        for i, pct in enumerate(percentage_pattern[:3]):
            claims.append(FabricationClaim(
                claim_id=f"FC-{paper_id}-{idx:02d}",
                claim_type="numerical_result",
                claim_location={"section": "Experiments", "paragraph": i},
                claim_text=f"achieves {pct}% accuracy",
                verification_method="results_json",
                tolerance={"absolute": 1.0, "relative": 0.02},
                required_evidence=f"results.json中包含accuracy字段，值在{float(pct)-1}-{float(pct)+1}范围内"
            ))
            idx += 1

        # 方法描述声明
        method_kw = ["transformer", "attention", "encoder", "decoder", "CNN", "RNN",
                     "Adam", "SGD", "BERT", "GPT", "ResNet", "ViT", "GNN", "MLP",
                     "catalyst", "synthesis", "CRISPR", "optimization"]
        found_methods = [kw for kw in method_kw if kw.lower() in abstract.lower()]
        for i, method in enumerate(found_methods[:2]):
            claims.append(FabricationClaim(
                claim_id=f"FC-{paper_id}-{idx:02d}",
                claim_type="method_description",
                claim_location={"section": "Method", "paragraph": i},
                claim_text=f"employs {method}",
                verification_method="code_inspection",
                tolerance=None,
                required_evidence=f"代码中存在{method}相关的类或函数实现"
            ))
            idx += 1

        # 比较声明
        if any(kw in abstract.lower() for kw in ["outperforms", "surpasses", "better than", "state-of-the-art"]):
            claims.append(FabricationClaim(
                claim_id=f"FC-{paper_id}-{idx:02d}",
                claim_type="comparison_claim",
                claim_location={"section": "Experiments", "paragraph": 0},
                claim_text="outperforms baseline methods",
                verification_method="results_json",
                tolerance={"absolute": 0.0, "relative": 0.0},
                required_evidence="results.json中至少存在两组对比数据，验证论文方法的数值确实高于所有基线"
            ))
            idx += 1

        # 引用依赖声明
        if any(kw in abstract.lower() for kw in ["following", "based on", "extends", "inspired by"]):
            claims.append(FabricationClaim(
                claim_id=f"FC-{paper_id}-{idx:02d}",
                claim_type="citation_dependency",
                claim_location={"section": "Introduction", "paragraph": 0},
                claim_text="builds upon prior work",
                verification_method="crossref_api",
                tolerance=None,
                required_evidence="CrossRef API验证引用论文的真实存在性和信息准确性"
            ))
            idx += 1

        # 确保至少5条
        if len(claims) < 5:
            for i in range(5 - len(claims)):
                claims.append(FabricationClaim(
                    claim_id=f"FC-{paper_id}-{idx:02d}",
                    claim_type="numerical_result",
                    claim_location={"section": "Experiments", "paragraph": i},
                    claim_text=f"demonstrates significant improvement",
                    verification_method="results_json",
                    tolerance={"absolute": 0.5, "relative": 0.01},
                    required_evidence="results.json验证实验数据"
                ))
                idx += 1

        return FabricationChecklist(
            paper_id=paper_id,
            verifiable_claims=claims[:10]
        )


# ============================================================
# 人工校验模块
# ============================================================

class HumanReviewModule:
    """人工校验：记录审核结果、计算交叉验证统计"""

    def __init__(self):
        self.reviews: Dict[str, Dict] = {}

    def review_annotation(self, record: AnnotationRecord,
                          reviewer_id: str,
                          approved: bool,
                          corrections: Dict = None) -> AnnotationRecord:
        """记录人工审核结果"""
        record.human_reviewed = True
        record.human_reviewer = reviewer_id

        if corrections:
            for field, value in corrections.items():
                parts = field.split(".")
                obj = record
                for part in parts[:-1]:
                    obj = getattr(obj, part, None)
                    if obj is None:
                        break
                if obj and hasattr(obj, parts[-1]):
                    setattr(obj, parts[-1], value)

        self.reviews[record.paper_id] = {
            "reviewer": reviewer_id,
            "approved": approved,
            "corrections": corrections,
            "reviewed_at": datetime.now().isoformat()
        }

        return record

    def compute_kappa(self, annotations1: List[AnnotationRecord],
                      annotations2: List[AnnotationRecord]) -> float:
        """简化的Cohen's Kappa计算"""
        if len(annotations1) != len(annotations2) or len(annotations1) == 0:
            return 0.0

        agreements = 0
        for a1, a2 in zip(annotations1, annotations2):
            if (a1.discipline.primary_path == a2.discipline.primary_path and
                a1.task.task_type == a2.task.task_type and
                a1.content.research_type == a2.content.research_type):
                agreements += 1

        po = agreements / len(annotations1)
        pe = 0.25  # 随机一致概率（四选一）
        return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0


# ============================================================
# 标注管线主引擎
# ============================================================

class AnnotationPipeline:
    """LLM辅助+人工校验的完整标注管线"""

    def __init__(self, output_dir: str):
        self.annotator = LLMAnnotator()
        self.reviewer = HumanReviewModule()
        self.output_dir = output_dir
        self.records: List[AnnotationRecord] = []
        os.makedirs(output_dir, exist_ok=True)

    def process_papers(self, papers: List[Dict]) -> List[AnnotationRecord]:
        """对论文列表执行完整标注流程"""
        print("=" * 60)
        print(f"标注管线开始: {len(papers)} 篇论文")
        print("=" * 60)

        for i, paper in enumerate(papers):
            paper_id = paper.get("paper_id", f"paper_{i}")
            print(f"\n[{i+1}/{len(papers)}] {paper_id}")

            # 阶段一：LLM辅助自动标注
            print("  [自动标注] 学科路径...", end=" ")
            discipline = self.annotator.annotate_discipline(paper)
            print(f"{' → '.join(discipline.primary_path)} (置信度:{discipline.confidence})")

            print("  [自动标注] 任务分配...", end=" ")
            task = self.annotator.annotate_task(paper)
            code_aware = "Code-Aware" if task.is_code_aware else "Text-Only"
            print(f"{task.task_type} L{task.difficulty_level} [{code_aware}]")

            print("  [自动标注] 内容元数据...", end=" ")
            content = self.annotator.annotate_content(paper)
            print(f"{content.research_type}/{content.argumentation_type}/math:{content.math_density}")

            print("  [自动标注] 质量元数据...", end=" ")
            quality = self.annotator.annotate_quality(paper)
            print(f"innovation:{quality.innovation_level}/grade:{quality.paper_quality_grade}")

            source = self.annotator.annotate_source(paper)
            decontamination = self.annotator.annotate_decontamination(paper)
            print(f"  [去污染] 风险等级: {decontamination.risk_level}")

            # 阶段二：Code-Aware标注（如适用）
            checklist = None
            if task.is_code_aware:
                print("  [Code-Aware] 生成编造检测清单...", end=" ")
                checklist = self.annotator.generate_fabrication_checklist(paper)
                valid, issues = checklist.validate()
                if valid:
                    print(f"✓ ({len(checklist.verifiable_claims)}条声明)")
                else:
                    print(f"⚠ 质量问题: {issues}")

            # 构建完整记录
            record = AnnotationRecord(
                paper_id=paper_id,
                discipline=discipline,
                content=content,
                quality=quality,
                source=source,
                decontamination=decontamination,
                task=task,
                fabrication_checklist=checklist,
                annotated_at=datetime.now().isoformat()
            )
            self.records.append(record)

        self._save_results()
        return self.records

    def human_review_batch(self, record_ids: List[str],
                           reviewer_id: str,
                           approval_decisions: Dict[str, Tuple[bool, Dict]]) -> List[AnnotationRecord]:
        """人工校验一批标注"""
        reviewed = []
        for record in self.records:
            if record.paper_id in record_ids:
                decision = approval_decisions.get(record.paper_id, (True, {}))
                reviewed.append(
                    self.reviewer.review_annotation(record, reviewer_id, decision[0], decision[1])
                )
        return reviewed

    def simulate_human_review(self, sample_ratio: float = 0.15) -> List[AnnotationRecord]:
        """模拟人工校验：随机抽取并模拟审核决策"""
        sample_size = max(1, int(len(self.records) * sample_ratio))
        sampled = random.sample(self.records, sample_size)

        print(f"\n{'='*60}")
        print(f"模拟人工校验: {sample_size}/{len(self.records)} 条 ({sample_ratio:.0%})")
        print(f"{'='*60}")

        corrections_made = 0
        for record in sampled:
            corrections = {}
            # 模拟人工修正：随机调整一些标注
            if random.random() < 0.3:  # 30%概率需要修正
                if random.random() < 0.5:
                    # 修正学科路径
                    record.discipline.primary_path[-1] += "（修正）"
                    corrections["discipline.primary_path"] = record.discipline.primary_path
                if random.random() < 0.5:
                    corrections["task.difficulty_level"] = max(1, min(3,
                        record.task.difficulty_level + random.choice([-1, 1])))
                corrections_made += 1

            self.reviewer.review_annotation(
                record,
                reviewer_id="simulated_reviewer_001",
                approved=len(corrections) == 0,
                corrections=corrections if corrections else None
            )

        print(f"  修正条目: {corrections_made}")
        print(f"  审核通过率: {(sample_size - corrections_made) / sample_size:.0%}")
        return sampled

    def _save_results(self):
        """保存标注结果"""
        # 完整标注记录
        annotations_path = os.path.join(self.output_dir, "annotations.json")
        with open(annotations_path, "w", encoding="utf-8") as f:
            json.dump([self._record_to_dict(r) for r in self.records],
                     f, ensure_ascii=False, indent=2)

        # 编造检测清单汇总
        checklists = {}
        for r in self.records:
            if r.fabrication_checklist:
                checklists[r.paper_id] = {
                    "paper_id": r.fabrication_checklist.paper_id,
                    "checklist_version": r.fabrication_checklist.checklist_version,
                    "verifiable_claims": [
                        asdict(c) for c in r.fabrication_checklist.verifiable_claims
                    ]
                }
        if checklists:
            checklists_path = os.path.join(self.output_dir, "fabrication_checklists.json")
            with open(checklists_path, "w", encoding="utf-8") as f:
                json.dump(checklists, f, ensure_ascii=False, indent=2)

        # 统计摘要
        summary = self._generate_summary()
        summary_path = os.path.join(self.output_dir, "annotation_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"\n标注结果保存至: {self.output_dir}")
        print(f"  - annotations.json: {len(self.records)} 条完整标注")
        print(f"  - annotation_summary.json: 统计摘要")

    def _record_to_dict(self, record: AnnotationRecord) -> Dict:
        return {
            "paper_id": record.paper_id,
            "discipline": asdict(record.discipline),
            "content": asdict(record.content),
            "quality": asdict(record.quality),
            "source": asdict(record.source),
            "decontamination": asdict(record.decontamination),
            "task": asdict(record.task),
            "fabrication_checklist": (
                asdict(record.fabrication_checklist)
                if record.fabrication_checklist else None
            ),
            "annotated_at": record.annotated_at,
            "human_reviewed": record.human_reviewed
        }

    def _generate_summary(self) -> Dict:
        """生成标注统计摘要"""
        discipline_dist = {}
        task_dist = {}
        level_dist = {1: 0, 2: 0, 3: 0}
        code_aware_count = 0
        risk_dist = {"safe": 0, "suspicious": 0, "high_risk": 0}

        for r in self.records:
            disc = r.discipline.primary_path[0] if r.discipline.primary_path else "未知"
            discipline_dist[disc] = discipline_dist.get(disc, 0) + 1
            task_dist[r.task.task_type] = task_dist.get(r.task.task_type, 0) + 1
            level_dist[r.task.difficulty_level] += 1
            if r.task.is_code_aware:
                code_aware_count += 1
            risk_dist[r.decontamination.risk_level] = risk_dist.get(r.decontamination.risk_level, 0) + 1

        return {
            "total_records": len(self.records),
            "discipline_distribution": discipline_dist,
            "task_distribution": task_dist,
            "difficulty_distribution": level_dist,
            "code_aware_count": code_aware_count,
            "decontamination_risk": risk_dist,
            "human_reviewed_count": sum(1 for r in self.records if r.human_reviewed),
            "generated_at": datetime.now().isoformat()
        }


# ============================================================
# 演示数据生成
# ============================================================

def generate_demo_papers(num: int = 20) -> List[Dict]:
    """生成演示论文数据（覆盖六大学科）"""
    demo = []
    templates = [
        # (学科领域, 标题模板, 摘要模板)
        ("cs_ai", "Adaptive {method} for {task}",
         "We propose a novel {method} approach to {task}. Our method achieves {pct}% accuracy, "
         "outperforming state-of-the-art baselines by {margin}%. Extensive experiments on {dataset} "
         "demonstrate significant improvements. We employ a transformer-based architecture with "
         "attention mechanisms and reinforcement learning for optimization."),
        ("physics", "{concept} in {system}: A Quantum Approach",
         "We investigate {concept} in {system} using quantum mechanical frameworks. "
         "Our theoretical analysis reveals that quantum error correction can improve coherence "
         "times by {pct}%. We validate our findings through numerical simulations."),
        ("chemistry", "Catalytic {reaction} via {catalyst}",
         "We present a novel {catalyst} for catalytic {reaction}. The catalyst shows {pct}% "
         "yield under mild conditions. DFT calculations reveal the reaction mechanism and "
         "provide insights for further optimization."),
        ("biology", "CRISPR-Mediated {target} Editing for {application}",
         "We develop a CRISPR-based approach for precise {target} editing. Our method achieves "
         "{pct}% editing efficiency with minimal off-target effects. We demonstrate applications "
         "in {application}, showing promising therapeutic potential."),
        ("economics", "Causal Effects of {treatment} on {outcome}: A {method} Approach",
         "Using a {method} design, we estimate the causal effect of {treatment} on {outcome}. "
         "Our analysis reveals a {pct}% increase in {outcome}, robust to multiple specification "
         "tests and falsification checks."),
        ("humanities", "{theme} in {period}: A {approach} Analysis",
         "This paper examines {theme} in {period} through a {approach} lens. Drawing on archival "
         "sources and textual analysis, we argue that {argument}. Our findings contribute to "
         "ongoing debates in {field} studies."),
    ]

    methods = ["Dual-Attention", "Hierarchical Fusion", "Recursive Decomposition",
               "Contrastive Alignment", "Stochastic Annealing"]
    tasks = ["Image Classification", "Semantic Parsing", "Molecular Generation",
             "Graph Completion", "Time Series Forecasting"]
    concepts = ["Quantum Entanglement", "Topological Order", "Spin Dynamics"]
    reactions = ["Cross-Coupling", "C-H Activation", "Asymmetric Hydrogenation"]

    for i in range(num):
        tmpl = templates[i % len(templates)]
        method = random.choice(methods)
        task = random.choice(tasks)
        pct = random.randint(75, 98)
        margin = round(random.uniform(1.0, 5.0), 1)

        title = tmpl[1].format(
            method=method, task=task,
            concept=random.choice(concepts), system=random.choice(["Spin Chains", "Photonic Lattices"]),
            reaction=random.choice(reactions), catalyst=random.choice(["Single-Atom Catalysts", "Metal-Organic Frameworks"]),
            target=random.choice(["Genomic", "Epigenetic"]), application=random.choice(["Cancer Therapy", "Gene Therapy"]),
            treatment=random.choice(["Minimum Wage", "Education Reform"]), outcome=random.choice(["Employment", "Earnings"]),
            theme=random.choice(["Identity", "Power"]), period=random.choice(["Early Modern Europe", "Post-War Asia"]),
            approach=random.choice(["Post-Structuralist", "Feminist"]),
            argument=random.choice(["discourse shaped material outcomes", "cultural practices mediated social change"]),
            field=random.choice(["Cultural", "Social"])
        )

        abstract = tmpl[2].format(
            method=method, task=task, pct=pct, margin=margin,
            dataset=random.choice(["CIFAR-100", "ImageNet", "COCO", "WMT14"]),
            concept=random.choice(concepts), system=random.choice(["Spin Chains"]),
            reaction=random.choice(reactions), catalyst=random.choice(["Palladium Complexes"]),
            target=random.choice(["Genomic"]), application=random.choice(["Cancer Therapy"]),
            treatment=random.choice(["Minimum Wage"]), outcome=random.choice(["Employment"]),
            theme=random.choice(["Identity"]), period=random.choice(["Early Modern Europe"]),
            approach=random.choice(["Post-Structuralist"]),
            argument=random.choice(["discourse shaped material outcomes"]),
            field=random.choice(["Cultural"])
        )

        demo.append({
            "paper_id": f"DEMO-{i+1:04d}",
            "title": title,
            "authors": [f"Author {chr(65+i)}" for _ in range(random.randint(2, 5))],
            "abstract": abstract,
            "categories": [tmpl[0]],
            "publication_date": f"202{random.randint(2,5)}-{random.randint(1,12):02d}",
            "source": "arxiv"
        })

    return demo


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="SciEval-Bench 标注管线"
    )
    parser.add_argument(
        "--input", type=str, default=DEFAULT_INPUT_PATH,
        help=f"待标注论文 JSON 路径 (默认: {DEFAULT_INPUT_PATH})"
    )
    parser.add_argument(
        "--output-dir", type=str, default=DEFAULT_OUTPUT_DIR,
        help=f"标注输出目录 (默认: {DEFAULT_OUTPUT_DIR})"
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="使用内置演示数据运行标注管线"
    )
    parser.add_argument(
        "--demo-count", type=int, default=20,
        help="演示模式下生成的论文数量 (默认: 20)"
    )
    parser.add_argument(
        "--skip-human-review", action="store_true",
        help="跳过模拟人工校验"
    )
    parser.add_argument(
        "--review-sample-ratio", type=float, default=0.15,
        help="模拟人工校验抽样比例 (默认: 0.15)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("SciEval-Bench 标注管线")
    print("=" * 60)

    output_dir = os.path.abspath(os.path.expanduser(args.output_dir))
    os.makedirs(output_dir, exist_ok=True)

    if args.demo:
        papers = generate_demo_papers(args.demo_count)
        print(f"\n演示数据: {len(papers)} 篇论文（覆盖六大学科）")
    else:
        input_path = os.path.abspath(os.path.expanduser(args.input))
        if not os.path.exists(input_path):
            print(f"错误：找不到待标注输入文件 {input_path}")
            print("请先准备筛选后的论文列表，或使用 --demo 运行演示模式")
            return

        with open(input_path, "r", encoding="utf-8") as f:
            papers = json.load(f)

        if not isinstance(papers, list):
            print(f"错误：输入文件 {input_path} 不是论文列表 JSON")
            return

        print(f"\n真实数据输入: {input_path}")
        print(f"待标注论文: {len(papers)} 篇")

    # 运行标注管线
    pipeline = AnnotationPipeline(output_dir=output_dir)
    pipeline.process_papers(papers)

    # 模拟人工校验
    if not args.skip_human_review:
        pipeline.simulate_human_review(sample_ratio=args.review_sample_ratio)
        pipeline._save_results()

    # 打印摘要
    print("\n" + "=" * 60)
    print("标注管线执行完成")
    print(f"输出目录: {output_dir}")
    print(f"标注记录: {len(pipeline.records)} 条")
    print(f"Code-Aware实例: {sum(1 for r in pipeline.records if r.task.is_code_aware)} 条")
    print(f"编造检测清单: {sum(1 for r in pipeline.records if r.fabrication_checklist)} 份")
    print(f"人工校验: {sum(1 for r in pipeline.records if r.human_reviewed)} 条")
    print("=" * 60)


if __name__ == "__main__":
    main()
