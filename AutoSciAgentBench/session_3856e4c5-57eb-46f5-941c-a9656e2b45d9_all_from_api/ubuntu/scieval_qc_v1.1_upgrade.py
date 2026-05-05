#!/usr/bin/env python3
"""
SciEval-Bench QC v1.1 — 富标签验证升级
=========================================
在原有三级QC基础上，新增第四级：富标签完整性验证。
对 publication_status, review_information, citation_impact, provenance
四类标签进行专门的格式、一致性和合理性检查。
"""
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List


# ============================================================
# 新增验证器
# ============================================================

class EnrichmentValidator:
    """第四级验证器：富标签完整性检查"""

    def validate(self, annotations: List[Dict]) -> List[Dict]:
        """执行全部富标签验证"""
        issues = []
        for ann in annotations:
            pid = ann.get("paper_id", "?")
            issues.extend(self._check_publication_status(ann, pid))
            issues.extend(self._check_review_information(ann, pid))
            issues.extend(self._check_citation_impact(ann, pid))
            issues.extend(self._check_provenance(ann, pid))
            issues.extend(self._check_cross_consistency(ann, pid))
        return issues

    # ---------- publication_status ----------

    def _check_publication_status(self, ann: Dict, pid: str) -> List[Dict]:
        issues = []
        ps = ann.get("publication_status", {})
        if not ps:
            issues.append(self._issue("error", "enrichment", pid,
                "publication_status", "缺少publication_status标签"))
            return issues

        status = ps.get("status", "")
        valid = ["accepted", "rejected", "preprint", "published", "withdrawn"]
        if status not in valid:
            issues.append(self._issue("error", "enrichment", pid,
                "publication_status.status", f"无效状态'{status}'，需为{valid}之一"))

        if status in ("accepted", "rejected") and not ps.get("venue"):
            issues.append(self._issue("warning", "enrichment", pid,
                "publication_status.venue", f"状态为{status}但缺少venue信息"))

        decision_source = ps.get("decision_source", "")
        valid_sources = ["openreview_api","peerread","moprd","re2","manual","unknown"]
        if decision_source not in valid_sources:
            issues.append(self._issue("warning", "enrichment", pid,
                "publication_status.decision_source",
                f"无效来源'{decision_source}'"))

        # acceptance_rate 合理性
        rate = ps.get("acceptance_rate")
        if rate is not None and (rate < 0 or rate > 1):
            issues.append(self._issue("warning", "enrichment", pid,
                "publication_status.acceptance_rate",
                f"接受率{rate}不在[0,1]范围内"))

        return issues

    # ---------- review_information ----------

    def _check_review_information(self, ann: Dict, pid: str) -> List[Dict]:
        issues = []
        ri = ann.get("review_information", {})
        if not ri:
            issues.append(self._issue("warning", "enrichment", pid,
                "review_information", "缺少review_information标签（preprint论文可接受）"))
            return issues

        has_reviews = ri.get("has_reviews", False)
        num_reviews = ri.get("num_reviews", 0)
        review_source = ri.get("review_source", "")

        if has_reviews:
            if num_reviews < 1:
                issues.append(self._issue("error", "enrichment", pid,
                    "review_information.num_reviews",
                    f"has_reviews=true但num_reviews={num_reviews}"))
            if review_source in ("none", "", None):
                issues.append(self._issue("warning", "enrichment", pid,
                    "review_information.review_source",
                    "有评审但未标注评审来源"))
            # 检查评审分数合理性
            scores = ri.get("review_scores", {}) or {}
            overall = scores.get("overall")
            if overall is not None and (overall < 1 or overall > 10):
                issues.append(self._issue("warning", "enrichment", pid,
                    "review_information.review_scores.overall",
                    f"评审总分{overall}不在[1,10]范围"))
        else:
            if num_reviews > 0:
                issues.append(self._issue("warning", "enrichment", pid,
                    "review_information.num_reviews",
                    f"has_reviews=false但num_reviews={num_reviews}>0"))

        # inter_reviewer_agreement
        ira = ri.get("inter_reviewer_agreement")
        if ira is not None and (ira < 0 or ira > 1):
            issues.append(self._issue("warning", "enrichment", pid,
                "review_information.inter_reviewer_agreement",
                f"评审者间一致性{ira}不在[0,1]范围"))

        return issues

    # ---------- citation_impact ----------

    def _check_citation_impact(self, ann: Dict, pid: str) -> List[Dict]:
        issues = []
        ci = ann.get("citation_impact", {})
        if not ci:
            issues.append(self._issue("warning", "enrichment", pid,
                "citation_impact", "缺少citation_impact标签"))
            return issues

        total = ci.get("total_citations", 0)
        cpy = ci.get("citations_per_year", 0)
        velocity = ci.get("citation_velocity", "")

        if total < 0:
            issues.append(self._issue("error", "enrichment", pid,
                "citation_impact.total_citations",
                f"引用总数{total}不能为负"))

        if cpy < 0:
            issues.append(self._issue("error", "enrichment", pid,
                "citation_impact.citations_per_year",
                f"年均引用{cpy}不能为负"))

        if velocity not in ("high", "medium", "low", ""):
            issues.append(self._issue("warning", "enrichment", pid,
                "citation_impact.citation_velocity",
                f"无效的引用速度'{velocity}'"))

        # citation_velocity 与 citations_per_year 的一致性
        if velocity == "high" and cpy < 20:
            issues.append(self._issue("info", "enrichment", pid,
                "citation_impact",
                f"citation_velocity=high但citations_per_year={cpy}<20"))
        if velocity == "low" and cpy >= 20:
            issues.append(self._issue("info", "enrichment", pid,
                "citation_impact",
                f"citation_velocity=low但citations_per_year={cpy}>=20"))

        return issues

    # ---------- provenance ----------

    def _check_provenance(self, ann: Dict, pid: str) -> List[Dict]:
        issues = []
        pv = ann.get("provenance", {})
        if not pv:
            issues.append(self._issue("warning", "enrichment", pid,
                "provenance", "缺少provenance标签"))
            return issues

        has_code = pv.get("has_code", False)
        code_url = pv.get("code_repository_url")

        if has_code and not code_url:
            issues.append(self._issue("error", "enrichment", pid,
                "provenance",
                "has_code=true但code_repository_url为空"))
        if not has_code and code_url:
            issues.append(self._issue("warning", "enrichment", pid,
                "provenance",
                "has_code=false但存在code_repository_url"))

        # conference 和 journal 至少有一个已知
        conf = pv.get("conference")
        journal = pv.get("journal")
        ps = ann.get("publication_status", {})
        if ps.get("status") in ("accepted", "published") and not conf and not journal:
            issues.append(self._issue("info", "enrichment", pid,
                "provenance",
                "论文已接受/已发表但conference和journal均为空"))

        return issues

    # ---------- 跨标签一致性 ----------

    def _check_cross_consistency(self, ann: Dict, pid: str) -> List[Dict]:
        """检查标签之间的一致性"""
        issues = []
        ps = ann.get("publication_status", {})
        ri = ann.get("review_information", {})
        ci = ann.get("citation_impact", {})
        pv = ann.get("provenance", {})

        # 已接受论文应该有评审
        if ps.get("status") == "accepted" and not ri.get("has_reviews", False):
            issues.append(self._issue("warning", "enrichment", pid,
                "cross:status_vs_reviews",
                "论文状态为accepted但has_reviews=false——已接受论文通常应有评审"))

        # 预印本不应该有接受状态
        if ps.get("status") in ("accepted", "rejected") and ps.get("decision_source") == "unknown":
            issues.append(self._issue("info", "enrichment", pid,
                "cross:status_vs_source",
                f"状态为{ps['status']}但decision_source=unknown——标签可能不准确"))

        # 有代码的论文更适合Code-Aware
        task = ann.get("task", {})
        if pv.get("has_code") and not task.get("is_code_aware", False):
            if task.get("task_type") in ("full_paper_generation", "experiment_design"):
                issues.append(self._issue("info", "enrichment", pid,
                    "cross:code_vs_task",
                    "论文有公开代码但未被标记为Code-Aware——建议审核"))

        # quality_grade 与 publication_status 一致性
        quality = ann.get("quality", {}).get("paper_quality_grade", "")
        if ps.get("status") == "accepted" and quality == "C":
            issues.append(self._issue("warning", "enrichment", pid,
                "cross:quality_vs_status",
                "论文已接受但paper_quality_grade=C——标注可能不一致"))
        if ps.get("status") == "rejected" and quality == "A":
            issues.append(self._issue("warning", "enrichment", pid,
                "cross:quality_vs_status",
                "论文被拒但paper_quality_grade=A——标注可能不一致"))

        # citation_depth 与 citation_impact 一致性
        orig_depth = ann.get("quality", {}).get("citation_depth", "")
        if ci.get("total_citations", 0) >= 50 and orig_depth == "low":
            issues.append(self._issue("info", "enrichment", pid,
                "cross:depth_vs_citations",
                f"citation_depth=low但total_citations={ci['total_citations']}>=50"))

        return issues

    @staticmethod
    def _issue(level: str, category: str, paper_id: str,
               field: str, message: str) -> Dict:
        return {
            "level": level, "category": category,
            "paper_id": paper_id, "field": field, "message": message
        }


# ============================================================
# 更新后的质量指标计算
# ============================================================

class UpdatedScoreCalculator:
    """更新后的评分计算器：纳入富标签质量"""

    def compute_scores(self, original_scores: Dict,
                       enrichment_issues: List[Dict]) -> Dict:
        """
        在原有三级评分基础上，增加第四级富标签评分
        总分 = 格式(30) + 一致性(25) + 多样性(25) + 富标签(20) = 100
        """
        enrichment_errors = [i for i in enrichment_issues if i["level"] == "error"]
        enrichment_warnings = [i for i in enrichment_issues if i["level"] == "warning"]

        enrichment_score = max(0, 20 - len(enrichment_errors) * 4 - len(enrichment_warnings) * 1)

        # 原有三级评分调整为满分80
        orig_total = original_scores.get("overall", 60)
        adjusted_orig = orig_total * 0.8  # 缩放到80分制

        return {
            "format": round(original_scores.get("format", 30) * 0.75, 1),
            "consistency": round(original_scores.get("consistency", 25) * 0.75, 1),
            "diversity": round(original_scores.get("diversity", 25) * 0.75, 1),
            "enrichment": round(enrichment_score, 1),
            "overall": round(adjusted_orig + enrichment_score, 1)
        }

    def compute_enrichment_coverage(self, annotations: List[Dict]) -> Dict:
        """计算富标签覆盖率"""
        n = len(annotations)
        if n == 0:
            return {}

        has_status = sum(1 for a in annotations
                        if a.get("publication_status", {}).get("decision_source") not in (None, "unknown"))
        has_reviews = sum(1 for a in annotations
                        if a.get("review_information", {}).get("has_reviews", False))
        has_citations = sum(1 for a in annotations
                          if a.get("citation_impact", {}).get("total_citations", 0) > 0)
        has_provenance = sum(1 for a in annotations
                           if a.get("provenance", {}).get("conference") or
                           a.get("provenance", {}).get("journal"))

        return {
            "total_papers": n,
            "with_acceptance_status": has_status,
            "with_reviews": has_reviews,
            "with_citations": has_citations,
            "with_provenance": has_provenance,
            "coverage_status": round(has_status / n, 3),
            "coverage_reviews": round(has_reviews / n, 3),
            "coverage_citations": round(has_citations / n, 3),
            "coverage_provenance": round(has_provenance / n, 3),
        }


# ============================================================
# 集成运行
# ============================================================

def run_enrichment_qc(
    annotations_path: str = "SciEval-Bench-v0.2.0/data/annotations.json",
    output_path: str = "qc_v1.1_enrichment_report.json",
):
    """运行富标签QC"""
    import os

    if not os.path.exists(annotations_path):
        print(f"错误: 找不到标注文件 {annotations_path}")
        return

    with open(annotations_path, "r", encoding="utf-8") as f:
        annotations = json.load(f)

    n = len(annotations)
    print("=" * 60)
    print(f"SciEval-Bench QC v1.1 — 富标签验证")
    print(f"标注条目: {n}")
    print("=" * 60)

    # 第四级验证
    print("\n[第四级] 富标签完整性检查")
    print("-" * 40)
    validator = EnrichmentValidator()
    issues = validator.validate(annotations)

    errors = [i for i in issues if i["level"] == "error"]
    warnings = [i for i in issues if i["level"] == "warning"]
    infos = [i for i in issues if i["level"] == "info"]

    print(f"  错误: {len(errors)}, 警告: {len(warnings)}, 信息: {len(infos)}")

    for issue in errors[:10]:
        print(f"  ✗ [{issue['paper_id']}] {issue['field']}: {issue['message']}")
    for issue in warnings[:10]:
        print(f"  ⚠ [{issue['paper_id']}] {issue['message']}")

    if len(errors) + len(warnings) > 20:
        print(f"  ... (共{len(errors)+len(warnings)}条, 仅显示前20条)")

    # 覆盖率
    print("\n[覆盖率统计]")
    print("-" * 40)
    calc = UpdatedScoreCalculator()
    coverage = calc.compute_enrichment_coverage(annotations)
    count_key_map = {
        "status": "with_acceptance_status",
        "reviews": "with_reviews",
        "citations": "with_citations",
        "provenance": "with_provenance",
    }
    for key, val in coverage.items():
        if key.startswith("coverage_"):
            label = key.replace("coverage_", "")
            count_key = count_key_map.get(label, f"with_{label}")
            print(f"  {label}: {val:.0%} ({coverage.get(count_key, 0)}/{n})")

    # 综合评分
    original_scores = {"format": 30, "consistency": 25, "diversity": 25, "overall": 80}
    new_scores = calc.compute_scores(original_scores, issues)
    print(f"\n  综合评分（含富标签）: {new_scores['overall']:.1f}/100")
    print(f"    格式: {new_scores['format']}/30")
    print(f"    一致性: {new_scores['consistency']}/25")
    print(f"    多样性: {new_scores['diversity']}/25")
    print(f"    富标签: {new_scores['enrichment']}/20")

    report = {
        "annotations_path": str(Path(annotations_path).resolve()),
        "summary": {
            "total_annotations": n,
            "errors": len(errors),
            "warnings": len(warnings),
            "infos": len(infos),
            "scores": new_scores,
            "coverage": coverage,
        },
        "issues": issues,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  报告输出: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SciEval-Bench 富标签QC v1.1")
    parser.add_argument(
        "--annotations-path",
        default="SciEval-Bench-v0.2.0/data/annotations.json",
        help="待检测的标注数据JSON路径",
    )
    parser.add_argument(
        "--output-path",
        default="qc_v1.1_enrichment_report.json",
        help="QC报告输出路径",
    )
    args = parser.parse_args()
    run_enrichment_qc(
        annotations_path=args.annotations_path,
        output_path=args.output_path,
    )
