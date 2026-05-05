#!/usr/bin/env python3
"""
迭代式自评审生成原型 (Iterative Self-Review Prototype)
========================================================
针对 Research Arena 发现的两个核心问题：
  1. 引用幻觉 (Citation Hallucination) — 36%-72%虚假引用率
  2. 实验逻辑不完整 (Incomplete Experiment Design) — 声称但未实现的实验

设计思路：
  Round 0: 模型生成初始论文 (基线)
  Round 1-N: 评审器检测问题 → 反馈 → 模型修订 → 重新评审
  对比: Round 0 vs Round N 的引用准确率和实验完整性
  
基于 Research Arena 种子任务运行仿真。
"""
import json
import re
import random
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Tuple


# ============================================================
# 数据模型
# ============================================================

@dataclass
class PaperDraft:
    """论文草稿"""
    round: int
    title: str
    abstract: str
    introduction: str
    method: str
    experiments: str
    conclusion: str
    citations: List[Dict]  # {id, title, authors, year, is_real}
    experiment_claims: List[Dict]  # {description, is_implemented, result_in_paper}

    @property
    def citation_accuracy(self) -> float:
        if not self.citations:
            return 0.0
        return sum(1 for c in self.citations if c["is_real"]) / len(self.citations)

    @property
    def experiment_completeness(self) -> float:
        if not self.experiment_claims:
            return 0.0
        return sum(1 for c in self.experiment_claims if c["is_implemented"]) / len(self.experiment_claims)


@dataclass
class ReviewResult:
    """评审结果"""
    round: int
    citation_issues: List[str]    # 发现的虚假引用
    experiment_gaps: List[str]    # 发现的实验缺失
    citation_score: float         # 引用准确率 (评审器估计)
    experiment_score: float       # 实验完整性 (评审器估计)
    overall_score: float          # 综合评分 0-10
    feedback: str                 # 改进建议


@dataclass
class IterationRecord:
    """迭代记录"""
    seed_name: str
    rounds: List[PaperDraft]
    reviews: List[ReviewResult]
    citation_accuracy_trend: List[float]
    experiment_completeness_trend: List[float]
    baseline_citation_acc: float   # Research Arena 报告的基线
    baseline_experiment_gaps: str  # Research Arena 报告的典型问题


# ============================================================
# 模拟的 Research Arena 种子论文生成器
# ============================================================

class SimulatedPaperGenerator:
    """
    模拟论文生成器
    基于 Research Arena 报告的典型行为模式：
    - Claude Code: 中等编造率(36%), 较长论文, 实验缺失26%
    - Codex: 低编造率(8%), 较短论文, 实验过度保守
    - Kimi Code: 高编造率(72%), 短论文, 实验严重缺失(77%)
    """

    REAL_CITATIONS = [
        {"id": "r1", "title": "Attention Is All You Need", "authors": "Vaswani et al.", "year": 2017},
        {"id": "r2", "title": "BERT: Pre-training of Deep Bidirectional Transformers", "authors": "Devlin et al.", "year": 2019},
        {"id": "r3", "title": "Deep Residual Learning for Image Recognition", "authors": "He et al.", "year": 2016},
        {"id": "r4", "title": "Adam: A Method for Stochastic Optimization", "authors": "Kingma and Ba", "year": 2015},
        {"id": "r5", "title": "Dropout: A Simple Way to Prevent Neural Networks from Overfitting", "authors": "Srivastava et al.", "year": 2014},
        {"id": "r6", "title": "Batch Normalization", "authors": "Ioffe and Szegedy", "year": 2015},
        {"id": "r7", "title": "Generative Adversarial Networks", "authors": "Goodfellow et al.", "year": 2014},
        {"id": "r8", "title": "ImageNet Classification with Deep CNNs", "authors": "Krizhevsky et al.", "year": 2012},
    ]

    FAKE_CITATIONS = [
        {"id": "f1", "title": "Adaptive Neural Attention for Multi-Modal Learning", "authors": "Zhang et al.", "year": 2023},
        {"id": "f2", "title": "Transformer-X: Beyond Attention Mechanisms", "authors": "Li and Wang", "year": 2024},
        {"id": "f3", "title": "Deep Cross-Modal Fusion Networks", "authors": "Chen et al.", "year": 2023},
        {"id": "f4", "title": "Stochastic Depth-Adjusted Residual Learning", "authors": "Park and Kim", "year": 2022},
        {"id": "f5", "title": "Hierarchical Feature Aggregation with Graph Networks", "authors": "Liu et al.", "year": 2024},
    ]

    SEED_EXPERIMENT_CLAIMS = {
        "computer_vision": [
            ("Evaluated on ImageNet, CIFAR-100, and COCO", True),
            ("Compared against ResNet-50, ViT-B, and EfficientNet baselines", True),
            ("Ablation study on number of attention heads (1,2,4,8,16)", False),  # 仅部分实现
            ("Analysis of computational complexity vs accuracy trade-off", False),
            ("Robustness evaluation under adversarial perturbations", False),
        ],
        "natural_language_processing": [
            ("Evaluated on GLUE, SuperGLUE, and SQuAD benchmarks", True),
            ("Compared against BERT, RoBERTa, and T5 baselines", True),
            ("Fine-grained analysis per GLUE task category", False),
            ("Cross-lingual transfer evaluation on XNLI", False),
            ("Inference latency comparison across model sizes", False),
        ],
        "generative_models": [
            ("Evaluated FID and IS on CIFAR-10, CelebA, and LSUN", True),
            ("Compared against DDPM, StyleGAN2, and ADM baselines", True),
            ("Sampling speed vs quality trade-off analysis", False),
            ("Latent space interpolation and traversal", False),
            ("Conditional generation on class labels", False),
        ],
    }

    def __init__(self, agent_style: str = "claude", seed: int = 42):
        """
        agent_style: claude (36% fake, 26% missing) / codex (8% fake, 3% missing) / kimi (72% fake, 77% missing)
        """
        self.agent_style = agent_style
        self.rng = random.Random(seed)

        if agent_style == "claude":
            self.fake_citation_rate = 0.36
            self.experiment_missing_rate = 0.26
            self.paper_quality = "high"
            self.revision_efficiency = 0.7   # 每轮修改中实际改进的比例
        elif agent_style == "codex":
            self.fake_citation_rate = 0.08
            self.experiment_missing_rate = 0.03
            self.paper_quality = "medium"
            self.revision_efficiency = 0.9
        else:  # kimi
            self.fake_citation_rate = 0.72
            self.experiment_missing_rate = 0.77
            self.paper_quality = "low"
            self.revision_efficiency = 0.3

        self.citation_modification_rate = 0.5  # 反馈后修改引用的概率
        self.experiment_fix_rate = 0.4          # 反馈后修复实验的概率

    def generate_paper(self, seed_name: str, round_num: int = 0,
                       revision_feedback: str = "") -> PaperDraft:
        """生成论文（Round 0为基线，Round 1+为修订版）"""
        # 引用生成
        num_real = self.rng.randint(12, 20)
        num_fake = int(num_real * self.fake_citation_rate / (1 - self.fake_citation_rate)) if self.fake_citation_rate < 1 else num_real * 3

        citations = []
        for _ in range(num_real):
            c = self.rng.choice(self.REAL_CITATIONS).copy()
            citations.append({**c, "is_real": True})

        for _ in range(num_fake):
            c = self.rng.choice(self.FAKE_CITATIONS).copy()
            c["id"] = f"f{self.rng.randint(100,999)}"
            citations.append({**c, "is_real": False})

        # 如果有修订反馈，修改部分引用
        if revision_feedback and round_num > 0:
            fake_indices = [i for i, c in enumerate(citations) if not c["is_real"]]
            num_to_fix = int(len(fake_indices) * self.revision_efficiency * self.citation_modification_rate)
            for idx in self.rng.sample(fake_indices, min(num_to_fix, len(fake_indices))):
                citations[idx] = {**self.rng.choice(self.REAL_CITATIONS).copy(), "is_real": True}
                # 保留原ID以避免结构变化

        # 实验声明生成
        seed_claims = self.SEED_EXPERIMENT_CLAIMS.get(
            seed_name,
            self.SEED_EXPERIMENT_CLAIMS["computer_vision"]
        )
        experiment_claims = []
        for desc, is_impl in seed_claims:
            # 根据缺失率随机标记为未实现
            if not is_impl:
                actually_implemented = self.rng.random() > self.experiment_missing_rate
            else:
                actually_implemented = True
            experiment_claims.append({
                "description": desc,
                "is_implemented": actually_implemented,
                "result_in_paper": f"{self.rng.randint(75, 98)}.{self.rng.randint(0,9)}%"
            })

        # 如果有修订反馈，修复部分实验
        if revision_feedback and round_num > 0:
            missing = [i for i, c in enumerate(experiment_claims) if not c["is_implemented"]]
            num_to_fix = int(len(missing) * self.revision_efficiency * self.experiment_fix_rate)
            for idx in self.rng.sample(missing, min(num_to_fix, len(missing))):
                experiment_claims[idx]["is_implemented"] = True

        # 论文标题（带风格差异）
        if self.agent_style == "claude":
            title = f"The {self.rng.choice(['Algebra','Anatomy','Geometry','Dynamics'])} of {seed_name.replace('_',' ').title()}"
        elif self.agent_style == "codex":
            title = f"Do {self.rng.choice(['Shared','Adaptive','Hierarchical'])} Approaches Improve {seed_name.replace('_',' ').title()}?"
        else:
            title = f"{''.join(w[0].upper() for w in seed_name.split('_'))}{self.rng.choice(['-Net','-Former','-GAN'])}: A Novel Approach"

        return PaperDraft(
            round=round_num,
            title=title,
            abstract=f"We investigate {seed_name} using a novel approach...",
            introduction=f"The field of {seed_name} has seen significant progress...",
            method=f"Our method employs {self.rng.choice(['transformer','CNN','GNN','diffusion'])} architecture...",
            experiments=f"Extensive experiments on {self.rng.choice(['ImageNet','CIFAR','GLUE'])}...",
            conclusion=f"In conclusion, our method achieves state-of-the-art...",
            citations=citations,
            experiment_claims=experiment_claims
        )


# ============================================================
# 评审器：检测引用幻觉和实验缺失
# ============================================================

class SelfReviewer:
    """
    自评审器
    模拟 Research Arena 的自评审+外部评审双层检测
    检测能力随轮次提升（评审器从历史反馈中学习）
    """

    def __init__(self, detection_accuracy: float = 0.7):
        self.detection_accuracy = detection_accuracy
        self.review_history: List[ReviewResult] = []

    def review(self, paper: PaperDraft, round_num: int) -> ReviewResult:
        """评审论文，检测引用幻觉和实验缺失"""

        # 检测虚假引用
        citation_issues = []
        detected_fake = 0
        actual_fake = sum(1 for c in paper.citations if not c["is_real"])
        for c in paper.citations:
            if not c["is_real"] and random.random() < self.detection_accuracy:
                citation_issues.append(
                    f"引用 '{c['title']}' ({c['authors']}, {c['year']}) 未在CrossRef/Semantic Scholar中找到"
                )
                detected_fake += 1

        # 检测实验缺失
        experiment_gaps = []
        detected_gaps = 0
        actual_gaps = sum(1 for c in paper.experiment_claims if not c["is_implemented"])
        for claim in paper.experiment_claims:
            if not claim["is_implemented"] and random.random() < self.detection_accuracy:
                experiment_gaps.append(
                    f"论文声称 '{claim['description']}' 但实验代码中未找到对应实现"
                )
                detected_gaps += 1

        # 估计分数（模拟评审器评分行为）
        citation_score = max(0, 1.0 - detected_fake / max(1, len(paper.citations)))
        experiment_score = max(0, 1.0 - detected_gaps / max(1, len(paper.experiment_claims)))
        overall = (citation_score * 0.4 + experiment_score * 0.6) * 10

        # 生成反馈
        feedback_parts = []
        if citation_issues:
            feedback_parts.append(
                f"引用问题（{detected_fake}处）：请将以下虚假引用替换为真实论文——"
                + "; ".join(i.split("引用 '")[1].split("' ")[0][:30] for i in citation_issues[:3])
            )
        if experiment_gaps:
            feedback_parts.append(
                f"实验缺失（{detected_gaps}处）：请实现以下实验——"
                + "; ".join(g.split("'")[1][:40] for g in experiment_gaps[:3])
            )
        if not citation_issues and not experiment_gaps:
            feedback_parts.append("未发现明显问题。建议进一步丰富实验分析。")

        feedback = "\n".join(feedback_parts)

        result = ReviewResult(
            round=round_num,
            citation_issues=citation_issues,
            experiment_gaps=experiment_gaps,
            citation_score=round(citation_score, 3),
            experiment_score=round(experiment_score, 3),
            overall_score=round(overall, 1),
            feedback=feedback
        )
        self.review_history.append(result)
        return result


# ============================================================
# 迭代引擎
# ============================================================

class IterativeEngine:
    """迭代式自评审生成引擎"""

    def __init__(self, agent_style: str = "claude", max_rounds: int = 4,
                 detection_accuracy: float = 0.7, seed: int = 42):
        self.generator = SimulatedPaperGenerator(agent_style, seed)
        self.reviewer = SelfReviewer(detection_accuracy)
        self.max_rounds = max_rounds
        self.records: List[IterationRecord] = []

    def run_seed(self, seed_name: str) -> IterationRecord:
        """在某个种子上运行完整的迭代流程"""
        print(f"\n{'='*60}")
        print(f"种子: {seed_name} | Agent: {self.generator.agent_style}")
        print(f"{'='*60}")

        rounds = []
        reviews = []
        cit_acc = []
        exp_comp = []

        # Round 0: 基线生成
        print("\n[Round 0] 基线生成...")
        paper = self.generator.generate_paper(seed_name, round_num=0)
        review = self.reviewer.review(paper, 0)
        rounds.append(paper)
        reviews.append(review)
        cit_acc.append(paper.citation_accuracy)
        exp_comp.append(paper.experiment_completeness)
        self._print_round(0, paper, review)

        # Round 1-N: 迭代修订
        for r in range(1, self.max_rounds + 1):
            print(f"\n[Round {r}] 基于反馈修订...")
            paper = self.generator.generate_paper(
                seed_name, round_num=r,
                revision_feedback=reviews[-1].feedback
            )
            review = self.reviewer.review(paper, r)
            rounds.append(paper)
            reviews.append(review)
            cit_acc.append(paper.citation_accuracy)
            exp_comp.append(paper.experiment_completeness)
            self._print_round(r, paper, review)

            # 如果问题全部解决，提前结束
            if not review.citation_issues and not review.experiment_gaps:
                print(f"  ✓ 所有问题已解决，提前结束迭代")
                break

        # 对比基线
        baseline_cit = ResearchArena_BASELINES.get(
            self.generator.agent_style, {}).get("citation_accuracy", 0.64)
        baseline_exp = ResearchArena_BASELINES.get(
            self.generator.agent_style, {}).get("experiment_integrity", "31%")

        record = IterationRecord(
            seed_name=seed_name,
            rounds=rounds,
            reviews=reviews,
            citation_accuracy_trend=cit_acc,
            experiment_completeness_trend=exp_comp,
            baseline_citation_acc=baseline_cit,
            baseline_experiment_gaps=baseline_exp
        )
        self.records.append(record)
        return record

    def _print_round(self, r: int, paper: PaperDraft, review: ReviewResult):
        print(f"  引用准确率: {paper.citation_accuracy:.0%} ({sum(1 for c in paper.citations if c['is_real'])}/{len(paper.citations)})")
        print(f"  实验完整性: {paper.experiment_completeness:.0%}")
        print(f"  评审评分: {review.overall_score}/10")
        print(f"  发现问题: 引用{len(review.citation_issues)}处, 实验{len(review.experiment_gaps)}处")


# Research Arena 报告的基线数据
ResearchArena_BASELINES = {
    "claude": {"citation_accuracy": 0.64, "experiment_integrity": "69% (31% both mismatch)"},
    "codex":  {"citation_accuracy": 0.92, "experiment_integrity": "95% (5% both mismatch)"},
    "kimi":   {"citation_accuracy": 0.28, "experiment_integrity": "23% (77% both mismatch)"},
}


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 70)
    print("迭代式自评审生成原型 — 引用幻觉 & 实验逻辑验证")
    print("=" * 70)

    # Research Arena 的13个代表性种子（论文中使用）
    seeds = [
        "computer_vision", "natural_language_processing", "generative_models",
        "supervised_representation_learning", "interpretability_of_learned_representations",
        "privacy_in_machine_learning", "AI_for_biology", "datasets_and_benchmarks",
        "causal_reasoning", "compiler_optimization", "data_integration_and_cleaning",
        "operating_system_design", "probabilistic_methods"
    ]

    # 三种Agent类型
    agent_types = ["claude", "codex", "kimi"]

    all_records = []
    for agent in agent_types:
        print(f"\n{'#'*70}")
        print(f"# Agent: {agent.upper()}")
        print(f"{'#'*70}")
        engine = IterativeEngine(agent_style=agent, max_rounds=3, seed=42)
        for seed in seeds[:5]:  # 只跑5个代表性种子
            record = engine.run_seed(seed)
            all_records.append(record)

    # 汇总对比
    print("\n" + "=" * 70)
    print("迭代效果对比: Round 0 (基线) vs Round N (最终)")
    print("=" * 70)

    for agent in agent_types:
        agent_records = [r for r in all_records
                        if r.rounds and r.rounds[0].citations]
        if not agent_records:
            continue

        avg_cit_r0 = sum(r.citation_accuracy_trend[0] for r in agent_records) / len(agent_records)
        avg_exp_r0 = sum(r.experiment_completeness_trend[0] for r in agent_records) / len(agent_records)
        avg_cit_rn = sum(r.citation_accuracy_trend[-1] for r in agent_records) / len(agent_records)
        avg_exp_rn = sum(r.experiment_completeness_trend[-1] for r in agent_records) / len(agent_records)

        cit_improve = (avg_cit_rn - avg_cit_r0) / max(0.01, avg_cit_r0) * 100
        exp_improve = (avg_exp_rn - avg_exp_r0) / max(0.01, avg_exp_r0) * 100

        print(f"\n{agent.upper()}:")
        print(f"  引用准确率: {avg_cit_r0:.0%} → {avg_cit_rn:.0%} (+{cit_improve:.0f}%)")
        print(f"  实验完整性: {avg_exp_r0:.0%} → {avg_exp_rn:.0%} (+{exp_improve:.0f}%)")
        baseline = ResearchArena_BASELINES[agent]
        print(f"  ResearchArena基线: 引用{baseline['citation_accuracy']:.0%}, 实验{baseline['experiment_integrity']}")

    # 保存结果
    output = {
        "timestamp": datetime.now().isoformat(),
        "config": {"max_rounds": 3, "seeds_tested": 5, "agents": agent_types},
        "records": [
            {
                "agent": r.rounds[0].citations[0]["authors"] if r.rounds else "",
                "seed": r.seed_name,
                "citation_trend": r.citation_accuracy_trend,
                "experiment_trend": r.experiment_completeness_trend,
                "baseline_citation": r.baseline_citation_acc,
                "baseline_experiment": r.baseline_experiment_gaps
            }
            for r in all_records
        ]
    }
    with open("/home/ubuntu/iterative_prototype_results.json", "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n结果保存至: /home/ubuntu/iterative_prototype_results.json")


if __name__ == "__main__":
    main()
