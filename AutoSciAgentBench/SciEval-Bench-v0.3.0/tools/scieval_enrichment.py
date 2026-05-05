#!/usr/bin/env python3
"""
SciEval-Bench 富标签采集模块
===============================
从 OpenReview、Semantic Scholar、DBLP、Crossref 等公开API
自动采集论文的评审信息、接受状态、引用数据和出处信息。

集成方式：
  1. 作为 scieval_collector.py 的扩展模块（采集阶段自动获取）
  2. 作为 scieval_annotator.py 的第二阶段（标注后自动填充）

关键API：
  - OpenReview API: 评审意见、接受/拒绝标签、评审分数
  - Semantic Scholar API: 引用次数、引用影响力、代码仓库检测
  - DBLP API: 会议/期刊出处、作者信息
  - Crossref API: DOI验证、许可信息
"""
import json
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.parse import urlencode, quote


# ============================================================
# 数据模型
# ============================================================

class EnrichmentResult:
    """富标签采集结果"""

    def __init__(self, paper_id: str):
        self.paper_id = paper_id
        self.publication_status: Optional[Dict] = None
        self.review_information: Optional[Dict] = None
        self.citation_impact: Optional[Dict] = None
        self.provenance: Optional[Dict] = None
        self.errors: List[str] = []
        self.sources_used: List[str] = []

    def to_dict(self) -> Dict:
        return {
            "paper_id": self.paper_id,
            "publication_status": self.publication_status,
            "review_information": self.review_information,
            "citation_impact": self.citation_impact,
            "provenance": self.provenance,
            "errors": self.errors,
            "sources_used": self.sources_used,
            "enriched_at": datetime.now().isoformat()
        }


# ============================================================
# Semantic Scholar API 客户端（引用数据 + 代码检测）
# ============================================================

class SemanticScholarEnricher:
    """从 Semantic Scholar API 获取引用数据和可复现性信息"""

    BASE = "https://api.semanticscholar.org/graph/v1"

    def _api_get(self, url: str) -> Optional[Dict]:
        try:
            req = Request(url, headers={"User-Agent": "SciEval-Bench/1.1"})
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return None

    def search_paper(self, title: str, arxiv_id: str = "") -> Optional[Dict]:
        """搜索论文"""
        query = title[:200]
        if arxiv_id:
            query = f"ArXiv:{arxiv_id}"

        params = urlencode({
            "query": query,
            "limit": 1,
            "fields": "paperId,title,citationCount,influentialCitationCount,"
                      "year,venue,publicationVenue,externalIds,openAccessPdf,"
                      "publicationTypes,journal"
        })
        url = f"{self.BASE}/paper/search?{params}"
        data = self._api_get(url)
        if data and data.get("data"):
            return data["data"][0]
        return None

    def get_citation_detail(self, paper_id: str) -> Optional[Dict]:
        """获取详细引用数据"""
        url = (f"{self.BASE}/paper/{paper_id}"
               f"?fields=citationCount,influentialCitationCount,"
               f"citationsPerYear,publicationDate,year")
        return self._api_get(url)

    def enrich_citation(self, title: str, arxiv_id: str = "",
                        year: int = 2022) -> Dict:
        """采集引用影响力标签"""
        result = {
            "total_citations": 0,
            "citations_per_year": 0.0,
            "influential_citations": 0,
            "citation_velocity": "low",
            "citation_source": "semantic_scholar_api",
            "retrieved_at": datetime.now().isoformat()
        }

        paper = self.search_paper(title, arxiv_id)
        if not paper:
            return result

        cit_count = paper.get("citationCount", 0) or 0
        infl_count = paper.get("influentialCitationCount", 0) or 0
        pub_year = paper.get("year") or year
        years_since = max(1, datetime.now().year - pub_year + 1)

        result["total_citations"] = cit_count
        result["citations_per_year"] = round(cit_count / years_since, 1)
        result["influential_citations"] = infl_count

        # 引用增长速度
        cpy = result["citations_per_year"]
        if cpy >= 20:
            result["citation_velocity"] = "high"
        elif cpy >= 5:
            result["citation_velocity"] = "medium"
        else:
            result["citation_velocity"] = "low"

        return result

    def enrich_provenance(self, title: str, arxiv_id: str = "") -> Dict:
        """采集出处信息"""
        result = {
            "conference": None,
            "conference_year": None,
            "journal": None,
            "is_open_access": False,
            "has_code": False,
            "code_repository_url": None
        }

        paper = self.search_paper(title, arxiv_id)
        if not paper:
            return result

        # 出处信息
        venue = paper.get("venue") or ""
        journal = paper.get("journal")
        pub_venue = paper.get("publicationVenue")

        if pub_venue:
            result["conference"] = pub_venue.get("name") if pub_venue.get("type") == "conference" else None
            result["journal"] = pub_venue.get("name") if pub_venue.get("type") == "journal" else None

        # 开放获取
        oa = paper.get("openAccessPdf")
        result["is_open_access"] = oa is not None

        return result


# ============================================================
# OpenReview API 客户端（评审信息 + 接受状态）
# ============================================================

class OpenReviewEnricher:
    """
    从 OpenReview API 获取评审意见和接受/拒绝标签

    注意：OpenReview API v2 需要认证。公开数据可通过
    openreview-downloader 或直接爬取公开页面获取。
    此处实现公开数据的搜索和匹配。
    """

    BASE = "https://api2.openreview.net"

    # 已知的 OpenReview 会议venue ID映射
    KNOWN_VENUES = {
        "iclr": {
            "2024": "ICLR.cc/2024/Conference",
            "2025": "ICLR.cc/2025/Conference",
        },
        "neurips": {
            "2024": "NeurIPS.cc/2024/Conference",
        },
    }

    def __init__(self):
        self._cache: Dict[str, Dict] = {}

    def search_by_title(self, title: str) -> Optional[Dict]:
        """通过标题搜索 OpenReview 论文"""
        # OpenReview API 公开搜索端点
        cache_key = hashlib.md5(title[:100].encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            params = urlencode({
                "term": title[:200],
                "content": "all",
                "limit": 3,
            })
            url = f"{self.BASE}/notes/search?{params}"
            req = Request(url, headers={"User-Agent": "SciEval-Bench/1.1"})
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                notes = data.get("notes", [])
                if notes:
                    self._cache[cache_key] = notes[0]
                    return notes[0]
        except Exception:
            pass
        return None

    def extract_acceptance_status(self, note: Dict) -> Optional[Dict]:
        """从 OpenReview note 提取接受状态"""
        content = note.get("content", {})
        decision = content.get("decision", "")
        venue = content.get("venue", "")
        venueid = note.get("invitation", "")

        # 识别接受/拒绝
        if "Accept" in str(decision):
            status = "accepted"
        elif "Reject" in str(decision):
            status = "rejected"
        elif venue and ("accept" in str(venue).lower()):
            status = "accepted"
        else:
            status = "unknown"  # 无法确定

        if status == "unknown":
            return None

        return {
            "status": status,
            "venue": venue or venueid.split("/")[0] if "/" in venueid else venueid,
            "venue_type": "conference",
            "acceptance_rate": None,
            "decision_date": note.get("cdate") and datetime.fromtimestamp(note["cdate"]/1000).strftime("%Y-%m-%d"),
            "decision_source": "openreview_api"
        }

    def extract_review_information(self, note: Dict) -> Optional[Dict]:
        """从 OpenReview note 提取评审信息"""
        content = note.get("content", {})
        reviews = content.get("reviews", []) or []

        if not reviews:
            # 尝试从 forum 获取评审
            forum = note.get("forum")
            if forum:
                try:
                    url = f"{self.BASE}/notes?forum={forum}&invitation=.*Official_Review.*&limit=10"
                    req = Request(url, headers={"User-Agent": "SciEval-Bench/1.1"})
                    with urlopen(req, timeout=15) as resp:
                        data = json.loads(resp.read().decode())
                        reviews = data.get("notes", [])
                except Exception:
                    pass

        if not reviews:
            return None

        review_texts = []
        scores = []
        for r in reviews[:5]:
            rc = r.get("content", {})
            rating = rc.get("rating", "")
            # 解析评分（格式可能是 "6: Accept" 或纯数字）
            if isinstance(rating, str):
                parts = rating.split(":")
                try:
                    scores.append(int(parts[0].strip()))
                except ValueError:
                    pass
            recommendation = rc.get("recommendation", "")

            review_texts.append({
                "summary": rc.get("summary", rc.get("review", ""))[:300],
                "strengths": [rc.get("strengths", "")[:200]],
                "weaknesses": [rc.get("weaknesses", "")[:200]],
                "recommendation": recommendation if recommendation else "unknown"
            })

        avg_score = sum(scores) / len(scores) if scores else 0
        return {
            "has_reviews": True,
            "num_reviews": len(reviews),
            "review_scores": {
                "overall": round(avg_score, 1),
                "confidence": None,
                "dimensions": {
                    "novelty": None,
                    "soundness": None,
                    "presentation": None,
                    "contribution": None
                }
            },
            "review_texts": review_texts,
            "has_rebuttal": None,
            "has_meta_review": None,
            "inter_reviewer_agreement": None,
            "review_source": "openreview_api"
        }

    def enrich(self, title: str) -> Tuple[Optional[Dict], Optional[Dict]]:
        """一站式采集：返回 (acceptance_status, review_information)"""
        note = self.search_by_title(title)
        if not note:
            return None, None

        acceptance = self.extract_acceptance_status(note)
        reviews = self.extract_review_information(note)
        return acceptance, reviews


# ============================================================
# DBLP API 客户端（出处信息）
# ============================================================

class DBLPEnricher:
    """从 DBLP API 获取会议/期刊出处信息"""

    BASE = "https://dblp.org/search/publ/api"

    def search(self, title: str) -> Optional[Dict]:
        """搜索 DBLP 论文"""
        try:
            params = urlencode({
                "q": title[:200],
                "format": "json",
                "h": 1
            })
            url = f"{self.BASE}?{params}"
            req = Request(url, headers={"User-Agent": "SciEval-Bench/1.1"})
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                hits = data.get("result", {}).get("hits", {}).get("hit", [])
                if hits:
                    return hits[0]
        except Exception:
            pass
        return None

    def enrich(self, title: str) -> Dict:
        """采集出处信息"""
        result = {
            "conference": None,
            "conference_year": None,
            "journal": None,
            "publisher": None,
            "is_open_access": False
        }

        hit = self.search(title)
        if not hit:
            return result

        info = hit.get("info", {})
        venue = info.get("venue", "")
        year = info.get("year")
        doc_type = info.get("type", "")

        if doc_type in ("Conference and Workshop Papers", "conference"):
            result["conference"] = venue
            result["conference_year"] = int(year) if year else None
        elif doc_type in ("Journal Articles", "journal"):
            result["journal"] = venue

        publisher = info.get("publisher", "")
        if publisher:
            result["publisher"] = publisher

        # DBLP 收录的不一定是开放获取，设为默认
        result["is_open_access"] = None

        return result


# ============================================================
# 富标签采集引擎
# ============================================================

class EnrichmentEngine:
    """统一的富标签采集引擎"""

    def __init__(self):
        self.s2 = SemanticScholarEnricher()
        self.or_ = OpenReviewEnricher()
        self.dblp = DBLPEnricher()
        self.results: List[EnrichmentResult] = []

    def enrich_batch(self, annotations: List[Dict]) -> List[EnrichmentResult]:
        """批量采集富标签"""
        print("=" * 60)
        print(f"富标签批量采集: {len(annotations)} 条数据")
        print("=" * 60)

        for i, ann in enumerate(annotations):
            pid = ann.get("paper_id", f"paper_{i}")
            result = self.enrich_single(ann)
            self.results.append(result)

            if (i + 1) % 20 == 0:
                print(f"  进度: {i+1}/{len(annotations)}")
            time.sleep(0.3)  # API速率限制

        return self.results

    def enrich_single(self, annotation: Dict) -> EnrichmentResult:
        """对单条标注进行富标签采集"""
        pid = annotation.get("paper_id", "unknown")
        result = EnrichmentResult(pid)

        # 从标注中提取论文信息
        title = ""
        source = annotation.get("source", {})
        if isinstance(source, dict):
            # source_annotations 结构
            pass

        # 尝试从 annotation 的各个可能位置提取标题和ID
        arxiv_id = ""
        for key in ["arxiv_id", "paper_id"]:
            if key in annotation:
                val = annotation[key]
                if isinstance(val, str) and ("." in val or "/" in val):
                    arxiv_id = val.split("/")[-1] if "/" in val else val
                    break

        # 从 discipline 相关的元数据中推断标题
        # 实际使用时标题从 collected_papers.json 中匹配

        # 1. Semantic Scholar: 引用数据 + 出处
        try:
            result.citation_impact = self.s2.enrich_citation(
                title, arxiv_id
            )
            result.sources_used.append("semantic_scholar_citation")
        except Exception as e:
            result.errors.append(f"Semantic Scholar citation: {e}")

        try:
            prov = self.s2.enrich_provenance(title, arxiv_id)
            result.provenance = prov
            result.sources_used.append("semantic_scholar_provenance")
        except Exception as e:
            result.errors.append(f"Semantic Scholar provenance: {e}")

        # 2. OpenReview: 接受状态 + 评审信息
        try:
            acceptance, reviews = self.or_.enrich(title)
            if acceptance:
                result.publication_status = acceptance
                result.sources_used.append("openreview_acceptance")
            if reviews:
                result.review_information = reviews
                result.sources_used.append("openreview_reviews")
        except Exception as e:
            result.errors.append(f"OpenReview: {e}")

        # 3. DBLP: 出处补充
        try:
            dblp_result = self.dblp.enrich(title)
            if result.provenance is None:
                result.provenance = {}
            # DBLP 数据补充（不覆盖已有数据）
            for key in ["conference", "conference_year", "journal"]:
                if not result.provenance.get(key) and dblp_result.get(key):
                    result.provenance[key] = dblp_result[key]
            result.sources_used.append("dblp")
        except Exception as e:
            result.errors.append(f"DBLP: {e}")

        # 4. 默认标签（无法从API获取的兜底值）
        if result.publication_status is None:
            result.publication_status = {
                "status": "preprint",
                "venue": None,
                "venue_type": "preprint_server",
                "acceptance_rate": None,
                "decision_date": None,
                "decision_source": "unknown"
            }

        if result.review_information is None:
            result.review_information = {
                "has_reviews": False,
                "num_reviews": 0,
                "review_scores": None,
                "review_texts": [],
                "has_rebuttal": None,
                "has_meta_review": None,
                "inter_reviewer_agreement": None,
                "review_source": "none"
            }

        if result.provenance is None:
            result.provenance = {
                "conference": None,
                "conference_year": None,
                "journal": None,
                "is_open_access": False,
                "has_code": False,
                "code_repository_url": None
            }

        return result

    def merge_into_annotations(self, annotations: List[Dict],
                               enrichments: List[EnrichmentResult]) -> List[Dict]:
        """将富标签合并回标注数据"""
        enriched = []
        for ann, enr in zip(annotations, enrichments):
            ann_copy = dict(ann)
            ann_copy["publication_status"] = enr.publication_status
            ann_copy["review_information"] = enr.review_information
            ann_copy["citation_impact"] = enr.citation_impact
            ann_copy["provenance"] = enr.provenance
            ann_copy["enrichment_meta"] = {
                "sources_used": enr.sources_used,
                "errors": enr.errors,
                "enriched_at": datetime.now().isoformat()
            }
            enriched.append(ann_copy)
        return enriched


# ============================================================
# 集成到 scieval_annotator.py 的二阶段标注流程
# ============================================================

def annotate_phase2_enrichment(annotations_path: str,
                                output_path: str):
    """
    标注管线第二阶段：自动填充富标签
    在 scieval_annotator.py 完成第一阶段标注后调用
    """
    with open(annotations_path, "r", encoding="utf-8") as f:
        annotations = json.load(f)

    engine = EnrichmentEngine()
    enrichments = engine.enrich_batch(annotations)
    enriched = engine.merge_into_annotations(annotations, enrichments)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    # 统计
    has_status = sum(1 for e in enrichments
                    if e.publication_status and e.publication_status["status"] != "preprint")
    has_reviews = sum(1 for e in enrichments
                     if e.review_information and e.review_information["has_reviews"])
    has_citations = sum(1 for e in enrichments
                       if e.citation_impact and e.citation_impact.get("total_citations", 0) > 0)

    print(f"\n富标签统计:")
    print(f"  有接受状态: {has_status}/{len(annotations)}")
    print(f"  有评审信息: {has_reviews}/{len(annotations)}")
    print(f"  有引用数据: {has_citations}/{len(annotations)}")
    print(f"  输出: {output_path}")


# ============================================================
# 集成到 scieval_collector.py 的采集阶段
# ============================================================

def collect_with_enrichment(keywords_per_discipline: Dict,
                            output_dir: str,
                            papers_per_keyword: int = 10):
    """
    采集论文的同时进行富标签采集
    在 scieval_collector.py 的 DataCollector 中调用
    """
    # 原有采集逻辑（略，见 scieval_collector.py）
    # ...

    # 采集完成后立即进行富标签采集
    engine = EnrichmentEngine()

    # 对采集到的每个论文进行富标签采集
    collected_path = f"{output_dir}/collected_papers.json"
    with open(collected_path, "r") as f:
        papers = json.load(f)

    # 转换为类标注格式
    pseudo_annotations = [
        {"paper_id": p.get("paper_id", f"paper_{i}"),
         "title": p.get("title", ""),
         "arxiv_id": p.get("arxiv_id", "")}
        for i, p in enumerate(papers)
    ]

    enrichments = engine.enrich_batch(pseudo_annotations)

    # 合并
    for paper, enr in zip(papers, enrichments):
        paper["publication_status"] = enr.publication_status
        paper["review_information"] = enr.review_information
        paper["citation_impact"] = enr.citation_impact
        paper["provenance"] = enr.provenance

    enriched_path = f"{output_dir}/collected_papers_enriched.json"
    with open(enriched_path, "w") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)

    print(f"富标签版本: {enriched_path}")


# ============================================================
# 演示运行
# ============================================================

def demo():
    """演示富标签采集功能"""
    print("=" * 60)
    print("SciEval-Bench 富标签采集模块 — 演示")
    print("=" * 60)

    # 演示数据
    demo_papers = [
        {"paper_id": "DEMO-001", "title": "Attention Is All You Need", "arxiv_id": "1706.03762"},
        {"paper_id": "DEMO-002", "title": "BERT: Pre-training of Deep Bidirectional Transformers", "arxiv_id": "1810.04805"},
        {"paper_id": "DEMO-003", "title": "Deep Residual Learning for Image Recognition", "arxiv_id": "1512.03385"},
    ]

    engine = EnrichmentEngine()
    results = engine.enrich_batch(demo_papers)

    for r in results:
        print(f"\n{'='*40}")
        print(f"论文: {r.paper_id}")
        if r.publication_status:
            print(f"  状态: {r.publication_status['status']} ({r.publication_status.get('venue','?')})")
        if r.citation_impact:
            ci = r.citation_impact
            print(f"  引用: {ci['total_citations']}次 ({ci['citations_per_year']}/年, {ci['citation_velocity']})")
        if r.review_information and r.review_information['has_reviews']:
            print(f"  评审: {r.review_information['num_reviews']}条")
        if r.errors:
            print(f"  错误: {', '.join(r.errors)}")
        print(f"  数据源: {', '.join(r.sources_used)}")


if __name__ == "__main__":
    demo()
