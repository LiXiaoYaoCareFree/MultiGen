#!/usr/bin/env python3
"""
SciEval-Bench v0.3.0 发布打包
===============================
基于 v0.2.0 升级，新增：
  - 富标签示例数据 (publication_status, review_information, citation_impact, provenance)
  - scieval_enrichment.py (富标签采集模块)
  - scieval_qc_v1.1_upgrade.py (QC v1.1)
  - dataset_spec_v1.1_upgrade.md (规范升级文档)
  - public_datasets_improvement.md (公开数据集分析)
"""
import json
import os
import shutil
import hashlib
import argparse
from pathlib import Path
from datetime import datetime

RELEASE_CONFIG = {
    "name": "SciEval-Bench",
    "version": "0.3.0",
    "codename": "enriched-prototype",
    "release_date": datetime.now().strftime("%Y-%m-%d"),
    "description": "统一AI自动科研评估数据集 — 富标签升级版",
    "whats_new": [
        "新增 publication_status 标签（accepted/rejected/preprint）",
        "新增 review_information 标签（评审分数、评审文本）",
        "新增 citation_impact 标签（引用次数、引用速度）",
        "新增 provenance 标签（出处、代码可用性）",
        "新增 scieval_enrichment.py 富标签采集模块",
        "新增 scieval_qc_v1.1_upgrade.py 四级QC验证",
    ],
}

def _is_valid_json_file(file_path: Path) -> bool:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            json.load(f)
        return True
    except Exception:
        return False


def generate_readme() -> str:
    v = RELEASE_CONFIG["version"]
    return f"""# SciEval-Bench v{v}

## 概述
SciEval-Bench 是一个统一AI自动科研评估数据集。v{v} 为富标签升级版。

## v{v} 新增功能
- **论文状态标签**: 标注 accepted/rejected/preprint/published/withdrawn
- **评审信息标签**: 包含评审分数、评论文本、评审者间一致性
- **引用影响力标签**: 量化引用数据（总引用、年均引用、引用速度）
- **出处标签**: 会议/期刊信息、开放获取状态、代码可用性

## 快速开始
```bash
# 富标签采集
python3 tools/scieval_enrichment.py

# 质量控制（含富标签验证）
python3 tools/scieval_qc_v1.1_upgrade.py
```

## 版本历史
- v0.1.0: 初始原型 (13条, 4学科)
- v0.2.0: 标注管线+QC引擎+Code-Aware
- v0.3.0: 富标签升级 (本版本)
"""


def generate_sample_data() -> str:
    """生成包含完整富标签的示例数据"""
    sample = {
        "paper_id": "CS-AI-001",
        "task_type": "full_paper_generation",
        "difficulty_level": 1,
        "discipline_path": ["形式科学", "计算机科学", "人工智能", "深度学习"],

        # === 富标签 ===
        "publication_status": {
            "status": "accepted",
            "venue": "ICLR 2024",
            "venue_type": "conference",
            "acceptance_rate": 0.27,
            "decision_date": "2024-01-15",
            "decision_source": "openreview_api"
        },
        "review_information": {
            "has_reviews": True,
            "num_reviews": 3,
            "review_scores": {
                "overall": 6.5,
                "confidence": 4,
                "dimensions": {"novelty": 3, "soundness": 3, "presentation": 3, "contribution": 3}
            },
            "review_texts": [
                {"summary": "This paper presents a novel approach to attention mechanisms...",
                 "strengths": ["Strong theoretical foundation"],
                 "weaknesses": ["Missing key baseline comparison"],
                 "recommendation": "weak_accept"}
            ],
            "has_rebuttal": True,
            "has_meta_review": True,
            "inter_reviewer_agreement": 0.72,
            "review_source": "openreview_api"
        },
        "citation_impact": {
            "total_citations": 145,
            "citations_per_year": 48.3,
            "influential_citations": 32,
            "citation_velocity": "high",
            "citation_source": "semantic_scholar_api",
            "retrieved_at": datetime.now().isoformat()
        },
        "provenance": {
            "conference": "ICLR",
            "conference_year": 2024,
            "journal": None,
            "publisher": "OpenReview",
            "is_open_access": True,
            "license": "CC BY 4.0",
            "has_code": True,
            "code_repository_url": "https://github.com/author/paper-code",
            "has_data": True,
            "is_preprint_of_published": False
        },

        # === 原有字段 ===
        "content_annotations": {
            "research_type": "methodological",
            "argumentation_type": "empirical",
            "math_density": "medium",
            "figure_dependency": "high"
        },
        "quality_annotations": {
            "citation_depth": "high",
            "argument_complexity": "high",
            "innovation_level": "significant_improvement",
            "paper_quality_grade": "A"
        },
        "decontamination": {"risk_level": "safe", "gpt4o_cutoff_safe": True}
    }
    return json.dumps(sample, ensure_ascii=False, indent=2)


def package_release(source_dir: str = ".", output_root: str = "."):
    version = RELEASE_CONFIG["version"]
    source_root = Path(source_dir).resolve()
    output_root_path = Path(output_root).resolve()
    release_dir = output_root_path / f"SciEval-Bench-v{version}"

    print("=" * 60)
    print(f"SciEval-Bench v{version} 发布打包")
    print("=" * 60)

    # 清理旧目录
    if release_dir.exists():
        shutil.rmtree(release_dir)

    # 创建目录结构
    for d in ["data", "reports", "tools", "docs"]:
        os.makedirs(release_dir / d, exist_ok=True)

    # 复制数据文件
    sample_path = release_dir / "data" / "sample_enriched.json"
    with open(sample_path, "w", encoding="utf-8") as f:
        f.write(generate_sample_data())
    print(f"  ✓ data/sample_enriched.json")

    # 复制可用的真实标注数据（来自已有v0.2.0发布包）
    legacy_data_dir = source_root / "SciEval-Bench-v0.2.0" / "data"
    copied_annotations = False
    copied_checklists = False
    if legacy_data_dir.exists():
        for name in ("annotations.json", "fabrication_checklists.json"):
            src = legacy_data_dir / name
            if src.exists() and _is_valid_json_file(src):
                shutil.copy2(src, release_dir / "data" / name)
                print(f"  ✓ data/{name}")
                if name == "annotations.json":
                    copied_annotations = True
                if name == "fabrication_checklists.json":
                    copied_checklists = True
            elif src.exists():
                print(f"  ! 跳过损坏文件 data/{name}")

    # 如果历史数据损坏，生成可用的最小数据集占位，确保发布包可被下游解析
    if not copied_annotations:
        with open(release_dir / "data" / "annotations.json", "w", encoding="utf-8") as f:
            f.write("[\n")
            f.write(generate_sample_data())
            f.write("\n]\n")
        print("  ✓ data/annotations.json (fallback from sample_enriched)")
    if not copied_checklists:
        with open(release_dir / "data" / "fabrication_checklists.json", "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        print("  ✓ data/fabrication_checklists.json (fallback empty)")

    legacy_reports_dir = source_root / "SciEval-Bench-v0.2.0" / "reports"
    if legacy_reports_dir.exists():
        for report_name in ("qc_report.json", "qc_issues.json"):
            src = legacy_reports_dir / report_name
            if src.exists():
                shutil.copy2(src, release_dir / "reports" / report_name)
                print(f"  ✓ reports/{report_name}")

    # 复制工具脚本
    tools = {
        "scieval_collector.py": source_root / "scieval_collector.py",
        "scieval_enrichment.py": source_root / "scieval_enrichment.py",
        "scieval_qc_v1.1_upgrade.py": source_root / "scieval_qc_v1.1_upgrade.py",
    }
    for name, src in tools.items():
        dest = release_dir / "tools" / name
        if os.path.exists(src):
            shutil.copy2(src, dest)
            print(f"  ✓ tools/{name}")

    # 复制文档
    docs = {
        "dataset_spec_v1.1_upgrade.md": source_root / "dataset_spec_v1.1_upgrade.md",
        "public_datasets_improvement.md": source_root / "public_datasets_improvement.md",
        "detailed_design_document.md": source_root / "detailed_design_document.md",
        "design_rationale.md": source_root / "design_rationale.md",
        "construction_steps_detail.md": source_root / "construction_steps_detail.md",
        "scieval_evaluation_guide.md": source_root / "scieval_evaluation_guide.md",
        "evaluation_input_spec.md": source_root / "evaluation_input_spec.md",
        "dataset_purpose_explanation.md": source_root / "dataset_purpose_explanation.md",
    }
    for name, src in docs.items():
        dest = release_dir / "docs" / name
        if os.path.exists(src):
            shutil.copy2(src, dest)
            print(f"  ✓ docs/{name}")

    # 生成 README / CHANGELOG / VERSION / MANIFEST
    with open(release_dir / "README.md", "w", encoding="utf-8") as f:
        f.write(generate_readme())
    with open(release_dir / "VERSION", "w", encoding="utf-8") as f:
        f.write(f"{version}\n")
    print(f"  ✓ README.md, VERSION")

    # 统计
    total_files = sum(1 for _ in os.walk(release_dir) for f in _[2])
    total_size = sum(os.path.getsize(os.path.join(r, f))
                    for r, _, files in os.walk(release_dir) for f in files)

    print(f"\n发布包: {release_dir}")
    print(f"文件数: {total_files}, 大小: {total_size/1024:.1f} KB")

    return str(release_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SciEval-Bench v0.3.0 本地打包工具")
    parser.add_argument(
        "--source-dir",
        default=str(Path(__file__).resolve().parent),
        help="源文件目录（默认脚本所在目录）",
    )
    parser.add_argument(
        "--output-root",
        default=str(Path.cwd()),
        help="发布包输出根目录（默认当前工作目录）",
    )
    args = parser.parse_args()
    package_release(source_dir=args.source_dir, output_root=args.output_root)
