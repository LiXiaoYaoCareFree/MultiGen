#!/usr/bin/env python3
"""
SciEval-Bench 自动化数据收集脚本
===================================
多渠道批量采集论文元数据，覆盖全部六大学科大类：
- 形式科学 (计算机科学、数学)
- 自然科学 (物理、化学、地球科学)
- 工程与技术科学 (电子工程、材料科学、机械工程)
- 医学与生命科学 (生物学、临床医学)
- 社会科学 (经济学、心理学、社会学)
- 人文学科 (哲学、历史学、语言学)

数据源: arXiv API, Semantic Scholar API
输出格式: 符合 dataset_final_spec.md 定义的 JSON Schema
"""
import json
import os
import sys
import time
import hashlib
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from dataclasses import dataclass, asdict, field

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "scieval_collected")


# ============================================================
# 学科定义：六大学科大类 → 子学科 → 领域关键词
# ============================================================

DISCIPLINE_KEYWORDS = {
    "formal_sciences": {
        "name_zh": "形式科学",
        "sub_disciplines": {
            "computer_science": {
                "name_zh": "计算机科学",
                "arxiv_cat": "cs.AI",  # 主分类
                "research_areas": {
                    "artificial_intelligence": {
                        "name_zh": "人工智能",
                        "keywords": [
                            "deep reinforcement learning", "graph neural network",
                            "diffusion models generative", "large language model reasoning",
                            "multi-agent reinforcement learning", "neural architecture search",
                            "contrastive learning representation", "transformers attention mechanism"
                        ]
                    },
                    "natural_language_processing": {
                        "name_zh": "自然语言处理",
                        "arxiv_cat": "cs.CL",
                        "keywords": [
                            "machine translation neural", "text summarization abstractive",
                            "question answering systems", "language model pretraining",
                            "sentiment analysis deep learning", "named entity recognition",
                            "dialogue systems conversational", "cross-lingual transfer learning"
                        ]
                    },
                    "computer_vision": {
                        "name_zh": "计算机视觉",
                        "arxiv_cat": "cs.CV",
                        "keywords": [
                            "object detection transformer", "image segmentation deep learning",
                            "video understanding temporal", "3D reconstruction neural",
                            "self-supervised visual learning", "image generation diffusion",
                            "visual question answering", "pose estimation human"
                        ]
                    }
                }
            },
            "mathematics": {
                "name_zh": "数学",
                "arxiv_cat": "math.OC",
                "research_areas": {
                    "optimization_theory": {
                        "name_zh": "优化理论",
                        "keywords": [
                            "stochastic gradient descent convergence",
                            "convex optimization theory", "non-convex optimization landscape",
                            "adaptive optimization methods", "minimax optimization",
                            "bilevel optimization", "Riemannian optimization"
                        ]
                    }
                }
            }
        }
    },

    "natural_sciences": {
        "name_zh": "自然科学",
        "sub_disciplines": {
            "physics": {
                "name_zh": "物理学",
                "arxiv_cat": "quant-ph",
                "research_areas": {
                    "quantum_computing": {
                        "name_zh": "量子计算",
                        "keywords": [
                            "quantum error correction", "quantum algorithm variational",
                            "superconducting qubit", "quantum machine learning",
                            "topological quantum computation", "quantum circuit optimization",
                            "quantum annealing", "quantum supremacy demonstration"
                        ]
                    },
                    "condensed_matter": {
                        "name_zh": "凝聚态物理",
                        "keywords": [
                            "topological insulator", "strongly correlated electron",
                            "two-dimensional materials", "superconductivity mechanism",
                            "quantum phase transition", "spin liquid",
                            "Moiré superlattice", "twisted bilayer graphene"
                        ]
                    }
                }
            },
            "chemistry": {
                "name_zh": "化学",
                "arxiv_cat": "physics.chem-ph",
                "research_areas": {
                    "organic_synthesis": {
                        "name_zh": "有机合成",
                        "keywords": [
                            "retrosynthetic planning", "catalytic asymmetric synthesis",
                            "photoredox catalysis", "C-H activation functionalization",
                            "flow chemistry synthesis", "organocatalysis",
                            "total synthesis natural product", "cross-coupling reaction"
                        ]
                    },
                    "computational_chemistry": {
                        "name_zh": "计算化学",
                        "keywords": [
                            "density functional theory", "molecular dynamics simulation",
                            "machine learning potential energy", "quantum chemistry computation",
                            "drug discovery docking", "materials design computational",
                            "reaction mechanism calculation", "force field development"
                        ]
                    }
                }
            },
            "earth_science": {
                "name_zh": "地球科学",
                "arxiv_cat": "physics.ao-ph",
                "research_areas": {
                    "climate_science": {
                        "name_zh": "气候科学",
                        "keywords": [
                            "climate model projection", "extreme weather attribution",
                            "carbon cycle feedback", "climate change mitigation",
                            "paleoclimate reconstruction", "ocean circulation modeling",
                            "cryosphere dynamics", "atmospheric chemistry aerosol"
                        ]
                    }
                }
            }
        }
    },

    "engineering": {
        "name_zh": "工程与技术科学",
        "sub_disciplines": {
            "materials_science": {
                "name_zh": "材料科学",
                "arxiv_cat": "cond-mat.mtrl-sci",
                "research_areas": {
                    "novel_materials": {
                        "name_zh": "新型材料",
                        "keywords": [
                            "perovskite solar cell", "battery materials lithium",
                            "2D materials heterostructure", "metamaterials electromagnetic",
                            "high-entropy alloys", "biomaterials scaffold",
                            "thermoelectric materials", "metal-organic framework catalysis"
                        ]
                    }
                }
            },
            "electrical_engineering": {
                "name_zh": "电子工程",
                "arxiv_cat": "eess.SP",
                "research_areas": {
                    "signal_processing": {
                        "name_zh": "信号处理",
                        "keywords": [
                            "compressed sensing recovery", "adaptive filtering algorithm",
                            "MIMO communication systems", "radar signal processing",
                            "image reconstruction inverse problem", "wireless communication 6G",
                            "channel estimation deep learning", "beamforming optimization"
                        ]
                    }
                }
            },
            "mechanical_engineering": {
                "name_zh": "机械工程",
                "keywords": [
                    "robotics manipulation control", "additive manufacturing process",
                    "finite element analysis optimization", "fluid dynamics turbulence modeling",
                    "vibration control active", "thermal management system",
                    "compliant mechanism design", "energy harvesting vibration"
                ]
            }
        }
    },

    "medical_life_sciences": {
        "name_zh": "医学与生命科学",
        "sub_disciplines": {
            "biology": {
                "name_zh": "生物学",
                "arxiv_cat": "q-bio.GN",
                "research_areas": {
                    "gene_editing": {
                        "name_zh": "基因编辑",
                        "keywords": [
                            "CRISPR genome editing", "base editing precision",
                            "prime editing technology", "gene therapy delivery",
                            "epigenetic editing tools", "RNA editing ADAR",
                            "CRISPR screen functional genomics", "gene regulation network"
                        ]
                    },
                    "protein_engineering": {
                        "name_zh": "蛋白质工程",
                        "keywords": [
                            "protein structure prediction", "enzyme design computational",
                            "directed evolution protein", "AlphaFold protein folding",
                            "antibody engineering therapeutic", "protein language model",
                            "de novo protein design", "protein-protein interaction"
                        ]
                    }
                }
            }
        }
    },

    "social_sciences": {
        "name_zh": "社会科学",
        "sub_disciplines": {
            "economics": {
                "name_zh": "经济学",
                "arxiv_cat": "econ.GN",
                "research_areas": {
                    "causal_inference": {
                        "name_zh": "因果推断",
                        "keywords": [
                            "difference-in-differences estimation", "instrumental variable method",
                            "regression discontinuity design", "synthetic control method",
                            "causal machine learning", "treatment effect heterogeneity",
                            "mediation analysis causal", "policy evaluation causal"
                        ]
                    },
                    "econometrics": {
                        "name_zh": "计量经济学",
                        "keywords": [
                            "panel data model", "time series forecasting",
                            "high-dimensional statistics", "Bayesian econometrics",
                            "structural equation modeling", "nonparametric regression",
                            "spatial econometrics", "financial econometrics volatility"
                        ]
                    }
                }
            },
            "psychology": {
                "name_zh": "心理学",
                "keywords": [
                    "cognitive bias decision making", "social cognition theory",
                    "working memory neural", "emotion regulation strategies",
                    "developmental psychology adolescent", "attention mechanisms cognitive",
                    "behavioral intervention mental health", "personality traits assessment"
                ]
            },
            "sociology": {
                "name_zh": "社会学",
                "keywords": [
                    "social network analysis", "inequality social mobility",
                    "urban sociology migration", "organizational behavior theory",
                    "social movement collective action", "digital sociology platform",
                    "cultural sociology identity", "political polarization society"
                ]
            }
        }
    },

    "humanities": {
        "name_zh": "人文学科",
        "sub_disciplines": {
            "philosophy": {
                "name_zh": "哲学",
                "keywords": [
                    "epistemology knowledge justification", "ethics artificial intelligence",
                    "philosophy of mind consciousness", "political philosophy justice",
                    "metaphysics ontology causation", "philosophy of science methodology",
                    "logic formal reasoning", "aesthetics theory art"
                ]
            },
            "linguistics": {
                "name_zh": "语言学",
                "arxiv_cat": "cs.CL",
                "research_areas": {
                    "theoretical_linguistics": {
                        "name_zh": "理论语言学",
                        "keywords": [
                            "syntax universal grammar", "semantics formal theory",
                            "phonology optimality theory", "morphology computational",
                            "pragmatics discourse analysis", "historical linguistics change",
                            "typology language universals", "sociolinguistics variation"
                        ]
                    }
                }
            },
            "history": {
                "name_zh": "历史学",
                "keywords": [
                    "digital humanities text analysis", "economic history industrialization",
                    "intellectual history modern", "social history revolution",
                    "environmental history anthropocene", "global history comparative",
                    "history of science technology", "historiography methodology"
                ]
            }
        }
    }
}


# ============================================================
# 数据模型
# ============================================================

@dataclass
class PaperMetadata:
    """论文元数据"""
    paper_id: str
    title: str
    authors: List[str]
    abstract: str
    arxiv_id: str
    doi: Optional[str]
    publication_date: str
    source: str               # "arxiv" | "semantic_scholar"
    categories: List[str]     # arXiv分类标签
    citation_count: Optional[int]
    license_type: Optional[str]
    is_open_access: bool
    discipline_path: List[str]  # 四层级学科路径
    research_type: str         # 初步标注的研究类型

    def to_dict(self) -> Dict:
        return asdict(self)


# ============================================================
# arXiv API 客户端
# ============================================================

class ArxivClient:
    """arXiv API 客户端，支持搜索和元数据解析"""

    BASE_URL = "https://export.arxiv.org/api/query"
    MIN_REQUEST_INTERVAL = 3.5
    RETRY_DELAYS = (5, 15, 30)

    def __init__(self):
        self._last_request_time = 0.0

    def _respect_rate_limit(self):
        """确保相邻 arXiv 请求之间有足够间隔，降低 429 概率。"""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)

    def search(self, query: str, max_results: int = 20,
               start: int = 0) -> List[PaperMetadata]:
        """搜索arXiv论文"""
        params = {
            "search_query": f"all:{query}",
            "start": start,
            "max_results": min(max_results, 100),
            "sortBy": "relevance",
            "sortOrder": "descending"
        }
        url = f"{self.BASE_URL}?{urlencode(params)}"

        papers = []
        for attempt, retry_delay in enumerate((0, *self.RETRY_DELAYS), start=1):
            if retry_delay:
                print(f"  [INFO] arXiv retry in {retry_delay}s")
                time.sleep(retry_delay)

            self._respect_rate_limit()
            try:
                req = Request(url, headers={"User-Agent": "SciEval-Bench/1.0"})
                with urlopen(req, timeout=30) as response:
                    xml_data = response.read().decode("utf-8")
                self._last_request_time = time.monotonic()
                papers = self._parse_response(xml_data)
                break
            except HTTPError as e:
                self._last_request_time = time.monotonic()
                if e.code == 429 and attempt <= len(self.RETRY_DELAYS):
                    print(f"  [WARN] arXiv rate limited for '{query[:50]}...': HTTP {e.code}")
                    continue
                print(f"  [WARN] arXiv API error for query '{query[:50]}...': HTTP {e.code}")
                break
            except URLError as e:
                self._last_request_time = time.monotonic()
                print(f"  [WARN] arXiv network error for query '{query[:50]}...': {e}")
                break
            except Exception as e:
                self._last_request_time = time.monotonic()
                print(f"  [WARN] arXiv API error for query '{query[:50]}...': {e}")
                break

        return papers

    def _parse_response(self, xml_data: str) -> List[PaperMetadata]:
        """解析arXiv API XML响应"""
        namespace = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom"
        }

        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError:
            return []

        papers = []
        for entry in root.findall("atom:entry", namespace):
            try:
                title = self._clean_text(
                    entry.find("atom:title", namespace).text or ""
                )
                abstract = self._clean_text(
                    entry.find("atom:summary", namespace).text or ""
                )

                authors = [
                    self._clean_text(author.find("atom:name", namespace).text or "")
                    for author in entry.findall("atom:author", namespace)
                ]

                arxiv_id = self._extract_arxiv_id(
                    entry.find("atom:id", namespace).text or ""
                )

                published = entry.find("atom:published", namespace).text or ""
                published = published[:10] if published else ""

                categories = [
                    cat.get("term", "")
                    for cat in entry.findall("atom:category", namespace)
                ]

                doi = None
                for link in entry.findall("atom:link", namespace):
                    href = link.get("href", "")
                    if "doi.org" in href:
                        doi = href.split("doi.org/")[-1]

                papers.append(PaperMetadata(
                    paper_id=f"ARXIV-{arxiv_id}",
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    arxiv_id=arxiv_id,
                    doi=doi,
                    publication_date=published,
                    source="arxiv",
                    categories=categories,
                    citation_count=None,
                    license_type=None,
                    is_open_access=True,
                    discipline_path=[],
                    research_type="unknown"
                ))
            except Exception as e:
                continue

        return papers

    @staticmethod
    def _clean_text(text: str) -> str:
        """清理文本中的换行和多余空格"""
        return " ".join(text.replace("\n", " ").split())

    @staticmethod
    def _extract_arxiv_id(id_url: str) -> str:
        """从arXiv ID URL中提取纯ID"""
        parts = id_url.split("/abs/")
        if len(parts) > 1:
            return parts[-1]
        return id_url


# ============================================================
# Semantic Scholar API 客户端
# ============================================================

class SemanticScholarClient:
    """Semantic Scholar API 客户端"""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    MIN_REQUEST_INTERVAL = 1.5
    RETRY_DELAYS = (3, 10, 20)

    def __init__(self):
        self.api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
        # 无 Key 时更保守，降低共享匿名池触发 429 的概率
        self.min_request_interval = 1.0 if self.api_key else 3.0
        self._last_request_time = 0.0

    def _respect_rate_limit(self):
        """控制无 API Key 情况下的调用频率，降低 429 概率。"""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)

    def _build_headers(self) -> Dict[str, str]:
        headers = {"User-Agent": "SciEval-Bench/1.0"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def search(self, query: str, limit: int = 20,
               fields: List[str] = None) -> List[Dict]:
        """搜索论文"""
        if fields is None:
            fields = ["title", "abstract", "authors", "externalIds",
                      "publicationDate", "citationCount", "openAccessPdf",
                      "journal", "publicationTypes"]

        params = {
            "query": query,
            "limit": min(limit, 100),
            "fields": ",".join(fields)
        }
        url = f"{self.BASE_URL}/paper/search?{urlencode(params)}"

        results = []
        for attempt, retry_delay in enumerate((0, *self.RETRY_DELAYS), start=1):
            if retry_delay:
                print(f"  [INFO] Semantic Scholar retry in {retry_delay}s")
                time.sleep(retry_delay)

            self._respect_rate_limit()
            try:
                req = Request(url, headers=self._build_headers())
                with urlopen(req, timeout=30) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    results = data.get("data", [])
                self._last_request_time = time.monotonic()
                break
            except HTTPError as e:
                self._last_request_time = time.monotonic()
                if e.code == 429 and attempt <= len(self.RETRY_DELAYS):
                    print(f"  [WARN] Semantic Scholar rate limited for '{query[:50]}...': HTTP {e.code}")
                    continue
                print(f"  [WARN] Semantic Scholar API error for '{query[:50]}...': HTTP {e.code}")
                break
            except URLError as e:
                self._last_request_time = time.monotonic()
                print(f"  [WARN] Semantic Scholar network error for '{query[:50]}...': {e}")
                break
            except Exception as e:
                self._last_request_time = time.monotonic()
                print(f"  [WARN] Semantic Scholar API error for '{query[:50]}...': {e}")
                break

        return results

    def get_paper_details(self, paper_id: str,
                          fields: List[str] = None) -> Optional[Dict]:
        """获取单篇论文的详细信息"""
        if fields is None:
            fields = ["title", "abstract", "authors", "externalIds",
                      "publicationDate", "citationCount", "references",
                      "citations", "tldr"]

        url = f"{self.BASE_URL}/paper/{paper_id}?fields={','.join(fields)}"
        try:
            req = Request(url, headers=self._build_headers())
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            return None

    def search_and_convert(self, query: str, limit: int = 20) -> List[PaperMetadata]:
        """搜索并转换为PaperMetadata格式"""
        raw_results = self.search(query, limit)
        papers = []
        for item in raw_results:
            try:
                ext_ids = item.get("externalIds", {}) or {}
                authors = [a.get("name", "") for a in (item.get("authors") or [])]

                papers.append(PaperMetadata(
                    paper_id=f"SS-{item.get('paperId', 'unknown')}",
                    title=item.get("title", ""),
                    authors=authors,
                    abstract=item.get("abstract", "") or "",
                    arxiv_id=ext_ids.get("ArXiv", ""),
                    doi=ext_ids.get("DOI"),
                    publication_date=item.get("publicationDate", "") or "",
                    source="semantic_scholar",
                    categories=[],
                    citation_count=item.get("citationCount"),
                    license_type="unknown",
                    is_open_access=bool(item.get("openAccessPdf")),
                    discipline_path=[],
                    research_type="unknown"
                ))
            except Exception:
                continue
        return papers


# ============================================================
# 主采集引擎
# ============================================================

class DataCollector:
    """多渠道论文数据采集引擎"""

    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR):
        self.arxiv = ArxivClient()
        self.semantic = SemanticScholarClient()
        self.output_dir = os.path.abspath(os.path.expanduser(output_dir))
        self.collected: Dict[str, PaperMetadata] = {}
        self.stats = {
            "total_queries": 0,
            "total_papers": 0,
            "by_discipline": {},
            "by_source": {"arxiv": 0, "semantic_scholar": 0},
            "errors": 0
        }
        os.makedirs(self.output_dir, exist_ok=True)

    def collect_all(self, papers_per_keyword: int = 10):
        """对全部六大学科进行批量采集"""
        print("=" * 70)
        print("SciEval-Bench 自动化数据采集")
        print(f"开始时间: {datetime.now().isoformat()}")
        print("=" * 70)

        for disc_key, disc_info in DISCIPLINE_KEYWORDS.items():
            disc_name = disc_info["name_zh"]
            print(f"\n{'='*50}")
            print(f"[采集] {disc_name} ({disc_key})")
            print(f"{'='*50}")

            self.stats["by_discipline"][disc_key] = 0

            for sub_key, sub_info in disc_info["sub_disciplines"].items():
                sub_name = sub_info["name_zh"]
                research_areas = sub_info.get("research_areas", {})

                if research_areas:
                    for area_key, area_info in research_areas.items():
                        area_name = area_info["name_zh"]
                        keywords = area_info.get("keywords", [])
                        self._collect_area(
                            disc_key, disc_name, sub_key, sub_name,
                            area_key, area_name, keywords, papers_per_keyword
                        )
                else:
                    # 子学科直接有关键词，无研究方向层级
                    keywords = sub_info.get("keywords", [])
                    if keywords:
                        self._collect_area(
                            disc_key, disc_name, sub_key, sub_name,
                            "general", sub_name, keywords, papers_per_keyword
                        )

        self._save_results()
        self._print_stats()

    def _collect_area(self, disc_key, disc_name, sub_key, sub_name,
                      area_key, area_name, keywords, papers_per_kw):
        """采集某个研究领域的论文"""
        print(f"\n  [{sub_name} → {area_name}]")

        disc_path = [disc_name, sub_name, area_name] if area_key != "general" else [disc_name, sub_name]

        for kw in keywords:
            self.stats["total_queries"] += 1
            print(f"    查询: \"{kw[:60]}...\"", end=" ")

            try:
                # arXiv 搜索
                arxiv_papers = self.arxiv.search(kw, max_results=papers_per_kw)
                for p in arxiv_papers:
                    p.discipline_path = disc_path
                    p.research_type = "unknown"
                    key = p.arxiv_id or p.paper_id
                    if key and key not in self.collected:
                        self.collected[key] = p
                        self.stats["total_papers"] += 1
                        self.stats["by_source"]["arxiv"] += 1
                        self.stats["by_discipline"][disc_key] += 1

                print(f"arXiv:{len(arxiv_papers)}", end=" ")

                # Semantic Scholar 补充搜索
                ss_papers = self.semantic.search_and_convert(kw, limit=max(5, papers_per_kw // 2))
                for p in ss_papers:
                    p.discipline_path = disc_path
                    key = p.arxiv_id or p.paper_id
                    if key and key not in self.collected:
                        self.collected[key] = p
                        self.stats["total_papers"] += 1
                        self.stats["by_source"]["semantic_scholar"] += 1
                        self.stats["by_discipline"][disc_key] += 1

                print(f"SS:{len(ss_papers)}", end=" ")

                # 速率限制
                print("✓")
                time.sleep(1.0)

            except Exception as e:
                self.stats["errors"] += 1
                print(f"✗ ({e})")

            if self.stats["total_queries"] % 10 == 0:
                self._save_results()
                print(f"    [已保存中间结果...当前累计{self.stats['total_papers']}篇]")

            # 每10次查询休息更长时间
            if self.stats["total_queries"] % 10 == 0:
                print(f"    [速率限制暂停10秒...已采集{self.stats['total_papers']}篇]")
                time.sleep(10)

    def _save_results(self):
        """保存采集结果"""
        # 完整数据集
        all_papers = [
            p.to_dict() for p in self.collected.values()
        ]

        all_path = os.path.join(self.output_dir, "collected_papers.json")
        with open(all_path, "w", encoding="utf-8") as f:
            json.dump(all_papers, f, ensure_ascii=False, indent=2)
        print(f"\n完整数据: {all_path} ({len(all_papers)}篇)")

        # 按学科分组保存
        for disc_key in DISCIPLINE_KEYWORDS:
            disc_name = DISCIPLINE_KEYWORDS[disc_key]["name_zh"]
            disc_papers = [
                p.to_dict() for p in self.collected.values()
                if p.discipline_path and p.discipline_path[0] == disc_name
            ]
            if disc_papers:
                disc_path = os.path.join(self.output_dir, f"{disc_key}.json")
                with open(disc_path, "w", encoding="utf-8") as f:
                    json.dump(disc_papers, f, ensure_ascii=False, indent=2)
                print(f"  {disc_name}: {disc_path} ({len(disc_papers)}篇)")

        # 统计报告
        stats_path = os.path.join(self.output_dir, "collection_stats.json")
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)
        print(f"统计报告: {stats_path}")

    def _print_stats(self):
        """打印采集统计"""
        print("\n" + "=" * 70)
        print("采集统计")
        print("=" * 70)
        print(f"  总查询次数: {self.stats['total_queries']}")
        print(f"  总采集论文: {self.stats['total_papers']}")
        print(f"  数据源: arXiv={self.stats['by_source']['arxiv']}, "
              f"Semantic Scholar={self.stats['by_source']['semantic_scholar']}")
        print(f"  错误次数: {self.stats['errors']}")
        print("\n  学科分布:")
        for disc_key, count in self.stats["by_discipline"].items():
            disc_name = DISCIPLINE_KEYWORDS[disc_key]["name_zh"]
            print(f"    {disc_name}: {count}篇")


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="SciEval-Bench 自动化论文数据采集工具"
    )
    parser.add_argument(
        "--papers-per-keyword", type=int, default=10,
        help="每个关键词采集的论文数 (默认: 10)"
    )
    parser.add_argument(
        "--output-dir", type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f"输出目录 (默认: {DEFAULT_OUTPUT_DIR})"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅打印将要查询的关键词，不实际采集"
    )
    args = parser.parse_args()

    if args.dry_run:
        print("=== 关键词预览 ===\n")
        total = 0
        for disc_key, disc_info in DISCIPLINE_KEYWORDS.items():
            print(f"{disc_info['name_zh']}:")
            for sub_key, sub_info in disc_info["sub_disciplines"].items():
                areas = sub_info.get("research_areas", {})
                if areas:
                    for area_key, area_info in areas.items():
                        kws = area_info.get("keywords", [])
                        print(f"  {sub_info['name_zh']} → {area_info['name_zh']}: {len(kws)}个关键词")
                        total += len(kws)
                else:
                    kws = sub_info.get("keywords", [])
                    print(f"  {sub_info['name_zh']}: {len(kws)}个关键词")
                    total += len(kws)
        print(f"\n总计: {total}个关键词, 预计采集{total * args.papers_per_keyword}篇论文")
        return

    collector = DataCollector(output_dir=args.output_dir)
    collector.collect_all(papers_per_keyword=args.papers_per_keyword)

    print(f"\n数据保存至: {args.output_dir}")
    print(f"完成时间: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
