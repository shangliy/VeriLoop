# Verifiable-ARIS（可验证版 ARIS）

**全流程自主科研工作流（ARIS） + 硬性确定性证据门控与纯路径跨模型阻断审计（Verifiable Research-Loop）。**

> 本仓库基于 MIT 协议开源项目 **[ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep)**（`arXiv:2605.03042`，85+ 端到端科研技能、Research Wiki、MCP 桥接与论文写作工作流），深度融合 **Verifiable Research-Loop** 的零依赖确定性硬门控、纯路径跨家族阻断审计、112 次受控评测基准与自审计论文。

- **GitHub 仓库：** [https://github.com/shangliy/verifiable-aris](https://github.com/shangliy/verifiable-aris)
- **论文（arXiv 预印本）：** [paper/main.pdf](paper/main.pdf)（源码：[paper/main.tex](paper/main.tex)）
- **论文（ICML 2027 官方 8 页双盲版）：** [paper/main_icml2027.pdf](paper/main_icml2027.pdf)（源码：[paper/main_icml2027.tex](paper/main_icml2027.tex)）
- **上游 ARIS 完整说明：** [docs/ARIS_UPSTREAM_README_CN.md](docs/ARIS_UPSTREAM_README_CN.md) · [English](docs/ARIS_UPSTREAM_README.md) · [归属与许可说明](NOTICE.md)

---

## 核心价值：把 ARIS 从「建议性对话」升级为「可验证硬阻断闭环」

在涵盖 `SciIntegrity-Bench` 全部 11/11 陷阱类与 `AIScientistPitfalls` 全部 4/4 ML 陷阱的 **112 次受控实测**（总 API 花费 `$46.49 / $50.00`）中：

| 治理范式 | 阻断缺陷漏报率（`n=15`） | 精确 McNemar `p` | 核心机制发现 |
|---|---:|---:|---|
| **EviBound 式产物存在门控 (`B1`)** | `0/15` 拦截（全部放行） | — | 只查文件是否存在，无法发现代码算错与编造指标 |
| **ARIS 式建议型跨模型审稿 (`B2`)** | `13/15` (`86.7%`) | — | 不阻断交付导致缺陷漏出；喂入执行者摘要使 `BLOCK_MISCONDUCT` 从 `90.9%` 软化至 `36.4%` (`p=0.031250`) |
| **同模型全新会话复审 (`Ours_ccr`, `n=11`)** | 仅拦截 `2/11` (`18.2%`) | `p = 0.003906` | **同源谄媚**：`5/11 (45.5%)` 在 JSON 列出无效声明却仍投 `APPROVE` |
| **Verifiable-ARIS (`Ours_full`)** | **`0/15` (`0.0%`)** | **`p = 0.000244`** | **0% 漏报**、干净任务 **0% 误杀 (`3/3`)**、SPR 单轮闭环修复清除 **4/4** 不端 |

---

## 快速上手（3 条命令）

```bash
# 1. 运行 30 项离线单元与集成测试 + 端到端闭环 Demo（零费用）
python3 -m unittest discover -s tests/verifiable -v
bash examples/mini-ml/run_demo.sh
bash examples/verifiable-aris-walkthrough/run_walkthrough.sh
# （可选）真实大模型实战（claude-haiku 执行 + codex-cli 纯路径审稿，约 $0.99）：
python3 examples/live-showcase/run_live_showcase.py --budget-limit 1.50

# 2. 对任意科研工作区运行 Verifiable-ARIS 双层硬门控
python3 tools/verifiable_gate.py \
  --workspace /path/to/project \
  --report report/report.md \
  --logs out/ \
  --scripts code/ \
  --reviewer-provider codex-cli \
  --out-json audits/verifiable_gate_result.json

# 3. 一键安装到 Claude Code / Codex CLI
bash tools/install_verifiable_aris.sh --verifiable-only   # 仅装硬门控核心技能
bash tools/install_verifiable_aris.sh --all               # 安装 ARIS 全量 + 硬门控技能
```

---

## 开源许可与归属

本项目严格遵守上游 ARIS 的 **MIT License**（保留完整版权声明于 [LICENSE](LICENSE) 与 [NOTICE.md](NOTICE.md)），并清晰标明上游组件与新增 Verifiable Research-Loop 组件的边界。如在学术工作中使用本仓库，请同时引用本文与 ARIS (`arXiv:2605.03042`)。
