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
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# ============================================================
# 数据模型
# ============================================================

@dataclass
class DisciplineAnnotation:
    """�