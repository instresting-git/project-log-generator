"""
TOML Config Parser
==================
Parses product/<vendor>/<product>.toml config files,
extracts log type definitions, field mappings, and output config.
"""

import os
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class FieldDefinition:
    """Single field definition — values → random pick, pattern → grok generation"""
    name: str
    pattern: Optional[str] = None  # grok pattern name
    values: Optional[List[str]] = None  # custom value pool


@dataclass
class LogType:
    """Log type definition"""
    name: str
    description: str
    template: str
    fields: Dict[str, FieldDefinition] = field(default_factory=dict)
    rate: int = 1  # events per second (for future use)


@dataclass
class OutputConfig:
    """Output destination config"""
    protocol: str = "stdout"  # syslog, tcp, udp, file, http, stdout
    host: Optional[str] = None
    port: Optional[int] = None
    file_path: Optional[str] = None
    http_url: Optional[str] = None
    facility: int = 1  # syslog facility (user-level)
    severity: int = 5  # syslog severity (notice)


@dataclass
class ProductConfig:
    """Complete product configuration"""
    name: str
    vendor: str
    product_type: str
    output: OutputConfig = field(default_factory=OutputConfig)
    logs: List[LogType] = field(default_factory=list)


class TOMLParser:
    """Simple TOML parser (avoids third-party deps for config file parsing)"""

    def __init__(self):
        self._configs: Dict[str, Dict[str, ProductConfig]] = {}  # vendor -> product_name -> config

    def load_all_products(self, product_dir: Optional[str] = None) -> Dict[str, Dict[str, ProductConfig]]:
        """Load all product TOML configs"""
        if product_dir is None:
            product_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "product"
            )

        if not os.path.exists(product_dir):
            raise FileNotFoundError(f"Product directory not found: {product_dir}")

        for vendor in os.listdir(product_dir):
            vendor_path = os.path.join(product_dir, vendor)
            if not os.path.isdir(vendor_path):
                continue
            for filename in os.listdir(vendor_path):
                if filename.endswith(".toml"):
                    filepath = os.path.join(vendor_path, filename)
                    config = self.parse_file(filepath)
                    if vendor not in self._configs:
                        self._configs[vendor] = {}
                    product_name = filename.replace(".toml", "")
                    self._configs[vendor][product_name] = config

        return self._configs

    def parse_file(self, filepath: str) -> ProductConfig:
        """Parse a single TOML file"""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        return self._parse_toml_content(content)

    def _parse_toml_content(self, content: str) -> ProductConfig:
        """Parse TOML content into ProductConfig"""
        config = ProductConfig(name="", vendor="", product_type="")
        current_section = ""
        current_subsection = ""
        current_log: Optional[LogType] = None
        log_index = -1

        lines = content.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                i += 1
                continue

            # Parse section header [section] or [[array]]
            section_match = re.match(r"^\[\[(\w+)\]\]$", line)  # [[logs]]
            table_match = re.match(r"^\[(\w+)(?:\.(\w+))?\]$", line)  # [product] or [output]

            if section_match:
                current_section = section_match.group(1)
                current_subsection = ""  # Reset sub-section
                if current_section == "logs":
                    log_index += 1
                    current_log = LogType(
                        name=f"log_{log_index}",
                        description="",
                        template="",
                    )
                    config.logs.append(current_log)
                i += 1
                continue

            if table_match:
                current_section = table_match.group(1)
                sub_section = table_match.group(2)
                current_subsection = sub_section or ""
                # [logs.fields] should not reset current_log
                if not (current_section == "logs" and sub_section == "fields"):
                    current_log = None
                i += 1
                continue

            # Parse key = value
            kv_match = re.match(r"^(\w+)\s*=\s*(.+)$", line)
            if kv_match:
                key = kv_match.group(1)
                value_str = kv_match.group(2)

                # Handle multi-line values (starting with """)
                if value_str.strip().startswith('"""'):
                    full_value = value_str.strip()[3:]
                    # Collect lines until closing """ is found
                    while i + 1 < len(lines) and '"""' not in full_value:
                        i += 1
                        full_value += "\n" + lines[i]
                    full_value = full_value.replace('"""', '').strip()
                    value = full_value
                else:
                    value = self._parse_toml_value(value_str)

                if current_section == "product":
                    setattr(config, key, value_str.strip('"\''))
                elif current_section == "output":
                    setattr(config.output, key, value)
                elif current_section == "logs" and current_log:
                    # If inside [logs.fields], parse as field definition
                    if current_subsection == "fields":
                        fd = self._parse_field_definition(key, value_str)
                        current_log.fields[key] = fd
                    elif hasattr(current_log, key):
                        setattr(current_log, key, value)

                i += 1
                continue

            # Parse inline table: key = { ... }
            inline_match = re.match(r"^(\w+)\s*=\s*\{(.+)\}$", line)
            if inline_match:
                key = inline_match.group(1)
                inline_content = inline_match.group(2)

                if current_section == "output":
                    pairs = self._parse_inline_kv(inline_content)
                    for k, v in pairs.items():
                        setattr(config.output, k, v)
                elif key == "fields" and current_log:
                    current_log.fields = self._parse_fields_section(inline_content, lines, i)

                i += 1
                continue

            # If inside [logs.fields] and is a pure field definition line (contains {})
            if current_section == "logs" and current_subsection == "fields" and current_log:
                field_match = re.match(r'^(\w+)\s*=\s*\{(.+)\}$', line)
                if field_match:
                    field_name = field_match.group(1)
                    field_content = field_match.group(2)
                    fd = self._parse_field_definition_from_content(field_name, field_content)
                    current_log.fields[field_name] = fd

            i += 1

        return config

    def _parse_toml_value(self, value_str: str) -> Any:
        """Parse a TOML value"""
        value_str = value_str.strip()
        # String
        if (value_str.startswith('"') and value_str.endswith('"')) or \
           (value_str.startswith("'") and value_str.endswith("'")):
            return value_str[1:-1]
        # Integer
        if value_str.isdigit() or (value_str.startswith("-") and value_str[1:].isdigit()):
            return int(value_str)
        # Float
        try:
            return float(value_str)
        except ValueError:
            pass
        # Boolean
        if value_str.lower() == "true":
            return True
        if value_str.lower() == "false":
            return False
        # Array
        if value_str.startswith("[") and value_str.endswith("]"):
            items = value_str[1:-1].split(",")
            return [self._parse_toml_value(item) for item in items if item.strip()]
        return value_str

    def _parse_inline_kv(self, content: str) -> Dict[str, Any]:
        """Parse { key = "value", key2 = 123 } format"""
        result = {}
        i = 0
        while i < len(content):
            # skip whitespace
            while i < len(content) and content[i] in " ,\t":
                i += 1
            if i >= len(content):
                break
            # read key
            key_start = i
            while i < len(content) and content[i] not in " =\n\r":
                i += 1
            key = content[key_start:i].strip()
            if not key:
                break
            # skip to =
            while i < len(content) and content[i] in " ":
                i += 1
            if i < len(content) and content[i] == "=":
                i += 1
            else:
                break
            # skip whitespace
            while i < len(content) and content[i] in " ":
                i += 1
            # read value
            if i >= len(content):
                break
            if content[i] == '"':
                i += 1
                val_start = i
                while i < len(content) and content[i] != '"':
                    if content[i] == '\\':
                        i += 1
                    i += 1
                value = content[val_start:i]
                i += 1  # skip closing "
            elif content[i] == "'":
                i += 1
                val_start = i
                while i < len(content) and content[i] != "'":
                    i += 1
                value = content[val_start:i]
                i += 1
            elif content[i] == "[":
                # Array
                i += 1
                val_start = i
                depth = 1
                while i < len(content) and depth > 0:
                    if content[i] == "[":
                        depth += 1
                    elif content[i] == "]":
                        depth -= 1
                    i += 1
                value = content[val_start:i-1]
            else:
                val_start = i
                while i < len(content) and content[i] not in " ,}":
                    i += 1
                value = content[val_start:i].strip()
            result[key] = value
        return result

    def _parse_field_definition(self, name: str, value_str: str) -> FieldDefinition:
        """Parse a single field definition: { type = "base", pattern = "INT" }"""
        # Remove outer {}
        content = value_str.strip()
        if content.startswith("{") and content.endswith("}"):
            content = content[1:-1]
        return self._parse_field_definition_from_content(name, content)

    def _parse_field_definition_from_content(self, name: str, content: str) -> FieldDefinition:
        """Parse FieldDefinition from { ... } content
        - has values → random pick from pool
        - has pattern → grok generation
        - neither → try field name as grok pattern name
        """
        pairs = self._parse_inline_kv(content)
        
        pattern = pairs.get("pattern", None)
        values_raw = pairs.get("values", None)
        
        values = None
        if values_raw:
            raw = values_raw.strip().strip('"\'').strip()
            separator = "|" if "|" in raw else ","
            values = []
            for item in raw.split(separator):
                item = item.strip().strip('"\'').strip()
                if item:
                    values.append(item)
        
        return FieldDefinition(
            name=name,
            pattern=pattern,
            values=values if values else None,
        )

    def _parse_fields_section(self, inline_content: str, lines: List[str], start_idx: int) -> Dict[str, FieldDefinition]:
        """Parse [logs.fields] inline table"""
        # This is handled inline now
        fields = {}
        return fields

    def get_config(self, vendor: str, product: str) -> Optional[ProductConfig]:
        """Get config for a specific product"""
        return self._configs.get(vendor, {}).get(product)

    def list_products(self) -> List[Dict[str, str]]:
        """List all loaded products"""
        products = []
        for vendor, vendor_configs in self._configs.items():
            for product_name in vendor_configs:
                products.append({"vendor": vendor, "product": product_name})
        return products


# Singleton
_parser_instance: Optional[TOMLParser] = None


def get_parser() -> TOMLParser:
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = TOMLParser()
    return _parser_instance
