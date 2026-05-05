# SciEval-Bench v0.3.0

## 概述
SciEval-Bench 是一个统一AI自动科研评估数据集。v0.3.0 为富标签升级版。

## v0.3.0 新增功能
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
