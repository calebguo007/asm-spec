# ASM A/B Test实验框架

对比 ASM TOPSIS 多准则决策算法与基线策略（随机选择、最贵优先）的效果。

## 实验设计

### 三组对照

| 组别 | 策略 | 说明 |
|---|---|---|
| **Group A (ASM)** | TOPSIS 多准则决策 | 根据用户偏好Weight，综合成本/质量/延迟/可用性Scoring，选择最优Service |
| **Group B (Random)** | 随机选择 | 从同 taxonomy 候选Service中随机选取 |
| **Group C (Expensive)** | 最贵优先 | 始终选择单位成本最高的Service（模拟"贵=好"假设） |

### Test场景

- 从 `manifests/` Load真实 ASM manifest 数据（14 个Service，6 种 taxonomy）
- 生成 50 个模拟任务请求（可Configuration），覆盖所有 taxonomy
- 每个任务随机分配偏好方向：
  - `cost_first`: 成本优先 (cost=0.55)
  - `quality_first`: 质量优先 (quality=0.55)
  - `speed_first`: 速度优先 (speed=0.55)
  - `balanced`: 均衡 (各 0.20-0.30)

### 评估指标

每次选择记录 5 个维度：
- 预估成本（从 manifest pricing 计算）
- 预估延迟（从 manifest sla 取 p50）
- 预估质量（从 manifest quality 取主指标）
- 可用性（从 manifest sla 取 uptime）
- TOPSIS 综合得分

## 运行

### 1. 运行 A/B Test

```bash
# 默认运行（50 个任务，seed=2024）
python ab_test.py

# 自定义参数
python ab_test.py --tasks 100 --seed 42 --output results/

# 指定 manifest 目录
python ab_test.py --manifests /path/to/manifests
```

### 2. 生成分析报告

```bash
# 从 CSV 生成 Markdown 报告
python analyze.py

# 指定文件路径
python analyze.py --csv results/ab_test_results.csv --output results/report.md
```

### 3. 一键运行

```bash
python ab_test.py && python analyze.py
```

## 输出文件

```
experiments/
├── ab_test.py                    # 主Test脚本
├── analyze.py                    # 分析脚本
├── README.md                     # 本文件
└── results/
    ├── ab_test_results.csv       # 原始选择记录
    ├── ab_test_analysis.json     # Structure化分析数据
    └── report.md                 # Markdown 分析报告
```

## 技术栈

- **Python 3.10+**
- **scipy** — 仅用于 Welch's t-test（如果不可用，自动回退到手动计算）
- **scorer.py** — 直接导入 ASM 的 TOPSIS Scoring逻辑
- 不依赖任何外部 API，全部使用 manifest 数据模拟

## 核心依赖

```
scorer.py → parse_manifest, filter_services, score_topsis, load_manifests
manifests/*.asm.json → 真实Service数据
```
