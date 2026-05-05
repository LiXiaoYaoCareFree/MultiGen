# 六大AI科研系统接口与能力对比 — 适配SciEval-Bench评估

## 一、系统概览

| 系统 | 发布方 | 时间 | 核心特点 |
|------|--------|------|----------|
| AI-Scientist v1 | Sakana AI | 2024.08 | 首个全自动发现系统，模板驱动 |
| AI-Scientist v2 | Sakana AI | 2025.04 | 去除模板依赖，树搜索+VLM评审 |
| AI-Researcher | 香港大学 | 2025.05 | 多Agent协作+Scientist-Bench基准 |
| AutoResearchClaw | aiming-lab | 2026.03 | 23阶段全链路+自进化 |
| DeepScientist | 西湖大学等 | 2025.09 | 目标驱动贝叶斯优化，月级探索 |
| AutoResearch-SibylSystem | 开源社区 | 2026.03 | Claude Code原生，MCP多Agent |

---

## 二、输入输出接口对比

| 系统 | 输入 | 输出 | 输入格式 | 输出格式 |
|------|------|------|----------|----------|
| **AI-Scientist v1** | 代码模板 + 研究方向 | LaTeX论文 + 代码 + 图表 | GitHub仓库URL + 文本描述 | LaTeX PDF + Python代码 |
| **AI-Scientist v2** | 研究方向（无需模板） | LaTeX论文 + 代码 + 图表 + VLM优化图 | 文本描述（无代码模板依赖） | LaTeX PDF + Python代码 + 优化图表 |
| **AI-Researcher** | 10-15篇参考文献 + 研究指令(可选) | 技术报告 + 代码实施 | 论文列表 + 文本指令 | 结构化论文 + GitHub代码仓库 |
| **AutoResearchClaw** | 研究主题（一句话） | 完整论文 + LaTeX + 代码 + 图表 + BibTeX | 文本描述 | LaTeX PDF + Python项目 + 实验数据 |
| **DeepScientist** | 基准代码仓库 + 性能指标目标 | 论文 + 代码 + 实验日志 + Findings Memory | SOTA代码 + 目标指标 | LaTeX PDF + 代码 + 结构化日志 |
| **SibylSystem** | 研究方向描述 | 论文 + 实验代码 + 评审报告 | 文本描述 | LaTeX PDF + Python代码 + 评审JSON |

### 2.1 关键发现：谁产生代码/数据

所有六个系统都**产生代码**，但质量和完整性差异显著：

- **AI-Scientist v1/v2、AI-Researcher、DeepScientist**：实验代码作为中间产物产生，论文草稿后自动丢弃或未结构化保存
- **AutoResearchClaw**：最完整的代码和数据产出——`experiment runs/`、`results.json`、`verification_report.json`、SHA256校验
- **SibylSystem**：实验代码通过GPU并行执行产生，但未标准化数据输出格式

这直接决定了它们在SciEval-Bench上的评估方式：
- **AutoResearchClaw**最容易适配Code-Aware子类型（已有结构化实验数据输出）
- **AI-Scientist v1/v2、AI-Researcher、DeepScientist**需要额外封装层将其中间产物标准化为`results.json`和`execution.log`
- **SibylSystem**需要添加结构化数据导出功能

---

## 三、支持的任务类型

| 系统 | 完整论文 | 文献综述 | 实验设计 | 研究提案 | 论文扩展 | 同行评审 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| AI-Scientist v1 | ✅ | ❌ | ✅(隐式) | ✅(隐式) | ❌ | ✅(自评审) |
| AI-Scientist v2 | ✅ | ❌ | ✅(隐式) | ✅(树搜索) | ❌ | ✅(VLM评审) |
| AI-Researcher | ✅ | ✅ | ✅ | ✅ | ❌ | ✅(评审Agent) |
| AutoResearchClaw | ✅ | ✅ | ✅ | ✅ | ✅ | ✅(多Agent) |
| DeepScientist | ✅ | ❌ | ✅ | ✅(目标驱动) | ❌ | ✅(自评审) |
| SibylSystem | ✅ | ✅ | ✅ | ❌ | ❌ | ✅(多Agent) |

**SciEval-Bench适配策略：**
- 所有系统都可参与**完整论文生成**（核心任务，30%实例）
- AI-Researcher和AutoResearchClaw可参与全部六种任务类型
- AI-Scientist v1需要封装其隐式的研究提案和实验设计能力
- SibylSystem自带literature_review和experiment_design的MCP工具，可直接映射

---

## 四、代码/数据产出能力与Code-Aware适配

| 系统 | 代码产出 | 结构化数据 | 适配Code-Aware难度 | 所需适配工作 |
|------|:---:|:---:|:---:|------|
| AI-Scientist v1 | ✅ | ❌ | 中等 | 需添加`results.json`导出 + 执行日志捕获 |
| AI-Scientist v2 | ✅ | ❌ | 中等 | 同v1，图表优化不影响Code-Aware |
| AI-Researcher | ✅ | ❌ | 中等 | 需添加结构化结果导出，代码已有完整仓库 |
| AutoResearchClaw | ✅ | ✅(部分) | **低** | 已有`results.json`和`verification_report.json`，仅需格式对齐 |
| DeepScientist | ✅ | ✅(Findings Memory) | **低** | Findings Memory可直接转化为`results.json` |
| SibylSystem | ✅ | ❌ | 高 | 需添加完整的数据导出层 |

### 4.1 适配方案

对于不支持结构化数据导出的系统（AI-Scientist v1/v2、AI-Researcher），需要开发**标准化封装器（Wrapper）**：

```
Wrapper 功能：
1. 拦截系统的实验执行输出
2. 将数值结果提取为 results.json 格式
3. 捕获完整的 stdout/stderr 为 execution.log
4. 生成论文中数值声明的逐项映射表
5. 计算 SHA256 校验和
```

封装器的实现复杂度因系统而异。AI-Researcher已有完整的Docker环境和代码仓库结构，封装难度最低（约200行Python）。AI-Scientist v1/v2的实验代码分散在多个脚本中，需要添加统一的结果收集层（约400行）。SibylSystem的GPU并行架构需要改造其执行引擎以支持结构化输出（约600行）。

---

## 五、如何用SciEval-Bench评估各系统

### 5.1 评估流程

对每个系统执行以下六步流程：

**第一步：准备输入。** 从SciEval-Bench数据集中为该系统支持的任务类型选择对应的`input.json`。对于AI-Scientist v1提供代码模板（如数据集中指定的GitHub仓库），对于AI-Researcher提供15-20篇参考论文，对于AutoResearchClaw只提供研究主题文本。

**第二步：运行系统。** 在统一的计算环境中运行系统（Docker容器，相同GPU规格），记录完整的运行日志。对于Code-Aware任务，确保封装器同步运行以收集实验数据。

**第三步：收集产出。** 论文文本（LaTeX或结构化JSON）、实验代码仓库（对于Code-Aware任务）、`results.json`和`execution.log`（对于Code-Aware任务）、引用列表（用于引用准确性验证）。

**第四步：Text-Only评审。** 使用五模型评审面板对论文进行九维度Text-Only评分。计算各评审器评分的均值和标准差。

**第五步：Code-Aware评审（如适用）。** 对于Code-Aware任务实例，运行编造检测清单逐项验证——数值声明与results.json比对、方法组件代码检查、引用CrossRef API验证。计算编造指数。

**第六步：汇总报告。** 生成包含九维度评分、编造指数、评审器间一致性指标和人类基线比较的完整评估报告。

### 5.2 各系统评估适配要点

**AI-Scientist v1：** 需要提供代码模板作为Level-1任务的起点。适合评估完整论文生成和研究提案生成。适配Code-Aware需要封装器。局限性：不支持文献综述和论文扩展任务。

**AI-Scientist v2：** 相比v1去除了模板依赖，更适合Level-2和Level-3任务。树搜索机制产生的中间想法可作为研究提案的输出。VLM优化的图表质量可作为写作质量维度的加分项。

**AI-Researcher：** 最适合全面评估——支持全部六种任务类型。Scientist-Bench的设计理念与SciEval-Bench最接近。多Agent架构产生的代码质量较高。适配Code-Aware难度低于AI-Scientist。

**AutoResearchClaw：** 适配难度最低——已有结构化数据输出。23阶段的完整管线使其可以参与从Level-1到Level-3的全面评估。4层引用验证使其在引用完整性维度上预期表现出色。Sentinel Watchdog和VerifiedRegistry天然对应编造检测。

**DeepScientist：** 目标驱动的贝叶斯优化架构特别适合Level-3（全自主）评估。Findings Memory可直接转化为结构化数据。5000+想法的探索量使其在创新性维度上有数据支撑。局限性：仅支持ML领域任务，且需要SOTA代码作为起点。

**SibylSystem：** MCP工具架构（literature_review、experiment_design、gpu_execution、paper_writing、peer_review）与SciEval-Bench的任务类型有直接映射关系。GPU并行执行适合大规模评估。局限性：数据导出需要额外开发，目前仅限ML领域。

### 5.3 统一运行环境

为确保公平比较，所有系统应在相同环境中运行：

```
硬件：1× NVIDIA A6000 (48GB) 或 1× H100 (80GB)
软件：Docker容器，Python 3.10，PyTorch 2.x
网络：允许访问 arXiv API、Semantic Scholar API、GitHub
时间限制：Level-1 2小时，Level-2 6小时，Level-3 24小时
成本限制：Level-1 $10，Level-2 $30，Level-3 $100
```
