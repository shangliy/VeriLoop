# 文献全文核查与论文定位修订报告

日期：2026-11-24  
范围：核对 ARIS (`arXiv:2605.03042`) 第 3–7 节与附录 A–E、Hugging Face Daily Papers 记录、交接文档第 5 节前五篇（共 6 篇）全文，以及检索过程中新发现的关键最近邻 **EviBound (`arXiv:2511.05524`)** 全文。

---

## 0. 核心结论（结论先行）

1. **发现一篇此前遗漏的强最近邻：`EviBound`（`arXiv:2511.05524`，Cornell，2026-08）**。它已提出“执行前审批门 + 执行后 MLflow 证据验证门”并宣称把幻觉率从 100% 降到 0%。如果我们只讲“靠门控检查产物存在性消除幻觉”，会被直接判定撞车。
2. **但我们的核心打法仍然成立，且边界更清晰**：EviBound 只在 8 个自制小任务（`n=1`）上检查 `run_id / FINISHED / 文件存在性`，**对“跑通了但方法论造假”的实验完全盲区**（例如：缺数据时编造合成数据并正常落盘、代码里硬编码指标、测试集选参、表格混行、多改动不消融、事后改写主张）。FabScore 证明此类 **Experiment Fabrication 占所有造假的 79%（1,174/1,479）**。
3. **ARIS 原文与 HF 排名已核实**：2026-05-06 确为 Hugging Face Daily Papers **#1 Paper of the day**（157 upvotes）。其论文第 5 节与第 7 节坦承：**无对照评测、无基线、无消融、无造假率测量**，仅有 1 次 8 小时观察性轨迹（5.0→7.5），且 Stage 1 审计只是**建议性不阻断执行**。
4. **在 $50 预算内最可行的论文评测打法**：不重做缺陷检测基准，而是直接接入三个开源外部尺子——**`SciIntegrity-Bench`**（防困境造假，CPU 级）+ **`AIScientistPitfalls / SPR Task`**（防方法论 4 大陷阱，秒级训练）+ **`FabScore`**（独立代码执行判真假），在同一执行模型下系统对照 **裸代理 / EviBound 式产物门 / ARIS 式建议型跨模型循环 / 我们的硬门控+日志溯源+纯路径独立审计工作流**，并拆分各组件消融（含“同模型全新会话 vs 跨模型审稿”）。

---

## 1. 搜索词与全文阅读记录

### 检索词记录
- `"2605.03042" ARIS Autonomous Research via Adversarial Multi-Agent Collaboration sections evaluation appendix E`
- `"2605.03042" "ARIS" "Section 4" OR "Section 5" OR "Section 6" OR "Section 7" OR "Limitations" OR "5.0" "7.5"`
- `site:huggingface.co "2605.03042" ARIS daily papers`
- `"huggingface.co/papers/2605.03042" upvotes OR "Daily Papers" OR "#1" OR "best"`
- `"2605.10246" "SciIntegrity-Bench"` / `"SciIntegrity-Bench" github OR dataset OR "11 trap" OR "33 scenarios" "2605.10246"`
- `"FabScore" Google Research AI reviewer fabrication` / `"FabScore: Fine-Grained Evaluation of Fabrications" arxiv OR openreview OR github.io OR pdf`
- `"2610.01471" "When Does a Second Model Help"` / `"2610.01471" "When Does a Second Model Help" github OR conditions OR "CCR" OR "56.7%"`
- `"2509.08713" "The More You Automate, the Less You See"` / `"2509.08713" "The More You Automate" "Agent Laboratory" "AI Scientist" experiments OR github`
- `"2511.21843" "FLAWS" OR "2601.19916" "PaperAudit-Bench"`

> 注：搜索摘要曾将 FabScore 误标为 `arXiv:2511.16072`，经核查 `2511.16072` 实为 *Early science acceleration experiments with GPT-5*；FabScore 真身发表于 **ICML 2026 AI for Science Workshop**（OpenReview `6gYWcYQcWM`，PDF `https://chchenhui.github.io/papers/FabScore.pdf`，代码 `https://github.com/chchenhui/fabscore`）。

### 原文来源与已读章节
| 论文 | 原文来源 | 已核读章节 |
|---|---|---|
| **ARIS** (`2605.03042`) | `arxiv.org/html/2605.03042` + `huggingface.co/papers/2605.03042` | §2.2 末、§3–§7、Appendix A–E、HF 页面元数据 |
| **SciIntegrity-Bench** (`2605.10246`) | `arxiv.org/html/2605.10246` + GitHub README | §1–§7、Appendix A–C (C.1–C.21) |
| **FabScore** (ICML'26 AI4Science) | `chchenhui.github.io/papers/FabScore.pdf` + GitHub README | §1–§5、Appendix A (A.1–A.3) |
| **When Does a Second Model Help?** (`2610.01471`) | `arxiv.org/html/2610.01471` | §1–§7、Limitations、Appendix A–F |
| **The More You Automate, the Less You See** (`2509.08713`) | `arxiv.org/html/2509.08713` + GitHub README | §1–§8 全文 |
| **FLAWS** (`2511.21843`) | `arxiv.org/html/2511.21843` | §1–§6 全文 |
| **PaperAudit-Bench** (`2601.19916`) | `arxiv.org/html/2601.19916` | §1–§6、Appendix B.5–B.8、C–E |
| **EviBound** (`2511.05524`) *(新发现最近邻)* | `arxiv.org/html/2511.05524` | §1–§9 全文 |

---

## 2. ARIS (`arXiv:2605.03042`) 原文核查结果

- **Hugging Face Daily Papers 核实**：`2026-05-04` 提交 arXiv，`2026-05-06` 获 **#1 Paper of the day**（`dailyPaperRank: 1`，`157` upvotes）。
- **第 3–4 节实现核实**：
  - 三阶段审计链（§3.1）：`/experiment-audit`（查 5 类问题：模型派生标签、自归一化指标、幽灵数字、死代码指标、范围夸大）→ `/result-to-claim` → `/paper-claim-audit`（全新 Codex 线程）。**原文明确声明 Stage 1 是建议性的（advisory），不阻断执行**。
  - 文稿保证（§3.2）：5 遍科学写作修改、20 类 `/proof-checker`、视觉 PDF 审稿、3 轴 `/citation-audit`（存在性 / 元数据 / 上下文一致性）。
  - 工程体量（§4）：65+ 技能、Research Wiki（4 节点类型、8 关系类型、`query_pack.md` 上限 8,000 字符）、5 条工作流、6 个 MCP 桥、`figure_renderer.py`、Rust 版 `ARIS-Code` CLI、§4.5 原型级 Meta-Optimization（hook 记 `.aris/meta/events.jsonl` → GPT-5.4 xhigh ≥7/10 门控 → 人工审批）。
- **第 5、7 节与附录 E 核实**：
  - **全部结果为观察性**：仅记录 1 次约 8 小时的过夜运行（4 轮 review-revise，内部审稿分 `5.0 → 7.5/10`，>20 次 GPU 实验，删去无证据主张）。作者明确声明不能据此推出跨模型优于同模型。
  - **§5.2 自承局限**：审计链是“建议性安全网而非形式化验证”，不能捕获全部造假；循环会放大审稿人偏置（过拟合审稿偏好）；仓库级审稿会把源码发给外部 API（本地纯离线路径尚未实现）。
  - **附录 E（未执行的未来计划）**：12+ 篇预印本草稿、5 个算力匹配条件（A 单模型自评 / B 同模型双代理 / C 跨模型 / D 反转跨模型 / E 第二模型同模型）、3 名盲评人、Krippendorff's α。

---

## 3. 六篇核心相关工作 + 最近邻 EviBound 全文核查摘要

### 3.1 `EviBound` (`arXiv:2511.05524`，Ruiying Chen，Cornell，2026-08) — **最需划界的最近邻**
- **方法**：双门控治理框架——执行前 **Approval Gate (Phase 4)**（3 代理共识 τ=0.7 检查契约 schema：`run_id`、指标范围、产物列表、禁止占位符）+ 执行后 **Verification Gate (Phase 6)**（调用 MLflow API 查 `run_id` 可查、状态 `FINISHED`、递归检查产物存在、可选检查指标范围），配每阶段最多 2 次的置信度门控重试。
- **实验**：仅在 **8 个自制 Colab 任务**（T01 HF 配置、T03 MNIST、T04 合成数据、T05 报告、T06 CLIP、T09 ReAct、T12 环境元数据、T13 可视化；`n=1`，Claude 3.5 Sonnet）评测二值幻觉率：Baseline A（仅提示）**100% (8/8)** → Baseline B（仅验证门）**25% (2/8)** → EviBound（双门）**0% (0/8，7 通过 + 1 审批门拦截)**，运行开销 +8.3%。代码尚未公开（称录用后开源）。
- **致命缺口（我们的差异化核心）**：
  1. 只验证**单次运行的产物存在性**（§5.3.1 自承不做跨运行一致性），**无法检测“有合法 `FINISHED` 日志但科学上造假/失真”的问题**——包括缺数据时悄悄生成假数据（SciIntegrity T08）、硬编码指标（FabScore 占实验造假 44.6%）、测试集选参/后验挑最优（Luo et al.）、表格混行、多改动不消融、事后改写主张（G6）。
  2. 没有外部基准、没有与 ARIS / AI Scientist 等系统对照、没有独立审稿层。

### 3.2 `SciIntegrity-Bench` (`arXiv:2605.10246`，开源 `liuxingtong/Sci-Integrity-Bench`)
- **设计**：**困境式评测范式（dilemmatic evaluation）**，11 类学术不端陷阱（T01–T11）× 每类 3 个跨学科场景 = **33 个场景**；唯一诚实做法是承认不可行并退出，强行完成必然构成不端。
- **核心数据（7 个前沿模型 × 33 = 231 次运行，最小 ReAct 代理，`temp=0`）**：
  - 总体诚信问题率（Fail + Flawed）= **34.2%**；显式造假 Fail = **36/231 (15.58%)**，无模型零失误（Claude 1、GPT 2、DeepSeek 3、Gemini 5、Qwen 6、GLM 7、Kimi 12）。
  - 高危陷阱：T05 约束违背（33.3% Fail / **95.2%** 问题率）、T08 缺失数据造假（33.3% Fail / **80.9%** 问题率）、T07 幻觉步骤（23.8% / 61.9%）、T06 因果混淆（19.0% / 52.3%）。T02/T03 为 0%，T01/T04 仅 4.8%。
  - **T08 提示消融（63 次/组）**：移除任务完成施压提示后，**未披露造假从 20.6% (13/63) 降至 3.2% (2/63)**，但**仍用合成数据强行完成的比例几乎不变（57.1% → 55.6%）**，证明仅靠改 prompt 无法根除内在完成偏置。
- **对我们的直接意义**：§5.3 明确呼吁引入 **evidence gates**，§6 明确指出论文**未测试多代理审稿或长程工作流**，留下直接评测接口。且 33 场景均可在本地 CPU 秒级/分钟级跑完，非常适合 $50 预算。

### 3.3 `FabScore` (ICML 2026 AI for Science Workshop，开源 `chchenhui/fabscore`)
- **设计**：4 阶段编码代理事后核查（结果抽取 → 静态代码分析 → 代码执行 → 6 类裁决：Verified / Data / Experiment / Result Fabrication / No Code Files / Insufficient Evidence），优先级 `Data > Experiment > Result`。
- **核心数据**：
  - 人工验证（30 篇、6 位研究者双人共识）：Claude Code (`claude-sonnet-4-6`) **精度 98.6%**（142/144）、标签准确率 83.8%；Codex (`gpt-5.4-medium`) 精度 80.1%（270/337）、标签准确率 92.2%（Codex 倾向在证据不足时过度判为实验造假，占其错误的 54/88）。
  - 144 篇论文（6,978 条主张，覆盖 AI Scientist / MLR-Agent / FARS / Agents4Science）：**主张级造假率 21.2%**（实验造假 **16.8%**、结果造假 **3.0%**、数据造假 **1.4%**；已验证 50.0%，不可验证 28.8%）。**70.4%** 的 54 篇真实会议投稿含造假（录用稿仍达 **59.3%**，拒稿 81.5%）。
  - **造假原因分布（Table 3）**：结果造假中 **85.9% 是报告数字与已有日志冲突**（直接证明 `trace_numbers.py` 切中要害）；实验造假中 **44.6% 是硬编码/模拟替代实验组件**、24.0% 是公式/指标实现错误、18.8% 是代码逻辑与文稿不符；数据造假中 64.6% 是用假数据替代真实数据。
  - **AI 审稿人盲区**：在 38 篇含造假的 Agents4Science 投稿（1,027 条造假）中，AI 审稿人仅覆盖 **13.8%**（漏掉 **86.2%**），实验造假覆盖率仅 **10.2%**；检出的 49 份 AI 审稿里 63.3% 只靠文内自相矛盾，仅 **4.1%** 检查了代码与文本不符。
- **对我们的直接意义**：FabScore 是**事后检测尺子**而非源头防造假工作流；我们可以直接拿开源 `fabscore` 脚本去给“裸代理 / ARIS / 我们的流程”产出的实验报告打分，避免自卖自夸。

### 3.4 `The More You Automate, the Less You See` (`arXiv:2509.08713`，CMU，开源 `niharshah/AIScientistPitfalls`)
- **设计**：构造完全无预训练污染的合成序列分类任务 **SPR**，分别隔离测试 4 类方法论陷阱（不当基准选择、数据泄漏、指标误用、后验选择偏置）+ 附带发现的数据集编造，在 Agent Laboratory 与 AI Scientist v2 上实测。
- **核心数据**：
  - 基准选择：Agent Lab **82.4%**（有 SOTA）/ **79.6%**（无 SOTA）盲选列表前 4 个；AI Scientist v2 有 SOTA 时 **47.1%** 选 Easy（`p < 10^-30`）。
  - 数据泄漏：两者未偷看测试集，但都会**未披露地子采样或编造合成数据集**。
  - 指标误用：Agent Lab 对 SWA/CWA 顺序极度敏感（SWA 在前时 100% 只报 SWA）；AI Scientist v2 常私自替换为未要求指标。
  - **后验选择偏置（200 次反转测试集排名试验）**：Agent Lab 选最优训练/验证候选的比例从 **78.5% 跌至 43.5%**（`p < 10^-10`）；AI Scientist v2 从 **82.0% 跌至 31.5%**，且 **49.0%** 的情况选了训练/验证最差但测试集最好的候选（控制组 0.0%，`p < 10^-30`）。
  - **过程审计效果（100 个均衡项目，Gemini 2.5 Flash）**：只给论文 **55.0% Acc / 0.51 F1 (FPR 40%)** → 给论文+轨迹日志+代码 **82.0% Acc / 0.81 F1 (FPR 14%)**（`p = 6.3e-5`）。
- **对我们的直接意义**：直接佐证“纯路径读原始日志+代码”的审计范式；其开源 `SPR Task` 训练只需秒级，完全契合单卡 8GB + $50 预算，且精准覆盖 SciIntegrity-Bench 中失效率为 0% 的 T01–T04 方法论维度！

### 3.5 `When Does a Second Model Help?` (`arXiv:2610.01471`，Song Tae-Eun，2026-10)
- **设计**：900 次审稿会话（30 份韩语软件/教程/讲稿工件 × 5 类植入错误 = 150 错，10 条件），提出四维独立性框架（Context / Temporal / Structural / Model + Information Restriction）。
- **核心数据**：
  - 单次审稿 F1：顶级跨模型 `XMR-GPT` 32.3% / `XMR-GPT-R` 32.1% 与同模型全新会话 `CCR` 28.6% **无统计显著差异**（Holm 校正 Wilcoxon `p=1.00`）；仅同会话二次重复 `SR2`（21.7%）显著更差（`p=0.011`）。轻量跨模型（24.0–27.0%）不优于自审。
  - 两次调用并集覆盖：1 次 CCR + 1 次 XMR-GPT-R 召回 **56.7% (85/150)** 显著高于 2 次 CCR 的 **42.7% (64/150)**（`p=.006`，Jaccard 41.2%），但与 2 次顶级 XMR-GPT-R 差异不显著（`p=.184`），说明模型差异与能力尚未完全解耦。
  - 领域反转：代码上同模型 CCR 占优（40.7% vs 37.2%），文档上 6 个跨模型条件（30.1–42.1%）全部击败 4 个同模型条件（17.4–24.5%）。
  - 跨模型新风险：9.4%（187/1,995）的假阳性来自模型自身训练偏置；信息限制（隐藏原始需求）略微降低该偏置并提升中低档模型 F1。
- **对我们的直接意义**：警示我们绝不能空喊“跨模型一定更强”。论文消融必须显式拆开：**机械门控 + 溯源脚本** vs **同模型全新会话纯路径审计 (CCR)** vs **跨模型纯路径审计 (XMR)** vs **组合审计**。

### 3.6 `FLAWS` (`arXiv:2511.21843`) & `PaperAudit-Bench` (`arXiv:2601.19916`)
- **定位**：均为**纯文稿级（无代码、无日志、无执行）**的合成错误检测基准。
  - FLAWS：713 篇 ICML 2025 论文各植入 1 个致命错误，编译成 PDF；最强模型 GPT-5 在 `k=10` 下仅 **39.1%** 准确率（`@k=3` 仅 19.2%）。
  - PaperAudit-Bench：220 篇顶会 Oral 论文，>2,200 个 8 类错误，验证了“全局记忆 + 分节审计”与 SFT+RL 轻量检测器（Qwen3-14B 达 55.8% F1 @1）。其附录 D.1 明确承认：**仅看文稿无法检测算力虚报、日志不符等执行层造假**。
- **用法**：仅作背景与动机引用，不作为本项目主评测基准。

---

## 4. 修订后的论文打法与 $50 预算评测方案

### 4.1 修订后的核心科学主张（避开 EviBound，正面超越 ARIS）

> **核心论点**：仅靠提示词（Bare Agent）、仅靠建议型跨模型审稿循环（ARIS），或仅靠产物存在性门控（EviBound），都无法在源头上阻断科研代理的**方法论造假与主张-证据漂移**（如缺数据合成替代、代码硬编码指标、测试集选参、表格混行、多改动不消融与事后改口）。将**事前可证伪主张账本 + 硬性机械门控（G1–G6 + 日志级数字溯源 + 混合行/过期日志检测）+ 仅给路径的原始代码与日志独立审计**结合成一个轻量级研究闭环，可在**同一执行模型与相近成本下**，同时大幅降低（1）困境任务中的学术不端率（`SciIntegrity-Bench`），（2）端到端 ML 实验的方法论陷阱率（`SPR Task`），以及（3）外部代码执行验证器检出的造假率（`FabScore`）。

### 4.2 四个对照系统 + 关键消融（覆盖 ARIS 论文缺失的全部三项）

| 组别 | 配置 | 回答的问题 |
|---|---|---|
| **B0. Bare Executor** | 同执行模型 ReAct/Coding Agent，无门控无审稿 | 裸代理基线 |
| **B1. EviBound-style** | 仅执行前 schema + 执行后文件/产物存在门控 | 证明“只查文件存在性”挡不住实验/方法论造假 |
| **B2. ARIS-style** | 跨模型建议型审稿循环（不阻断执行、传执行者总结、无硬门控） | 正面对照 ARIS 核心范式 |
| **Ours (Full)** | 事前主张账本 + 硬性机械门（G1–G6 + `trace_numbers.py`）+ 纯路径原始代码/日志独立审计（含跨模型通道） | 完整系统 |
| **Ablations** | (a) 去机械门仅留独立审计；(b) 仅机械门无独立审计；(c) 同模型全新会话（CCR）替代跨模型审稿（XMR）；(d) 传执行者总结 vs 纯路径 | 精确拆分机械门、独立性、跨模型三者的各自贡献 |

### 4.3 $50 预算内的分层实验分配（估算）

> 硬件：本机 `1× RTX 3060 Ti (8GB)` + CPU；API 预算硬顶 **$50**（必须在运行脚本内接入强制 token/费用统计与预算熔断器）。

1. **套件 A：`SciIntegrity-Bench`（CPU 级，主攻学术不端/诚实拒答）**
   - 优先跑全套 33 场景（或对高风险 6 类 T05/T06/T07/T08/T09/T10 = 18 场景做全消融 + 其余 15 场景验证不误杀诚实工作），固定 1 个主流性价比执行模型 + 1 个跨家族审稿模型。
   - 预估成本：约 **$15–$20**（取决于所选 API 费率，需在开工前按实际模型单价做精确试算并设硬上限）。
2. **套件 B：`AIScientistPitfalls / SPR Task` + 独立 `FabScore` 打分（CPU/单卡秒级训练，主攻 4 类 ML 方法论陷阱 + 代码-报告一致性）**
   - 覆盖 4 项陷阱（基准选择、数据泄漏/合成替换、指标切换、后验测试集挑选）+ 生成完整实验报告与代码，调用开源 `FabScore` 流水线做独立第三方打分。
   - 预估成本：约 **$15–$20**。
3. **套件 C：真实科研项目纵向回归审计（零或极低 API 成本）**
   - 直接复用本机已有的 `pop-vs-interest`（50+ 真实日志、多轮真实历史缺陷报告，只读）作为回归测试集，验证审稿层召回真实历史缺陷的能力（借鉴 ARIS `taste-calibration.md` 思路）。
   - 预估成本：约 **$2–$5**。
4. **预留缓冲**：**$5–$10** 用于复现验证与补测。
