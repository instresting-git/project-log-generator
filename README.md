# Project Log Generator 🚀

**Multi-Vendor Log Generator** — purpose-built to fill the gap in professional log generation tooling, designed for SIEM engineers and security operations.

Generate realistic, vendor-specific log formats (Cisco, Huawei, Juniper & more) from TOML configurations. Supports multiple output protocols for SIEM testing, Logstash pipeline validation, performance benchmarking, and more.

---

## ✨ Features

- 🔌 **Multi-Vendor Support** — Cisco ASA, Huawei USG, Juniper SRX (easily extensible)
- 📝 **Grok Pattern-Driven** — Map Grok patterns to regex for intelligent random data generation
- 🎯 **Rich Log Types** — Traffic, ACL, VPN, IDS/IPS, Policy, System & more
- 🚀 **Multi-Protocol Output** — Syslog (RFC 5424), TCP, UDP, HTTP, File, stdout
- ⚡ **Controllable Rate** — EPS (Events Per Second) with weighted distribution across log types
- 🎛️ **Output Profile Management** — Reusable destination profiles in `output/*.conf`
- 📂 **Sample Export** — `sample --output-dir` to save samples to any folder
- 🛠 **Zero Dependencies** — Pure Python standard library, no `pip install` needed
- 📊 **TOML-Driven Config** — Add new vendors by simply writing a TOML file
- 🔗 **3-Tier Priority Override** — CLI args > Output Profile > TOML default

---

## 📁 Project Structure

```
project-log-generator/
├── project.py                    # CLI entry point (6 subcommands)
├── grok_pattern/                 # Grok Pattern definitions
│   ├── __init__.py
│   ├── base_patterns.conf        # Base patterns (INT, WORD, UUID, etc.)
│   ├── network_patterns.conf     # Network patterns (IPV4, PORT, MAC, etc.)
│   └── timestamp_patterns.conf   # Timestamp patterns (ISO8601, Cisco, Juniper, etc.)
├── product/                      # Vendor log configs (TOML)
│   ├── cisco/
│   │   └── asa_firewall.toml     # Cisco ASA Firewall
│   ├── huawei/
│   │   └── firewall.toml         # Huawei USG Firewall
│   └── juniper/
│       └── firewall.toml         # Juniper SRX Firewall
├── output/                       # Output profiles & example configs
│   ├── output_profiles.example.conf  # Template — copy to output_profiles.conf
│   └── .gitkeep
├── src/                          # Core modules
│   ├── __init__.py
│   ├── grok_loader.py            # Grok loader + 50+ built-in generators + regex engine
│   ├── toml_parser.py            # TOML config parser
│   ├── config_generator.py       # Core generation + 6-protocol send engine
│   └── output_config.py          # Output profile loader
├── requirements.txt
├── README.md
└── README_zh.md
```

---

## 🚀 Quick Start

### Requirements

- Python >= 3.8
- Zero external dependencies

### Discover Available Resources

```bash
# List all products and log types
python3 project.py list
python3 project.py list -v

# List output profiles
python3 project.py list-outputs
```

### Generate Sample Logs

```bash
# Cisco ASA Firewall (print to stdout)
python3 project.py sample --vendor cisco --product asa_firewall

# Huawei Firewall — VPN logs only
python3 project.py sample --vendor huawei --product firewall --type vpn --count 10

# Save to folder
python3 project.py sample --vendor juniper --product firewall --type idp -o ./my_samples
```

### Continuous Generation & Send

```bash
# Use output profile from output/output_profiles.conf
python3 project.py generate --vendor cisco --product asa_firewall --eps 10 --output-conf local_syslog
python3 project.py generate --vendor juniper --product firewall --output-conf local_file

# Profile + CLI override
python3 project.py generate --vendor huawei --product firewall -O local_syslog --host 10.0.0.50

# Direct protocol (no profile needed)
python3 project.py generate --vendor cisco --product asa_firewall --eps 10 --protocol tcp --host 10.0.0.1 --port 5514

# Specific log type, rate, and duration
python3 project.py generate --vendor cisco --product asa_firewall --type vpn --eps 5 --duration 60

# Pipe to Logstash
python3 project.py generate --vendor juniper --product firewall --protocol stdout | logstash -f pipeline.conf
```

### One-shot Batch Send

```bash
python3 project.py oneshot --vendor cisco --product asa_firewall --count 100 -O local_file
python3 project.py oneshot --vendor juniper --product firewall --type idp -c 50 -O console
```

### Validate Configuration

```bash
python3 project.py validate
# Validates product TOMLs + output profiles
```

---

## 🎛️ Output Profile System

### 3-Tier Priority Override

```
CLI args  >  --output-conf profile  >  (no product default)
 (highest)       (mid)                   (lowest)
```

### Setup

```bash
# Copy the example template
cp output/output_profiles.example.conf output/output_profiles.conf

# Edit with your own targets
vim output/output_profiles.conf
```

`output_profiles.conf` is git-ignored — each user maintains their own.

### Built-in Profiles (`output/output_profiles.example.conf`)

| Profile | Protocol | Target |
|---------|----------|--------|
| `local_syslog` | syslog | `127.0.0.1:514` |
| `local_file` | file | `output/generated_logs.log` |
| `console` | stdout | — |

Remote server examples (`remote_syslog`, `tcp_logstash`, `http_collector`) are included as commented-out templates.

---

## 🔧 Adding a New Vendor / Product

1. Create `<product>.toml` under `product/<vendor>/`
2. Define `[product]`, `[[logs]]`, `[logs.fields]` sections
3. Run `python3 project.py validate` to verify
4. Custom values accept `|` delimiter (for values containing commas)

### TOML Config Example

```toml
[product]
name = "My Firewall"
vendor = "myvendor"
type = "firewall"

[[logs]]
name = "traffic"
description = "Traffic flow logs"
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

### Field Definition Rules

- `{ pattern = "GROK_NAME" }` → generate via Grok pattern
- `{ values = "a|b|c" }` → random pick from value pool (`|` or `,` delimiter)
- If neither is specified → uses field name as Grok pattern name

---

## 🎯 Use Cases

| Scenario | Example Command |
|----------|----------------|
| **SIEM Go-Live Testing** | `generate --vendor cisco --product asa_firewall --eps 50 -O local_syslog` |
| **Elasticsearch Load Test** | `generate --vendor cisco --product asa_firewall --eps 1000 -O tcp_logstash` |
| **Grok Pattern Debugging** | `sample --vendor cisco --product asa_firewall --count 5` |
| **SOC Training Data** | `sample --vendor juniper --product firewall --type idp -o ./training` |
| **Pipeline Development** | `generate --vendor juniper --product firewall --protocol stdout \| logstash -f pipeline.conf` |
| **Batch Sample Export** | `sample --vendor huawei --product firewall -c 100 -o ./test_data` |

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

## 📋 CLI Reference

| Command | Description |
|---------|------------|
| `list` | List products & log types (`-v` verbose) |
| `list-outputs` | List output/ profiles |
| `sample` | Generate sample logs (`-o` save to folder) |
| `generate` | Continuous generation (`-O` use profile, `--eps` rate, `-d` duration) |
| `oneshot` | One-shot batch send (`-O` use profile, `-c` count) |
| `validate` | Validate all product TOMLs + output profiles |

---
## 🗺️ Roadmap

- [x] Cisco ASA Firewall
- [x] Huawei USG Firewall
- [x] Juniper SRX Firewall
- [x] Output Profile Management
- [x] Sample Export to Folder
- [x] Weighted Log Type Distribution
- [x] Regex-based Random Generator Engine
- [ ] Palo Alto PAN-OS
- [ ] Fortinet FortiGate
- [ ] Check Point Firewall
- [ ] Windows Event Log (XML)
- [ ] Linux syslog
- [ ] Async high-throughput send (aiohttp)
- [ ] JSON output format
- [ ] Docker deployment
- [ ] Web Dashboard

---

## 📄 License

MIT
