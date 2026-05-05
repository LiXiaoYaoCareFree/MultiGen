# SciEval-Bench 构建步骤详解

本文档按时间顺序详细描述从原始论文采集到最终发布打包的每一个操作步骤、使用的工具与命令、预期的输入输出、以及每个步骤的注意事项。全部操作在 Linux 环境下完成，Python 版本 ≥ 3.10。

---

## 步骤一：原始论文采集（第1-2周）

### 1.1 预览关键词覆盖

**目的：** 确认167个领域关键词完整覆盖六大学科所有子学科，在消耗API配额前验证学科覆盖无误。

**工具：** `scieval_collector.py`

**命令：**
```bash
python3 scieval_collector.py --dry-run
```

**预期输出：**
```
形式科学:
  计算机科学 → 人工智能: 8个关键词
  计算机科学 → 自然语言处理: 8个关键词
  ...
  数学 → 优化理论: 7个关键词
...
人文学科:
  哲学: 8个关键词
  语言学 → 理论语言学: 8个关键词
  历史学: 8个关键词

总计: 167个关键词, 预计采集1670篇论文
```

**检查清单：**
- 六大学科大类全部出现（形式科学、自然科学、工程与技术科学、医学与生命科学、社会科学、人文学科）
- 人文学科包含哲学、语言学、历史学三个子学科
- 工程学科包含材料科学、电子工程、机械工程
- 关键词总数167个，每个子学科至少5个关键词

**注意事项：** 如果关键词覆盖不完整，编辑脚本中的`DISCIPLINE_KEYWORDS`字典，在对应学科的`keywords`列表中添加关键词后重新运行`--dry-run`。

### 1.2 小批量测试采集

**目的：** 验证arXiv和Semantic Scholar API连通性，确认速率限制策略有效，检查返回数据的格式和字段完整性。

**工具：** `scieval_collector.py`

**命令：**
```bash
python3 scieval_collector.py \
    --papers-per-keyword 2 \
    --output-dir /home/ubuntu/data/collected/test_run
```

**参数说明：**
- `--papers-per-keyword 2`：每个关键词仅采集2篇论文，总计约330篇（用于快速验证）
- `--output-dir`：输出目录，测试数据保存在独立目录中

**预期输出文件：**
```
data/collected/test_run/
├── collected_papers.json       # 全部采集论文
├── collection_stats.json       # 采集统计
├── formal_sciences.json        # 形式科学论文
├── natural_sciences.json       # 自然科学论文
├── engineering.json            # 工程论文
├── medical_life_sciences.json  # 医学论文
├── social_sciences.json        # 社会科学论文
└── humanities.json             # 人文学科论文
```

**检查：**
```bash
# 查看采集统计
python3 -c "
import json
with open('data/collected/test_run/collection_stats.json') as f:
    s = json.load(f)
print(f'总查询: {s[\"total_queries\"]}')
print(f'总论文: {s[\"total_papers\"]}')
print(f'错误: {s[\"errors\"]}')
print('学科分布:')
for k,v in s['by_discipline'].items():
    print(f'  {k}: {v}')
"
```

**注意事项：**
- 沙箱环境可能频繁触发HTTP 429限速，表现为`[WARN] arXiv API error...HTTP Error 429`。如果错误率超过50%，修改脚本中`time.sleep(0.5)`为`time.sleep(3.0)`增大间隔。
- 如果某学科采集量为0，检查该学科的关键词是否过于专业（arXiv可能无匹配结果），替换为更通用的关键词。

### 1.3 正式批量采集

**目的：** 执行完整的167个关键词采集，每关键词10篇论文，目标约1670篇原始元数据。

**工具：** `scieval_collector.py`

**命令：**
```bash
# 创建正式采集输出目录
mkdir -p data/collected/batch_01

# 执行正式采集（耗时30-60分钟）
python3 scieval_collector.py \
    --papers-per-keyword 10 \
    --output-dir data/collected/batch_01
```

**执行中检查：** 观察终端输出，确认每行显示`arXiv:N SS:M ✓`（N和M为非零值）。如果连续多条显示`arXiv:0 SS:0 ✗`，立即`Ctrl+C`终止，检查网络和API状态。

**完成后检查：**
```bash
python3 -c "
import json
with open('data/collected/batch_01/collection_stats.json') as f:
    s = json.load(f)
total = s['total_papers']
print(f'总采集: {total}篇')
print(f'来源: arXiv={s[\"by_source\"][\"arxiv\"]}, Semantic Scholar={s[\"by_source\"][\"semantic_scholar\"]}')
# 每学科至少100条（为筛选留余量）
for k,v in s['by_discipline'].items():
    status = '✓' if v >= 100 else '✗ 不足'
    print(f'  {k}: {v}篇 {status}')
"
```

**注意事项：**
- 采集总量目标2000-3000条（167关键词×10篇≈1670为基础，加上Semantic Scholar补充约2000+）
- 任一学科不足100条时需要补充采集（见步骤1.4）
- 如果中断后需要继续，可修改脚本只遍历未完成的学科

### 1.4 补充采集（按需）

**目的：** 对采集不足的学科进行定向补充。

**命令（示例）：**
```bash
# 仅补充人文学科——手动构造更多关键词后重新运行
# 编辑脚本中humanities的keywords，追加5-10个新关键词
python3 scieval_collector.py \
    --papers-per-keyword 10 \
    --output-dir data/collected/batch_02_humanities
```

---

## 步骤二：论文筛选与预处理（第2-3周）

### 2.1 去重

**目的：** 移除同一篇论文在多个关键词下的重复条目（基于arXiv ID）。

**工具：** Python脚本（内联执行）

**命令：**
```bash
python3 -c "
import json

with open('data/collected/batch_01/collected_papers.json') as f:
    papers = json.load(f)

print(f'去重前: {len(papers)}篇')

seen = set()
unique = []
duplicates = 0
for p in papers:
    key = p.get('arxiv_id') or p.get('paper_id', '')
    if key and key not in seen:
        seen.add(key)
        unique.append(p)
    else:
        duplicates += 1

with open('data/collected/deduplicated.json', 'w') as f:
    json.dump(unique, f, ensure_ascii=False, indent=2)

print(f'去重后: {len(unique)}篇 (移除{duplicates}条重复)')
"
```

**预期结果：** 重复率5-15%。重复率超过20%说明多个学科的关键词重叠度过高，需调整关键词。

### 2.2 全文可获取性过滤

**目的：** 筛选有arXiv ID的论文（这些论文可以通过arXiv API下载LaTeX源码，确保后续标注时可以获取全文）。

**命令：**
```bash
python3 -c "
import json

with open('data/collected/deduplicated.json') as f:
    papers = json.load(f)

with_arxiv = [p for p in papers if p.get('arxiv_id')]
no_arxiv = [p for p in papers if not p.get('arxiv_id')]

print(f'有arXiv ID（可获取全文）: {len(with_arxiv)}篇')
print(f'无arXiv ID: {len(no_arxiv)}篇')

with open('data/collected/filtered_fulltext.json', 'w') as f:
    json.dump(with_arxiv, f, ensure_ascii=False, indent=2)
"
```

**预期结果：** 85-95%的论文有arXiv ID。如果低于70%，检查Semantic Scholar来源的论文比例是否过高。

### 2.3 时间窗口过滤

**目的：** 保留2022年及以后发表的论文（对于论文产出较少的子学科可放宽至2020年）。

**命令：**
```bash
python3 -c "
import json

with open('data/collected/filtered_fulltext.json') as f:
    papers = json.load(f)

recent = []
older = []
for p in papers:
    pub = p.get('publication_date', '')
    year = int(pub[:4]) if pub and len(pub) >= 4 else 0
    if year >= 2022:
        recent.append(p)
    else:
        older.append(p)

print(f'2022年及以后: {len(recent)}篇')
print(f'2022年以前: {len(older)}篇')

with open('data/collected/filtered_recent.json', 'w') as f:
    json.dump(recent, f, ensure_ascii=False, indent=2)
"
```

**注意事项：** 如果某学科过滤后不足30篇，对该学科放宽时间限制至2020年。

### 2.4 筛选后统计

**目的：** 确认筛选后的数据量满足标注需求（需要1200条，筛选后应保留1500-1800条）。

**命令：**
```bash
python3 -c "
import json
from collections import Counter

with open('data/collected/filtered_recent.json') as f:
    papers = json.load(f)

discs = Counter()
for p in papers:
    dp = p.get('discipline_path', [])
    if dp: discs[dp[0]] += 1

print(f'筛选后总计: {len(papers)}篇')
print(f'目标: 1500-1800篇')
print(f'状态: {\"✓ 达标\" if len(papers) >= 1500 else \"✗ 不足\"}')
print()
for d,c in discs.most_common():
    print(f'  {d}: {c}篇')

# 每学科至少100篇
for d,c in discs.items():
    if c < 100:
        print(f'  ⚠ {d}不足100篇，需补充')
"
```

---

## 步骤三：结构化标注（第3-6周）

### 3.1 准备待标注列表

**目的：** 从筛选后的论文中随机选取1200条，确保学科分布均衡。

**命令：**
```bash
python3 -c "
import json, random

with open('data/collected/filtered_recent.json') as f:
    papers = json.load(f)

random.seed(42)
random.shuffle(papers)
to_annotate = papers[:1200]

with open('data/annotated/to_annotate.json', 'w') as f:
    json.dump(to_annotate, f, ensure_ascii=False, indent=2)

print(f'标注目标: {len(to_annotate)}条')
"
```

### 3.2 标注者培训

**操作：** 标注者阅读`dataset_final_spec_v1.0.md`第五章（标注人员详细准则），完成规范考试（正确率≥85%），在5条预试点标注上达到Kappa≥0.7。

**培训材料：** 规范第五章包含完整的六步骤标注流程、每个维度的判定规则、编造检测清单生成规则。

### 3.3 运行自动标注

**目的：** LLM辅助生成初始标注（学科路径、任务类型、难度级别、五维元数据、Code-Aware编造检测清单）。

**工具：** `scieval_annotator.py`

**生产环境适配：** 在运行前，将脚本中的`LLMAnnotator`类的规则方法替换为真实LLM API调用（如OpenAI API）。关键替换点：
- `annotate_discipline()` → 使用GPT-4o生成学科路径
- `annotate_task()` → 使用GPT-4o分配任务类型
- `annotate_content()` → 使用GPT-4o标注内容元数据
- `generate_fabrication_checklist()` → 使用GPT-4o生成编造检测清单

**命令：**
```bash
python3 scieval_annotator.py
```

**输出文件：**
- `data/annotated/annotations.json` — 1200条完整标注
- `data/annotated/fabrication_checklists.json` — Code-Aware实例的编造检测清单
- `data/annotated/annotation_summary.json` — 标注统计摘要

**完成后检查：**
```bash
python3 -c "
import json
with open('data/annotated/annotation_summary.json') as f:
    s = json.load(f)
print(f'标注条目: {s[\"total_records\"]}')
print(f'Code-Aware: {s[\"code_aware_count\"]}')
print(f'学科分布: {json.dumps(s[\"discipline_distribution\"], ensure_ascii=False)}')
print(f'任务分布: {json.dumps(s[\"task_distribution\"], ensure_ascii=False)}')
"
```

### 3.4 人工校验（标注者A + 标注者B交叉标注）

**目的：** 两名标注者独立标注同一批数据，计算Kappa，低于0.7触发仲裁。

**操作流程：**
1. 标注者A先行完成全部1200条标注（第3-4周，日均15条）
2. 标注者B以盲法独立标注同一批数据（第5-6周）
3. 自动计算学科路径、任务类型、研究类型的Cohen's Kappa
4. Kappa低于0.7的维度触发仲裁（引入第三名资深标注者）

**修正记录：**
```bash
echo "=== 修正日志 ===" > data/annotated/corrections.log
# 每修正一条追加:
# echo "PAPER_ID: 描述修正内容" >> data/annotated/corrections.log
```

---

## 步骤四：三级质量控制（第6-8周）

### 4.1 运行第一级QC：自动格式验证

**目的：** 检查所有标注数据的JSON格式合规性、必填字段完整性、枚举值有效性。

**工具：** `scieval_qc.py`

**命令：**
```bash
python3 scieval_qc.py
```

**预期输出：** 第一级不应有格式错误（error级别）。警告（warning）可以接受，但需逐一审查。

**常见格式错误及修复：**
- `无效任务类型` → 修改标注中的task_type为六种合法值之一
- `无效风险等级` → 修改decontamination.risk_level为safe/suspicious/high_risk
- `Code-Aware任务缺少编造检测清单` → 为该实例补充fabrication_checklist
- `编造检测清单声明不足5条` → 从论文中额外提取声明

### 4.2 运行第二级QC：去污染与一致性校验

**目的：** 验证去污染标注的准确性（与LLM截止日期比对）、检查标注间的语义一致性。

**检查内容：**
- 出版日期与8个LLM模型的训练截止日期比对
- 研究类型与论证类型的一致性（theoretical不应使用empirical论证）
- 创新程度与质量等级的合理性（breakthrough不应为C级）

**典型修复：**
```bash
# 去污染标注不匹配 → 重新计算risk_level
# 研究类型=theoretical但论证类型=empirical → 检查论文原文，修正其中一个
# 突破性创新但质量C → 升级quality_grade或降级innovation_level
```

### 4.3 运行第三级QC：难度与多样性平衡

**目的：** 检查三级难度分布（目标40:35:25）、六种任务类型覆盖率、六大学科覆盖率、Code-Aware比例（≥25%）。

**检查项与修复：**

| 问题 | 修复操作 |
|------|----------|
| L1占比>50% | 将部分L1实例的难度上调至L2或L3 |
| 缺失某任务类型 | 回到筛选阶段，为该任务类型补充论文并标注 |
| 缺失某学科大类 | 回到采集阶段补充该学科数据 |
| Code-Aware<25% | 检查是否遗漏了符合Code-Aware条件的实例 |

### 4.4 迭代修复循环

```bash
# 修复 → 运行QC → 检查评分 → 重复
python3 scieval_qc.py
# 目标：passed=true, overall≥60/100 (原型), ≥85/100 (正式发布)
```

### 4.5 人工抽样审核

**目的：** 从每100条数据中随机抽取10条，由资深标注者审核。

**操作：**
```bash
python3 -c "
import json, random
with open('data/annotated/annotations.json') as f:
    anns = json.load(f)
random.seed(42)
sample = random.sample(anns, 120)  # 10% of 1200
for a in sample:
    print(f'{a[\"paper_id\"]}: 学科={\"→\".join(a[\"discipline\"][\"primary_path\"])} | 任务={a[\"task\"][\"task_type\"]} L{a[\"task\"][\"difficulty_level\"]}')
print(f'需人工审核: {len(sample)}条')
"
```

**审核标准：** 标注准确率≥85%、任务合理性（难度与论文匹配）、编造检测清单质量（声明精确引用原文）。审核不通过率>20%时整批次退回。

---

## 步骤五：发布打包（第8周）

### 5.1 运行打包脚本

**目的：** 生成包含数据、报告、工具、文档的完整发布包。

**工具：** `scieval_packager.py`

**命令：**
```bash
python3 scieval_packager.py
```

**输出目录结构：**
```
SciEval-Bench-v1.0.0/
├── README.md              # 概述、用途、快速开始
├── CHANGELOG.md           # 完整变更日志
├── LICENSE.txt            # CC BY 4.0 + MIT
├── VERSION                # 1.0.0
├── manifest.json          # SHA256校验清单
├── data/                  # 数据集本体
├── reports/               # QC报告
├── tools/                 # 采集/标注/QC/打包工具
└── docs/                  # 规范与设计文档
```

### 5.2 验证发布包

**命令：**
```bash
RELEASE_DIR="/home/ubuntu/SciEval-Bench-v1.0.0"

# 计数
echo "文件总数: $(find $RELEASE_DIR -type f | wc -l)"

# 验证SHA256
python3 -c "
import json, hashlib, os
with open('$RELEASE_DIR/manifest.json') as f:
    m = json.load(f)
issues = 0
for path, info in m['files'].items():
    fp = os.path.join('$RELEASE_DIR', path)
    if os.path.exists(fp):
        with open(fp, 'rb') as f2:
            actual = hashlib.sha256(f2.read()).hexdigest()
        if actual != info['sha256']:
            print(f'  ✗ {path}: SHA256不匹配')
            issues += 1
if issues == 0:
    print('✓ 所有文件SHA256校验通过')
"

# 检查README完整性
head -50 "$RELEASE_DIR/README.md"
```

### 5.3 发布前最终检查清单

逐项确认：
- [ ] 1200条标注数据，多于此前的目标数量
- [ ] 六大学科全部覆盖，每学科≥100条
- [ ] 六种任务类型全部覆盖，每种≥96条（8%）
- [ ] Code-Aware实例≥300条（25%），每份附带合格的编造检测清单
- [ ] 三级难度分布偏差≤15%（L1 40%±15、L2 35%±15、L3 25%±15）
- [ ] QC综合评分≥85/100（正式发布标准）
- [ ] 自动格式验证零错误
- [ ] 去污染标注准确率≥95%
- [ ] 标注者间Kappa≥0.7
- [ ] 人工审核通过率≥85%
- [ ] 测试集标签已确认保密
- [ ] README/CHANGELOG/LICENSE/VERSION/manifest五文件齐全
- [ ] SHA256全部通过

---

## 常见问题速查

| 问题 | 原因 | 解决 |
|------|------|------|
| arXiv HTTP 429 | 请求过于频繁 | 增大time.sleep至3-5秒 |
| 某学科采集为0 | 关键词过于专业 | 替换为更通用的关键词 |
| 筛选后不足1500条 | 采集基数不够 | 回到采集阶段补充 |
| Kappa<0.7 | 标注者对规范理解不一致 | 标注对齐会议，讨论前10条分歧 |
| QC综合评分<60 | 格式错误或清单质量问题 | 优先修复error级格式问题 |
| Code-Aware<25% | 符合条件的论文未被标记 | 检查is_code_aware判定逻辑 |
| SHA256不匹配 | 文件在打包后有修改 | 重新打包 |
