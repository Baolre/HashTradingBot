# Hash Trading Bot

基于 Python + PySide6 的 **TRON 区块单双监控桌面应用**。实时监听链上出块，按配置只统计区块号为指定倍数（默认 20）的区块，按"区块哈希末位数字（忽略字母）"判定单/双，提供连珠走势图、实时统计、以及"单双单双…"交叉预警。

## 功能特性

- **监控**：轮询 TronGrid `wallet/getnowblock` + `wallet/getblockbynum`，自动过滤区块号为 `N` 的倍数的区块（默认 20），断线补齐
- **判定**：从区块哈希右侧向左找第一个数字字符，奇数=单，偶数=双
- **走势**：黑底红绿连珠图，胶囊显示单/双累计计数，样式参考设计图
- **统计**：总期数、单/双占比、当前连号、最长单/双连号、当前交叉长度、最近 20 期明细
- **预警**：连续单双交叉达到阈值（可配）时触发桌面通知 + 声音 + 历史记录，阈值/冷却期可调
- **持久化**：SQLite 存储区块历史与预警记录，重启后自动恢复

## 目录结构

```
HashTradingBot/
├── main.py                  # 入口
├── config.yaml              # 运行配置
├── requirements.txt
├── app/
│   ├── api/trongrid.py      # TronGrid API
│   ├── core/
│   │   ├── analyzer.py      # 单双判定与统计
│   │   ├── monitor.py       # 后台轮询线程
│   │   └── alerter.py       # 预警引擎
│   ├── storage/db.py        # SQLite
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── trend_view.py    # 连珠走势图
│   │   ├── stats_panel.py
│   │   ├── alert_panel.py
│   │   ├── settings_panel.py
│   │   └── theme.py
│   └── utils/
│       ├── config.py
│       ├── logger.py
│       └── notifier.py
└── data/                    # 运行时生成：SQLite 数据库
```

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. 配置 API Key

免费在 [https://www.trongrid.io/](https://www.trongrid.io/) 申请 TronGrid API Key，然后两种方式之一：

- **编辑** `config.yaml` 中的 `api.trongrid_api_key`
- **或**运行后在界面【设置】页粘贴 Key 并点"保存设置"

### 3. 运行

```bash
python main.py
```

界面顶部点击 **"开始监控"**；数秒后走势面板就会出现第一颗圆珠。

## 配置项说明（`config.yaml`）

| 分组 | 字段 | 说明 |
| --- | --- | --- |
| `api` | `trongrid_api_key` | TronGrid API Key（必填） |
| `api` | `poll_interval` | 轮询间隔秒数，TRON 出块 ~3s，建议 2~4 |
| `filter` | `block_multiple` | 仅统计 `blockNumber % N == 0` 的区块，默认 **20** |
| `analyzer` | `max_history` | 走势/统计保留的最大期数 |
| `alert` | `alternation_enabled` | 是否启用"单双交叉"预警 |
| `alert` | `alternation_threshold` | 连续交叉到达多少期触发，默认 6 |
| `alert` | `cooldown_periods` | 触发后多少期内不再重复提醒 |

## 预警规则

当前支持 **单双交叉预警**：若最近 N 期呈现"单双单双…"交替模式且 N ≥ 阈值，则触发。
示例：阈值 = 6，最近 6 期是 `单 双 单 双 单 双` → 触发。

## 运行注意

- TronScan / TronGrid 目前对所有请求都要求携带 API Key，未配置会无法拉取区块
- 本应用仅做**链上数据监控与统计**，不涉及交易下单，也不提供任何投注建议
- 单双判定逻辑在 `app/core/analyzer.py::last_digit_of_hash`，如需改用"哈希整体十六进制末位转十进制"等其它玩法，在此处调整即可

## License

Private / Internal Use
