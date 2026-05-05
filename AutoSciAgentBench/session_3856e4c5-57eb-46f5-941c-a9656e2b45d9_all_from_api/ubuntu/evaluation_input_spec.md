# SciEval-Bench 评估输入规格文档

## 一、总体输入架构

使用 SciEval-Bench 评估一个AI科研系统需要经过四个阶段，每个阶段有独立的输入、参数和输出。以下按阶段逐一说明。

**评估流程总览：**
```
数据集任务实例 → [适配器] → 系统运行 → 产出收集 → [Text-Only评审] → [Code-Aware评审] → 汇总报告
```

---

## 二、阶段一：数据集任务实例（input.json）

这是 SciEval-Bench 提供的最核心输入，每个任务实例一个 `input.json` 文件。

### 2.1 所有字段一览

| 字段 | 类型 | 必要性 | 格式 | 说明 |
|------|------|:---:|------|------|
| `paper_id` | string | **必填** | `{学科缩写}-{子学科缩写}-{序号}` | 如 `CS-AI-001` |
| `task_type` | string | **必填** | 枚举值 | 见2.2 |
| `difficulty_level` | int | **必填** | 1/2/3 | L1引导式/L2半自主/L3全自主 |
| `discipline_path` | string[] | **必填** | 四层级数组 | 如 `["形式科学","计算机科学","人工智能","深度学习"]` |
| `input_content.hypothesis` | string | L1必填 | 100-300字文本 | 研究假设描述 |
| `input_content.background` | string | **必填** | 100-500字文本 | 领域背景 |
| `input_content.reference_papers` | object[] | L1/L2必填 | 论文列表 | 每篇含 title/abstract/arxiv_id/year |
| `input_content.experiment_data` | object | L1可选 | 结构化JSON | 实验数据（仅L1完整论文生成） |
| `input_content.constraints` | object | 可选 | 约束条件 | 字数限制、格式要求等 |
| `code_aware` | object | 条件必填 | Code-Aware标记 | 见2.3 |

### 2.2 task_type 枚举值

| 值 | 含义 | 适用学科 | 典型输入 |
|------|------|----------|----------|
| `full_paper_generation` | 完整论文生成 | 全部 | 假设+数据+参考文献 |
| `literature_review` | 文献综述生成 | 全部 | 主题+参考文献列表 |
| `experiment_design` | 实验方案设计 | 形式/自然/工程/医学 | 假设+方法描述 |
| `research_proposal` | 研究提案生成 | 全部 | 领域+方向描述 |
| `paper_extension` | 论文扩展改写 | 全部 | 已有草稿+扩展要求 |
| `peer_review` | 同行评审生成 | 全部 | 待评审论文全文 |

### 2.3 code_aware 子字段

仅当实例标记为 Code-Aware 时出现：

| 字段 | 类型 | 必要性 | 说明 |
|------|------|:---:|------|
| `code_aware.is_code_aware` | bool | **必填** | 固定为 true |
| `code_aware.expected_files` | string[] | **必填** | 系统需提交的文件列表：`["code/","run.sh","results.json","execution.log","README.md","SHA256SUMS"]` |
| `code_aware.fabrication_checklist_id` | string | **必填** | 关联的编造检测清单ID，格式 `FC-{paper_id}` |
| `code_aware.hardware_constraint` | object | 可选 | `{"gpu_memory_gb": 48, "max_runtime_minutes": 120}` |

### 2.4 完整 input.json 示例

**示例1：Level-1 完整论文生成（Code-Aware）**

```json
{
  "paper_id": "CS-AI-001",
  "task_type": "full_paper_generation",
  "difficulty_level": 1,
  "discipline_path": ["形式科学", "计算机科学", "人工智能", "深度学习"],
  "input_content": {
    "hypothesis": "在Transformer中引入反馈注意力机制可以显著提升长上下文处理能力，其核心在于将历史注意力模式作为工作记忆注入当前层的计算。",
    "background": "Transformer架构在处理长序列时面临注意力复杂度平方增长的问题。最近的研究尝试通过稀疏注意力、线性注意力和状态空间模型来缓解这一问题，但这些方法通常牺牲了注意力机制的全局建模能力。",
    "reference_papers": [
      {"title": "Attention Is All You Need", "abstract": "We propose a new simple network architecture...", "arxiv_id": "1706.03762", "year": 2017},
      {"title": "Efficient Transformers: A Survey", "abstract": "This survey...", "arxiv_id": "2009.06732", "year": 2020}
    ],
    "experiment_data": {
      "baseline_accuracy": {"cifar10": 92.2, "imagenet": 76.5},
      "target_dataset": "Long Range Arena",
      "evaluation_metrics": ["accuracy", "perplexity", "throughput"]
    },
    "constraints": {
      "max_words": 8000,
      "format": "ICLR LaTeX template",
      "required_sections": ["Abstract","Introduction","Related Work","Method","Experiments","Conclusion"]
    }
  },
  "code_aware": {
    "is_code_aware": true,
    "expected_files": ["code/","run.sh","results.json","execution.log","README.md","SHA256SUMS"],
    "fabrication_checklist_id": "FC-CS-AI-001",
    "hardware_constraint": {"gpu_memory_gb": 48, "max_runtime_minutes": 120}
  }
}
```

**示例2：Level-2 研究提案生成（非Code-Aware，纯理论）**

```json
{
  "paper_id": "PHIL-001",
  "task_type": "research_proposal",
  "difficulty_level": 2,
  "discipline_path": ["人文学科", "哲学", "科学哲学", "认识论"],
  "input_content": {
    "background": "近年来AI系统的快速发展引发了关于机器知识本质的哲学讨论。传统认识论将知识定义为'被证成的真信念'(JTB)，但这一框架在面对AI系统时暴露出局限性。",
    "reference_papers": [
      {"title": "Knowledge and Its Limits", "abstract": "...", "arxiv_id": "", "year": 2000},
      {"title": "On the Epistemology of AI", "abstract": "...", "arxiv_id": "2305.xxxxx", "year": 2023}
    ],
    "constraints": {
      "max_words": 5000,
      "format": "Academic philosophy essay"
    }
  }
}
```

---

## 三、阶段二：系统适配器输入

适配器接收 `input.json`，将其转换为各系统可执行的命令和参数。

### 3.1 通用输入参数

所有适配器共用的参数：

| 参数 | 必要性 | 格式 | 来源 | 示例 |
|------|:---:|------|------|------|
| `task_input` | **必填** | JSON对象 | `input.json` 完整内容 | 见上节 |
| `work_dir` | **必填** | 绝对路径 | 由评估框架分配 | `/tmp/scieval_run/CS-AI-001/` |
| `timeout_seconds` | **必填** | int | 由难度级别确定 | L1=7200, L2=21600, L3=86400 |
| `cost_budget_usd` | **必填** | float | 由难度级别确定 | L1=10, L2=30, L3=100 |
| `gpu_device` | 条件必填 | string | 硬件配置 | `"cuda:0"` / `"mps"` / `"cpu"` |
| `docker_image` | 可选 | string | 系统预构建镜像 | `"scieval/ai-scientist:v1"` |
| `api_keys` | 条件必填 | object | 环境变量 | `{"OPENAI_API_KEY":"sk-...","ANTHROPIC_API_KEY":"sk-..."}` |
| `network_access` | 可选 | bool | 默认true | 是否允许访问arXiv API/GitHub |

### 3.2 六系统适配器具体参数

#### AI-Scientist v1

| 参数 | 必要性 | 说明 | 示例值 |
|------|:---:|------|--------|
| `template_name` | **必填** | 代码模板名称 | 从 `input.json` 的 `experiment_data` 推断 |
| `model` | **必填** | 使用的LLM | `"gpt-4o"` |
| `num_ideas` | 可选(默认1) | 生成的研究想法数 | `1` |
| `iterations` | 可选(默认5) | 实验迭代次数 | `5` |

**适配示例：** input.json → AI-Scientist v1 命令：
```bash
TEMPLATE=$(python3 -c "import json; d=json.load(open('input.json')); print(d['input_content']['experiment_data'].get('template','nanoGPT'))")

python launch_scientist.py \
    --model "gpt-4o" \
    --experiment "$TEMPLATE" \
    --num-ideas 1 \
    --write-up-num 1
```

#### AI-Scientist v2

| 参数 | 必要性 | 说明 | 示例值 |
|------|:---:|------|--------|
| `research_topic` | **必填** | 研究方向文本 | hypothesis + background 拼接 |
| `model` | **必填** | 使用的LLM | `"claude-sonnet-4-20250514"` |
| `search_budget` | 可选(默认100) | 树搜索节点数 | `100` |

**适配示例：**
```bash
TOPIC=$(python3 -c "
import json; d=json.load(open('input.json'))
c = d['input_content']
print(f\"{c.get('hypothesis','')} {c.get('background','')}\"[:500])
")

python run_scientist.py \
    --research-topic "$TOPIC" \
    --model "claude-sonnet-4-20250514" \
    --search-budget 100
```

#### AI-Researcher

| 参数 | 必要性 | 说明 | 示例值 |
|------|:---:|------|--------|
| `task_file` | **必填** | JSON任务文件路径 | 适配器生成的中间文件 |
| `model` | **必填** | 使用的LLM | `"claude-3-5-sonnet-20241022"` |
| `reference_papers` | L1/L2**必填** | 论文列表 | `input.json` 中的 reference_papers |
| `research_instruction` | L1**必填** | 研究指令 | `input.json` 中的 hypothesis |

**适配示例：**
```bash
# 适配器生成 task.json
python3 -c "
import json
d = json.load(open('input.json'))
task = {
    'task_id': d['paper_id'],
    'reference_papers': d['input_content']['reference_papers'],
    'research_instruction': d['input_content'].get('hypothesis', ''),
    'difficulty': d['difficulty_level']
}
json.dump(task, open('task.json','w'), ensure_ascii=False, indent=2)
"

python main.py --task task.json --model "claude-3-5-sonnet-20241022"
```

#### AutoResearchClaw

| 参数 | 必要性 | 说明 | 示例值 |
|------|:---:|------|--------|
| `topic` | **必填** | 研究主题 | hypothesis + background 拼接 |
| `mode` | **必填** | 运行模式 | `"full-auto"` (评估时全自动) |
| `config` | **必填** | 配置文件路径 | `"config.arc.yaml"` |

**适配示例：**
```bash
TOPIC=$(python3 -c "
import json; d=json.load(open('input.json'))
print(d['input_content'].get('hypothesis', d['input_content'].get('background',''))[:300])
")

researchclaw run \
    --topic "$TOPIC" \
    --auto-approve \
    --config config.arc.yaml
```

#### DeepScientist

| 参数 | 必要性 | 说明 | 示例值 |
|------|:---:|------|--------|
| `baseline_repo` | **必填** | SOTA基准代码URL | 从 `input.json` 提取 |
| `target_metric` | **必填** | 优化目标指标 | 从 `input.json` 的 experiment_data 提取 |
| `gpu_count` | **必填** | GPU数量 | `1` |
| `exploration_budget_hours` | 可选(默认24) | 探索时长上限 | `24` |

**适配示例：**
```bash
BASELINE=$(python3 -c "import json; d=json.load(open('input.json')); print(d['input_content'].get('experiment_data',{}).get('baseline_repo',''))")
METRIC=$(python3 -c "import json; d=json.load(open('input.json')); print(d['input_content'].get('experiment_data',{}).get('target_metric','val_loss'))")

python run_deepscientist.py \
    --baseline-repo "$BASELINE" \
    --target-metric "$METRIC" \
    --gpu-count 1 \
    --exploration-budget-hours 24
```

#### SibylSystem

| 参数 | 必要性 | 说明 | 示例值 |
|------|:---:|------|--------|
| `prompt` | **必填** | 完整研究描述 | 所有 input 字段拼接 |
| `mcp_tools` | **必填** | 启用的MCP工具 | `["literature_review","experiment_design","paper_writing"]` |

**适配示例：**
```bash
PROMPT=$(python3 -c "
import json; d=json.load(open('input.json'))
c = d['input_content']
parts = [c.get('hypothesis',''), c.get('background','')]
print(' '.join(parts)[:1000])
")

claude code --mcp sibylsystem \
    --prompt "Research topic: $PROMPT. Task type: $(python3 -c "import json;print(json.load(open('input.json'))['task_type'])"). Conduct full research and generate paper."
```

---

## 四、阶段三：评审器输入

### 4.1 Text-Only 评审输入

| 参数 | 必要性 | 格式 | 来源 | 示例 |
|------|:---:|------|------|------|
| `paper_text` | **必填** | 结构化JSON | 系统产出 | `{"title":"...","abstract":"...","sections":{...}}` |
| `reference_paper` | **必填** | 结构化JSON | `reference.json` | 人类撰写的参考论文 |
| `reviewer_models` | **必填** | string[] | 配置 | `["gpt4o","claude_sonnet","gemini_pro"]` |
| `rubric` | **必填** | JSON | `rubric.json` | 九维度权重和评分描述 |
| `task_type` | **必填** | string | `input.json` | 决定适用哪些评估维度 |
| `pairwise_mode` | 可选(默认false) | bool | 配置 | 是否与人类参考论文匿名配对比较 |

**Text-Only 评审器命令：**
```bash
python3 evaluator_system.py evaluate \
    --papers outputs/$SYSTEM_NAME/papers/ \
    --references data/references/ \
    --reviewers gpt4o,claude_sonnet,gemini_pro \
    --rubric data/rubric.json \
    --output-dir evaluations/$SYSTEM_NAME/text_only/
```

### 4.2 Code-Aware 评审额外输入

Code-Aware 评审在 Text-Only 评审的基础上增加以下输入：

| 参数 | 必要性 | 格式 | 来源 |
|------|:---:|------|------|
| `code_repo_path` | **必填** | 绝对路径 | 系统产出的代码仓库目录 |
| `results_json` | **必填** | JSON文件路径 | 系统产出的 `results.json` |
| `execution_log` | **必填** | 文本文件路径 | 系统产出的 `execution.log` |
| `fabrication_checklist` | **必填** | JSON | 数据集的 `fabrication_checklist.json` |
| `sha256_sums` | **必填** | 文本文件路径 | 系统产出的 `SHA256SUMS` |
| `tolerance_overrides` | 可选 | object | 覆盖默认容差的配置 |

**Code-Aware 评审器命令：**
```bash
python3 evaluator_system.py evaluate_code_aware \
    --papers outputs/$SYSTEM_NAME/papers/ \
    --code-dirs outputs/$SYSTEM_NAME/code/ \
    --results-jsons outputs/$SYSTEM_NAME/results/ \
    --execution-logs outputs/$SYSTEM_NAME/logs/ \
    --checklists data/fabrication_checklists/ \
    --sha256-sums outputs/$SYSTEM_NAME/SHA256SUMS \
    --output-dir evaluations/$SYSTEM_NAME/code_aware/
```

### 4.3 替代验证输入（纯理论论文）

对于豁免 Code-Aware 的纯理论论文，替代验证需要的输入：

| 参数 | 必要性 | 格式 | 说明 |
|------|:---:|------|------|
| `verification_type` | **必填** | `"theoretical"` | 固定值 |
| `mathematical_claims` | 条件必填 | JSON数组 | 待验证的数学声明（如有） |
| `argument_graph` | 条件必填 | JSON | 论点论证图（哲学/理论类） |
| `citation_list` | **必填** | JSON数组 | 所有引用 |
| `sympy_scripts` | 可选 | 文件路径 | 数学验证的SymPy脚本 |

### 4.4 人类评审输入

人类评审的输入与 Text-Only 评审相同，但额外包含：

| 参数 | 必要性 | 说明 |
|------|:---:|------|
| `reviewer_qualification` | **必填** | 评审者资质（博士在读及以上） |
| `blind_mode` | **必填** | 固定为 true（双盲评审） |
| `min_reviewers_per_paper` | **必填** | 固定为 2 |
| `review_deadline_days` | 可选(默认14) | 评审完成期限 |

---

## 五、各输入参数的常见默认值与可选配置

### 5.1 通用默认值

| 参数 | 默认值 | 何时可省略 |
|------|--------|-----------|
| `difficulty_level` | 1 | 仅当任务类型为 paper_extension 或 peer_review 时固定为1 |
| `network_access` | true | 离线环境设为 false |
| `gpu_device` | `"cuda:0"` | CPU-only环境省略 |
| `docker_image` | 无 | 使用宿主机 Python 环境时省略 |
| `api_keys` | 从环境变量读取 | 如果已设置 `OPENAI_API_KEY` 等环境变量 |
| `pairwise_mode` | false | 快速评估时省略（默认仅评审AI论文） |
| `tolerance_overrides` | 使用默认±0.5/±1% | 高精度任务需显式设置 |

### 5.2 按任务类型的默认约束

| 任务类型 | 默认字数 | 默认格式 | 默认时间限制 |
|----------|----------|----------|-------------|
| full_paper_generation | 4000-8000 | ICLR LaTeX | L1:2h L2:6h L3:24h |
| literature_review | 3000-6000 | Academic Markdown | L1:1h L2:3h |
| experiment_design | 2000-4000 | Structured JSON+Markdown | L1:1h L2:3h |
| research_proposal | 2000-5000 | Academic Markdown | L2:3h L3:6h |
| paper_extension | 由输入决定 | 继承输入格式 | 1h |
| peer_review | 1000-2000 | Structured JSON | 30min |

---

## 六、产出收集与验证输入

### 6.1 系统产出必需文件

| 文件 | 必要性 | 格式 | 验证方式 |
|------|:---:|------|----------|
| `paper.{tex,md,json}` | **必填** | LaTeX/Markdown/JSON | 文件存在 + 非空 + 包含必需章节 |
| `code/` (目录) | Code-Aware**必填** | Python项目目录 | 存在 `requirements.txt` + 可导入 |
| `results.json` | Code-Aware**必填** | JSON | 符合Schema + 数值类型正确 |
| `execution.log` | Code-Aware**必填** | 文本 | 非空 + 包含执行痕迹 |
| `README.md` | Code-Aware**必填** | Markdown | 包含运行说明 |
| `SHA256SUMS` | Code-Aware**必填** | 文本 | 每行 `hash filename` 格式 |
| `citations.json` | 可选 | JSON | 引用列表（如系统不单独输出则从论文提取） |

### 6.2 产出验证命令

```bash
# 验证Code-Aware产出完整性
python3 -c "
import json, os
ca = json.load(open('input.json'))['code_aware']
for f in ca['expected_files']:
    path = f'outputs/{f}'
    exists = os.path.exists(path)
    size = os.path.getsize(path) if exists else 0
    status = '✓' if (exists and size > 0) else '✗ 缺失'
    print(f'  {status} {f} ({size}B)')
"
```
