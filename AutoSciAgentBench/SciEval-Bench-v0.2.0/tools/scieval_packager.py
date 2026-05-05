#!/usr/bin/env python3
"""
SciEval-Bench 数据发布打包工具
================================
按照语义化版本 (MAJOR.MINOR.PATCH) 打包完整的数据集发布包，
包含：数据本体、标注说明、质量报告、构建代码、README和CHANGELOG。
"""
import json
import os
import shutil
import hashlib
import argparse
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 发布配置
# ============================================================

RELEASE_CONFIG = {
    "name": "SciEval-Bench",
    "version": "0.2.0",        # 原型验证版本
    "codename": "prototype",
    "release_date": datetime.now().strftime("%Y-%m-%d"),
    "description": "统一AI自动科研评估数据集 — 原型验证版本",
    "license": "CC BY 4.0 (数据) / MIT (代码)",
    "maintainer": "SciEval-Bench Community",
}

# ============================================================
# 生成文件内容
# ============================================================

def generate_readme(version: str, date: str) -> str:
    return f"""# SciEval-Bench v{version}

## 概述

SciEval-Bench 是一个统一AI自动科研评估数据集，旨在为各类AI科研论文生成工具提供标准化、可横向对比的评估基准。

### 核心用途
- **统一评估**：所有AI工具在相同任务、相同输入、相同标准下接受评估
- **横向对比**：在同一数据集上直接比较多种AI科研工具的能力差异
- **人机比较**：将AI生成论文与人类论文进行匿名化配对评审

### 数据规模（v{version}）
- 学科大类：6个（形式科学、自然科学、工程与技术科学、医学与生命科学、社会科学、人文学科）
- 子学科：12+
- 任务实例：20条（原型验证）
- Code-Aware实例：2条
- 编造检测清单：2份

### 目录结构
```
SciEval-Bench-v{version}/
├── README.md
├── CHANGELOG.md
├── LICENSE.txt
├── VERSION
├── data/
│   ├── annotations.json          # 完整标注数据
│   ├── fabrication_checklists.json  # 编造检测清单
│   └── taxonomy.json             # 学科分类学定义
├── reports/
│   ├── qc_report.json            # 质量控制报告
│   └── annotation_summary.json   # 标注统计摘要
├── tools/
│   ├── scieval_collector.py      # 数据采集工具
│   ├── scieval_annotator.py      # 标注管线
│   └── scieval_qc.py             # 质量控制引擎
├── docs/
│   ├── dataset_final_spec.md     # 数据集最终规范
│   └── final_unified_scheme_upgraded.md  # 升级版方案文档
└── manifest.json                 # 文件清单与校验和
```

### 快速开始
```bash
# 查看数据集内容
python3 -c "import json; d=json.load(open('data/annotations.json')); print(f'{{len(d)}}条标注数据')"

# 运行质量控制
python3 tools/scieval_qc.py

# 构建自己的数据集
python3 tools/scieval_collector.py --dry-run  # 预览
python3 tools/scieval_collector.py --papers-per-keyword 10  # 采集
python3 tools/scieval_annotator.py            # 标注
```

### 引用
如果使用本数据集，请引用：
```
@misc{{scieval-bench-{version},
  title={{SciEval-Bench: A Unified Evaluation Benchmark for AI Scientific Research}},
  version={{v{version}}},
  year={{2026}},
  url={{https://github.com/scieval-bench}}
}}
```

### 许可证
- 数据标注和文档：CC BY 4.0
- 工具代码：MIT

---
发布日期：{date}
"""


def generate_changelog() -> str:
    return """# Changelog

## [0.2.0] - 2026-04-28

### Added
- 完整的三级质量控制引擎 (scieval_qc.py)
- 编造检测清单生成与验证
- Code-Aware任务子类型支持
- 人工校验模块与Kappa计算
- LLM辅助+人工校验标注管线 (scieval_annotator.py)
- 多源数据采集工具 (scieval_collector.py)
- 六大学科全覆盖的关键词体系（167个关键词）
- 人文学科和工程学科数据覆盖

### Changed
- 评估维度从六维扩展为九维（新增可复现性、参考文献完整性、结果完整性）
- 评审体系从单层升级为Text-Only + Code-Aware双层

### Fixed
- 去污染验证的LLM截止日期比对逻辑

## [0.1.0] - 2026-04-27

### Added
- 初始原型数据集（13条实例，4学科大类，5任务类型）
- 基础评估器系统 (evaluator_system.py)
- 三种工具横向对比基准 (tool_benchmark.py)
- 统一方案架构设计文档
"""


def generate_manifest(files: dict) -> dict:
    """生成文件清单与SHA256校验和"""
    manifest = {
        "release": RELEASE_CONFIG["name"],
        "version": RELEASE_CONFIG["version"],
        "generated_at": datetime.now().isoformat(),
        "files": {}
    }
    for rel_path, abs_path in files.items():
        if os.path.isfile(abs_path):
            with open(abs_path, "rb") as f:
                sha = hashlib.sha256(f.read()).hexdigest()
            size = os.path.getsize(abs_path)
            manifest["files"][rel_path] = {
                "sha256": sha,
                "size_bytes": size
            }
    return manifest


def project_path(*parts: str) -> str:
    return os.path.join(PROJECT_ROOT, *parts)


def resolve_existing_path(*candidates: str) -> str:
    """返回第一个存在的候选路径；若都不存在，则返回首个候选值。"""
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return candidates[0]


# ============================================================
# 打包主流程
# ============================================================

def package_release(release_dir: str = None):
    version = RELEASE_CONFIG["version"]
    if release_dir is None:
        release_dir = project_path(f"SciEval-Bench-v{version}")
    release_dir = os.path.abspath(os.path.expanduser(release_dir))
    date = RELEASE_CONFIG["release_date"]

    print("=" * 70)
    print(f"SciEval-Bench v{version} 发布打包")
    print(f"日期: {date}")
    print("=" * 70)

    # 清理旧发布
    if os.path.exists(release_dir):
        shutil.rmtree(release_dir)

    # 创建目录结构
    dirs = ["data", "reports", "tools", "docs"]
    for d in dirs:
        os.makedirs(os.path.join(release_dir, d), exist_ok=True)
    print(f"\n创建目录结构: {', '.join(dirs)}")

    # 收集源文件
    sources = {
        # 数据文件
        "data/annotations.json": project_path("scieval_annotations", "annotations.json"),
        "data/fabrication_checklists.json": project_path("scieval_annotations", "fabrication_checklists.json"),
        "data/taxonomy.json": project_path("scieval_annotations", "annotation_summary.json"),

        # 报告文件
        "reports/qc_report.json": project_path("scieval_qc", "qc_report.json"),
        "reports/qc_issues.json": project_path("scieval_qc", "qc_issues.json"),

        # 工具代码
        "tools/scieval_collector.py": project_path("scieval_collector.py"),
        "tools/scieval_annotator.py": project_path("scieval_annotator.py"),
        "tools/scieval_qc.py": project_path("scieval_qc.py"),
        "tools/scieval_filter.py": project_path("scieval_filter.py"),
        "tools/scieval_packager.py": project_path("scieval_packager.py"),

        # 文档
        "docs/dataset_final_spec.md": resolve_existing_path(
            project_path("dataset_final_spec.md"),
            project_path("home", "ubuntu", "dataset_final_spec.md"),
        ),
        "docs/final_unified_scheme_upgraded.md": resolve_existing_path(
            project_path("final_unified_scheme_upgraded.md"),
            project_path("home", "ubuntu", "final_unified_scheme_upgraded.md"),
        ),
        "docs/dataset_build_guide.md": resolve_existing_path(
            project_path("dataset_build_guide.md"),
            project_path("home", "ubuntu", "dataset_build_guide.md"),
        ),
        "docs/dataset_purpose_explanation.md": resolve_existing_path(
            project_path("dataset_purpose_explanation.md"),
            project_path("home", "ubuntu", "dataset_purpose_explanation.md"),
        ),
        "docs/deep_comparison_analysis.md": resolve_existing_path(
            project_path("deep_comparison_analysis.md"),
            project_path("home", "ubuntu", "deep_comparison_analysis.md"),
        ),
        "docs/integrated_optimization_plan.md": resolve_existing_path(
            project_path("integrated_optimization_plan.md"),
            project_path("home", "ubuntu", "integrated_optimization_plan.md"),
        ),
        "docs/scieval_operations_guide.md": project_path("scieval_operations_guide.md"),
        "docs/dataset_build_report.md": project_path("dataset_build_report.md"),
    }

    # 复制文件
    copied = 0
    skipped = 0
    for rel_path, abs_path in sources.items():
        dest = os.path.join(release_dir, rel_path)
        if os.path.exists(abs_path):
            shutil.copy2(abs_path, dest)
            copied += 1
            print(f"  ✓ {rel_path}")
        else:
            skipped += 1
            print(f"  ✗ {rel_path} (源文件不存在)")

    print(f"\n复制: {copied} 个文件, 跳过: {skipped} 个")

    # 生成README
    readme_path = os.path.join(release_dir, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(generate_readme(version, date))
    print("  ✓ README.md")

    # 生成CHANGELOG
    changelog_path = os.path.join(release_dir, "CHANGELOG.md")
    with open(changelog_path, "w", encoding="utf-8") as f:
        f.write(generate_changelog())
    print("  ✓ CHANGELOG.md")

    # 生成VERSION文件
    version_path = os.path.join(release_dir, "VERSION")
    with open(version_path, "w") as f:
        f.write(f"{version}\n")
    print("  ✓ VERSION")

    # 生成LICENSE
    license_path = os.path.join(release_dir, "LICENSE.txt")
    with open(license_path, "w") as f:
        f.write("""SciEval-Bench License

Data annotations and documentation: CC BY 4.0
  https://creativecommons.org/licenses/by/4.0/

Tool code: MIT License
  Permission is hereby granted, free of charge, to any person obtaining a copy...
""")
    print("  ✓ LICENSE.txt")

    # 生成MANIFEST
    all_files = {}
    for root, _, files in os.walk(release_dir):
        for fn in files:
            abs_path = os.path.join(root, fn)
            rel_path = os.path.relpath(abs_path, release_dir)
            all_files[rel_path] = abs_path

    manifest = generate_manifest(all_files)
    manifest_path = os.path.join(release_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("  ✓ manifest.json")

    # 统计
    total_size = sum(
        os.path.getsize(os.path.join(release_dir, f))
        for f in all_files
    )
    print(f"\n{'='*70}")
    print(f"发布包生成完成!")
    print(f"  路径: {release_dir}")
    print(f"  文件数: {len(all_files)}")
    print(f"  总大小: {total_size / 1024:.1f} KB")
    print(f"{'='*70}")

    return release_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="SciEval-Bench 数据发布打包工具"
    )
    parser.add_argument(
        "--release-dir", type=str, default=None,
        help="发布包输出目录，默认输出到当前项目根目录下的 SciEval-Bench-v<version>"
    )
    args = parser.parse_args()
    package_release(release_dir=args.release_dir)
