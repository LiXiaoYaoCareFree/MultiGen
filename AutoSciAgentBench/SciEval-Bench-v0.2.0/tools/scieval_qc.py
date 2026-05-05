#!/usr/bin/env python3
"""
SciEval-Bench 三级质量控制模块
================================
对标注完成的数据集执行三级递进式质量验证：

第一级：自动格式验证
  - JSON Schema 合规性
  - 必填字段完整性
  - 学科标签有效性
  - 引用一致性
  - 编造检测清单完整性

第二级：去污染与一致性校验
  - 时间戳过滤
  - LLM训练数据截止日期比对
  - 三级风险分类 (safe/suspicious/high_risk)
  - 标注间一致性验证

第三级：难度与多样性平衡检查
  - 难度级别分布均衡性
  - 学科覆盖完整性
  - 任务类型多样性
  - Code-Aware实例比例
  - 数据稀疏性预警
"""
import json
import os
import re
import argparse
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ANNOTATIONS_PATH = os.path.join(PROJECT_ROOT, "scieval_annotations", "annotations.json")
DEFAULT_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "scieval_qc")


# ============================================================
# LLM训练数据截止日期参考表
# ============================================================

LLM_CUTOFF_DATES = {
    "gpt4": "2023-12",
    "gpt4o": "2024-06",
    "gpt4o_latest": "2024-08",
    "claude_3_5_sonnet": "2024-04",
    "claude_opus_4": "2025-06",
    "gemini_1_5_pro": "2024-05",
    "deepseek_v3": "2024-07",
    "qwen_2_5_72b": "2024-09",
}


# ============================================================
# 质量验证数据模型
# ============================================================

@dataclass
class ValidationIssue:
    """验证发现的问题"""
    level: str          # "error" | "warning" | "info"
    category: str       # "format" | "decontamination" | "consistency" | "diversity"
    paper_id: str
    field: str
    message: str
    suggestion: str = ""


@dataclass
class QCReport:
    """质量控制报告"""
    timestamp: str
    total_entries: int
    passed: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)
    stage_details: Dict[str, Dict] = field(default_factory=dict)


# ============================================================
# 第一级：自动格式验证
# ============================================================

class FormatValidator:
    """第一级验证器：自动格式检查"""

    # 有效的枚举值
    VALID_RESEARCH_TYPES = ["theoretical", "empirical", "methodological", "survey", "application"]
    VALID_ARGUMENTATION_TYPES = ["deductive", "inductive", "analogical", "empirical"]
    VALID_MATH_DENSITIES = ["none", "low", "medium", "high"]
    VALID_FIGURE_DEPENDENCIES = ["none", "low", "medium", "high"]
    VALID_INNOVATION_LEVELS = ["incremental_improvement", "significant_improvement", "breakthrough", "survey"]
    VALID_QUALITY_GRADES = ["A", "B", "C"]
    VALID_TASK_TYPES = ["full_paper_generation", "literature_review", "experiment_design",
                        "research_proposal", "paper_extension", "peer_review"]
    VALID_RISK_LEVELS = ["safe", "suspicious", "high_risk"]

    def validate(self, annotations: List[Dict]) -> List[ValidationIssue]:
        """执行格式验证"""
        issues = []
        all_paper_ids = {a.get("paper_id", "") for a in annotations}

        for ann in annotations:
            paper_id = ann.get("paper_id", "UNKNOWN")
            issues.extend(self._check_required_fields(ann, paper_id))
            issues.extend(self._check_discipline(ann, paper_id))
            issues.extend(self._check_task(ann, paper_id))
            issues.extend(self._check_content(ann, paper_id))
            issues.extend(self._check_quality(ann, paper_id))
            issues.extend(self._check_decontamination(ann, paper_id))
            issues.extend(self._check_fabrication_checklist(ann, paper_id))

        return issues

    def _check_required_fields(self, ann: Dict, pid: str) -> List[ValidationIssue]:
        issues = []
        required_top = ["paper_id", "discipline", "content", "quality",
                       "source", "decontamination", "task"]
        for field in required_top:
            if field not in ann or ann[field] is None:
                issues.append(ValidationIssue("error", "format", pid, field,
                    f"缺少必填字段: {field}", "补充该字段"))
                return issues  # 如果顶层缺失，跳过子字段检查
        return issues

    def _check_discipline(self, ann: Dict, pid: str) -> List[ValidationIssue]:
        issues = []
        disc = ann.get("discipline", {})
        path = disc.get("primary_path", [])
        if len(path) < 2:
            issues.append(ValidationIssue("error", "format", pid, "discipline.primary_path",
                f"学科路径至少需要2个层级，当前{len(path)}个", "补充完整的四层级路径"))
        valid_domains = ["形式科学", "自然科学", "工程与技术科学",
                        "医学与生命科学", "社会科学", "人文学科"]
        if path and path[0] not in valid_domains:
            issues.append(ValidationIssue("error", "format", pid, "discipline.primary_path[0]",
                f"无效的学科大类: {path[0]}", f"从{valid_domains}中选择"))
        confidence = disc.get("confidence", 0)
        if confidence < 0.3:
            issues.append(ValidationIssue("warning", "format", pid, "discipline.confidence",
                f"学科标注置信度过低({confidence})", "需要人工复核"))
        return issues

    def _check_task(self, ann: Dict, pid: str) -> List[ValidationIssue]:
        issues = []
        task = ann.get("task", {})
        task_type = task.get("task_type", "")
        if task_type not in self.VALID_TASK_TYPES:
            issues.append(ValidationIssue("error", "format", pid, "task.task_type",
                f"无效任务类型: {task_type}", f"从{self.VALID_TASK_TYPES}中选择"))
        level = task.get("difficulty_level", 0)
        if level not in [1, 2, 3]:
            issues.append(ValidationIssue("error", "format", pid, "task.difficulty_level",
                f"无效难度级别: {level}", "设置为1、2或3"))
        is_ca = task.get("is_code_aware", False)
        if is_ca and task_type not in ["full_paper_generation", "experiment_design"]:
            issues.append(ValidationIssue("warning", "format", pid, "task.is_code_aware",
                f"Code-Aware仅适用于完整论文生成或实验方案设计，当前为{task_type}",
                "将is_code_aware改为false"))
        return issues

    def _check_content(self, ann: Dict, pid: str) -> List[ValidationIssue]:
        issues = []
        content = ann.get("content", {})
        rt = content.get("research_type", "")
        if rt and rt not in self.VALID_RESEARCH_TYPES:
            issues.append(ValidationIssue("error", "format", pid, "content.research_type",
                f"无效研究类型: {rt}"))
        at = content.get("argumentation_type", "")
        if at and at not in self.VALID_ARGUMENTATION_TYPES:
            issues.append(ValidationIssue("error", "format", pid, "content.argumentation_type",
                f"无效论证类型: {at}"))
        md = content.get("math_density", "")
        if md and md not in self.VALID_MATH_DENSITIES:
            issues.append(ValidationIssue("error", "format", pid, "content.math_density",
                f"无效数学密集度: {md}"))
        fd = content.get("figure_dependency", "")
        if fd and fd not in self.VALID_FIGURE_DEPENDENCIES:
            issues.append(ValidationIssue("error", "format", pid, "content.figure_dependency",
                f"无效图表依赖度: {fd}"))
        return issues

    def _check_quality(self, ann: Dict, pid: str) -> List[ValidationIssue]:
        issues = []
        quality = ann.get("quality", {})
        il = quality.get("innovation_level", "")
        if il and il not in self.VALID_INNOVATION_LEVELS:
            issues.append(ValidationIssue("error", "format", pid, "quality.innovation_level",
                f"无效创新程度: {il}"))
        grade = quality.get("paper_quality_grade", "")
        if grade and grade not in self.VALID_QUALITY_GRADES:
            issues.append(ValidationIssue("error", "format", pid, "quality.paper_quality_grade",
                f"无效质量等级: {grade}"))
        return issues

    def _check_decontamination(self, ann: Dict, pid: str) -> List[ValidationIssue]:
        issues = []
        dc = ann.get("decontamination", {})
        risk = dc.get("risk_level", "")
        if risk not in self.VALID_RISK_LEVELS:
            issues.append(ValidationIssue("error", "format", pid, "decontamination.risk_level",
                f"无效风险等级: {risk}"))
        return issues

    def _check_fabrication_checklist(self, ann: Dict, pid: str) -> List[ValidationIssue]:
        issues = []
        task = ann.get("task", {})
        if not task.get("is_code_aware", False):
            return issues

        checklist = ann.get("fabrication_checklist")
        if checklist is None:
            issues.append(ValidationIssue("error", "format", pid, "fabrication_checklist",
                "Code-Aware任务缺少编造检测清单", "生成fabrication_checklist"))
            return issues

        claims = checklist.get("verifiable_claims", [])
        n = len(claims)
        if n < 5:
            issues.append(ValidationIssue("error", "format", pid, "fabrication_checklist",
                f"编造检测清单声明数量不足({n}条，需要≥5)", "增加至少{5-n}条声明"))
        if n > 15:
            issues.append(ValidationIssue("warning", "format", pid, "fabrication_checklist",
                f"编造检测清单声明过多({n}条，建议≤15)", "精简至15条以内"))

        sections = set()
        type_counts = {}
        for c in claims:
            loc = c.get("claim_location", {})
            sections.add(loc.get("section", ""))
            ct = c.get("claim_type", "")
            type_counts[ct] = type_counts.get(ct, 0) + 1

        if len(sections) < 3:
            issues.append(ValidationIssue("warning", "format", pid, "fabrication_checklist",
                f"声明仅覆盖{len(sections)}个章节，需要≥3", "增加跨章节的声明"))

        return issues


# ============================================================
# 第二级：去污染与一致性校验
# ============================================================

class ConsistencyValidator:
    """第二级验证器：去污染与一致性检查"""

    def validate(self, annotations: List[Dict]) -> List[ValidationIssue]:
        issues = []
        issues.extend(self._check_temporal_decontamination(annotations))
        issues.extend(self._check_llm_cutoff_alignment(annotations))
        issues.extend(self._check_annotation_consistency(annotations))
        return issues

    def _check_temporal_decontamination(self, annotations: List[Dict]) -> List[ValidationIssue]:
        """时间戳过滤"""
        issues = []
        for ann in annotations:
            pid = ann.get("paper_id", "?")
            source = ann.get("source", {})
            pub_date = source.get("publication_date", "")
            if not pub_date:
                issues.append(ValidationIssue("warning", "decontamination", pid,
                    "source.publication_date", "缺少出版日期，无法评估污染风险",
                    "补充publication_date字段"))
                continue

            year = int(pub_date[:4]) if len(pub_date) >= 4 else 0
            if year < 2022:
                issues.append(ValidationIssue("warning", "decontamination", pid,
                    "source.publication_date",
                    f"论文发表于{year}年，可能较为陈旧", "考虑替换为更新的论文"))
        return issues

    def _check_llm_cutoff_alignment(self, annotations: List[Dict]) -> List[ValidationIssue]:
        """验证去污染标注是否与LLM截止日期一致"""
        issues = []
        for ann in annotations:
            pid = ann.get("paper_id", "?")
            dc = ann.get("decontamination", {})
            source = ann.get("source", {})
            pub_date = source.get("publication_date", "")

            if not pub_date or len(pub_date) < 7:
                continue

            pub_year = int(pub_date[:4])
            pub_month = int(pub_date[5:7])

            # 重新计算实际应标注的风险等级
            safe_count = 0
            for model, cutoff in LLM_CUTOFF_DATES.items():
                cy = int(cutoff[:4])
                cm = int(cutoff[5:7]) if len(cutoff) >= 7 else 1
                if pub_year > cy or (pub_year == cy and pub_month > cm):
                    safe_count += 1

            total_models = len(LLM_CUTOFF_DATES)
            if safe_count == total_models:
                expected_risk = "safe"
            elif safe_count >= total_models // 2:
                expected_risk = "suspicious"
            else:
                expected_risk = "high_risk"

            actual_risk = dc.get("risk_level", "")
            if actual_risk != expected_risk:
                issues.append(ValidationIssue("warning", "decontamination", pid,
                    "decontamination.risk_level",
                    f"去污染标注({actual_risk})与计算值({expected_risk})不一致",
                    f"检查出版日期{pub_date}与LLM截止日期的比对"))

        return issues

    def _check_annotation_consistency(self, annotations: List[Dict]) -> List[ValidationIssue]:
        """标注间一致性检查"""
        issues = []
        for ann in annotations:
            pid = ann.get("paper_id", "?")
            content = ann.get("content", {})
            quality = ann.get("quality", {})

            # 检查研究类型与论证类型的一致性
            rt = content.get("research_type", "")
            at = content.get("argumentation_type", "")
            if rt == "theoretical" and at == "empirical":
                issues.append(ValidationIssue("warning", "consistency", pid,
                    "content", f"研究类型为theoretical但论证类型为empirical，可能不一致"))
            if rt == "empirical" and at == "deductive":
                issues.append(ValidationIssue("info", "consistency", pid,
                    "content", f"实证研究通常采用empirical论证而非deductive"))

            # 检查数学密集度与研究类型的合理性
            md = content.get("math_density", "")
            if rt in ["survey", "application"] and md in ["medium", "high"]:
                issues.append(ValidationIssue("info", "consistency", pid,
                    "content", f"{rt}类型论文数学密集度为{md}，可能偏高"))

            # 检查创新程度与质量等级的一致性
            il = quality.get("innovation_level", "")
            grade = quality.get("paper_quality_grade", "")
            if il == "breakthrough" and grade == "C":
                issues.append(ValidationIssue("warning", "consistency", pid,
                    "quality", "突破性创新但质量等级为C，标注可能不一致"))

        return issues


# ============================================================
# 第三级：难度与多样性平衡检查
# ============================================================

class DiversityValidator:
    """第三级验证器：难度与多样性平衡"""

    # 目标分布
    VALID_TASK_TYPES = ["full_paper_generation", "literature_review", "experiment_design",
                        "research_proposal", "paper_extension", "peer_review"]

    TARGETS = {
        "difficulty": {1: 0.40, 2: 0.35, 3: 0.25},   # L1:L2:L3 = 40:35:25
        "task_types": {                                  # 每种任务类型的最低占比
            "full_paper_generation": 0.25,
            "literature_review": 0.12,
            "experiment_design": 0.10,
            "research_proposal": 0.10,
            "paper_extension": 0.08,
            "peer_review": 0.08,
        },
        "code_aware_ratio": 0.25,                        # Code-Aware实例占比
        "min_per_discipline": 30,                        # 每学科大类最少实例数
        "min_per_subdiscipline": 10,                     # 每子学科最少实例数
    }

    def validate(self, annotations: List[Dict]) -> List[ValidationIssue]:
        issues = []
        n = len(annotations)

        issues.extend(self._check_difficulty_balance(annotations, n))
        issues.extend(self._check_task_diversity(annotations, n))
        issues.extend(self._check_discipline_coverage(annotations, n))
        issues.extend(self._check_code_aware_ratio(annotations, n))
        issues.extend(self._check_sparsity_warnings(annotations, n))

        return issues

    def _check_difficulty_balance(self, annotations: List[Dict], n: int) -> List[ValidationIssue]:
        issues = []
        level_counts = {1: 0, 2: 0, 3: 0}
        for ann in annotations:
            level = ann.get("task", {}).get("difficulty_level", 1)
            level_counts[level] = level_counts.get(level, 0) + 1

        for level, target in self.TARGETS["difficulty"].items():
            actual = level_counts.get(level, 0) / n if n else 0
            deviation = abs(actual - target)
            if deviation > 0.15:
                issues.append(ValidationIssue("warning", "diversity", "ALL",
                    f"difficulty_level_{level}",
                    f"L{level}占比{actual:.0%}偏离目标{target:.0%}（偏差{deviation:.0%}）",
                    f"调整任务分配使L{level}占比接近{target:.0%}"))
        return issues

    def _check_task_diversity(self, annotations: List[Dict], n: int) -> List[ValidationIssue]:
        issues = []
        task_counts = {}
        for ann in annotations:
            tt = ann.get("task", {}).get("task_type", "unknown")
            task_counts[tt] = task_counts.get(tt, 0) + 1

        covered = set(task_counts.keys())
        missing = set(self.VALID_TASK_TYPES) - covered
        if missing:
            issues.append(ValidationIssue("error", "diversity", "ALL",
                "task_types", f"缺失任务类型: {missing}", "为缺失类型添加任务实例"))

        for tt, min_ratio in self.TARGETS["task_types"].items():
            actual = task_counts.get(tt, 0) / n if n else 0
            if actual < min_ratio * 0.5:  # 低于目标的一半
                issues.append(ValidationIssue("warning", "diversity", "ALL",
                    f"task_{tt}", f"{tt}占比{actual:.0%}远低于最低要求{min_ratio:.0%}",
                    f"增加{tt}类型实例"))

        return issues

    def _check_discipline_coverage(self, annotations: List[Dict], n: int) -> List[ValidationIssue]:
        issues = []
        disc_counts = {}
        sub_counts = {}
        for ann in annotations:
            path = ann.get("discipline", {}).get("primary_path", [])
            if len(path) >= 1:
                disc = path[0]
                disc_counts[disc] = disc_counts.get(disc, 0) + 1
            if len(path) >= 2:
                sub = f"{path[0]}→{path[1]}"
                sub_counts[sub] = sub_counts.get(sub, 0) + 1

        all_domains = ["形式科学", "自然科学", "工程与技术科学",
                      "医学与生命科学", "社会科学", "人文学科"]
        missing_domains = set(all_domains) - set(disc_counts.keys())
        if missing_domains:
            issues.append(ValidationIssue("error", "diversity", "ALL",
                "discipline_coverage", f"缺失学科大类: {missing_domains}",
                "为缺失学科补充数据"))

        for disc, count in disc_counts.items():
            if count < self.TARGETS["min_per_discipline"]:
                issues.append(ValidationIssue("warning", "diversity", "ALL",
                    f"discipline_{disc}", f"{disc}仅有{count}条（目标≥{self.TARGETS['min_per_discipline']}）",
                    f"增加{self.TARGETS['min_per_discipline'] - count}条"))

        for sub, count in sub_counts.items():
            if count < self.TARGETS["min_per_subdiscipline"] and count > 0:
                issues.append(ValidationIssue("info", "diversity", "ALL",
                    f"subdiscipline_{sub}", f"{sub}仅有{count}条（目标≥{self.TARGETS['min_per_subdiscipline']}）",
                    "小型子学科可适度降低目标"))

        return issues

    def _check_code_aware_ratio(self, annotations: List[Dict], n: int) -> List[ValidationIssue]:
        issues = []
        ca_count = sum(1 for a in annotations
                      if a.get("task", {}).get("is_code_aware", False))
        ca_ratio = ca_count / n if n else 0
        target = self.TARGETS["code_aware_ratio"]
        if ca_ratio < target * 0.5:
            issues.append(ValidationIssue("warning", "diversity", "ALL",
                "code_aware_ratio", f"Code-Aware占比{ca_ratio:.0%}远低于目标{target:.0%}",
                "增加Code-Aware任务实例"))
        return issues

    def _check_sparsity_warnings(self, annotations: List[Dict], n: int) -> List[ValidationIssue]:
        """检测数据稀疏性"""
        issues = []
        # 检查学科×任务交叉矩阵中的空白
        disc_task = {}
        for ann in annotations:
            path = ann.get("discipline", {}).get("primary_path", [])
            disc = path[0] if path else "?"
            task = ann.get("task", {}).get("task_type", "?")
            key = f"{disc}×{task}"
            disc_task[key] = disc_task.get(key, 0) + 1

        if n >= 50:  # 仅在数据量足够时检查
            sparse = [k for k, v in disc_task.items() if v == 1]
            if sparse:
                issues.append(ValidationIssue("info", "diversity", "ALL",
                    "sparsity", f"{len(sparse)}个学科×任务组合仅1条实例",
                    "为这些组合增加实例以提高统计可靠性"))

        return issues


# ============================================================
# QC引擎
# ============================================================

class QualityControlEngine:
    """三级质量控制引擎"""

    def __init__(self):
        self.format_validator = FormatValidator()
        self.consistency_validator = ConsistencyValidator()
        self.diversity_validator = DiversityValidator()
        self.issues: List[ValidationIssue] = []

    def run(self, annotations_path: str) -> QCReport:
        """执行完整的三级质量控制流程"""
        print("=" * 70)
        print("SciEval-Bench 三级质量控制")
        print(f"执行时间: {datetime.now().isoformat()}")
        print("=" * 70)

        # 加载数据
        with open(annotations_path, "r", encoding="utf-8") as f:
            annotations = json.load(f)
        n = len(annotations)
        print(f"\n加载标注数据: {n} 条")

        # 第一级
        print("\n" + "-" * 50)
        print("[第一级] 自动格式验证")
        print("-" * 50)
        format_issues = self.format_validator.validate(annotations)
        errors = [i for i in format_issues if i.level == "error"]
        warnings = [i for i in format_issues if i.level == "warning"]
        print(f"  错误: {len(errors)}, 警告: {len(warnings)}, 信息: {len(format_issues) - len(errors) - len(warnings)}")
        for issue in format_issues:
            icon = {"error": "✗", "warning": "⚠", "info": "ℹ"}.get(issue.level, "?")
            print(f"  {icon} [{issue.paper_id}] {issue.field}: {issue.message}")
        self.issues.extend(format_issues)

        # 第二级
        print("\n" + "-" * 50)
        print("[第二级] 去污染与一致性校验")
        print("-" * 50)
        consistency_issues = self.consistency_validator.validate(annotations)
        for issue in consistency_issues:
            icon = {"error": "✗", "warning": "⚠", "info": "ℹ"}.get(issue.level, "?")
            print(f"  {icon} [{issue.paper_id}] {issue.message}")
        self.issues.extend(consistency_issues)

        # 第三级
        print("\n" + "-" * 50)
        print("[第三级] 难度与多样性平衡检查")
        print("-" * 50)
        diversity_issues = self.diversity_validator.validate(annotations)
        for issue in diversity_issues:
            icon = {"error": "✗", "warning": "⚠", "info": "ℹ"}.get(issue.level, "?")
            print(f"  {icon} [{issue.paper_id}] {issue.message}")
        self.issues.extend(diversity_issues)

        # 汇总
        all_errors = [i for i in self.issues if i.level == "error"]
        all_warnings = [i for i in self.issues if i.level == "warning"]
        passed = len(all_errors) == 0

        # 计算质量评分
        scores = self._compute_scores(n, all_errors, all_warnings)

        print("\n" + "=" * 70)
        print(f"质量控制{'通过' if passed else '未通过'}")
        print(f"  总条目: {n}")
        print(f"  错误: {len(all_errors)}, 警告: {len(all_warnings)}, 信息: {len(self.issues) - len(all_errors) - len(all_warnings)}")
        print(f"  综合评分: {scores['overall']:.1f}/100")
        print("=" * 70)

        return QCReport(
            timestamp=datetime.now().isoformat(),
            total_entries=n,
            passed=passed,
            issues=self.issues,
            scores=scores,
            stage_details={
                "format": {"errors": len(errors), "warnings": len(warnings)},
                "consistency": {"issues": len(consistency_issues)},
                "diversity": {"issues": len(diversity_issues)}
            }
        )

    def _compute_scores(self, n: int, errors: List, warnings: List) -> Dict[str, float]:
        """计算质量评分"""
        format_score = max(0, 40 - len(errors) * 5 - len(warnings) * 2)
        consistency_score = max(0, 30 - len([i for i in self.issues
            if i.category == "consistency"]) * 3)
        diversity_score = max(0, 30 - len([i for i in self.issues
            if i.category == "diversity" and i.level in ["error", "warning"]]) * 3)
        overall = format_score + consistency_score + diversity_score
        return {
            "format": round(format_score, 1),
            "consistency": round(consistency_score, 1),
            "diversity": round(diversity_score, 1),
            "overall": round(overall, 1)
        }


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="SciEval-Bench 三级质量控制"
    )
    parser.add_argument(
        "--annotations-path", type=str, default=DEFAULT_ANNOTATIONS_PATH,
        help=f"标注文件路径 (默认: {DEFAULT_ANNOTATIONS_PATH})"
    )
    parser.add_argument(
        "--output-dir", type=str, default=DEFAULT_OUTPUT_DIR,
        help=f"QC 输出目录 (默认: {DEFAULT_OUTPUT_DIR})"
    )
    args = parser.parse_args()

    annotations_path = os.path.abspath(os.path.expanduser(args.annotations_path))

    if not os.path.exists(annotations_path):
        print(f"错误：找不到标注文件 {annotations_path}")
        print("请先运行 scieval_annotator.py 生成标注数据")
        return

    engine = QualityControlEngine()
    report = engine.run(annotations_path)

    # 保存报告
    output_dir = os.path.abspath(os.path.expanduser(args.output_dir))
    os.makedirs(output_dir, exist_ok=True)

    report_path = os.path.join(output_dir, "qc_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2, default=str)
    print(f"\nQC报告保存至: {report_path}")

    issues_path = os.path.join(output_dir, "qc_issues.json")
    with open(issues_path, "w", encoding="utf-8") as f:
        json.dump([asdict(i) for i in engine.issues], f, ensure_ascii=False, indent=2)
    print(f"问题清单保存至: {issues_path}")


if __name__ == "__main__":
    main()
