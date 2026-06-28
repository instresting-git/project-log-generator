# Project Log Generator 🚀

**多厂商日志生成器** — 填补市面上缺少专业日志生成工具的空白，专为 SIEM 工程师和安全运维人员设计。

根据 TOML 配置生成不同厂商（Cisco、Huawei、Juniper 等）的真实格式日志，支持多种协议发送到不同端口，可用于 SIEM 测试、Logstash Pipeline 验证、性能压测等场景。

---

## ✨ 功能特性

- 🔌 **多厂商支持** — Cisco ASA、Huawei USG、Juniper SRX（可扩展更多厂商）
- 📝 **Grok Pattern 驱动** — 基于 Grok Pattern 映射到 Regex 进行随机数据生成
- 🎯 **多种日志类型** — Traffic、ACL、VPN、IDS/IPS、Policy、System 等
- 🚀 **多协议输出** — Syslog (RFC 5424)、TCP、UDP、HTTP、File、stdout
- ⚡ **可控生成速率** — 支持 EPS (Events Per Second) 控制，按 log type 加权分配
- 🎛️ **输出配置管理** — `output/*.conf` 定义可复用的发送目标 profile
- 📂 **样本导出** — `sample --output-dir` 将样本储存到指定 folder
- 🛠 **纯 Python 标准库** — 无需第三方依赖即可运行
- 📊 **TOML 配置驱动** — 新增厂商只需添加 TOML 文件
- 🔗 **三层优先级覆盖** — CLI 参数 > Output Profile > TOML 默认

---

## 📁 项目结构

```
project-log-generator/
├── project.py                    # CLI 主程序入口 (6 个子命令)
├── grok_pattern/                 # Grok Pattern 类型定义库
│   ├── __init__.py
│   ├── base_patterns.conf        # 基础 Pattern (INT, WORD, UUID 等)
│   ├── network_patterns.conf     # 网络相关 (IPV4, PORT, MAC 等)
│   └── timestamp_patterns.conf   # 时间戳相关 (ISO8601, Cisco, Juniper 等)
├── product/                      # 厂商日志配置 (TOML)
│   ├── cisco/
│   │   └── asa_firewall.toml     # Cisco ASA Firewall
│   ├── huawei/
│   │   └── firewall.toml         # Huawei USG Firewall
│   └── juniper/
│       └── firewall.toml         # Juniper SRX Firewall
├── output/                       # 输出配置与日志储存
│   ├── output_profiles.example.conf  # 模板 — 复制为 output_profiles.conf
│   └── .gitkeep
├── src/                          # 核心源码
│   ├── __init__.py
│   ├── grok_loader.py            # Grok 加载 + 50+ 随机生成器 + regex 引擎
│   ├── toml_parser.py            # TOML 配置解析
│   ├── config_generator.py       # 核心生成 + 6 协议发送引擎
│   └── output_config.py          # 输出 profile 加载器
├── requirements.txt
├── README.md
├── README_zh.md
└── README_zh-CN.md
```

---

## 🚀 快速开始

### 基本要求

- Python >= 3.8
- 无需第三方依赖

### 查看可用资源

```bash
# 列出所有产品与日志类型
python3 project.py list
python3 project.py list -v

# 列出输出 profile
python3 project.py list-outputs
```

### 生成样本日志

```bash
# Cisco ASA Firewall（打印到 stdout）
python3 project.py sample --vendor cisco --product asa_firewall

# Huawei Firewall — 只生成 VPN 日志
python3 project.py sample --vendor huawei --product firewall --type vpn --count 10

# 储存到指定 folder
python3 project.py sample --vendor juniper --product firewall --type idp -o ./my_samples
```

### 持续生成并发送

```bash
# 使用 output/ 中的 profile
python3 project.py generate --vendor cisco --product asa_firewall --eps 10 --output-conf local_syslog
python3 project.py generate --vendor juniper --product firewall --output-conf local_file

# 使用 profile + CLI 覆盖 host
python3 project.py generate --vendor huawei --product firewall -O local_syslog --host 10.0.0.50

# 直接指定协议（不依赖 profile）
python3 project.py generate --vendor cisco --product asa_firewall --eps 10 --protocol tcp --host 10.0.0.1 --port 5514

# 指定日志类型、速率、持续时间
python3 project.py generate --vendor cisco --product asa_firewall --type vpn --eps 5 --duration 60

# Pipe 到 Logstash
python3 project.py generate --vendor juniper --product firewall --protocol stdout | logstash -f pipeline.conf
```

### 一次性批量发送

```bash
python3 project.py oneshot --vendor cisco --product asa_firewall --count 100 -O local_file
python3 project.py oneshot --vendor juniper --product firewall --type idp -c 50 -O console
```

### 验证配置

```bash
python3 project.py validate
# 同时验证产品 TOML + output profiles
```

---

## 🎛️ 输出配置系统

### 三层优先级覆盖

```
CLI 直接参数  >  --output-conf profile  >  (无产品默认值)
   (最高)            (中)                    (最低)
```

### 配置方式

```bash
# 复制示例模板
cp output/output_profiles.example.conf output/output_profiles.conf

# 编辑自己的目标地址
vim output/output_profiles.conf
```

`output_profiles.conf` 已加入 `.gitignore` — 每位用户维护自己的配置。

### 内置 Profiles (`output/output_profiles.example.conf`)

| Profile | Protocol | Target |
|---------|----------|--------|
| `local_syslog` | syslog | `127.0.0.1:514` |
| `local_file` | file | `output/generated_logs.log` |
| `console` | stdout | — |

远程服务器示例（`remote_syslog`、`tcp_logstash`、`http_collector`）以注释形式保留在模板中。

---

## 🔧 如何新增厂商/产品

1. 在 `product/<vendor>/` 下创建 `<product>.toml`
2. 定义 `[product]`、`[[logs]]`、`[logs.fields]` 等区块
3. 运行 `python3 project.py validate` 验证配置
4. 自定义值可用 `|` 分隔符（支持含逗号的值）

### TOML 配置结构范例

```toml
[product]
name = "My Firewall"
vendor = "myvendor"
type = "firewall"

[[logs]]
name = "traffic"
description = "流量日志"
template = "%{TIMESTAMP_ISO8601} %{HOSTNAME} src=%{SRC_IP}:%{SRC_PORT} dst=%{DST_IP}:%{DST_PORT} proto=%{PROTOCOL}"
rate = 100

[logs.fields]
TIMESTAMP_ISO8601 = { pattern = "TIMESTAMP_ISO8601" }
HOSTNAME = { pattern = "HOSTNAME" }
SRC_IP = { pattern = "IPV4" }
DST_IP = { pattern = "IPV4" }
SRC_PORT = { pattern = "PORT" }
DST_PORT = { pattern = "PORT" }
PROTOCOL = { pattern = "PROTOCOL" }
```

### 字段定义规则

- `{ pattern = "GROK_NAME" }` → 通过 Grok pattern 生成
- `{ values = "a|b|c" }` → 从候选值随机选取（`|` 或 `,` 分隔）
- 两者都不指定 → 用字段名作为 Grok pattern 名查找

---

## 🎯 使用场景

| 场景 | 命令示例 |
|------|---------|
| **SIEM 上线测试** | `generate --vendor cisco --product asa_firewall --eps 50 -O local_syslog` |
| **Elasticsearch 压测** | `generate --vendor cisco --product asa_firewall --eps 1000 -O tcp_logstash` |
| **Grok Pattern 调试** | `sample --vendor cisco --product asa_firewall --count 5` |
| **SOC 培训素材** | `sample --vendor juniper --product firewall --type idp -o ./training` |
| **Pipeline 开发** | `generate --vendor juniper --product firewall --protocol stdout \| logstash -f pipeline.conf` |
| **批量样本导出** | `sample --vendor huawei --product firewall -c 100 -o ./test_data` |

---

## 🧪 Sample Output

### Cisco ASA Firewall
```
Jun 28 2026 15:35:12 fw-secondary %ASA-4-106100: Deny HTTPS src ge-0/0/0:164.18.22.180/50591
  dst FastEthernet0/0:172.28.237.74/514 by access-group "outside_access_in"
```

### Huawei USG Firewall
```
2026-06-28 18:18:22+00:00 host-011 %%01SESSION/4/WARNING/SESSION_CREATE:
  (Slot=2)[GigabitEthernet1/0/1]:GRE SrcIP:192.177.227.88, DstIP:192.182.27.220,
  SrcPort:8862, DstPort:18049, Action: Permit, Policy: inside_to_outside
```

### Juniper SRX Firewall (IDP)
```
2026-06-28 14:04:31 fw-secondary RT_IDP[13035]: RT_IDP_ATTACK_LOG_EVENT:
  attack=HTTP:CVE-2021-44228 severity=CRITICAL src=147.135.145.95:64183
  dst=192.179.157.127:5432 proto=SMTP service=ssh action=drop connection
```

---

## 📋 CLI 命令总览

| 命令 | 功能 |
|------|------|
| `list` | 列出产品与日志类型（`-v` 详细模式） |
| `list-outputs` | 列出 output/ 中的输出 profile |
| `sample` | 生成样本（`-o` 导出到 folder） |
| `generate` | 持续生成并发送（`-O` 使用 profile，`--eps` 速率，`-d` 持续时间） |
| `oneshot` | 一次性生成并发送（`-O` 使用 profile，`-c` 数量） |
| `validate` | 验证产品 TOML + output profiles |

---

## 🗺️ Roadmap

- [x] Cisco ASA Firewall
- [x] Huawei USG Firewall
- [x] Juniper SRX Firewall
- [x] Output Profile 配置管理系统
- [x] Sample 导出到 Folder
- [x] 加权日志类型分配
- [x] 基于 Regex 的随机生成引擎
- [ ] Palo Alto PAN-OS
- [ ] Fortinet FortiGate
- [ ] Check Point Firewall
- [ ] Windows Event Log (XML)
- [ ] Linux syslog
- [ ] 异步高吞吐发送 (aiohttp)
- [ ] JSON 格式输出
- [ ] 性能基准测试报告
- [ ] Docker 部署支持
- [ ] Web Dashboard 监控

---

## 📄 License

MIT
