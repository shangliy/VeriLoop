# VeriLoop

**端到端可验证自主科研流水线：90+ 全周期模块化科研技能 × 确定性硬证据门控 × 纯路径跨模型阻断审计。**

- **GitHub 仓库：** [https://github.com/shangliy/VeriLoop](https://github.com/shangliy/VeriLoop)
- **论文（arXiv 预印本）：** [paper/main.pdf](paper/main.pdf)（源码：[paper/main.tex](paper/main.tex)）
- **论文（ICML 2027 官方 8 页双盲版）：** [paper/main_icml2027.pdf](paper/main_icml2027.pdf)（源码：[paper/main_icml2027.tex](paper/main_icml2027.tex)）
- **English README:** [README.md](README.md) · **第三方归属与许可说明：** [NOTICE.md](NOTICE.md) · [上游 ARIS 原版文档](docs/ARIS_UPSTREAM_README_CN.md)
- **论文自审计通过：** `trace_numbers.py` **69/69 全量可追溯（0 未追溯，0 符号反转）** · `citation_audit.py` **26/26 引用校验通过（0 异常）**

---

## 为什么选择 VeriLoop？

自主科研 Agent 很少因为「忘记输出文件」而失败；它们真正的失败模式是**代码正常跑完，却在报告中写出与原始日志、代码路径或统计结果相矛盾的数值与结论**。**VeriLoop** 将完整科研流程与硬验证机制合二为一，打造更完备、更便捷、更高效的科研流水线：

1. **更完备（90+ 全周期技能 + 顶会写作引擎）：** 覆盖选题探索、文献检索与持久化 Research Wiki、多随机种子实验、双层硬门控审计、单轮靶向闭环修复、**内置 [Best-Paper-Writing-Skill](https://github.com/shangliy/Best-Paper-Writing-Skill)（60 篇顶会获奖论文写作规范 + Okabe-Ito 绘图样式 + 自动文风/图表质检）**、LaTeX 论文生成与 Rebuttal 全流程。
2. **更便捷（统一入口 `./veriloop`）：** 单一零依赖命令行工具统一调度 `gate` / `claims` / `board` / `demo` / `live` / `install` / `test` / `lint-paper` / `audit-paper`，开箱即用。
3. **更高效（`$0` 确定性快速失败 + 四合一投稿自检 + 预算熔断）：** 第一层在毫秒级以零 API 成本拦截数值编造、正负号反转、6 类 Python AST 代码作弊、SHA-256 账本篡改、缺失 BibTeX 与 AI 写作/图表硬伤；仅对通过确定性校验的工作区触发纯路径跨模型硬阻断审计，并内置严格 USD 熔断器。

---

## 112 次受控实测结果

在覆盖 `SciIntegrity-Bench` 全部 `11/11` 陷阱类与 `AIScientistPitfalls` 全部 `4/4` ML 陷阱的 **112 次受控实测**（总 API 花费 `$46.49 / $50.00`）中：

| 治理范式 | 主评测阻断漏报率（`n=15`） | 精确 McNemar `p` | 核心机制发现 |
|---|---:|---:|---|
| **存在性门控（`B1`，EviBound 式）** | `0/15` 拦截（全部放行） | — | 只查产物文件是否存在，无法发现代码缺陷与编造指标 |
| **建议型跨模型审稿（`B2`，ARIS 式）** | `13/15`（`86.7%`） | — | 建议性交付放行阻断缺陷；执行者摘要使 `BLOCK_MISCONDUCT` 从 `90.9%` 软化至 `36.4%`（`p=0.031250`） |
| **同模型全新会话复审（`Ours_ccr`, `n=11`）** | 仅拦截 `2/11`（`18.2%`） | `p = 0.003906` | **同源谄媚：** `5/11 (45.5%)` 在 JSON 列出无效声明却仍投 `APPROVE` |
| **VeriLoop（`Ours_full`）** | **`0/15`（`0.0%`）** | **`p = 0.000244`** | **0% 漏报**、干净任务 **0% 误杀（`3/3`）**、SPR 单轮闭环修复清除 **4/4** 不端 |

> **真实双模型实战（`./veriloop live`，花费 `$0.99`）：** `claude-haiku` 执行完整分类实验，`codex-cli` 纯路径审稿在 Round 1 零摘要条件下直接从原始代码与日志揪出 5 项真实方法学硬伤（95% 置信区间跨零、测试集暴露、用优化器随机种子冒充独立划分、缺失多数类基线、过度宣称收敛）并硬阻断（`rc=2`）；Round 2 完成基线补齐与措辞修正，且 G1 SHA-256 哈希实时捕获日志覆盖漂移。

---

## 快速上手

```bash
git clone https://github.com/shangliy/VeriLoop.git
cd VeriLoop

# 1. 运行全部 30 项离线测试 + 技能目录完整性校验（零费用）
./veriloop test

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

# 6. 四合一论文自检（数值溯源 + BibTeX + Best-Paper 摘要/引言/图表质检）与真实双模型实战
./veriloop audit-paper
./veriloop lint-paper --draft paper/sec/0_abstract.tex paper/sec/1_intro.tex --tex paper/main_icml2027.tex --layout two
./veriloop live --budget-limit 1.50
```

---

## 开源许可与归属

**VeriLoop** 核心代码采用 **MIT License** 开源：工作流技能库基于 MIT 协议的上游 **ARIS**（[wanshuiyin/Auto-claude-code-research-in-sleep](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep)，`arXiv:2605.03042`）扩展构建，并原生集成 **CC BY 4.0** 协议的 **[Best-Paper-Writing-Skill](https://github.com/shangliy/Best-Paper-Writing-Skill)**（`skills/bestpaper-writing/`）。完整版权与模块边界详见 [LICENSE](LICENSE) 与 [NOTICE.md](NOTICE.md)。如在学术工作中使用本仓库，请同时引用 VeriLoop 与 ARIS。
