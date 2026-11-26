#!/usr/bin/env python3
"""Run a sanitized mixed-site UniFi fixture through the Client and optional Server path."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace


CLIENT_ROOT = Path("/app")
if CLIENT_ROOT.is_dir():
    sys.path.insert(0, str(CLIENT_ROOT))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "clients"))

from host_collector import HostExtensionCollector
from multi_device_contracts import build_envelope
from device_client_transport import DeviceHTTPSClient
from device_client_config import load_client_selection
from unifi_api import APIError, UniFiAPICollector
from unifi_collector import UniFiDomainCollector


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path):
    with Path(path).open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _site_payloads(fixture_directory, *, total_power_override=None):
    root = Path(fixture_directory)
    rps_capture = _load_json(root / "usp-rps-raw.json")
    raw_ssh = _load_json(root / "ucg-max-raw.json")
    collected_at = _utc_now()
    target = {
        "id": "fixture-ucg-max", "model": "UCG Max", "name": "Fixture UCG Max",
        "type": "gateway", "state": "ONLINE",
    }
    ethernet_devices = [
        {"id": "fixture-udw", "model": "UniFi Dream Wall", "name": "Fixture UDW", "type": "gateway", "state": "ONLINE"},
        {"id": "fixture-pro-hd", "model": "USW Pro HD 24", "name": "Fixture Pro HD", "type": "switch", "state": "ONLINE"},
        {"id": "fixture-promax24", "model": "USW Pro Max 24 PoE", "name": "Fixture Pro Max 24", "type": "switch", "state": "ONLINE"},
        {"id": "fixture-u6-mesh", "model": "U6 Mesh", "name": "Fixture Mesh AP", "type": "ap", "state": "ONLINE"},
        {"id": "fixture-unknown", "model": "Uncatalogued Test Device", "name": "Fixture Unknown", "type": "switch", "state": "ONLINE"},
    ]
    devices = [target] + copy.deepcopy(rps_capture["devices"]) + ethernet_devices
    legacy = copy.deepcopy(rps_capture["legacy_stat_device"])
    legacy_rps = legacy["data"][0]
    legacy_rps["last_seen"] = collected_at
    if total_power_override is not None:
        if total_power_override not in (99, 101):
            raise ValueError("unsupported fixture power vector")
        # The repository capture is 101 W. A separate synthetic 99 W vector
        # changes only the same-snapshot measured bus field; it is not labeled
        # as a new live observation.
        legacy_rps["rps"]["rps_port_table"][5]["power_54v_power"] = str(total_power_override - 34)
    for device in [target] + ethernet_devices:
        is_promax = device["id"] == "fixture-promax24"
        legacy["data"].append({
            "device_id": device["id"],
            "model": device["model"],
            "port_table": [{
                "port_idx": 1, "name": "Port 1", "up": True,
                "speed": 1000, "rx_bytes": 1000, "tx_bytes": 2000,
                "port_poe": is_promax, "poe_power": "3.25" if is_promax else "0",
            }],
        })
    raw_ssh["collected_at"] = collected_at
    raw_ssh["target_id"] = "ucg-max"
    raw_ssh["profile_id"] = "ucg-max"
    return target, devices, legacy, raw_ssh, collected_at


class _FixtureRawCollector:
    def __init__(self, payload):
        self.payload = payload

    def collect(self):
        return copy.deepcopy(self.payload)

    def diagnostics(self):
        return copy.deepcopy(self.payload.get("diagnostics", {}))


def collect_unifi_fixture(fixture_directory, *, total_power_override=None):
    """Exercise UniFiAPICollector.collect(), _telemetry(), and domain normalization."""
    target, devices, legacy, raw_ssh, collected_at = _site_payloads(
        fixture_directory, total_power_override=total_power_override
    )
    api_config = SimpleNamespace(
        enabled=True, base_url="https://fixture.invalid", ca_file=None,
        tls_sha256=None, timeout_seconds=3, site_id=None,
    )
    config = SimpleNamespace(
        profile_id="ucg-max", host="fixture.invalid", port=22,
        username="fixture", credential_file="", known_hosts_file="",
        connect_timeout_seconds=3, interval_seconds=60, api=api_config,
    )

    with tempfile.TemporaryDirectory(prefix="hardwarestatus-unifi-fixture-") as temporary:
        key_path = Path(temporary) / "fixture-api-key"
        key_path.write_text("fixture-only-api-key\n", encoding="ascii")
        key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

        def request(_config, path, _key):
            if path.endswith("/info"):
                return {"applicationVersion": "fixture"}, 200
            if path.endswith("/sites"):
                return {"data": [{"id": "fixture-site", "internalReference": "fixture", "name": "Fixture Site"}]}, 200
            if path.endswith("/devices"):
                return {"data": devices}, 200
            if path.endswith("/statistics/latest"):
                return {"cpuUtilizationPct": 10.0, "memoryUtilizationPct": 25.0, "uptimeSec": 1000}, 200
            if path.endswith("/devices/fixture-ucg-max"):
                return {"id": target["id"], "model": target["model"], "interfaces": {"ports": []}}, 200
            if path.endswith("/stat/device"):
                return legacy, 200
            if path.endswith("/stat/health") or path.endswith("/stat/sysinfo"):
                return {"data": []}, 200
            if path.endswith("/clients") or path.endswith("/networks") or path.endswith("/switching/lags") or path.endswith("/topology") or path.endswith("/ports/port-anomalies") or path.endswith("/wans") or path.endswith("/enriched-configuration") or path.endswith("/load-balancing/status") or path.endswith("/load-balancing/configuration") or path.endswith("/wan-slas"):
                return {"data": []}, 200
            raise AssertionError("unexpected fixed API route in fixture test")

        api_config.api_key_file = str(key_path)
        api_collector = UniFiAPICollector(api_config, request=request, target_profile="ucg-max")
        domain = UniFiDomainCollector(config, raw_collector=_FixtureRawCollector(raw_ssh))
        domain.api_collector = api_collector
        normalized = domain.collect()
    return normalized, collected_at


def _send_fixture_report(fixture_directory):
    from host_collector import collect_client_build

    unifi, collected_at = collect_unifi_fixture(fixture_directory)
    if unifi.get("stale") is not False or unifi.get("transport", {}).get("status") != "available":
        raise RuntimeError("fixture UniFi normalization did not produce a fresh observation")
    extension = HostExtensionCollector(
        collect_build_metadata=False, unifi_collector=None,
        hardware_enabled=False, filesystem_enabled=False,
        docker_enabled=False, hermes_enabled=False,
    )
    stats = extension.extension_payload()
    stats["client_build"] = collect_client_build(protocol="device_v2")
    stats["unifi"] = unifi
    stats.update({
        "uptime": 1, "load_1": 0.1, "load_5": 0.1, "load_15": 0.1,
        "tcp": 0, "udp": 0, "process": 1, "thread": 1,
        "memory_total": 1024, "memory_used": 128, "swap_total": 0, "swap_used": 0,
        "hdd_total": 1024, "hdd_used": 128, "cpu": 1, "cpu_cores": 1,
        "network_rx": 0, "network_tx": 0, "network_in": 0, "network_out": 0,
        "io_read": 0, "io_write": 0, "cpu_model": "CI fixture", "os": "CI fixture",
    })
    selection = load_client_selection([])
    envelope = build_envelope(
        selection.device_v2, collected_at=_utc_now(), stats=stats,
        hostname="hardwarestatus-unifi-fixture",
    )
    response = DeviceHTTPSClient(selection.device_v2).send(envelope)
    if response.get("accepted") is not True:
        raise RuntimeError("isolated Server did not accept the normalized UniFi fixture report")
    print("UNIFI_FIXTURE_NORMALIZATION=PASS")
    print("UNIFI_FIXTURE_REPORT=ACCEPTED")
    print("UNIFI_RPS_OUTPUT_W=" + str(unifi["rps"]["devices"][0]["total_output_power_w"]))
    print("UNIFI_PROMAX24_PORTS=" + str(sum(
        1 for port in unifi["api"]["telemetry"]["ports"]
        if port.get("device_id") == "fixture-promax24"
    )))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-directory", required=True)
    parser.add_argument("--send-report", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        if arguments.send_report:
            _send_fixture_report(arguments.fixture_directory)
        else:
            normalized, _ = collect_unifi_fixture(arguments.fixture_directory)
            print("UNIFI_FIXTURE_STATUS=" + normalized["api"]["status"])
    except (APIError, OSError, ValueError, KeyError, TypeError, AssertionError, RuntimeError):
        print("UNIFI_FIXTURE=FAIL", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
