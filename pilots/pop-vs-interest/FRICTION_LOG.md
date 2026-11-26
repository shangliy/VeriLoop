# `research-loop` 端到端五步干跑卡点与缺陷清单（`pop-vs-interest`）

日期：2026-11-24  
干跑工作区：`/home/shawnyang/Documents/auto-research/pilots/pop-vs-interest/`  
只读数据源：`/home/shawnyang/Documents/Sigir/exp_resid/out/` 与 `ideas/2026-11-23-pop-vs-interest/scripts/`（零修改 `Documents/Sigir`）

---

## 0. 核心结论

1. **五步闭环已首次完整跑通，且“纯路径独立审稿”的设计价值得到强验证**：
   - `trace_numbers.py` 报 `285/285 traced, 0 UNTRACED, 0 MIXED ROW`，`claims.py` 放行 `C1 (6/6 ok)`；
   - **但全新只读独立审稿代理（只给路径，零总结）直接从原始代码与日志里挖出 16 条带精确 `file:line` 的真实缺陷**，含 4 条 blocker（包括代码级 non-telescoping `beta_inf` 假匹配 `tau`、日志中已存在击败 `GeoTrie-GR` 的训练免基线 `hybrid-kNN` 与 30× 更快的 `noID+L2+IVF`）、8 条 major（包括缺失配对 CI、网格边界最优、不忠实的 LIGER 两阶段代理、选择指标不对齐）和 4 条 minor（包括脚本硬编码 `[Ref ...]` 导致的 `0.3720` vs `0.3718` 漂移、乐观平局 `(sc > st).sum()`）。
2. **同时暴露出当前 `research-loop` 仓库的 10 个真实工程与机制短板**（下表），直接决定接下来补齐仓库的精确优先级。

---

## 1. 干跑暴露的 10 个真实卡点 / Bug

| ID | 模块 | 实测问题（均在本次干跑中复现） | 严重度 | 对应修复方案 |
|---|---|---|---|---|
| **F1** | `claims.py` | **Schema 不一致 Bug**：`SKILL.md:148` 与 `reviewer-brief.md:43` 要求审稿人返回 `unsupported`，但 `claims.py:31` 的 `STATUSES` 列表里**根本没有 `unsupported`**！一旦审稿人判 `unsupported`，写账本直接报错退出。 | **P0 Bug** | 在 `STATUSES` 加入 `unsupported`，补单元测试校验 `SKILL.md` / `reviewer-brief.md` / `claims.py` 枚举一致。 |
| **F2** | `claims.py` | **G2 `max()` 漏洞 + 基线无种子校验**：`C1` 挂了 3-seed 主日志和 1-seed 消融日志，`G2` 用 `max(seeds)=3` 直接放行；且 `--arm` 基线（如 1-seed `LIGER`/Office `TIGER`）完全不查种子数。 | **P0 漏洞** | 按 `(dataset, role)` 检查种子数，消融证据与必需基线单独校验 `seeds >= planned`（或显式标注 `--deterministic`）。 |
| **F3** | `claims.py` | **G3/G5 自报可信度漏洞**：执行者手动传 `--selected-on valid` 和 `--ablated 1`，脚本零核验（实测 `C3` 报告里 `tau` 是测试集选的、缺固定门消融，但 `claims.py` 照单全收；`C1` 缺配对 CI 仍拿到 `6/6 ok`）。 | **P0 漏洞** | 要求 `--ablation-log` 指向真实消融日志、`--ci-log` 指向配对区间日志；并新增静态代码启发式预检（检测试集选择、网格边界、乐观平局）。 |
| **F4** | `claims.py` | **G1 无内容哈希与截断检查**：`microlens_benchmark.txt` 在 Stage 3 ep 10 截断未跑完，`G1` 只查 `os.path.exists()` 就过关；日志若被覆写，账本毫不知情。 | **P1** | 挂载证据时记录 `sha256`、`bytes`、`mtime` 和可选完成标记；`check` 时对比哈希防止静默篡改/覆写。 |
| **F5** | `claims.py` | **G6 1 秒时间戳碰撞 + 缺少确定性基线标记**：`evidence` 与 `revise` 同一秒执行均打印 `20:41:30`；训练免基线 `hybrid-kNN` 被迫传假 `--seeds 1`。 | **P1** | 改用单调递增事件序号 `seq` + ISO 微秒时间戳；为训练免/确定性基线支持 `--deterministic` 替代 `--seeds 1`。 |
| **F6** | `trace_numbers.py` | **符号盲区与低精度盲区**：正则忽略前导负号（把 `-0.0106` 翻成 `+0.0106` 竟判 `TRACED`！），且跳过 `<3` 位小数、整数计数、延迟与超参（如 `2/3`、`1.53 ms/q`、`220x`、`tau=0.75`）。 | **P0 漏洞** | 保留并强校验正负号（`SIGNED MISMATCH`）；支持 `±` 配对、CI `[lo,hi]` 整组校验与带单位数值（`ms/q`, `%`）。 |
| **F7** | `trace_numbers.py` | **忽略表行自报日志名 + 全局 STALE 噪音**：报告每行都写了 `Log File` 列，脚本却全局搜 56 个日志，不核验数字是否真的来自该行声明的日志；且对报告未引用的 `test_levers_1_and_2.txt` 报全局 `STALE`。 | **P0 漏洞** | 解析表行引用的日志名并强制**同文件校验（`WRONG LOG`）**；区分 `CITED STALE`（阻断）与 `WORKSPACE STALE`（提示）。 |
| **F8** | `trace_numbers.py` | **被日志里的硬编码 `[Ref ...]` 打印欺骗**：`audit_and_frontier_logs.py:273` 硬编码了 `0.3720`（真实值 `0.3718`），因打印进了 `.txt`，`trace_numbers.py` 判为已溯源。这也对应 FabScore 中占 44.6% 的硬编码实验造假！ | **P1（论文亮点）** | 新增轻量级 Python AST 静态扫描器 `audit_code.py`：检测打印语句中的硬编码指标字面量、`[Ref ...]` 伪日志、`(sc > st).sum()` 乐观平局、空数据后 `np.random` 合成替代等高危模式。 |
| **F9** | `SKILL.md` / `reviewer-brief.md` | **跨模型审稿桥与严格只读沙箱未封装**：本次只能靠同家族子代理 + 提示词约束不改文件，无法一键拉起 Claude + OpenAI 跨模型审稿、记录 token/费用，也无法强制执行只读隔离。 | **P0 工程** | 构建统一的 Python 独立审稿启动器 `run_audit.py`：先在本地跑完机械检查（`claims.py` + `trace_numbers.py` + `audit_code.py`），再把纯路径+检查输出送给 **Claude / OpenAI** 跨模型审稿通道，强制记录每次调用的 token 与美元花费并设硬预算熔断。 |
| **F10** | `checklist.md` | **还缺来自 ARIS 与 FabScore 的 4 条高价值检查项**：(1) 代码中硬编码/模拟指标替代真实计算（FabScore 44.6%）；(2) 范围用词检查（小实验禁用 robust/extensive）；(3) 死代码/未执行指标（ARIS `experiment-integrity.md`）；(4) 跨模型两段式“强拒稿攻击 → 逐条裁决”（ARIS `kill-argument`）。 | **P1** | 补入 `checklist.md` 与 `audit_code.py`，并加入“算力预算行”到 `reviewer-brief.md`。 |

---

## 2. 基于 Claude + OpenAI 的 $50 评测预算分配草案

用户已确认：**预算硬顶 `$50`**，可用模型家族为 **Claude** 与 **OpenAI**。

为保证在 `$50` 内完成 **4 个对照组（Bare / EviBound-style / ARIS-style / Ours）+ 关键消融**，并留出安全缓冲，建议采用“高性价比执行模型 + 强推理跨家族审稿模型”的组合，并在评测框架中接入强制 `budget_ledger.json`（超 `$45` 自动暂停）：

1. **模型配对（跨家族对称）**：
   - 执行模型（Executor）：`claude-sonnet-4-6`（或 `gpt-4.1-mini` / `claude-haiku-4-5` 做大规模扫描 + `claude-sonnet-4-6` 做主实验，按实际账号单价在开工前先跑 1 个场景实测单次成本）。
   - 跨模型审稿人（Reviewer）：`gpt-5.4` / `o4-mini`（OpenAI）审 Claude 执行结果；并在反转消融中用 Claude 审 OpenAI 执行结果。
2. **分项预算上限（总计 ≤ $50）**：
   - **套件 A — `SciIntegrity-Bench`**（33 场景主表 × 4 系统 + 高危 6 类 18 场景消融）：硬顶 **`$18`**
   - **套件 B — `AIScientistPitfalls / SPR Task` + `FabScore` 独立代码执行打分**：硬顶 **`$18`**
   - **套件 C — `pop-vs-interest` 真实历史缺陷回归集**（Claude vs OpenAI 跨模型审稿对照）：硬顶 **`$6`**
   - **缓冲与补测预留**：**`$8`**
