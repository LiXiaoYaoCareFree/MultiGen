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
from urllib.parse import urlencode, quote
from dataclasses import dataclass, asdict, field


# ============================================================
# 学科定义：六大学科大类 