#!/usr/bin/env python3
"""
SciEval-Bench 采集结果筛选脚本
================================
将采集阶段输出的论文列表收敛为适合进入标注阶段的候选集，包含：

1. 去重
2. 全文可获取性过滤
3. 时间窗口过滤
"""
import argparse
import json
import os
from collections import Counter
from typing import Dict, List

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT_PATH = os.path.join(PROJECT_ROOT, "scieval_collected", "collected_papers.json")
DEFAULT_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "scieval_collected")


def load_papers(input_path: str) -> List[Dict]:
    with open(input_path, "r", encoding="utf-8") as f:
        papers = json.load(f)
    if not isinstance(papers, list):
        raise ValueError("输入文件不是论文列表 JSON")
    return papers


def deduplicate_papers(papers: List[Dict]) -> List[Dict]:
    seen = set()
    unique = []
    for paper in papers:
        key = paper.get("arxiv_id") or paper.get("paper_id") or ""
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(paper)
    return unique


def filter_fulltext_available(papers: List[Dict]) -> List[Dict]:
    return [paper for paper in papers if paper.get("arxiv_id")]


def filter_recent_papers(papers: List[Dict], min_year: int) -> List[Dict]:
    filtered = []
    for paper in papers:
        pub_date = str(paper.get("publication_date", ""))
        year_text = pub_date[:4]
        if year_text.isdigit() and int(year_text) >= min_year:
            filtered.append(paper)
    return filtered


def build_stats(raw: List[Dict], deduplicated: List[Dict], fulltext: List[Dict],
                recent: List[Dict], min_year: int) -> Dict:
    discipline_counter = Counter()
    for paper in recent:
        path = paper.get("discipline_path") or []
        if path:
            discipline_counter[path[0]] += 1

    return {
        "input_count": len(raw),
        "deduplicated_count": len(deduplicated),
        "fulltext_count": len(fulltext),
        "recent_count": len(recent),
        "min_year": min_year,
        "discipline_distribution": dict(discipline_counter),
    }


def save_json(file_path: str, data) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="SciEval-Bench 采集结果筛选脚本"
    )
    parser.add_argument(
        "--input", type=str, default=DEFAULT_INPUT_PATH,
        help=f"采集结果输入文件 (默认: {DEFAULT_INPUT_PATH})"
    )
    parser.add_argument(
        "--output-dir", type=str, default=DEFAULT_OUTPUT_DIR,
        help=f"筛选结果输出目录 (默认: {DEFAULT_OUTPUT_DIR})"
    )
    parser.add_argument(
        "--min-year", type=int, default=2022,
        help="保留的最早发表年份 (默认: 2022)"
    )
    parser.add_argument(
        "--allow-no-arxiv", action="store_true",
        help="不过滤无 arXiv ID 的论文"
    )
    args = parser.parse_args()

    input_path = os.path.abspath(os.path.expanduser(args.input))
    output_dir = os.path.abspath(os.path.expanduser(args.output_dir))
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(input_path):
        print(f"错误：找不到采集结果文件 {input_path}")
        return

    print("=" * 70)
    print("SciEval-Bench 采集结果筛选")
    print("=" * 70)
    print(f"输入文件: {input_path}")
    print(f"输出目录: {output_dir}")

    raw_papers = load_papers(input_path)
    deduplicated = deduplicate_papers(raw_papers)
    fulltext = deduplicated if args.allow_no_arxiv else filter_fulltext_available(deduplicated)
    recent = filter_recent_papers(fulltext, args.min_year)

    save_json(os.path.join(output_dir, "deduplicated.json"), deduplicated)
    save_json(os.path.join(output_dir, "filtered_fulltext.json"), fulltext)
    save_json(os.path.join(output_dir, "filtered_recent.json"), recent)

    stats = build_stats(raw_papers, deduplicated, fulltext, recent, args.min_year)
    stats_path = os.path.join(output_dir, "filter_stats.json")
    save_json(stats_path, stats)

    print(f"\n去重前: {len(raw_papers)}")
    print(f"去重后: {len(deduplicated)}")
    print(f"全文可获取: {len(fulltext)}")
    print(f"{args.min_year} 年及以后: {len(recent)}")
    print(f"统计文件: {stats_path}")


if __name__ == "__main__":
    main()
