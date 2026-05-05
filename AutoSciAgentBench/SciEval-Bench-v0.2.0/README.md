# SciEval-Bench v0.2.0

## 概述

SciEval-Bench 是一个统一AI自动科研评估数据集，旨在为各类AI科研论文生成工具提供标准化、可横向对比的评估基准。

### 核心用途
- **统一评估**：所有AI工具在相同任务、相同输入、相同标准下接受评估
- **横向对比**：在同一数据集上直接比较多种AI科研工具的能力差异
- **人机比较**：将AI生成论文与人类论文进行匿名化配对评审

### 数据规模（v0.2.0）
- 学科大类：6个（形式科学、自然科学、工程与技术科学、医学与生命科学、社会科学、人文学科）
- 子学科：12+
- 任务实例：20条（原型验证）
- Code-Aware实例：2条
- 编造检测清单：2份

### 目录结构
```
SciEval-Bench-v0.2.0/
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
python3 -c "import json; d=json.load(open('data/annotations.json')); print(f'{len(d)}条标注数据')"

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
@misc{scieval-bench-0.2.0,
  title={SciEval-Bench: A Unified Evaluation Benchmark for AI Scientific Research},
  version={v0.2.0},
  year={2026},
  url={https://github.com/scieval-bench}
}
```

### 许可证
- 数据标注和文档：CC BY 4.0
- 工具代码：MIT

---
发布日期：2026-05-04
