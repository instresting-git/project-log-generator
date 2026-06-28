#!/usr/bin/env python3
"""
Project Log Generator — Multi-Vendor Log Generator CLI
=======================================================
Generates logs for different vendors (Cisco, Huawei, Juniper, etc.)
from TOML configs. Supports multiple output protocols (syslog, TCP, UDP, HTTP, File, stdout).

Usage:
  # List all available products
  python project.py list
  python project.py list-outputs

  # Generate sample logs (print or save to folder)
  python project.py sample --vendor cisco --product asa_firewall
  python project.py sample --vendor huawei --product firewall --type vpn --output-dir ./samples

  # Continuous generation using output/ profiles
  python project.py generate --vendor cisco --product asa_firewall --eps 10 --output-conf local_syslog
  python project.py generate --vendor juniper --product firewall --output-conf tcp_logstash

  # Override / custom output
  python project.py generate --vendor huawei --product firewall --protocol tcp --host 10.0.0.1 --port 5514
"""

import argparse
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config_generator import ConfigGenerator
from src.toml_parser import OutputConfig
from src.output_config import get_output_loader, OutputProfile


def _resolve_output_config(args, default_output: OutputConfig) -> OutputConfig:
    """
    Resolve output config priority:
    1. --output-conf profile (loaded from output/*.conf)
    2. CLI args --protocol / --host / --port etc.
    3. TOML product default output config
    """
    # Start with TOML default
    output = OutputConfig(
        protocol=default_output.protocol,
        host=default_output.host,
        port=default_output.port,
        file_path=default_output.file_path,
        http_url=default_output.http_url,
        facility=getattr(default_output, 'facility', 16),
        severity=getattr(default_output, 'severity', 5),
    )

    # --output-conf profile overrides
    if hasattr(args, 'output_conf') and args.output_conf:
        loader = get_output_loader()
        profile = loader.get_profile(args.output_conf)
        if not profile:
            print(f"[ERROR] Output profile not found: {args.output_conf}")
            print("[INFO] Available profiles:")
            for name, p in loader.list_profiles().items():
                print(f"  - {name}: {p.description}")
            sys.exit(1)
        output.protocol = profile.protocol or output.protocol
        output.host = profile.host or output.host
        output.port = profile.port or output.port
        output.file_path = profile.file_path or output.file_path
        output.http_url = profile.http_url or output.http_url
        output.facility = profile.facility if hasattr(profile, 'facility') else output.facility
        output.severity = profile.severity if hasattr(profile, 'severity') else output.severity

    # CLI args override everything
    if hasattr(args, 'protocol') and args.protocol:
        output.protocol = args.protocol
    if hasattr(args, 'host') and args.host:
        output.host = args.host
    if hasattr(args, 'port') and args.port:
        output.port = args.port
    if hasattr(args, 'file') and args.file:
        output.file_path = args.file
    if hasattr(args, 'http_url') and args.http_url:
        output.http_url = args.http_url
    if hasattr(args, 'facility') and args.facility:
        output.facility = args.facility
    if hasattr(args, 'severity') and args.severity:
        output.severity = args.severity

    return output


def cmd_list(args):
    """List all products and log types"""
    cg = ConfigGenerator()
    products = cg.load_products()

    if args.verbose:
        print("=" * 70)
        print(f"{'Vendor':<12} {'Product':<20} {'Log Types'}")
        print("=" * 70)
        for p in products:
            vendor, product = p.split("/")
            log_types = cg.list_log_types(vendor, product)
            for i, lt in enumerate(log_types):
                prefix = f"{vendor:<12} {product:<20}" if i == 0 else " " * 33
                print(f"{prefix} {lt}")
        print("=" * 70)
        print(f"Total: {len(products)} products")
    else:
        print(f"{'Vendor':<12} {'Product':<25} {'Log Types'}")
        print("-" * 60)
        for p in products:
            vendor, product = p.split("/")
            log_types = cg.list_log_types(vendor, product)
            print(f"{vendor:<12} {product:<25} {', '.join(log_types)}")
        print("-" * 60)
        print(f"Total: {len(products)} products")


def cmd_list_outputs(args):
    """List all output profiles"""
    loader = get_output_loader()
    profiles = loader.list_profiles()

    if not profiles:
        print("[INFO] No output profiles found in output/*.conf")
        return

    print(f"\n{'='*70}")
    print(f" Output Profiles (output/*.conf)")
    print(f"{'='*70}")
    print(f"{'Name':<20} {'Protocol':<10} {'Target':<30} {'Description'}")
    print("-" * 70)
    for name, p in profiles.items():
        if p.protocol in ("syslog", "tcp", "udp"):
            target = f"{p.host or '127.0.0.1'}:{p.port or '-'}"
        elif p.protocol == "file":
            target = p.file_path or "-"
        elif p.protocol == "http":
            target = p.http_url or "-"
        else:
            target = p.protocol
        print(f"{name:<20} {p.protocol:<10} {target:<30} {p.description}")
    print("-" * 70)
    print(f"Total: {len(profiles)} profiles")
    print()


def cmd_sample(args):
    """Generate sample logs"""
    cg = ConfigGenerator()
    cg.load_products()

    count = args.count or 5
    samples = cg.generate_sample(
        args.vendor, args.product,
        log_type=args.type,
        count=count,
    )

    header = f"Sample Logs: {args.vendor}/{args.product}"
    if args.type:
        header += f" | Type: {args.type}"

    # Output to folder
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        vendor = args.vendor
        product = args.product
        log_type_tag = f"_{args.type}" if args.type else ""
        filename = os.path.join(args.output_dir, f"{vendor}_{product}{log_type_tag}_sample.log")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# {header}\n")
            f.write(f"# Generated: {count} samples\n")
            f.write("#" + "="*68 + "\n")
            for sample in samples:
                f.write(sample + "\n")

        print(f"\n{'='*70}")
        print(f" {header}")
        print(f" Count: {count}")
        print(f" Saved to: {filename}")
        print(f"{'='*70}")
        print(f"\n  Preview (first 3):")
        for i, sample in enumerate(samples[:3], 1):
            print(f"  [{i}] {sample}")
        if count > 3:
            print(f"  ... ({count - 3} more lines)")
    else:
        # Print to stdout
        print(f"\n{'='*70}")
        print(f" {header}")
        print(f" Count: {count}")
        print(f"{'='*70}\n")
        for i, sample in enumerate(samples, 1):
            print(f"  [{i}] {sample}")

    print(f"\n{'='*70}")
    print(f" Generated {len(samples)} sample logs")


def cmd_generate(args):
    """Continuously generate and send logs"""
    cg = ConfigGenerator()
    cg.load_products()

    gen = cg.get_generator(args.vendor, args.product)
    if not gen:
        print(f"[ERROR] Product not found: {args.vendor}/{args.product}")
        print("[INFO] Available products:")
        for p in cg.list_products():
            print(f"  - {p['vendor']}/{p['product']}")
        sys.exit(1)

    # Resolve output config (output-conf > CLI args > TOML default)
    output = _resolve_output_config(args, gen.config.output)

    print(f"\n{'='*70}")
    print(f" Log Generator Started")
    print(f" Product: {gen.config.vendor}/{gen.config.name}")
    print(f" Protocol: {output.protocol}")
    if output.protocol in ("syslog", "tcp", "udp"):
        print(f" Target: {output.host}:{output.port}")
    elif output.protocol == "file":
        print(f" File: {output.file_path}")
    elif output.protocol == "http":
        print(f" URL: {output.http_url}")
    if hasattr(args, 'output_conf') and args.output_conf:
        print(f" Profile: {args.output_conf}")
    print(f"{'='*70}\n")

    gen.run_continuous(
        log_type_name=args.type,
        eps=args.eps or 1.0,
        duration=args.duration,
        output=output,
    )


def cmd_oneshot(args):
    """One-shot: generate and send a fixed number of logs"""
    cg = ConfigGenerator()
    cg.load_products()

    gen = cg.get_generator(args.vendor, args.product)
    if not gen:
        print(f"[ERROR] Product not found: {args.vendor}/{args.product}")
        sys.exit(1)

    # Resolve output config
    output = _resolve_output_config(args, gen.config.output)

    results = gen.run_single(
        log_type_name=args.type,
        count=args.count or 1,
        output=output,
    )

    print(f"\n[INFO] Generated and sent {len(results)} logs")
    print(f"[INFO] Protocol: {output.protocol}")
    if output.protocol in ("syslog", "tcp", "udp"):
        print(f"[INFO] Target: {output.host}:{output.port}")


def cmd_validate(args):
    """Validate all configs"""
    cg = ConfigGenerator()
    products = cg.load_products()

    print(f"\n{'='*70}")
    print(f" Configuration Validation Report")
    print(f"{'='*70}\n")

    total_log_types = 0
    all_ok = True

    for vendor_product, gen in cg._generators.items():
        config = gen.config
        print(f"[{vendor_product}]")
        print(f"  Name: {config.name}")
        print(f"  Output Protocol: {config.output.protocol}")
        print(f"  Log Types: {len(config.logs)}")
        for lt in config.logs:
            total_log_types += 1
            print(f"    - {lt.name}: {lt.description[:60]}...")
            # Validate template
            try:
                test_log = gen.generate_log(lt)
                print(f"      ✓ Template OK | Sample: {test_log[:80]}...")
            except Exception as e:
                print(f"      ✗ Template ERROR: {e}")
                all_ok = False
        print()

    print(f"{'='*70}")
    print(f" Products: {len(products)}")
    print(f" Log Types: {total_log_types}")
    print(f" Status: {'✓ ALL OK' if all_ok else '✗ ERRORS FOUND'}")
    print(f"{'='*70}")

    # Also check output profiles
    loader = get_output_loader()
    profiles = loader.list_profiles()
    if profiles:
        print(f"\n Output Profiles: {len(profiles)} loaded from output/*.conf")
        for name, p in profiles.items():
            print(f"    - {name}: {p.protocol} -> {p.host or p.file_path or p.http_url or '-'}")


def main():
    parser = argparse.ArgumentParser(
        description="Project Log Generator — Multi-vendor log generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list
  %(prog)s list -v
  %(prog)s list-outputs
  %(prog)s sample --vendor cisco --product asa_firewall
  %(prog)s sample --vendor huawei --product firewall --type vpn --count 10 --output-dir ./samples
  %(prog)s generate --vendor cisco --product asa_firewall --eps 10 --output-conf local_syslog
  %(prog)s generate --vendor juniper --product firewall --output-conf tcp_logstash
  %(prog)s generate --vendor huawei --product firewall --protocol file --file /var/log/fw.log
  %(prog)s oneshot --vendor cisco --product asa_firewall --count 100 --output-conf http_collector
  %(prog)s validate
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # ---- list ----
    p_list = subparsers.add_parser("list", help="List all products and log types")
    p_list.add_argument("-v", "--verbose", action="store_true", help="Show detailed info")
    p_list.set_defaults(func=cmd_list)

    # ---- list-outputs ----
    p_lout = subparsers.add_parser("list-outputs", help="List output/ destination profiles")
    p_lout.set_defaults(func=cmd_list_outputs)

    # ---- sample ----
    p_sample = subparsers.add_parser("sample", help="Generate sample logs")
    p_sample.add_argument("--vendor", "-V", required=True, help="Vendor (cisco/huawei/juniper)")
    p_sample.add_argument("--product", "-p", required=True, help="Product name")
    p_sample.add_argument("--type", "-t", help="Log type")
    p_sample.add_argument("--count", "-c", type=int, default=5, help="Number of logs to generate")
    p_sample.add_argument("--output-dir", "-o", help="Save to folder (writes .log files)")
    p_sample.set_defaults(func=cmd_sample)

    # ---- generate ----
    p_gen = subparsers.add_parser("generate", help="Continuously generate and send logs")
    p_gen.add_argument("--vendor", "-V", required=True, help="Vendor")
    p_gen.add_argument("--product", "-p", required=True, help="Product name")
    p_gen.add_argument("--type", "-t", help="Log type")
    p_gen.add_argument("--eps", "-r", type=float, default=1.0, help="Events per second")
    p_gen.add_argument("--duration", "-d", type=float, help="Duration in seconds (omit for unlimited)")
    # Output config (3-tier priority)
    p_gen.add_argument("--output-conf", "-O", help="Output profile name from output/")
    p_gen.add_argument("--protocol", choices=["syslog", "tcp", "udp", "http", "file", "stdout"], help="Override protocol")
    p_gen.add_argument("--host", help="Target host IP (overrides profile)")
    p_gen.add_argument("--port", type=int, help="Target port (overrides profile)")
    p_gen.add_argument("--file", help="Output file path (overrides profile)")
    p_gen.add_argument("--http-url", help="HTTP endpoint URL (overrides profile)")
    p_gen.add_argument("--facility", type=int, help="Syslog Facility 0-23 (overrides profile)")
    p_gen.add_argument("--severity", type=int, help="Syslog Severity 0-7 (overrides profile)")
    p_gen.set_defaults(func=cmd_generate)

    # ---- oneshot ----
    p_one = subparsers.add_parser("oneshot", help="One-shot: generate and send a fixed number of logs")
    p_one.add_argument("--vendor", "-V", required=True, help="Vendor")
    p_one.add_argument("--product", "-p", required=True, help="Product name")
    p_one.add_argument("--type", "-t", help="Log type")
    p_one.add_argument("--count", "-c", type=int, default=1, help="Number of logs to generate")
    p_one.add_argument("--output-conf", "-O", help="Output profile name from output/")
    p_one.add_argument("--protocol", choices=["syslog", "tcp", "udp", "http", "file", "stdout"], help="Override protocol")
    p_one.add_argument("--host", help="Target host IP")
    p_one.add_argument("--port", type=int, help="Target port")
    p_one.add_argument("--file", help="Output file path")
    p_one.add_argument("--http-url", help="HTTP endpoint URL")
    p_one.set_defaults(func=cmd_oneshot)

    # ---- validate ----
    p_val = subparsers.add_parser("validate", help="Validate all configs (products + output profiles)")
    p_val.set_defaults(func=cmd_validate)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
