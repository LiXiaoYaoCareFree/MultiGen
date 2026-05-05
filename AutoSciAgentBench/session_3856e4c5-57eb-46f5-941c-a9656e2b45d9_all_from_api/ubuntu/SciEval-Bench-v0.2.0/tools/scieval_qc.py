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
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional


# ============================================================
# LLM训练数据截止日期参考表
# ============================================================

LLM_CUTOF