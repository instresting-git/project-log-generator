"""
Config Generator — Core Generation Logic
=========================================
Generates logs from parsed TOML configs,
sends them via different protocols (syslog, TCP, UDP, HTTP, File).
"""

import re
import time
import random
import socket
import threading
import json
import os
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from .grok_loader import get_loader
from .toml_parser import ProductConfig, LogType, FieldDefinition, OutputConfig


@dataclass
class GenerationStats:
    """Generation statistics"""
    total_generated: int = 0
    total_sent: int = 0
    total_failed: int = 0
    start_time: float = 0.0
    bytes_sent: int = 0
    per_type: dict = field(default_factory=dict)  # log_type_name -> count


class LogGenerator:
    """Core log generation and send engine"""

    def __init__(self, config: ProductConfig):
        self.config = config
        self.loader = get_loader()
        self.stats = GenerationStats()
        self._running = False
        self._custom_generators: Dict[str, Callable] = {}

    # ================================================================
    # Log Generation
    # ================================================================

    def generate_log(self, log_type: LogType) -> str:
        """
        Generate a single log line from LogType definition.
        Supports %{PATTERN_NAME} placeholders and custom field values.
        """
        template = log_type.template
        fields = log_type.fields

        def replacer(match):
            field_name = match.group(1)

            # Check if there is a custom field definition
            if field_name in fields:
                fd = fields[field_name]
                if fd.values:
                    return random.choice(fd.values)
                elif fd.pattern:
                    return self.loader.generate_value(fd.pattern)
                else:
                    return self.loader.generate_value(field_name)
            else:
                # Use grok loader default generation
                return self.loader.generate_value(field_name)

        return re.sub(r"%\{(\w+)\}", replacer, template)

    def generate_batch(self, log_type: LogType, count: int) -> List[str]:
        """Batch generate logs"""
        return [self.generate_log(log_type) for _ in range(count)]

    # ================================================================
    # Log Sending
    # ================================================================

    def send_log(self, log_line: str, output: Optional[OutputConfig] = None) -> bool:
        """Send a single log line to the target"""
        if output is None:
            output = self.config.output

        protocol = output.protocol.lower()

        try:
            if protocol == "stdout":
                self._send_stdout(log_line)
            elif protocol == "syslog":
                self._send_syslog(log_line, output)
            elif protocol == "tcp":
                self._send_tcp(log_line, output)
            elif protocol == "udp":
                self._send_udp(log_line, output)
            elif protocol == "http":
                self._send_http(log_line, output)
            elif protocol == "file":
                self._send_file(log_line, output)
            else:
                print(f"[WARN] Unknown protocol '{protocol}', falling back to stdout")
                self._send_stdout(log_line)

            self.stats.total_sent += 1
            self.stats.bytes_sent += len(log_line.encode("utf-8"))
            return True

        except Exception as e:
            self.stats.total_failed += 1
            print(f"[ERROR] Failed to send log: {e}")
            return False

    def send_batch(self, logs: List[str], output: Optional[OutputConfig] = None) -> int:
        """Batch send logs, returns number of successes"""
        success = 0
        for log_line in logs:
            if self.send_log(log_line, output):
                success += 1
            self.stats.total_generated += 1
        return success

    # ---- Protocol Implementations ----

    def _send_stdout(self, log_line: str) -> None:
        """Write to standard output"""
        print(log_line)

    def _send_syslog(self, log_line: str, output: OutputConfig) -> None:
        """
        Syslog protocol (RFC 5424 simplified).
        Defaults to UDP port 514.
        """
        host = output.host or "127.0.0.1"
        port = output.port or 514
        facility = output.facility or 1
        severity = output.severity or 5

        # Build PRI part: <priority>
        pri = facility * 8 + severity

        # Build HEADER part
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")
        hostname = socket.gethostname()
        app_name = self.config.name.replace(" ", "-").lower()
        msgid = "LOG"

        # RFC 5424 format: <PRI>VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID [SD] MSG
        syslog_msg = f"<{pri}>1 {timestamp} {hostname} {app_name} - {msgid} - {log_line}\n"

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        try:
            sock.sendto(syslog_msg.encode("utf-8"), (host, port))
        finally:
            sock.close()

    def _send_tcp(self, log_line: str, output: OutputConfig) -> None:
        """Raw TCP send"""
        host = output.host or "127.0.0.1"
        port = output.port or 9000

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            sock.connect((host, port))
            sock.sendall((log_line + "\n").encode("utf-8"))
        finally:
            sock.close()

    def _send_udp(self, log_line: str, output: OutputConfig) -> None:
        """Raw UDP send"""
        host = output.host or "127.0.0.1"
        port = output.port or 9000

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        try:
            sock.sendto((log_line + "\n").encode("utf-8"), (host, port))
        finally:
            sock.close()

    def _send_http(self, log_line: str, output: OutputConfig) -> None:
        """HTTP POST send (using urllib to avoid extra dependencies)"""
        import urllib.request

        url = output.http_url or "http://127.0.0.1:8080/logs"
        data = json.dumps({
            "timestamp": datetime.now().isoformat(),
            "vendor": self.config.vendor,
            "product": self.config.name,
            "message": log_line,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            raise ConnectionError(f"HTTP send failed: {e}")

    def _send_file(self, log_line: str, output: OutputConfig) -> None:
        """Write to file"""
        file_path = output.file_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "output",
            f"{self.config.vendor}_{self.config.product_type}.log",
        )
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")

    # ================================================================
    # Continuous Generation Mode
    # ================================================================

    def run_continuous(
        self,
        log_type_name: Optional[str] = None,
        eps: float = 1.0,  # events per second
        duration: Optional[float] = None,  # seconds, None = forever
        output: Optional[OutputConfig] = None,
    ) -> None:
        """Continuously generate and send logs with weighted random distribution across log types"""
        # Select log types
        if log_type_name:
            log_types = [lt for lt in self.config.logs if lt.name == log_type_name]
        else:
            log_types = self.config.logs

        if not log_types:
            print(f"[ERROR] No log types found for {self.config.vendor}/{self.config.name}")
            return

        # Calculate weighted distribution
        weights = [lt.rate for lt in log_types]
        total_weight = sum(weights)

        self.stats.start_time = time.time()
        self.stats.per_type = {lt.name: 0 for lt in log_types}
        self._running = True
        interval = 1.0 / eps if eps > 0 else 1.0
        start = time.time()

        print(f"[INFO] Starting log generation: {self.config.vendor}/{self.config.name}")
        print(f"[INFO] Protocol: {output.protocol if output else self.config.output.protocol}")
        print(f"[INFO] Rate: {eps} EPS | Duration: {duration if duration else 'unlimited'}")
        if not log_type_name:
            print(f"[INFO] Weighted distribution ({total_weight} total):")
            for lt, w in zip(log_types, weights):
                pct = w / total_weight * 100
                print(f"       {lt.name}: rate={w} ({pct:.1f}%)")
        print("-" * 60)

        try:
            while self._running:
                # Weighted random selection of log type
                lt = random.choices(log_types, weights=weights, k=1)[0]
                log_line = self.generate_log(lt)
                self.stats.total_generated += 1
                self.stats.per_type[lt.name] = self.stats.per_type.get(lt.name, 0) + 1
                self.send_log(log_line, output)
                time.sleep(interval)

                # Check duration
                if duration and (time.time() - start) >= duration:
                    break

        except KeyboardInterrupt:
            print("\n[INFO] Interrupted by user")
        finally:
            self._running = False
            self._print_stats()

    def stop(self) -> None:
        """Stop generation"""
        self._running = False

    def _print_stats(self) -> None:
        """Print statistics"""
        elapsed = time.time() - self.stats.start_time
        mb_sent = self.stats.bytes_sent / (1024 * 1024)
        eps = self.stats.total_generated / elapsed if elapsed > 0 else 0

        print("-" * 60)
        print(f"[STATS] Elapsed: {elapsed:.2f}s")
        print(f"[STATS] Generated: {self.stats.total_generated}")
        print(f"[STATS] Sent: {self.stats.total_sent}")
        print(f"[STATS] Failed: {self.stats.total_failed}")
        print(f"[STATS] Data: {mb_sent:.2f} MB")
        print(f"[STATS] Avg Rate: {eps:.2f} EPS")
        if self.stats.per_type:
            print(f"[STATS] Per Type:")
            for name, count in sorted(self.stats.per_type.items()):
                pct = count / self.stats.total_generated * 100 if self.stats.total_generated else 0
                print(f"         {name}: {count} ({pct:.1f}%)")

    def run_single(
        self,
        log_type_name: Optional[str] = None,
        count: int = 1,
        output: Optional[OutputConfig] = None,
    ) -> List[str]:
        """Generate and send a fixed number of logs (weighted distribution)"""
        if log_type_name:
            log_types = [lt for lt in self.config.logs if lt.name == log_type_name]
        else:
            log_types = self.config.logs

        if not log_types:
            print(f"[ERROR] No log types found")
            return []

        results = []
        weights = [lt.rate for lt in log_types]
        for _ in range(count):
            lt = random.choices(log_types, weights=weights, k=1)[0]
            log_line = self.generate_log(lt)
            results.append(log_line)
            self.stats.total_generated += 1
            if output:
                self.send_log(log_line, output)
            else:
                self._send_stdout(log_line)

        return results


class ConfigGenerator:
    """Config loader and generator factory"""

    def __init__(self):
        from .toml_parser import get_parser
        self.parser = get_parser()
        self._generators: Dict[str, LogGenerator] = {}

    def load_products(self, product_dir: Optional[str] = None) -> List[str]:
        """Load all products, return product list"""
        configs = self.parser.load_all_products(product_dir)
        products = []
        for vendor, vendor_configs in configs.items():
            for product_name, config in vendor_configs.items():
                key = f"{vendor}/{product_name}"
                self._generators[key] = LogGenerator(config)
                products.append(key)
        return products

    def get_generator(self, vendor: str, product: str) -> Optional[LogGenerator]:
        """Get generator for a specific product"""
        key = f"{vendor}/{product}"
        if key not in self._generators:
            config = self.parser.get_config(vendor, product)
            if config:
                self._generators[key] = LogGenerator(config)
        return self._generators.get(key)

    def list_products(self) -> List[Dict[str, str]]:
        """List products"""
        return self.parser.list_products()

    def list_log_types(self, vendor: str, product: str) -> List[str]:
        """List log types for a product"""
        config = self.parser.get_config(vendor, product)
        if config:
            return [lt.name for lt in config.logs]
        return []

    def generate_sample(
        self,
        vendor: str,
        product: str,
        log_type: Optional[str] = None,
        count: int = 3,
    ) -> List[str]:
        """Generate sample logs (no send)"""
        gen = self.get_generator(vendor, product)
        if not gen:
            return []
        results = []
        log_type_obj = None
        if log_type:
            matches = [lt for lt in gen.config.logs if lt.name == log_type]
            if matches:
                log_type_obj = matches[0]
        for _ in range(count):
            lt = log_type_obj or random.choice(gen.config.logs)
            results.append(gen.generate_log(lt))
        return results
