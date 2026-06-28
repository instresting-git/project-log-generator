"""
Grok Pattern Loader
===================
Loads grok_pattern/*.conf files, parses pattern definitions,
supports nested pattern resolution (%{PATTERN_NAME}),
and provides regex + random data generators for each pattern.
"""

import re
import os
import random
import string
import ipaddress
import uuid as uuid_lib
from datetime import datetime, timedelta
from typing import Dict, Tuple, Callable, Any, List, Optional

GROK_PATTERN_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "grok_pattern")


class GrokLoader:
    """Grok Pattern Loader and Random Data Generator"""

    # Built-in generator registry: pattern_name -> generator function
    _generators: Dict[str, Callable[[], str]] = {}

    def __init__(self):
        self.patterns: Dict[str, str] = {}   # pattern_name -> regex string
        self._loaded = False

    def load_all(self) -> None:
        """Load all .conf files under grok_pattern/"""
        if self._loaded:
            return

        # Auto-scan all .conf files under grok_pattern/
        if not os.path.isdir(GROK_PATTERN_DIR):
            raise FileNotFoundError(f"Grok pattern directory not found: {GROK_PATTERN_DIR}")

        conf_files = sorted(
            f for f in os.listdir(GROK_PATTERN_DIR)
            if f.endswith(".conf")
        )
        for filename in conf_files:
            filepath = os.path.join(GROK_PATTERN_DIR, filename)
            self._parse_conf_file(filepath)

        # Resolve nested patterns (%{PATTERN_NAME})
        self._resolve_nested_patterns()

        # Register built-in generators
        self._register_builtin_generators()

        self._loaded = True

    def _parse_conf_file(self, filepath: str) -> None:
        """Parse a single .conf file"""
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                # Format: PATTERN_NAME REGEX
                match = re.match(r"^(\w+)\s+(.+)$", line)
                if match:
                    name, regex = match.group(1), match.group(2)
                    self.patterns[name] = regex

    def _resolve_nested_patterns(self) -> None:
        """Resolve all nested %{PATTERN} to final regex (max 10 layers to avoid infinite loops)"""
        max_iterations = 10
        for _ in range(max_iterations):
            changed = False
            for name, regex in list(self.patterns.items()):
                nested_matches = list(re.finditer(r"%\{(\w+)\}", regex))
                if nested_matches:
                    new_regex = regex
                    for m in nested_matches:
                        ref_name = m.group(1)
                        if ref_name in self.patterns:
                            ref_regex = self.patterns[ref_name]
                            # Wrap in (?: ... ) to avoid capture group interference
                            new_regex = new_regex.replace(
                                f"%{{{ref_name}}}", f"(?:{ref_regex})", 1
                            )
                    if new_regex != regex:
                        self.patterns[name] = new_regex
                        changed = True
            if not changed:
                break

    def get_regex(self, pattern_name: str) -> Optional[str]:
        """Get the fully-resolved regex for a pattern"""
        self.load_all()
        return self.patterns.get(pattern_name)

    # ================================================================
    # Random Data Generation
    # ================================================================

    def _register_builtin_generators(self) -> None:
        """Register generators for all built-in patterns"""

        # --- Basic Numbers ---
        self._generators["INT"] = lambda: str(random.randint(0, 999999))
        self._generators["NUMBER"] = lambda: str(random.randint(-999, 9999)) + (
            f".{random.randint(0, 99)}" if random.random() > 0.5 else ""
        )
        self._generators["FLOAT"] = lambda: f"{random.uniform(-999.99, 9999.99):.2f}"
        self._generators["PERCENTAGE"] = lambda: f"{random.randint(0, 100)}%"

        # --- String ---
        self._generators["WORD"] = lambda: "".join(
            random.choice(string.ascii_letters) for _ in range(random.randint(3, 12))
        )
        self._generators["NOTSPACE"] = lambda: "".join(
            random.choice(string.ascii_letters + string.digits + "_-")
            for _ in range(random.randint(3, 16))
        )
        self._generators["DATA"] = lambda: " ".join(
            "".join(random.choice(string.ascii_letters) for _ in range(random.randint(2, 8)))
            for _ in range(random.randint(1, 5))
        )
        self._generators["GREEDYDATA"] = lambda: " ".join(
            "".join(random.choice(string.ascii_letters + string.digits) for _ in range(random.randint(3, 10)))
            for _ in range(random.randint(2, 8))
        )
        self._generators["QUOTEDSTRING"] = lambda: '"' + "".join(
            random.choice(string.ascii_letters + string.digits + " _-")
            for _ in range(random.randint(5, 20))
        ) + '"'
        self._generators["HOSTNAME"] = lambda: random.choice([
            "fw-primary", "fw-secondary", f"host-{random.randint(1, 99):03d}",
            "edge-gateway-01", "core-switch-01", "dmz-proxy-01"
        ])

        # --- Identity ---
        self._generators["USERNAME"] = lambda: "".join(
            random.choice(string.ascii_lowercase + string.digits + "._-")
            for _ in range(random.randint(3, 12))
        )
        self._generators["EMAIL"] = lambda: f"user{random.randint(1, 999)}@example{random.choice(['.com', '.org', '.net', '.io'])}"
        self._generators["URI"] = lambda: random.choice([
            f"https://api.example.com/v{random.randint(1,3)}/data",
            f"http://192.168.{random.randint(1,255)}.{random.randint(1,255)}:8080/status",
            f"https://login.example.com/auth?token={uuid_lib.uuid4().hex[:12]}",
        ])
        self._generators["PATH"] = lambda: random.choice([
            "/var/log/messages", "/etc/config/settings.conf",
            "/usr/local/bin/app", "/home/admin/scripts/backup.sh",
        ])
        self._generators["UUID"] = lambda: str(uuid_lib.uuid4())

        # --- Boolean/Status ---
        self._generators["BOOLEAN"] = lambda: random.choice(["true", "false", "yes", "no", "1", "0"])
        self._generators["STATUS"] = lambda: random.choice([
            "success", "failure", "error", "ok", "permitted", "denied", "blocked", "up"
        ])

        # --- ID ---
        self._generators["SESSION_ID"] = lambda: format(random.randint(0, 0xFFFFFFFFFFFF), 'x')
        self._generators["PROCESS_ID"] = lambda: str(random.randint(100, 65535))
        self._generators["THREAD_ID"] = lambda: format(random.randint(0, 0xFFFF), 'x')
        self._generators["TRANSACTION_ID"] = lambda: uuid_lib.uuid4().hex[:random.choice([8, 16, 24, 32])]

        # --- Network ---
        self._generators["PROTOCOL"] = lambda: random.choice([
            "TCP", "UDP", "ICMP", "HTTP", "HTTPS", "FTP", "SSH", "SMTP",
            "DNS", "SNMP", "TLS", "SSL", "GRE"
        ])
        self._generators["SERVICE_NAME"] = lambda: random.choice([
            "http", "https", "ssh", "mysql", "postgresql", "redis", "elasticsearch",
            "nginx", "apache", "smtp", "dnsmasq", "openvpn"
        ])

        # IPv4
        self._generators["IPV4"] = lambda: self._gen_ipv4()
        self._generators["IPV4_PRIVATE"] = lambda: self._gen_private_ipv4()
        self._generators["IPV4_PUBLIC"] = lambda: self._gen_public_ipv4()

        # IPv6
        self._generators["IPV6"] = lambda: self._gen_ipv6()
        self._generators["IPV6_SHORT"] = lambda: self._gen_ipv6_short()

        # PORT
        self._generators["PORT"] = lambda: str(random.randint(1, 65535))
        self._generators["PORT_WELL_KNOWN"] = lambda: str(random.choice([
            20, 21, 22, 23, 25, 53, 67, 68, 80, 110, 123, 143, 161, 162, 389,
            443, 445, 465, 514, 587, 636, 993, 995, 1433, 1521, 3306, 3389,
            5432, 6379, 8080, 8443, 9090, 9200, 27017
        ]))

        # MAC
        self._generators["MAC"] = lambda: ":".join(
            f"{random.randint(0, 255):02x}" for _ in range(6)
        )
        self._generators["MAC_CISCO"] = lambda: ".".join(
            f"{random.randint(0, 65535):04x}" for _ in range(3)
        )

        # Interface
        self._generators["INTERFACE_NAME"] = lambda: random.choice([
            "GigabitEthernet0/0", "GigabitEthernet0/1", "GigabitEthernet0/2",
            "TenGigabitEthernet1/0", "FastEthernet0/0", "Port-channel1",
            "ge-0/0/0", "ge-0/0/1", "xe-0/1/0", "vlan10", "vlan20",
            "tunnel0", "loopback0", "wan1", "eth0"
        ])

        # Domain
        self._generators["DOMAIN"] = lambda: random.choice([
            "example.com", "google.com", "github.com", "cdn.cloudflare.com",
            "login.microsoftonline.com", "api.aws.amazon.com", "azure.com",
            "elastic.co", "splunk.com", "internal.corp.local"
        ])
        self._generators["FQDN"] = lambda: random.choice([
            "fw01.datacenter.example.com", "lb-prod-01.us-east-1.aws.example.com",
            "mail.corp.internal.local", "vpn-gateway.hq.company.org"
        ])

        # Subnet / CIDR
        self._generators["SUBNET_MASK"] = lambda: random.choice([
            "255.255.255.0", "255.255.0.0", "255.255.255.128",
            "255.255.255.192", "255.255.255.252"
        ])
        self._generators["CIDR"] = lambda: str(random.randint(8, 32))

        # SOCKET_ADDR
        self._generators["SOCKET_ADDR"] = lambda: f"{self._gen_ipv4()}:{random.randint(1, 65535)}"

        # --- Timestamp ---
        self._generators["MONTH"] = lambda: random.choice([
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
        ])
        self._generators["MONTHNUM"] = lambda: f"{random.randint(1, 12):02d}"
        self._generators["MONTHDAY"] = lambda: f"{random.randint(1, 28):02d}"
        self._generators["DAY"] = lambda: random.choice([
            "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"
        ])
        self._generators["YEAR"] = lambda: str(datetime.now().year)
        self._generators["HOUR"] = lambda: f"{random.randint(0, 23):02d}"
        self._generators["MINUTE"] = lambda: f"{random.randint(0, 59):02d}"
        self._generators["SECOND"] = lambda: f"{random.randint(0, 59):02d}"
        self._generators["TIME"] = lambda: f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}"
        self._generators["ISO8601_TIMEZONE"] = lambda: random.choice([
            "+08:00", "+00:00", "-05:00", "-08:00", "+01:00", "+05:30", "Z"
        ])
        self._generators["TZ"] = lambda: random.choice(["UTC", "HKT", "EST", "PST", "CET", "IST"])
        self._generators["UNIX_EPOCH_MS"] = lambda: str(int(datetime.now().timestamp() * 1000))
        self._generators["UNIX_EPOCH_SEC"] = lambda: str(int(datetime.now().timestamp()))

        # --- Composite Timestamps ---
        self._generators["TIMESTAMP_ISO8601"] = lambda: self._gen_iso8601()
        self._generators["SYSLOGTIMESTAMP"] = lambda: self._gen_syslog_timestamp()
        self._generators["CISCO_TIMESTAMP"] = lambda: self._gen_cisco_timestamp()
        self._generators["CISCO_ASA_TIMESTAMP"] = lambda: self._gen_asa_timestamp()
        self._generators["JUNIPER_TIMESTAMP"] = lambda: self._gen_juniper_timestamp()
        self._generators["HUAWEI_TIMESTAMP"] = lambda: self._gen_huawei_timestamp()

    # ---- IP Generation ----
    def _gen_ipv4(self) -> str:
        return ".".join(str(random.randint(0, 255)) for _ in range(4))

    def _gen_private_ipv4(self) -> str:
        """RFC 1918 private IPv4: 10/8, 172.16/12, 192.168/16"""
        choice_idx = random.randint(0, 2)
        if choice_idx == 0:
            # 10.0.0.0/8
            return f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
        elif choice_idx == 1:
            # 172.16.0.0/12
            return f"172.{random.randint(16, 31)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
        else:
            # 192.168.0.0/16
            return f"192.168.{random.randint(0, 255)}.{random.randint(1, 254)}"

    def _gen_public_ipv4(self) -> str:
        # Exclude private ranges, simplified generation
        while True:
            a = random.randint(1, 223)
            if a in (10, 127) or (a == 172 and 16 <= random.randint(0, 31) <= 31) or a == 192:
                continue
            return f"{a}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"

    def _gen_ipv6(self) -> str:
        # Generate full IPv6
        segments = [f"{random.randint(0, 65535):04x}" for _ in range(8)]
        return ":".join(segments)

    def _gen_ipv6_short(self) -> str:
        # Generate abbreviated IPv6 (with ::)
        parts = [f"{random.randint(0, 65535):04x}" for _ in range(random.randint(2, 5))]
        return ":".join(parts) + "::" + ":".join(
            f"{random.randint(0, 65535):04x}" for _ in range(random.randint(1, 3))
        )

    # ---- Timestamp Generation ----
    def _gen_iso8601(self) -> str:
        now = datetime.now() - timedelta(seconds=random.randint(0, 86400))
        return now.strftime("%Y-%m-%dT%H:%M:%S") + random.choice(["+08:00", "+00:00", "Z"])

    def _gen_syslog_timestamp(self) -> str:
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        now = datetime.now() - timedelta(seconds=random.randint(0, 86400))
        return f"{months[now.month - 1]} {now.day:2d} {now.strftime('%H:%M:%S')}"

    def _gen_cisco_timestamp(self) -> str:
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        now = datetime.now() - timedelta(seconds=random.randint(0, 86400))
        return f"{months[now.month - 1]} {now.day:2d} {now.year} {now.strftime('%H:%M:%S')}"

    def _gen_asa_timestamp(self) -> str:
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        now = datetime.now() - timedelta(seconds=random.randint(0, 86400))
        return f"{months[now.month - 1]} {now.day:2d} {now.year} {now.strftime('%H:%M:%S')}"

    def _gen_juniper_timestamp(self) -> str:
        now = datetime.now() - timedelta(seconds=random.randint(0, 86400))
        return now.strftime("%Y-%m-%d %H:%M:%S")

    def _gen_huawei_timestamp(self) -> str:
        now = datetime.now() - timedelta(seconds=random.randint(0, 86400))
        tz = random.choice(["+08:00", "+00:00", "+05:30"])
        return now.strftime("%Y-%m-%d %H:%M:%S") + tz

    # ---- Public Interface ----
    def generate_value(self, pattern_name: str) -> str:
        """
        Generate a random value for a given pattern name
        Prefer built-in generator, fall back to regex sampling
        """
        self.load_all()
        if pattern_name in self._generators:
            return self._generators[pattern_name]()
        # fallback: generate from regex (using rstr or simple method)
        regex = self.patterns.get(pattern_name)
        if regex:
            return self._sample_from_regex(regex)
        return f"<UNKNOWN:{pattern_name}>"

    def _sample_from_regex(self, regex_str: str) -> str:
        """Generate a random matching string from regex — supports alternation, groups, quantifiers, char classes"""
        return self._regex_gen(regex_str)

    def _regex_gen(self, pattern: str) -> str:
        """Recursive regex random generator"""
        # 1. Top-level alternation: find | not inside parens/brackets
        parts = self._split_alternation(pattern)
        if len(parts) > 1:
            return self._regex_gen(random.choice(parts))

        result = []
        i = 0
        while i < len(pattern):
            c = pattern[i]

            # Escape sequences
            if c == "\\" and i + 1 < len(pattern):
                esc = pattern[i + 1]
                esc_map = {
                    "d": random.choice(string.digits),
                    "D": random.choice(string.ascii_letters + string.punctuation.replace("\\", "")),
                    "w": random.choice(string.ascii_letters + string.digits + "_"),
                    "W": random.choice("!@#$%^&*()-=+[]{}\\|;:',.<>/? "),
                    "s": random.choice(" \t"),
                    "S": random.choice(string.ascii_letters + string.digits),
                    "t": "\t",
                    "n": "\n",
                    "r": "\r",
                    ".": ".",
                    "-": "-",
                    "\\": "\\",
                    "*": "*",
                    "+": "+",
                    "?": "?",
                    "|": "|",
                    "(": "(",
                    ")": ")",
                    "[": "[",
                    "]": "]",
                    "{": "{",
                    "}": "}",
                    "b": "",
                }
                result.append(esc_map.get(esc, esc))
                i += 2
                continue

            # Character class [...]
            if c == "[":
                j = i + 1
                depth = 1
                while j < len(pattern) and depth > 0:
                    if pattern[j] == "\\":
                        j += 1  # skip escaped char
                    elif pattern[j] == "[":
                        depth += 1
                    elif pattern[j] == "]":
                        depth -= 1
                    j += 1
                char_class = pattern[i + 1 : j - 1]
                chars = self._expand_char_class(char_class)
                # Check for quantifier after
                q = self._read_quantifier(pattern, j)
                count = self._quantifier_count(q)
                result.append("".join(random.choice(chars) for _ in range(count)))
                i = j + len(q)
                continue

            # Group (?:...) or (...)
            if c == "(":
                j = i + 1
                depth = 1
                is_noncap = False
                if pattern[j:j+2] == "?:":
                    is_noncap = True
                    j += 2
                elif pattern[j:j+2] in ("?=", "?!"):
                    # lookahead: skip, return empty
                    j += 2
                start = j
                while j < len(pattern) and depth > 0:
                    if pattern[j] == "\\":
                        j += 1
                    elif pattern[j] == "(" and not (j > start and pattern[j-1] == "\\"):
                        depth += 1
                    elif pattern[j] == ")" and not (j > start and pattern[j-1] == "\\"):
                        depth -= 1
                    j += 1
                group_content = pattern[start : j - 1]
                q = self._read_quantifier(pattern, j)
                count = self._quantifier_count(q)
                inner = "".join(self._regex_gen(group_content) for _ in range(count))
                result.append(inner)
                i = j + len(q)
                continue

            # Anchors / word boundaries → skip
            if c in ("^", "$"):
                i += 1
                continue

            # Literal character
            q = self._read_quantifier(pattern, i + 1)
            count = self._quantifier_count(q)
            result.append(c * count)
            i += 1 + len(q)

        return "".join(result)

    def _split_alternation(self, pattern: str) -> list:
        """Split at top-level | (ignore those inside parens/brackets)"""
        parts = []
        depth_paren = 0
        depth_bracket = 0
        last = 0
        i = 0
        while i < len(pattern):
            c = pattern[i]
            if c == "\\":
                i += 2
                continue
            if c == "[":
                depth_bracket += 1
            elif c == "]":
                depth_bracket -= 1
            elif c == "(" and depth_bracket == 0:
                depth_paren += 1
            elif c == ")" and depth_bracket == 0:
                depth_paren -= 1
            elif c == "|" and depth_paren == 0 and depth_bracket == 0:
                parts.append(pattern[last:i])
                last = i + 1
            i += 1
        parts.append(pattern[last:])
        return parts

    def _read_quantifier(self, pattern: str, start: int) -> str:
        """Read pos quantifier at position: {n,m}, {n}, *, +, ?"""
        if start >= len(pattern):
            return ""
        c = pattern[start]
        if c in ("*", "+", "?"):
            return c
        if c == "{":
            j = start
            while j < len(pattern) and pattern[j] != "}":
                j += 1
            if j < len(pattern):
                return pattern[start : j + 1]
        return ""

    def _quantifier_count(self, q: str) -> int:
        """Parse quantifier to a concrete count"""
        if not q:
            return 1
        if q == "*":
            return random.randint(0, 3)
        if q == "+":
            return random.randint(1, 4)
        if q == "?":
            return random.randint(0, 1)
        # {n} or {n,m}
        m = re.match(r"\{(\d+)(?:,(\d*))?\}", q)
        if m:
            lo = int(m.group(1))
            hi_str = m.group(2)
            if hi_str is None:
                return lo
            hi = int(hi_str) if hi_str else lo * 3
            return random.randint(lo, hi)
        return 1

    def _expand_char_class(self, char_class: str) -> list:
        """Expand character class [...content...] into a list of possible characters"""
        chars = []
        i = 0
        negate = False
        if char_class.startswith("^"):
            negate = True
            i = 1

        while i < len(char_class):
            c = char_class[i]
            # Escape sequences inside char class
            if c == "\\" and i + 1 < len(char_class):
                esc = char_class[i + 1]
                esc_map = {
                    "d": string.digits,
                    "D": string.ascii_letters + string.punctuation.replace("\\", ""),
                    "w": string.ascii_letters + string.digits + "_",
                    "W": "!@#$%^&*()-=+[]{}|;:',.<>/? ",
                    "s": " \t\n\r",
                    "S": string.ascii_letters + string.digits,
                    "t": "\t",
                    "n": "\n",
                }
                if esc in esc_map:
                    chars.extend(esc_map[esc])
                else:
                    chars.append(esc)
                i += 2
                continue

            # Range: a-z, 0-9, A-Z
            if i + 2 < len(char_class) and char_class[i + 1] == "-" and char_class[i + 2] != "]":
                start_c, end_c = c, char_class[i + 2]
                for code in range(ord(start_c), ord(end_c) + 1):
                    chars.append(chr(code))
                i += 3
                continue

            chars.append(c)
            i += 1

        if negate:
            # Simple approach: take complement of common printable characters
            all_chars = set(string.ascii_letters + string.digits + " _-.:")
            chars = list(all_chars - set(chars))

        return chars if chars else [" "]

    def generate_from_template(self, template: str) -> str:
        """Generate log line from template, replacing all %{PATTERN}"""
        self.load_all()

        def replacer(match):
            pattern_name = match.group(1)
            return self.generate_value(pattern_name)

        return re.sub(r"%\{(\w+)\}", replacer, template)


# Singleton
_loader_instance: Optional[GrokLoader] = None


def get_loader() -> GrokLoader:
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = GrokLoader()
    return _loader_instance
