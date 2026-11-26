# VeriLoop

**端到端可验证自主科研流水线：90+ 全周期模块化科研技能 × 确定性硬证据门控 × 纯路径跨模型阻断审计。**

- **GitHub 仓库：** [https://github.com/shangliy/VeriLoop](https://github.com/shangliy/VeriLoop)
- **论文评测状态：** **v2 冻结产物重测重构中**（arXiv v1 已在投稿前经独立原始日志审计主动撤回，详见下方「评测状态说明」）
- **English README:** [README.md](README.md) · **第三方归属与许可说明：** [NOTICE.md](NOTICE.md) · [上游 ARIS 原版文档](docs/ARIS_UPSTREAM_README_CN.md)

---

## 为什么选择 VeriLoop？

自主科研 Agent 很少因为「忘记输出文件」而失败；它们真正的失败模式是**代码正常跑完，却在报告中写出与原始日志、代码路径或统计结果相矛盾的数值与结论**。**VeriLoop** 将完整科研流程与硬验证机制合二为一，打造更完备、更便捷、更高效的科研流水线：

1. **更完备（90+ 全周期技能 + 顶会写作引擎）：** 覆盖选题探索、文献检索与持久化 Research Wiki、多随机种子实验、双层硬门控审计、单轮靶向闭环修复、**内置 [Best-Paper-Writing-Skill](https://github.com/shangliy/Best-Paper-Writing-Skill)（60 篇顶会获奖论文写作规范 + Okabe-Ito 绘图样式 + 自动文风/图表质检）**、LaTeX 论文生成与 Rebuttal 全流程。
2. **更便捷（统一入口 `./veriloop`）：** 单一零依赖命令行工具统一调度 `gate` / `claims` / `board` / `demo` / `live` / `install` / `test` / `lint-paper` / `audit-paper`，开箱即用。
3. **更高效（`$0` 确定性快速失败 + 四合一投稿自检 + 预算熔断）：** 第一层在毫秒级以零 API 成本拦截数值编造、正负号反转、6 类 Python AST 代码作弊、SHA-256 账本篡改、缺失 BibTeX 与 AI 写作/图表硬伤；仅对通过确定性校验的工作区触发纯路径跨模型硬阻断审计，并内置严格 USD 熔断器。

---

## 评测状态说明（v2 冻结产物重测进行中）

> [!WARNING]
> **v1 论文旧结论已主动暂停并撤出 README：** 在 arXiv 上传前，我们通过独立的原始日志逐行复核发现了 v1 评测中的核心方法学漏洞（同义反复的「泄漏率」指标、聚合脚本事后硬编码覆盖、把小数/百分比单位误报当成机械门控成果、消融未冻结同一产物且混杂模型强弱、缺少独立真值与干净产出放行率）。
>
> 遵循 VeriLoop 自身的科研诚信底线，我们已**暂停 arXiv v1 发布**、新增 [`milestone-dual-audit`](skills/milestone-dual-audit/SKILL.md)（阶段性成果最新 Gemini + 最新 Claude 并行独立评审），并正在执行 **v2 冻结产物重测**：
> 1. **冻结 SHA-256 产物库 + 独立真值标签**：同时包含 `claude` 与 `codex` 执行者产物，改报 Precision / Recall / F1 / FPR / 干净报告放行率（废除同义反复指标）。
> 2. **真·配对 2×2 因子实验**：在同一批冻结工作区上解耦同/跨家族与模型强弱，并做 `Path-Only` vs `+Summary` 的多次重复方差估计。
> 3. **冻结版机械门控盲测**：修复单位换算与参考打印误报后冻结版本，在完全未见任务上零事后覆盖重测。
> 4. **全量评测记录公开可复现**：公开脱敏后的原始评测 JSONL 与独立真值标签表。

当前 **VeriLoop** 工程工具链（`./veriloop` 统一 CLI、确定性门控、`milestone-dual-audit`、`bestpaper-writing`、37 项离线测试与 `./veriloop demo`）均可直接稳定使用。

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
