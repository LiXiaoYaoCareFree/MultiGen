# SciEval-Bench 评估操作指南 — 评估六大AI科研系统

## 一、评估前准备

### 1.1 环境配置

```bash
# 创建评估环境
python3 -m venv scieval_eval
source scieval_eval/bin/activate
pip install requests docker

# 准备数据集
git clone https://github.com/scieval-bench/SciEval-Bench.git
cd SciEval-Bench
```

### 1.2 数据集选择

根据评估目标从SciEval-Bench中选择任务子集。完整评估使用全部1200条实例。快速评估从每个任务类型和学科组合中各选5条、共约50条。Code-Aware专项评估仅选取Code-Aware子类型实例（约360条）。

### 1.3 统一运行环境

所有系统在相同Docker环境中运行以确保公平比较：

```
硬件: 1× NVIDIA A6000 (48GB) / 可选 H100 (80GB)
软件: Docker 24+, Python 3.10, PyTorch 2.x
网络: arXiv API, Semantic Scholar API, GitHub
超时: L1任务2h, L2任务6h, L3任务24h
成本上限: L1 $10, L2 $30, L3 $100
```

---

## 二、适配器开发：统一SystemRunner接口

### 2.1 适配器接口规范

每个系统需要一个适配器实现以下接口（`system_adapters/base.py`）：

```python
class SystemAdapter:
    def prepare(self, task_input: dict) -> dict:
        """将SciEval-Bench任务输入转换为系统可接收的格式"""
        pass

    def run(self, prepared_input: dict, work_dir: str) -> dict:
        """运行系统并返回产出"""
        pass

    def collect_outputs(self, work_dir: str) -> dict:
        """从工作目录收集标准化产出"""
        return {
            "paper": "...",          # 论文文本（LaTeX或JSON）
            "code_repo": "...",      # 代码仓库路径（Code-Aware）
            "results_json": "...",   # 实验结果JSON（Code-Aware）
            "execution_log": "...",  # 执行日志（Code-Aware）
            "citations": [...]       # 引用列表
        }
```

### 2.2 AI-Scientist v1 适配器

**输入转换：** Level-1任务将`input.json`中的代码模板URL传递给系统。Level-2任务将研究主题作为`research_dir`参数。

**运行命令：**
```bash
cd ai-scientist-v1
python launch_scientist.py \
    --model "gpt-4o" \
    --experiment "$TEMPLATE_NAME" \
    --num-ideas 1
```

**Code-Aware适配：** AI-Scientist v1的实验代码分散在多个脚本中，需添加结果收集层。在系统运行完成后，运行封装脚本扫描实验输出目录，将数值结果提取为`results.json`，收集stdout/stderr为`execution.log`。

### 2.3 AI-Scientist v2 适配器

**输入转换：** v2去除了模板依赖，仅需研究方向文本。将`input.json`中的研究假设和背景描述合并为系统的`research_topic`参数。

**运行命令：**
```bash
cd ai-scientist-v2
python run_scientist.py \
    --research-topic "$TOPIC" \
    --model "claude-sonnet-4-20250514"
```

**Code-Aware适配：** v2的树搜索产生中间实验节点，每个节点的实验结果需要被聚合。编写`collect_tree_results.py`遍历实验树，提取每个节点的数值结果和图表描述。

### 2.4 AI-Researcher 适配器

**输入转换：** 最自然的适配——将`input.json`中的参考论文列表和研究指令传递给系统的Knowledge Acquisition Agent。Level-2任务不提供研究指令。

**运行命令：**
```bash
cd AI-Researcher
python main.py \
    --task "$TASK_FILE" \
    --model "claude-3-5-sonnet-20241022"
```

**Code-Aware适配：** AI-Researcher的Docker环境已经隔离了实验代码，适配难度最低。添加`export_results.py`在系统完成实验后自动导出`results.json`。

### 2.5 AutoResearchClaw 适配器

**输入转换：** 最简洁——仅需将研究主题文本传递给`--topic`参数。系统自身的23阶段管线会自动处理文献检索和实验设计。

**运行命令：**
```bash
researchclaw run \
    --topic "$TOPIC" \
    --auto-approve \
    --config config.arc.yaml
```

**Code-Aware适配：** 几乎零适配——AutoResearchClaw已产出`verification_report.json`（含数值结果）和SHA256校验。仅需将`verification_report.json`重命名为SciEval-Bench标准的`results.json`格式。

### 2.6 DeepScientist 适配器

**输入转换：** 将SOTA基准代码仓库URL和目标性能指标传递给系统。系统会自主进行贝叶斯优化探索。

**运行命令：**
```bash
cd DeepScientist
python run_deepscientist.py \
    --baseline-repo "$BASELINE_URL" \
    --target-metric "$METRIC_NAME" \
    --gpu-count 1
```

**Code-Aware适配：** DeepScientist的Findings Memory是天然的结构化数据源。编写`findings_to_results.py`从Findings Memory中提取验证通过的实验结果，转换为`results.json`。注意DeepScientist可能产生数千条探索记录——仅提取最终被选中的Progress Findings。

### 2.7 SibylSystem 适配器

**输入转换：** 将研究方向描述通过MCP协议传递给literature_review工具。如果任务类型是实验方案设计，同时调用experiment_design工具。

**运行命令：**
```bash
# 通过Claude Code + MCP协议启动
claude code --mcp sibylsystem \
    --prompt "Research topic: $TOPIC. Conduct full research and generate paper."
```

**Code-Aware适配：** 适配难度最高——SibylSystem当前无标准化数据导出。需改造其gpu_execution工具，在执行实验时将数值结果写入指定的`results.json`路径，将日志重定向到`execution.log`。

---

## 三、评估管线执行

### 3.1 单系统评估流程

```bash
# 步骤1：选取任务子集
python3 tools/select_tasks.py \
    --dataset data/ \
    --system "$SYSTEM_NAME" \
    --output tasks_for_system.json

# 步骤2：运行适配器
python3 system_adapters/run_$SYSTEM_NAME.py \
    --tasks tasks_for_system.json \
    --output-dir outputs/$SYSTEM_NAME/

# 步骤3：运行Text-Only评审
python3 evaluator_system.py evaluate \
    --papers outputs/$SYSTEM_NAME/papers/ \
    --reviewers gpt4o,claude_sonnet,gemini_pro \
    --output-dir evaluations/$SYSTEM_NAME/text_only/

# 步骤4：运行Code-Aware评审（仅Code-Aware任务）
python3 evaluator_system.py evaluate_code_aware \
    --papers outputs/$SYSTEM_NAME/papers/ \
    --code-dirs outputs/$SYSTEM_NAME/code/ \
    --checklists data/fabrication_checklists/ \
    --output-dir evaluations/$SYSTEM_NAME/code_aware/

# 步骤5：汇总报告
python3 evaluator_system.py summarize \
    --text-only evaluations/$SYSTEM_NAME/text_only/ \
    --code-aware evaluations/$SYSTEM_NAME/code_aware/ \
    --output evaluations/$SYSTEM_NAME/final_report.json
```

### 3.2 Code-Aware评估详细流程

Code-Aware评估是SciEval-Bench区别于其他基准的核心环节。对每个Code-Aware任务实例执行以下步骤：

**第一步：加载编造检测清单。** 从数据集加载该实例的`fabrication_checklist.json`，解析所有可验证声明。

**第二步：数值声明验证。** 对清单中`claim_type=numerical_result`的每条声明，从论文中定位`claim_text`描述的数值（如"94.3% accuracy"），在`results.json`中查找对应的度量值（如`cifar10_test_accuracy`），计算偏差是否在容差范围内。偏差在容差内→标记"一致"，偏差超容差→标记"不一致-数值偏差"，results.json中无对应key→标记"不一致-数据缺失"。

**第三步：方法声明验证。** 对清单中`claim_type=method_description`的每条声明，使用AST分析或关键字符串匹配检查代码仓库中是否存在声明的实现。在代码中找到匹配的类/函数→标记"一致"，代码中无匹配→标记"不一致-实现缺失"，代码存在但实现与描述不匹配→标记"不一致-实现偏差"。

**第四步：引用声明验证。** 对清单中`claim_type=citation_dependency`的每条声明，通过CrossRef API或Semantic Scholar API验证引用论文的真实存在性和信息准确性（标题、作者、年份匹配）。

**第五步：计算编造指数。**
```
编造指数 = (
    0.5 × (不一致数值声明数 / 总数值声明数) +
    0.3 × (不一致方法声明数 / 总方法声明数) +
    0.2 × (不一致引用声明数 / 总引用声明数)
)
```
编造指数范围0-1。0表示完全一致（无编造迹象），0-0.1表示低编造风险，0.1-0.3表示中等风险需要人工复核，>0.3表示高编造风险。

### 3.3 人类基线对照

为每个学科和任务类型选取2-3条实例，由至少两位领域研究者完成相同的任务输入（不告知论文来源），产出人类撰写的论文。将人类论文与AI系统论文进行匿名化配对比较。评审器在不知晓论文来源的情况下对两者评分，计算AI论文得分相对于人类论文得分的比例。

---

## 四、结果分析与报告

### 4.1 六系统对比矩阵

评估产出核心对比矩阵，包含以下维度。九维度评分按维度分解的均值±标准差（Text-Only和Code-Aware两层各自报告）。Code-Aware降幅——同一论文在Code-Aware评审下的评分与Text-Only评分的差值（预期为负值，反映编造被检测后的评分下降）。编造指数——数值不匹配率、方法不匹配率、引用不匹配率和综合编造指数。评审器间一致性——五模型评审面板的Spearman ρ和Kendall τ。人类基线比率——AI论文得分/人类论文得分×100%。任务覆盖度——该系统成功完成的任务类型数/6。

### 4.2 重点分析维度

**"看起来好vs实际上好"差距分析。** 计算每个系统在Text-Only和Code-Aware评审下的评分差值。差距越大的系统越依赖"表面功夫"——写出漂亮的论文但实验数据不支撑。差距小且Code-Aware评分高的系统是真正可靠的科研工具。

**学科能力剖面。** 按六大学科大类分解每个系统的九维度评分，生成能力雷达图。识别系统在哪些学科上有竞争力、哪些学科是盲区。

**编造模式分析。** 按编造类型（数值编造、方法编造、引用编造）分解编造指数，识别每个系统的典型编造模式。例如，Research Arena发现Kimi Code主要在数值和方法上编造，而Claude Code的编造率中等但在引用上的错误更多。

**一致性-质量关联分析。** 分析评审器间一致性高的论文是否也质量更高。如果一致性高但评分低，说明系统产出稳定但质量不足。如果一致性低，说明系统产出质量波动大。

### 4.3 报告产出

最终评估报告包含：六系统综合排名表（按Code-Aware融合评分排序）、维度级分解雷达图、Text-Only vs Code-Aware降幅柱状图、编造指数按类型分解的堆叠柱状图、学科能力剖面热力图、人类基线对照表、评审器间一致性矩阵（Spearman ρ热力图）、每个系统详细的弱点诊断和建议。

---

## 五、常见问题与注意事项

**Q：某个系统不支持某种任务类型怎么办？** 在对比报告中标注"不支持"，该任务类型不纳入该系统的综合排名。最终排名按实际参与的任务类型加权。

**Q：DeepScientist需要数周运行时间怎么办？** 设置时间上限（Level-3最长24小时），截取其在该时间内的最优产出。对比报告标注"受时间限制"。

**Q：AI-Scientist v1和v2的代码质量差异大，Code-Aware评分如何公平比较？** Code-Aware评分不依赖于代码风格——编造检测清单只关注"声明是否在结果文件中有对应值"，不评判代码质量。

**Q：如果某个系统的论文中完全没有可验证的数值声明？** 该论文的编造指数无法计算，在Code-Aware报告中标注"N/A"——这本身就是一个重要发现（系统在回避可验证的声明）。


---

## 六、补充章节：纯理论论文的Code-Aware评审

### 6.1 问题的提出

SciEval-Bench 的 Code-Aware 子类型最初设计时假设所有可评估的论文都包含可执行的实验代码——数值结果可以在 `results.json` 中验证，方法组件可以在代码仓库中找到。然而，六大学科中的人文学科（哲学、历史学、语言学理论方向）、形式科学中的数学和逻辑学、以及社会科学中的纯理论研究，其论文通常不包含实验代码。一篇关于哥德尔不完备定理的哲学论文不会产生 `results.json`，一篇纯数学的拓扑学证明不会有可执行的 Python 脚本。

这引发了一个核心问题：**Code-Aware 评审是否适用于纯理论论文？如果不适用，如何在不依赖实验代码的情况下实现同等严格程度的真实性验证？**

### 6.2 Code-Aware 适用性判定标准

Code-Aware 子类型不是一刀切的"所有论文都要代码"。以下判定标准明确了 Code-Aware 的触发条件和豁免规则。

**必须标记为 Code-Aware 的条件（三个条件全部满足）：**
1. 任务类型为完整论文生成或实验方案设计
2. 论文的核心贡献通过实验或数据驱动的方式验证（研究类型为 empirical 或 methodological）
3. 论文中至少包含3条可量化的数值型声明（如准确率、F1分数、运行时间、统计显著性水平）

**必须豁免 Code-Aware 的条件（满足任意一条即豁免）：**
1. 研究类型为 theoretical 或 survey——纯理论推导或综述性论文
2. 研究类型为 application 且核心贡献是概念框架而非实现——应用理论分析而非实验验证
3. 论文的核心论证方式为 deductive（演绎型）或 analogical（类比型），且不依赖数值型实验结果
4. 学科为人文学科（哲学、历史学、文学研究）——这些学科的研究方法天然不涉及可执行代码

**灰色地带条件（需人工判定）：**
1. 论文声称有实验但实验数据不完整——标记为 Code-Aware 但编造检测清单标注为"低置信度"
2. 社会科学中的实证研究——如果使用公开数据集和统计分析代码，应标记为 Code-Aware
3. 计算理论论文——如果包含可执行的算法实现，应标记为 Code-Aware；如果仅含伪代码，应豁免

**判定流程：**
```
IF research_type == 'theoretical' OR research_type == 'survey'
    → 豁免 Code-Aware，进入 alternative_verification
ELSE IF task_type NOT IN ['full_paper_generation', 'experiment_design']
    → 豁免 Code-Aware
ELSE IF 论文中数值型声明数 < 3
    → 豁免 Code-Aware，但标注 "低可验证性"
ELSE
    → 标记为 Code-Aware，生成编造检测清单
```

### 6.3 替代验证方法：非实验论文的真实性检查

对于豁免 Code-Aware 的纯理论论文，使用以下三类替代验证方法确保评审的严格性。这些方法不依赖代码执行，但同样实现了"逐项核对"的验证目标。

**方法一：数学推导校验（Mathematical Derivation Verification）。** 适用范围：包含数学公式、定理、引理和推导步骤的论文（数学、理论物理、理论计算机科学）。实施方式：从论文中提取关键数学声明（定理陈述、关键等式、推导步骤），标记每条声明的依赖关系（该推导依赖哪些前置公式），使用符号计算工具（SymPy或Mathematica脚本）重新计算关键等式，检测是否存在推导跳跃或逻辑漏洞。声明类型对应：`mathematical_claim`替代`numerical_result`，`proof_step`替代`method_description`。验证方式从`results_json`替换为`symbolic_verification`（符号计算验证）和`dependency_check`（依赖链完整性检查）。

**方法二：逻辑一致性检查（Logical Consistency Check）。** 适用范围：以论证链条和概念框架为核心的论文（哲学、理论语言学、法学、部分社会科学理论）。实施方式：提取论文的核心论点（thesis statements）和支持论证（supporting arguments），构建论证图——将论点作为节点、支持/反驳关系作为边，检查论证图是否存在循环依赖（循环论证）、悬空论点（无支持论证的强断言）、矛盾边（同一论点同时被支持和反驳）。声明类型对应：`thesis_statement`替代`numerical_result`，`supporting_argument`替代`method_description`。验证方式从`results_json`替换为`logical_graph_check`（论证图完整性检查）和`contradiction_detection`（矛盾检测）。

**方法三：引用溯源验证（Citation Provenance Verification）。** 适用范围：所有类型的论文（这是Code-Aware评审中引用验证的增强版）。实施方式：对论文中的每条引用进行三级溯源——第一级验证论文是否真实存在（DOI/arXiv ID验证），第二级验证引用内容是否与被引论文的实际内容一致（提取引文中声称的观点，在被引论文中搜索匹配），第三级验证引用链是否完整（被引论文→被引论文的引文→原始来源）。这种方式对纯理论论文尤为重要，因为理论论文通常更依赖引文链的完整性而非实验数据。

### 6.4 替代验证的清单格式

对于豁免Code-Aware的纯理论论文，使用与编造检测清单相同结构但声明类型和验证方式不同的"真实性验证清单"。

```json
{
  "paper_id": "MATH-001",
  "verification_type": "theoretical",
  "verifiable_claims": [
    {
      "claim_id": "TV-MATH-001-01",
      "claim_type": "mathematical_claim",
      "claim_location": {"section": "Main Results", "paragraph": 2},
      "claim_text": "Theorem 3.1: For any ε > 0, there exists δ > 0 such that...",
      "verification_method": "symbolic_verification",
      "tolerance": null,
      "required_evidence": "SymPy脚本可重新推导该定理的关键不等式（附录A.2）"
    },
    {
      "claim_id": "TV-MATH-001-02",
      "claim_type": "proof_step",
      "claim_location": {"section": "Proof of Theorem 3.1", "paragraph": 1},
      "claim_text": "Applying Lemma 2.3 yields the bound ||x|| ≤ C·log(n)",
      "verification_method": "dependency_check",
      "tolerance": null,
      "required_evidence": "Lemma 2.3确实被引用且其结论支持该推导步骤"
    },
    {
      "claim_id": "TV-MATH-001-03",
      "claim_type": "citation_dependency",
      "claim_location": {"section": "Introduction", "paragraph": 0},
      "claim_text": "This work builds on the framework of Smith (2019)...",
      "verification_method": "citation_provenance_level3",
      "tolerance": null,
      "required_evidence": "Smith(2019)真实存在，其框架描述与本文引用一致，且Smith的引文链完整可追溯"
    }
  ]
}
```

### 6.5 Code-Aware 与替代验证的分布预期

基于SciEval-Bench六大学科的学科特征，Code-Aware标注和替代验证的预期分布如下。

| 学科大类 | Code-Aware比例 | 替代验证比例 | 完全豁免 | 说明 |
|----------|:---:|:---:|:---:|------|
| 形式科学 | 70% | 25% | 5% | 数学和逻辑学使用替代验证 |
| 自然科学 | 85% | 10% | 5% | 理论物理使用替代验证 |
| 工程与技术科学 | 90% | 5% | 5% | 几乎全部Code-Aware |
| 医学与生命科学 | 80% | 15% | 5% | 纯理论生物学论文豁免 |
| 社会科学 | 50% | 35% | 15% | 理论经济学、纯社会学理论豁免 |
| 人文学科 | 5% | 60% | 35% | 语言学计算方向可能Code-Aware，其余替代验证或豁免 |

### 6.6 对评估报告的补充

在评估报告中，对豁免Code-Aware但使用替代验证的论文，增加以下分析维度。替代验证得分替代编造指数——数学推导完整率（通过symbolic_verification的声明比例）、逻辑一致性得分（无循环论证/无悬空论点/无矛盾的论证图比例）、引用溯源完整率（通过三级溯源的引用比例）。替代验证评审摘要——与Code-Aware论文的Text-Only评审结果进行同一论文内的交叉对比，检验Text-Only评审是否也能捕获替代验证发现的问题。
