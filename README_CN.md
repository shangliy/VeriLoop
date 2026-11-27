# VeriLoop

**端到端可验证自主科研流水线：90+ 全周期模块化科研技能 × 确定性硬证据门控 × 纯路径跨模型阻断审计。**

- **GitHub 仓库：** [https://github.com/shangliy/VeriLoop](https://github.com/shangliy/VeriLoop)
- **论文（arXiv v2 预印本）：** [paper/main.pdf](paper/main.pdf)（源码：[paper/main.tex](paper/main.tex)）
- **论文（ICML 2027 官方 8 页双盲版）：** [paper/main_icml2027.pdf](paper/main_icml2027.pdf)（源码：[paper/main_icml2027.tex](paper/main_icml2027.tex)）
- **English README:** [README.md](README.md) · **第三方归属与许可说明：** [NOTICE.md](NOTICE.md) · [上游 ARIS 原版文档](docs/ARIS_UPSTREAM_README_CN.md)
- **全量公开可复现：** 全部 16 个冻结 SHA-256 工作区、独立 `file:line` 真值表、245 次配对审稿 JSONL、21 个未见盲测取证表与零覆盖脚本均已提交至本仓库

---

## 为什么选择 VeriLoop？

自主科研 Agent 很少因为「忘记输出文件」而失败；它们真正的失败模式是**代码正常跑完，却在报告中写出与原始日志、代码路径或统计结果相矛盾的数值与结论**。**VeriLoop** 将完整科研流程与硬验证机制合二为一，打造更完备、更便捷、更高效的科研流水线：

1. **更完备（90+ 全周期技能 + 顶会写作引擎）：** 覆盖选题探索、文献检索与持久化 Research Wiki、多随机种子实验、双层硬门控审计、单轮靶向闭环修复、**内置 [Best-Paper-Writing-Skill](https://github.com/shangliy/Best-Paper-Writing-Skill)（60 篇顶会获奖论文写作规范 + Okabe-Ito 绘图样式 + 自动文风/图表质检）**、LaTeX 论文生成与 Rebuttal 全流程。
2. **更便捷（统一入口 `./veriloop`）：** 单一零依赖命令行工具统一调度 `gate` / `verify-cites` / `fetch-bib` / `bind` / `review-ui` / `audit-pdf` / `gpu-showcase` / `claims` / `board` / `demo` / `live` / `install` / `test` / `lint-paper` / `audit-paper` / `milestone-audit` / `eval-v2`，开箱即用。
3. **更高效（`$0` 确定性快速失败 + 四合一投稿自检 + 预算熔断）：** 第一层在毫秒级以零 API 成本拦截数值编造、正负号反转、6 类 Python AST 代码作弊、SHA-256 账本篡改、缺失 BibTeX 与 AI 写作/图表硬伤；仅对通过确定性校验的工作区触发纯路径跨模型硬阻断审计，并内置严格 USD 熔断器。

---

## 与其他开源科研 / 写论文工具的定位对比

> *如果别人都在卷“怎么让 AI 把论文自动写出来”，**VeriLoop** 卷的是“怎么让 AI 写出的每一组数字、每一张图、每一条引用和每一个结论都经得起审稿人逐行查账”。*

| 系统 / 工作 | 定位阵营 | 端到端实验→成文 | 执行期硬门控（AST/数值溯源） | 日志直出 LaTeX 宏/表/图 | 联网文献真伪与摘要核验 | 顶会文风/图表自动质检 | 交互式查账 UI（文↔日志联动） | 冻结对照与未见盲测 |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **AI-Scientist / v2**（Sakana） | 全自动科研 Agent | ✅（树搜索探索） | ❌（仅 LLM 自审） | ⚠️（定制脚本） | ⚠️（S2 检索，无硬阻断） | ❌ | ❌ | ❌ |
| **ARIS**（上游基座） | 跨模型科研工作流 | ✅（65+ 技能） | ❌（仅建议性 review） | ❌ | ❌ | ❌ | ❌ | ❌（单次轨迹） |
| **EviBound** | 执行期存在性门控 | ⚠️（Colab 编排） | ⚠️（仅查文件存在/`rc=0`） | ❌（MLflow 登记） | ❌ | ❌ | ❌ | ⚠️（8 个自建任务） |
| **FabScore / FLAWS / PaperAudit** | 事后造假审计基准 | ❌（事后尸检） | ⚠️（FabScore 事后复跑） | ❌ | ⚠️（部分核验） | ❌ | ❌ | ✅（事后论文集） |
| **PaperQA2 / OpenScholar / STORM** | 文献 RAG 与综述生成 | ❌（纯文献/写作） | ❌ | ❌ | ✅（强在全文 RAG 综述） | ❌ | ⚠️（引文溯源） | ✅（文献 QA 基准） |
| **AI-research-feedback**（`claesbackman`） | 多角色审稿与成果传播技能包 | ❌（成稿后反馈） | ❌（纯 LLM 子 Agent，建议性） | ❌ | ⚠️（LLM 检查，无 API 门控） | ✅（`voice-builder` + Beamer/网页） | ⚠️（`explain-diff` HTML） | ❌ |
| **Overleaf / Cursor + LaTeX** | 协作/IDE 写作环境 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌（无日志联动） | — |
| **VeriLoop（本仓库）** | **可验证端到端科研与写论文流水线** | ✅（**90+ 技能 + 真实 GPU 标杆**） | ✅（**`$0` AST + 有符号溯源 + G1–G7 + XMR**） | ✅（**零依赖读 TB/W&B/CSV→宏/表/PDF**） | ✅（**arXiv/Crossref/S2 硬门控 + 摘要核对 + `fetch-bib`**） | ✅（**60 篇顶会获奖规范 + Okabe-Ito**） | ✅（**零依赖分栏 `review-ui`**） | ✅（**16 冻结 + 21 未见，零覆盖**） |

---

## v2 冻结产物与未见盲测实证结果（零事后覆盖）

### 1. 16 个 SHA-256 冻结工作区配对实验（统一 Route A 规则：`9` 干净 / `7` 缺陷，`k=3`，`245` 次有效审稿）

| 评估器 / 组合 | Framing | `n` | Precision | Recall | F1 | FPR | Clean Yield | 3 次一致率 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **`layer1_mechanical`（`$0`）** | deterministic | 16 | `71.4%` | `71.4%` | `71.4%` | `22.2%` | `77.8%` | `100.0%` |
| **`claude-sonnet`** | `path_only` | 48 | `100.0%` | `85.7%` | `92.3%` | `0.0%` | `100.0%` | `100.0%` |
| **`claude-haiku`** | `path_only` | 48 | `91.3%` | `100.0%` | `95.5%` | `7.4%` | `92.6%` | `87.5%` |
| **`claude-haiku`** | `with_summary` | 48 | `95.5%` | `100.0%` | `97.7%` | `3.7%` | `96.3%` | `93.8%` |
| **`codex-cli`** | `path_only` | 48 | **`100.0%`** | **`100.0%`** | **`100.0%`** | **`0.0%`** | **`100.0%`** | `100.0%` |
| **`L1 ∪ claude-haiku`** | `path_only` | 48 | `72.4%` | `100.0%` | `84.0%` | `29.6%` | `70.4%` | — |
| **`L1 ∪ claude-haiku`** | `with_summary` | 48 | `77.8%` | `100.0%` | `87.5%` | `22.2%` | `77.8%` | — |
| **`L1 ∪ claude-sonnet`** | `path_only` | 48 | `75.0%` | `85.7%` | `80.0%` | `22.2%` | `77.8%` | — |
| **VeriLoop（`L1 ∪ codex-cli` 严格硬阻断）** | **`path_only`** | **48** | **`77.8%`** | **`100.0%`** | **`87.5%`** | **`22.2%`** | **`77.8%`** | — |

- **零成本预过滤与严格硬阻断权衡：** 在审稿后统一采纳的跨划分规则下（由已入日志原始计数按明确披露公式推导且**算术正确**的近似值，如 `H06` 的正态近似 CI `[0.9965, 0.9985]` 与未见 `04c` 的解析中点 `0.425`，统一归为 `CLEAN` 良性溯源缺口而非作弊；论文附录表 5 同步报告原 `H06=DEFECTIVE` 口径敏感性），`$0` 锁定 v2 Layer 1（`eval/v2_frozen/locked/`，样本内）可在触发付费审稿前拦截 **`5/7 (71.4%)` 真实缺陷**（其中 `4/7 = 57.1%` 为直接归因命中，`1/7` 为 `C05` 上由百万单位换算附带触发，详见 `eval/v2_frozen/counterfactual_c05.json`），只读 `codex-cli` 补齐剩余逻辑分母 bug（`H05`）与纯推断夸大（`C08`）达 `7/7 (100.0%)` 召回。严格硬阻断 Layer-1 数值告警会使干净产出率降至 `77.8%`（`H06`/`C04` 两例溯源缺口），因此工程最佳实践为：**高精度 AST 规则（样本内外均 `0.0%` FPR）直接硬阻断，数值溯源告警作为 `$0` 诊断证据送入 Layer 2 裁决**。
- **冻结配对关键发现：** 全部 LLM 在 5 例构造孪生缺陷上达 `100%` 检出，`claude-sonnet` 在自然分母 bug `H05` 上 6/6 漏检；工作区级配对检验显示在校准二元量表下附加执行者摘要零多数票翻转（`n=16` 工作区，`p=1.000000`）。v3 `trace_numbers.py` 的 `--data` 与负向措辞更新基于 `C04`/`09c`（样本内），需在新的未见集验证后方可主张 v3 样本外误报下降。

### 2. 21 个严格未见 `SciIntegrity-Bench` 场景锁定门控盲测（`$0.3187`）

在 SHA-256 锁定门控（`eval/v2_frozen/locked/trace_numbers_v2.py` `42c39cf4a4adeee1`、`audit_code_v2.py` `72dac256a9caf775`）零修改、零覆盖下（`18/21` 生成报告，经官方 checklist 核验全部 `18/18` 均规避陷阱为 `CLEAN`，其中 `12/18` 含 ≥3 位小数，详见 [eval/v2_unseen/unseen_forensic_audit.csv](eval/v2_unseen/unseen_forensic_audit.csv) 及已公开提交的 `eval/v2_unseen/workspaces/` 最小取证文件）：
- **静态 AST 样本外 FPR：** **`0/18 (0.0%)`**
- **数值级样本外 FPR：** **`2/289 (0.69%)`**（场景级 `2/18 = 11.1%`：`04c` 解析中点 `0.425` 与 `09c` 原始 CSV 值 `3.542`）。
- **样本外机械召回率：** 未测得（`0/18` 完成的未见运行触发基准陷阱）。

### 3. 长程真实 GPU 端到端标杆案例（`42` 次 RTX 3060 Ti 训练轨迹）

完整公开轨迹与复现脚本已提交至 [examples/gpu-overnight-research/](examples/gpu-overnight-research/)（`bash examples/gpu-overnight-research/run_reproduce.sh`）：在本地 **NVIDIA GeForce RTX 3060 Ti** 上执行可断点续跑的 42 次多随机种子 PyTorch AMP fp16 训练（总耗时 `5548.4s` / `92.47 min`，峰值显存 `593.0 MB`），覆盖 CIFAR-10 八阶段渐进消融（30 epochs × 3 seeds）与 Fashion-MNIST 六阶段跨数据集验证（15 epochs × 3 seeds）：
- **全阶段零费用硬门控：** `wiki/RESEARCH_WIKI.md` 全部 **`14/14` 阶段门控通过**（累计溯源 `1365` 个小数、`0` 未溯源、`0` 正负号错误、`0` AST 高危告警，中位耗时 `81.8 ms`）；4 条事前预注册假设全部通过 `G1–G7`（`0` 次事后改口）。
- **零手工抄数成文与全链路核验：** `./veriloop bind` 直接读取 126 个 TensorBoard/W&B 日志生成 `\vlC*` / `\vlF*` LaTeX 宏、Booktabs 表格与 Okabe-Ito 矢量图 → 编译出 [overnight_study.pdf](examples/gpu-overnight-research/paper/overnight_study.pdf)（**PDF 宏展开后 `75/75` 数值 100% 溯源**、`0` Type-3 字体、`0` 排版警告、`10/10` 参考文献通过 arXiv/Crossref/S2 联网核验）并生成交互式分栏审稿界面 [review_ui.html](examples/gpu-overnight-research/review_ui.html)。
- **真实科学发现：** CIFAR-10 上 `M7_SEResNet_Full` 达到 `0.9193±0.0004`（较 `M1_PlainCNN` 提升 `+14.06 pp`）；两个数据集一致复现了**校准反转现象**——无增强残差网 `M2_ResNet_Base` 极度过自信（`raw_ece=0.1261 → cal_ece=0.0098`，`T*=2.6460`），而 Label Smoothing（`T*=0.7234` / `0.6716`）与 Mixup（`T*=0.6449`）反转为欠自信，经验证集温度缩放 `T*<1` 后重新压回 `1.5%` 以下。

---

## 快速上手

```bash
git clone https://github.com/shangliy/VeriLoop.git
cd VeriLoop

# 1. 运行全部离线验证测试 + 技能目录完整性校验（零费用）
./veriloop test

# 1b. 从已提交的 v2 冻结语料直接复现零覆盖统计表（零费用）
./veriloop eval-v2 summary

# 2. 运行 10 秒零 API 闭环演示（Round 1 硬阻断 -> Round 2 修复放行 -> 生成 HTML 看板）
./veriloop demo

# 3. 对任意科研工作区执行双层硬门控
./veriloop gate \
  --workspace /path/to/project \
  --report report/report.md \
  --logs out/ \
  --scripts code/ \
  --reviewer-provider codex-cli \
  --out-json audits/veriloop_gate.json

# 4. 一键安装技能到 Claude Code / Codex CLI
./veriloop install --core-only         # 安装核心四件套（research-loop + verifiable-gate + bestpaper-writing + milestone-dual-audit）
./veriloop install --all               # 安装全部 90+ 科研技能 + 硬门控 + Best-Paper 写作 + 双模型里程碑审计

# 5. 阶段性成果双模型独立评审（最新 Claude + 最新 Gemini 并行纯路径审计 → 输出修正行动清单）
./veriloop milestone-audit --milestone M2-experiments --workspace . --artifacts paper/build_tables_and_figures.py paper/out/stats_summary.txt --dry-run

# 6. 四合一论文自检、联网三源文献硬核验、GPU 日志自动绑定与交互式 Web 审稿视图
./veriloop audit-paper
./veriloop fetch-bib 1512.03385 1708.07747
./veriloop verify-cites examples/gpu-dl-benchmark/paper/gpu_showcase.tex --bib examples/gpu-dl-benchmark/paper/refs.bib --online --check-claims
./veriloop gpu-showcase --skip-train   # 5 秒零 GPU 复现 RTX 3060 Ti 标杆案例 -> bind -> PDF -> 硬门控 -> review_ui.html
./veriloop review-ui --report paper/sec/3_experiments.tex --logs paper/out/stats_summary.txt --bib paper/refs.bib --out review_ui.html
```

---

## 开源许可与归属

**VeriLoop** 核心代码采用 **MIT License** 开源：工作流技能库基于 MIT 协议的上游 **ARIS**（[wanshuiyin/Auto-claude-code-research-in-sleep](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep)，`arXiv:2605.03042`）扩展构建，并原生集成 **CC BY 4.0** 协议的 **[Best-Paper-Writing-Skill](https://github.com/shangliy/Best-Paper-Writing-Skill)**（`skills/bestpaper-writing/`）。完整版权与模块边界详见 [LICENSE](LICENSE) 与 [NOTICE.md](NOTICE.md)。如在学术工作中使用本仓库，请同时引用 VeriLoop 与 ARIS。
