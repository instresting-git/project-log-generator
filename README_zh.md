# Project Log Generator 🚀

**多廠商日誌生成器** — 填補市面上缺少專業日誌生成工具的空白，專為 SIEM 工程師和安全運維人員設計。

根據 TOML 配置生成不同廠商（Cisco、Huawei、Juniper 等）的真實格式日誌，支援多種協議發送到不同端口，可用於 SIEM 測試、Logstash Pipeline 驗證、性能壓測等場景。

---

## ✨ 功能特性

- 🔌 **多廠商支援** — Cisco ASA、Huawei USG、Juniper SRX（可擴展更多廠商）
- 📝 **Grok Pattern 驅動** — 基於 Grok Pattern 映射到 Regex 進行隨機數據生成
- 🎯 **多種日誌類型** — Traffic、ACL、VPN、IDS/IPS、Policy、System 等
- 🚀 **多協議輸出** — Syslog (RFC 5424)、TCP、UDP、HTTP、File、stdout
- ⚡ **可控生成速率** — 支援 EPS (Events Per Second) 控制
- 🎛️ **輸出配置管理** — `output/*.conf` 定義可復用的發送目標 profile
- 📂 **樣本匯出** — `sample --output-dir` 將樣本儲存到指定 folder
- 🛠 **純 Python 標準庫** — 無需第三方依賴即可運行
- 📊 **TOML 配置驅動** — 新增廠商只需添加 TOML 文件
- 🔗 **三層優先級覆蓋** — CLI 參數 > Output Profile > TOML 默認

---

## 📁 項目結構

```
project-log-generator/
├── project.py                    # CLI 主程式入口 (6 個子命令)
├── grok_pattern/                 # Grok Pattern 類型定義庫
│   ├── __init__.py
│   ├── base_patterns.conf        # 基礎 Pattern (INT, WORD, UUID 等)
│   ├── network_patterns.conf     # 網絡相關 (IPV4, PORT, MAC 等)
│   └── timestamp_patterns.conf   # 時間戳相關 (ISO8601, Cisco, Juniper 等)
├── product/                      # 廠商日誌配置 (TOML)
│   ├── cisco/
│   │   └── asa_firewall.toml     # Cisco ASA Firewall
│   ├── huawei/
│   │   └── firewall.toml         # Huawei USG Firewall
│   └── juniper/
│       └── firewall.toml         # Juniper SRX Firewall
├── output/                       # 輸出配置與日誌儲存
│   ├── output_profiles.conf      # 輸出目標 profile 定義 ✨
│   └── .gitkeep
├── src/                          # 核心源碼
│   ├── __init__.py
│   ├── grok_loader.py            # Grok Pattern 加載 + 50+ 隨機生成器
│   ├── toml_parser.py            # TOML 配置解析
│   ├── config_generator.py       # 核心生成 + 6 協議發送引擎
│   └── output_config.py          # 輸出 profile 加載器 ✨
├── requirements.txt
└── README.md
```

---

## 🚀 快速開始

### 基本要求

- Python >= 3.8
- 無需第三方依賴 (`pip install` 都不用！)

### 查看可用資源

```bash
# 列出所有產品與日誌類型
python3 project.py list
python3 project.py list -v

# 列出輸出 profile
python3 project.py list-outputs
```

### 生成樣本日誌

```bash
# Cisco ASA Firewall（打印到 stdout）
python3 project.py sample --vendor cisco --product asa_firewall

# Huawei Firewall — 只生成 VPN 日誌
python3 project.py sample --vendor huawei --product firewall --type vpn --count 10

# 儲存到指定 folder ✨
python3 project.py sample --vendor juniper --product firewall --type idp -o ./my_samples

# 批量匯出所有類型
python3 project.py sample --vendor cisco --product asa_firewall --count 20 -o ./samples
```

### 持續生成並發送

```bash
# 使用 output/ 中的 profile ✨
python3 project.py generate --vendor cisco --product asa_firewall --eps 10 --output-conf local_syslog
python3 project.py generate --vendor juniper --product firewall --output-conf tcp_logstash

# 使用 profile + CLI 覆蓋 host
python3 project.py generate --vendor huawei --product firewall --output-conf local_syslog --host 10.0.0.50

# 直接指定協議（不依賴 profile）
python3 project.py generate --vendor cisco --product asa_firewall --eps 10 --protocol tcp --host 192.168.1.100 --port 5514

# 寫入文件
python3 project.py generate --vendor huawei --product firewall --output-conf local_file

# 指定日誌類型、速率、持續時間
python3 project.py generate --vendor cisco --product asa_firewall --type vpn --eps 5 --duration 60

# Pipe 到 Logstash
python3 project.py generate --vendor juniper --product firewall --protocol stdout | logstash -f pipeline.conf
```

### 一次性批量發送

```bash
python3 project.py oneshot --vendor cisco --product asa_firewall --count 100 --output-conf http_collector
python3 project.py oneshot --vendor juniper --product firewall --type idp -c 50 -O local_file
```

### 驗證配置

```bash
python3 project.py validate
# 同時驗證產品 TOML + output profiles
```

---

## 🎛️ 輸出配置系統 ✨

### 三層優先級覆蓋

```
CLI 直接參數  >  --output-conf profile  >  TOML 產品默認
   (最高)            (中)                    (最低)
```

### 預設 Output Profiles (`output/output_profiles.conf`)

| Profile | Protocol | Target |
|---------|----------|--------|
| `local_syslog` | syslog | `127.0.0.1:514` |
| `remote_syslog` | syslog | `192.168.1.100:5514` |
| `tcp_logstash` | tcp | `192.168.1.100:5000` |
| `udp_logstash` | udp | `192.168.1.100:5001` |
| `http_collector` | http | `http://192.168.1.100:8080/logs` |
| `local_file` | file | `output/generated_logs.log` |
| `console` | stdout | — |

### 新增自定義 Profile

編輯 `output/output_profiles.conf`，添加：

```toml
[my_syslog_server]
protocol = "syslog"
host = "10.0.0.100"
port = 514
facility = 16
severity = 5
description = "Production SIEM Collector"
```

---

## 🔧 如何新增廠商/產品

1. 在 `product/<vendor>/` 下創建 `<product>.toml`
2. 定義 `[product]`、`[output]`、`[[logs]]`、`[logs.fields]` 等區塊
3. 每個 `[[logs]]` 定義日誌類型的 template 和 fields
4. 運行 `python3 project.py validate` 驗證配置
5. 自定義值可用 `|` 分隔符（支援含逗號的值）

### TOML 配置結構範例

```toml
[product]
name = "My Firewall"
vendor = "myvendor"
type = "firewall"

[[logs]]
name = "traffic"
description = "流量日誌"
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

---

## 🎯 使用場景

| 場景 | 命令示例 |
|------|---------|
| **SIEM 上線測試** | `generate --vendor cisco --product asa_firewall --eps 50 -O local_syslog` |
| **Elasticsearch 壓測** | `generate --vendor cisco --product asa_firewall --eps 1000 -O tcp_logstash` |
| **Grok Pattern 調試** | `sample --vendor cisco --product asa_firewall --count 5` |
| **SOC 培訓素材** | `sample --vendor juniper --product firewall --type idp -o ./training` |
| **Pipeline 開發** | `generate --vendor juniper --product firewall --protocol stdout \| logstash -f pipeline.conf` |
| **批量樣本匯出** | `sample --vendor huawei --product firewall -c 100 -o ./test_data` |

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

## 📋 CLI 命令總覽

| 命令 | 功能 | 新增 |
|------|------|:--:|
| `list` | 列出產品與日誌類型 (`-v` 詳細模式) | |
| `list-outputs` | 列出 output/ 中的輸出 profile | ✨ |
| `sample` | 生成樣本 (`-o` 匯出到 folder) | ✨ |
| `generate` | 持續生成並發送 (`-O` 使用 profile) | ✨ |
| `oneshot` | 一次性生成並發送 (`-O` 使用 profile) | ✨ |
| `validate` | 驗證產品 TOML + output profiles | ✨ |

---

## 📄 License

MIT
