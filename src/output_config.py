"""
Output Config Loader
====================
Loads output destination config files from the output/ directory,
supporting multiple output profile definitions (syslog, tcp, udp, http, file).
"""

import os
import re
from typing import Dict, Optional
from dataclasses import dataclass, field


@dataclass
class OutputProfile:
    """Output destination config"""
    name: str
    protocol: str = "syslog"
    host: Optional[str] = None
    port: Optional[int] = None
    file_path: Optional[str] = None
    http_url: Optional[str] = None
    facility: int = 16
    severity: int = 5
    description: str = ""


class OutputConfigLoader:
    """Output profile config loader"""

    def __init__(self):
        self._profiles: Dict[str, OutputProfile] = {}
        self._loaded = False

    def load_all(self, output_dir: Optional[str] = None) -> Dict[str, OutputProfile]:
        """Load all .conf files under output/"""
        if self._loaded:
            return self._profiles

        if output_dir is None:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "output"
            )

        if not os.path.exists(output_dir):
            return self._profiles

        for filename in os.listdir(output_dir):
            if filename.endswith(".conf") and not filename.endswith(".example.conf"):
                filepath = os.path.join(output_dir, filename)
                self._parse_conf_file(filepath)

        self._loaded = True
        return self._profiles

    def _parse_conf_file(self, filepath: str) -> None:
        """Parse a TOML-format output config file"""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Match all [profile_name] sections
        # Format: [profile_name] \n key = value \n ...
        section_pattern = re.compile(
            r'^\[(\w+)\]\s*\n(.*?)(?=\n\[|\Z)', re.MULTILINE | re.DOTALL
        )

        for match in section_pattern.finditer(content):
            profile_name = match.group(1)
            section_body = match.group(2)

            profile = OutputProfile(name=profile_name)

            for line in section_body.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                kv_match = re.match(r'^(\w+)\s*=\s*(.+)$', line)
                if kv_match:
                    key = kv_match.group(1)
                    value_str = kv_match.group(2).strip()

                    # Parse value
                    value = self._parse_value(value_str)

                    if hasattr(profile, key):
                        setattr(profile, key, value)

            self._profiles[profile_name] = profile

    def _parse_value(self, value_str: str):
        """Parse a TOML value"""
        value_str = value_str.strip()
        if (value_str.startswith('"') and value_str.endswith('"')) or \
           (value_str.startswith("'") and value_str.endswith("'")):
            return value_str[1:-1]
        if value_str.isdigit() or (value_str.startswith("-") and value_str[1:].isdigit()):
            return int(value_str)
        try:
            return float(value_str)
        except ValueError:
            pass
        if value_str.lower() in ("true", "false"):
            return value_str.lower() == "true"
        return value_str

    def get_profile(self, name: str) -> Optional[OutputProfile]:
        """Get a specific output profile"""
        self.load_all()
        return self._profiles.get(name)

    def list_profiles(self) -> Dict[str, OutputProfile]:
        """List all output profiles"""
        self.load_all()
        return self._profiles


# Singleton
_loader_instance: Optional[OutputConfigLoader] = None


def get_output_loader() -> OutputConfigLoader:
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = OutputConfigLoader()
    return _loader_instance
