#!/usr/bin/env python3
"""Exercise the built Client image against an isolated real Server image."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time


class SmokeFailure(RuntimeError):
    pass


ROOT = Path(__file__).resolve().parents[1]


def _run(command, *, timeout=90, check=True, input_text=None):
    result = subprocess.run(
        command,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and result.returncode != 0:
        # Do not echo argv, environment, or stderr: Docker diagnostics can
        # include container configuration, and the test handles credentials.
        raise SmokeFailure(
            "test infrastructure command failed (exit code "
            + str(result.returncode)
            + ")"
        )
    return result


def _docker_json(*arguments):
    result = _run(["docker", *arguments])
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SmokeFailure("Docker returned invalid inspection data") from exc


def _write_json(path, value):
    path.write_text(json.dumps(value, separators=(",", ":")) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _inspect_image(image):
    result = _docker_json("image", "inspect", image)
    if not isinstance(result, list) or len(result) != 1:
        raise SmokeFailure("expected exactly one local image")
    return result[0]


def _check_image(image, component, arguments):
    item = _inspect_image(image)
    labels = (item.get("Config") or {}).get("Labels") or {}
    expected_labels = {
        "org.opencontainers.image.version": arguments.version,
        "org.opencontainers.image.revision": arguments.source_sha,
        "io.hardwarestatus.component": component,
        "io.hardwarestatus.unifi.catalog.revision": arguments.catalog_revision,
        "io.hardwarestatus.unifi.catalog.schema_version": str(arguments.catalog_schema_version),
        "io.hardwarestatus.unifi.catalog.sha256": arguments.catalog_sha256,
    }
    for key, value in expected_labels.items():
        if labels.get(key) != value:
            raise SmokeFailure("built image provenance does not match the requested candidate")
    if item.get("Os") != "linux" or item.get("Architecture") != "amd64":
        raise SmokeFailure("runtime smoke requires a linux/amd64 image")
    entrypoint = (item.get("Config") or {}).get("Entrypoint") or []
    expected_entrypoint = (
        ["/app/entrypoint.sh"] if component == "client"
        else ["/usr/local/bin/hardwarestatus-server"]
    )
    if entrypoint != expected_entrypoint:
        raise SmokeFailure("built image entrypoint does not match the expected runtime")
    return item


def _network_addresses(network):
    network_data = _docker_json("network", "inspect", network)[0]
    configs = ((network_data.get("IPAM") or {}).get("Config") or [])
    if not configs or not configs[0].get("Subnet"):
        raise SmokeFailure("isolated Docker network has no IPv4 subnet")
    ipv4_config = next(
        (entry for entry in configs if ipaddress.ip_network(entry["Subnet"], strict=False).version == 4),
        None,
    )
    if ipv4_config is None:
        raise SmokeFailure("isolated Docker network has no IPv4 subnet")
    subnet = ipaddress.ip_network(ipv4_config["Subnet"], strict=False)
    gateway_text = ipv4_config.get("Gateway")
    if not gateway_text:
        raise SmokeFailure("isolated Docker subnet has no declared gateway")
    gateway = ipaddress.ip_address(gateway_text)
    hosts = []
    for address in subnet.hosts():
        if address != gateway:
            hosts.append(address)
        if len(hosts) == 2:
            break
    if len(hosts) < 2:
        raise SmokeFailure("isolated Docker subnet is too small")
    return str(hosts[0]), str(hosts[1])


def _create_test_documents(directory, device_id):
    token = secrets.token_urlsafe(32)
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise SmokeFailure("generated test token did not match Device v2 format")
    token_path = directory / "device-token"
    token_path.write_text(token + "\n", encoding="ascii")
    token_path.chmod(0o400)

    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    not_before = (now - dt.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    not_after = (now + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    _write_json(directory / "registry.json", {
        "version": 1,
        "defaults": {
            "default_device_id": device_id,
            "stale_seconds": 300,
            "offline_seconds": 900,
        },
        "devices": [{
            "id": device_id,
            "display_name": "CI isolated runtime smoke",
            "expected_fqdn": None,
            "enabled": True,
            "order": 1,
            "tags": ["ci", "synthetic"],
            "group": "ci-smoke",
            "ingestion": {
                "mode": "device_v2",
                "active_protocol": "device_v2",
                "cutover_not_after": None,
            },
        }],
    })
    _write_json(directory / "credentials.json", {
        "version": 1,
        "device_id": device_id,
        "algorithm": "sha256",
        "credentials": [{
            "id": "current",
            "digest": digest,
            "not_before": not_before,
            "not_after": not_after,
        }],
    })
    credentials = directory / "credentials"
    credentials.mkdir(mode=0o700)
    (credentials / (device_id + ".json")).write_bytes(
        (directory / "credentials.json").read_bytes()
    )
    (credentials / (device_id + ".json")).chmod(0o600)
    _write_json(directory / "legacy-mapping.json", {"version": 1, "mappings": []})
    return token_path


def _create_tls_material(directory):
    certificate_directory = directory / "proxy-certs"
    certificate_directory.mkdir(mode=0o700)
    certificate = certificate_directory / "server.crt"
    private_key = certificate_directory / "server.key"
    _run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-days", "1", "-keyout", str(private_key), "-out", str(certificate),
        "-subj", "/CN=hardwarestatus-smoke-proxy",
        "-addext", "subjectAltName=DNS:hardwarestatus-smoke-proxy",
        "-addext", "basicConstraints=critical,CA:TRUE",
        "-addext", "keyUsage=critical,digitalSignature,keyEncipherment,keyCertSign",
        "-addext", "extendedKeyUsage=serverAuth",
    ])
    certificate.chmod(0o644)
    private_key.chmod(0o600)
    proxy_config = directory / "default.conf"
    proxy_config.write_text(
        "server {\n"
        "  listen 8443 ssl;\n"
        "  server_name hardwarestatus-smoke-proxy;\n"
        "  ssl_certificate /etc/nginx/certs/server.crt;\n"
        "  ssl_certificate_key /etc/nginx/certs/server.key;\n"
        "  location / {\n"
        "    proxy_pass http://hardwarestatus-smoke-server:80;\n"
        "    proxy_set_header Host $host;\n"
        "    proxy_set_header X-Forwarded-Proto https;\n"
        "    proxy_set_header X-Forwarded-For $remote_addr;\n"
        "  }\n"
        "}\n",
        encoding="ascii",
    )
    proxy_config.chmod(0o644)
    return certificate, proxy_config, certificate_directory


def _container_state(name):
    item = _docker_json("inspect", name)[0]
    state = item.get("State") or {}
    return {
        "running": state.get("Running") is True,
        "restart_count": item.get("RestartCount"),
        "exit_code": state.get("ExitCode"),
        "health": ((state.get("Health") or {}).get("Status")),
    }


def _safe_client_exit_summary(name, state):
    """Expose only bounded, allowlisted diagnostics from a failed test Client."""
    summary = "exit_code=" + str(state.get("exit_code"))
    logs = _run(["docker", "logs", "--tail", "30", name], check=False, timeout=15)
    allowed = (
        re.compile(r"^Client configuration error: (invalid_device_v2_configuration)$"),
        re.compile(r"^device_v2 transport: ([a-z0-9_]{1,64})$"),
    )
    for line in (logs.stdout + "\n" + logs.stderr).splitlines():
        for pattern in allowed:
            match = pattern.fullmatch(line.strip())
            if match:
                summary += " diagnostic=" + match.group(1)
                return summary
    return summary


def _wait_for_server_health(name, timeout_seconds=60):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        state = _container_state(name)
        if not state["running"]:
            raise SmokeFailure("isolated candidate Server exited before becoming healthy")
        if state["health"] == "healthy":
            return
        time.sleep(2)
    raise SmokeFailure("isolated candidate Server health timed out")


def _server_stats(server_name):
    result = _run([
        "docker", "exec", server_name,
        "wget", "-q", "-O-", "http://127.0.0.1/json/stats.json",
    ], timeout=15)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SmokeFailure("isolated Server stats response was invalid JSON") from exc


def _wait_for_accepted_report(server_name, client_name, device_id, arguments):
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        state = _container_state(client_name)
        if not state["running"] or state["restart_count"] != 0:
            raise SmokeFailure(
                "actual Client entrypoint exited or restarted ("
                + _safe_client_exit_summary(client_name, state)
                + ")"
            )
        snapshot = _server_stats(server_name)
        devices = snapshot.get("servers")
        if isinstance(devices, list):
            for device in devices:
                if not isinstance(device, dict) or device.get("device_id") != device_id:
                    continue
                build = device.get("client_build")
                if not isinstance(build, dict):
                    continue
                if (
                    device.get("protocol_mode") != "device_v2"
                    or device.get("stale") is not False
                    or build.get("version") != arguments.version
                    or build.get("revision") != arguments.source_sha
                    or build.get("protocol") != "device_v2"
                    or not device.get("collected_at")
                    or not device.get("received_at")
                ):
                    raise SmokeFailure("accepted report did not retain expected Device v2 provenance")
                return device
        time.sleep(2)
    raise SmokeFailure("actual Client report was not accepted before timeout")


def _wait_for_unifi_fixture_report(server_name, device_id, previous_received_at, arguments):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        snapshot = _server_stats(server_name)
        devices = snapshot.get("servers")
        if isinstance(devices, list):
            for device in devices:
                if not isinstance(device, dict) or device.get("device_id") != device_id:
                    continue
                if device.get("received_at") == previous_received_at:
                    break
                build = device.get("client_build")
                unifi = device.get("unifi")
                if (
                    device.get("protocol_mode") != "device_v2"
                    or device.get("stale") is not False
                    or not isinstance(build, dict)
                    or build.get("revision") != arguments.source_sha
                    or not isinstance(unifi, dict)
                ):
                    raise SmokeFailure("Server output did not retain the fixture Device v2 report")
                _verify_unifi_fixture_projection(unifi)
                return unifi
        time.sleep(1)
    raise SmokeFailure("isolated Server did not expose the accepted UniFi fixture report")


def _verify_unifi_fixture_projection(unifi):
    api = unifi.get("api") if isinstance(unifi.get("api"), dict) else {}
    telemetry = api.get("telemetry") if isinstance(api.get("telemetry"), dict) else {}
    rps = unifi.get("rps") if isinstance(unifi.get("rps"), dict) else {}
    rps_devices = rps.get("devices") if isinstance(rps.get("devices"), list) else []
    if (
        unifi.get("profile") != "ucg-max"
        or unifi.get("transport", {}).get("status") != "available"
        or unifi.get("stale") is not False
        or api.get("status") != "available"
        or not rps_devices
        or len(rps_devices[0].get("ports", [])) != 6
        or rps_devices[0].get("total_output_power_w") != 101
    ):
        raise SmokeFailure("Server rejected or changed the sanitized RPS fixture projection")
    ports = telemetry.get("ports") if isinstance(telemetry.get("ports"), list) else []
    if any(port.get("device_id") == "rps-device-01" for port in ports if isinstance(port, dict)):
        raise SmokeFailure("RPS DC outputs leaked into Ethernet port records")
    promax = [port for port in ports if isinstance(port, dict) and port.get("device_id") == "fixture-promax24"]
    if (
        len(promax) != 26
        or {port.get("model_id") for port in promax} != {"USW-Pro-Max-24-PoE"}
        or telemetry.get("port_summary", {}).get("poe_total_power_w") != 3.25
    ):
        raise SmokeFailure("Server changed Pro Max 24 PoE port or PoE projection")


def _run_unifi_fixture_in_client_image(
    image, network_name, client_name, device_id, previous_received_at,
    secret_volume_name, client_env, fixture_directory, server_name, arguments,
):
    state = _container_state(client_name)
    if not state["running"] or state["restart_count"] != 0:
        raise SmokeFailure("normal Client must remain stable before the fixture report phase")
    _run(["docker", "stop", client_name], timeout=30)
    if _container_state(client_name)["running"]:
        raise SmokeFailure("normal Client did not stop before the single fixture writer started")
    # The fixture report has second-resolution timestamps. Ensure it is newer
    # than the report sent by the normal production entrypoint in this test.
    time.sleep(2)
    root = Path(__file__).resolve().parents[1]
    helper = root / "scripts" / "client_image_unifi_fixture.py"
    fixture_name = "hardwarestatus-smoke-unifi-fixture-" + secrets.token_hex(5)
    command = [
        "docker", "run", "--rm", "--name", fixture_name,
        "--network", network_name, "--read-only",
        "--security-opt", "no-new-privileges:true",
        "--tmpfs", "/tmp:size=32m,mode=1777,nosuid,nodev,noexec",
        "--mount", "type=volume,src=" + secret_volume_name + ",dst=/run/secrets,readonly",
        "--mount", "type=bind,src=" + str(helper) + ",dst=/ci/client_image_unifi_fixture.py,readonly",
        "--mount", "type=bind,src=" + str(fixture_directory) + ",dst=/ci/unifi-fixtures,readonly",
    ]
    for key, value in client_env.items():
        command.extend(["--env", key + "=" + value])
    command.extend([
        "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--entrypoint", "python3", image,
        "/ci/client_image_unifi_fixture.py",
        "--fixture-directory", "/ci/unifi-fixtures", "--send-report",
    ])
    result = _run(command, timeout=90)
    if "UNIFI_FIXTURE_NORMALIZATION=PASS" not in result.stdout or "UNIFI_FIXTURE_REPORT=ACCEPTED" not in result.stdout:
        raise SmokeFailure("actual Client image did not normalize and submit the sanitized UniFi fixture")
    if "UNIFI_RPS_OUTPUT_W=101.0" not in result.stdout or "UNIFI_PROMAX24_PORTS=26" not in result.stdout:
        raise SmokeFailure("actual Client image fixture totals did not match expected bounded projections")
    unifi = _wait_for_unifi_fixture_report(
        server_name, device_id, previous_received_at, arguments
    )
    _verify_unifi_frontend_render(unifi, root)
    print("ACTUAL_IMAGE_UNIFI_FIXTURE=PASS")
    print("SERVER_CONTRACT_FIXTURE_REPORT=ACCEPTED")
    print("SERVER_UNIFI_RPS_OUTPUT_W=101")
    print("SERVER_PROMAX24_ETHERNET_PORTS=26")
    print("FRONTEND_FIXTURE_RENDER=PASS")


def _verify_unifi_frontend_render(unifi, repository_root):
    source = (
        "const assert=require('node:assert/strict');\n"
        "const app=require(" + json.dumps(str(repository_root / "web" / "js" / "app.js")) + ");\n"
        "let input=''; process.stdin.setEncoding('utf8');\n"
        "process.stdin.on('data',chunk=>input+=chunk);\n"
        "process.stdin.on('end',()=>{const u=JSON.parse(input);"
        "const r=app.unifiRPSMarkup(u); const p=app.unifiPortTelemetryMarkup(u);"
        "assert.match(r,/101 W/); assert.match(r,/DC 6/);"
        "assert.match(p,/Fixture Pro Max 24/); assert.match(p,/Port 26/);"
        "assert.doesNotMatch(p,/rps-device-01/); console.log('FRONTEND_RENDER=PASS');});\n"
    )
    result = _run(["node", "-e", source], timeout=30, input_text=json.dumps(unifi, separators=(",", ":")))
    if "FRONTEND_RENDER=PASS" not in result.stdout:
        raise SmokeFailure("frontend did not render the Server-projected RPS and Pro Max fixture")


def _verify_catalog_in_client_image(image):
    code = (
        "from unifi_model_catalog import load_catalog, resolve_model; "
        "c=load_catalog(); "
        "p=resolve_model(c, 'USW Pro Max 24 PoE', kind='api_model'); "
        "r=resolve_model(c, 'USP RPS', kind='api_model'); "
        "assert p and p['canonical_sku']=='USW-Pro-Max-24-PoE'; "
        "assert r and r.get('schema_version')==2; "
        "print('catalog-v2-load=pass')"
    )
    _run([
        "docker", "run", "--rm", "--network", "none",
        "--entrypoint", "python3", image, "-c", code,
    ], timeout=30)


def _populate_client_secret_volume(image, client_secrets, volume_name):
    _run([
        "docker", "run", "--rm", "--network", "none",
        "--mount", "type=bind,src=" + str(client_secrets) + ",dst=/source,readonly",
        "--mount", "type=volume,src=" + volume_name + ",dst=/run/secrets",
        "--entrypoint", "sh", image, "-c",
        "cp /source/device-token /run/secrets/device-token && "
        "cp /source/test-ca.crt /run/secrets/test-ca.crt && "
        "chmod 0400 /run/secrets/device-token && "
        "chmod 0600 /run/secrets/test-ca.crt",
    ], timeout=30)


def _preflight_client_runtime(image, secret_volume_name, client_env):
    code = "\n".join((
        "try:",
        "    from device_client_config import ClientMode, load_client_selection, load_custom_ca, load_device_token",
        "    from multi_device_contracts import ClientContractError",
        "    import runpy",
        "    selection = load_client_selection([])",
        "    assert selection.mode is ClientMode.DEVICE_V2",
        "    load_device_token(selection.device_v2.token_file)",
        "    load_custom_ca(selection.device_v2.ca_file)",
        "    client = runpy.run_path('/app/client-psutil.py', run_name='smoke_preflight')",
        "    client['_device_v2_extension_collector'](selection.device_v2, [])",
        "except Exception as exc:",
        "    from multi_device_contracts import ClientContractError",
        "    if isinstance(exc, ClientContractError):",
        "        print('CLIENT_PREFLIGHT_ERROR=' + str(exc))",
        "    else:",
        "        print('CLIENT_PREFLIGHT_ERROR=' + type(exc).__name__)",
        "    raise SystemExit(2)",
        "print('CLIENT_PREFLIGHT=PASS')",
    ))
    command = [
        "docker", "run", "--rm", "--network", "none", "--read-only",
        "--mount", "type=volume,src=" + secret_volume_name + ",dst=/run/secrets,readonly",
    ]
    for key, value in client_env.items():
        command.extend(["--env", key + "=" + value])
    command.extend(["--entrypoint", "python3", image, "-c", code])
    result = _run(command, check=False, timeout=30)
    if result.returncode != 0:
        diagnostic = next(
            (line.strip() for line in result.stdout.splitlines()
             if line.startswith("CLIENT_PREFLIGHT_ERROR=")),
            "CLIENT_PREFLIGHT_ERROR=unclassified",
        )
        raise SmokeFailure("actual Client configuration preflight failed: " + diagnostic)
    if "CLIENT_PREFLIGHT=PASS" not in result.stdout:
        raise SmokeFailure("actual Client configuration preflight returned no pass marker")


def run_smoke(arguments):
    server_image = _check_image(arguments.server_image, "server", arguments)
    client_image = _check_image(arguments.client_image, "client", arguments)
    if server_image.get("Id") == client_image.get("Id"):
        raise SmokeFailure("Server and Client images unexpectedly share one image identity")

    python_version = _run([
        "docker", "run", "--rm", "--network", "none",
        "--entrypoint", "python3", arguments.client_image, "--version",
    ], timeout=30).stdout.strip()
    if not re.match(r"^Python 3\.8\.", python_version):
        raise SmokeFailure("built Client image is not running the required Python 3.8 runtime")
    print("CLIENT_IMAGE_PYTHON=" + python_version)
    _verify_catalog_in_client_image(arguments.client_image)

    suffix = secrets.token_hex(5)
    network_name = "hardwarestatus-smoke-net-" + suffix
    server_name = "hardwarestatus-smoke-server-" + suffix
    proxy_name = "hardwarestatus-smoke-proxy-" + suffix
    client_name = "hardwarestatus-smoke-client-" + suffix
    secret_volume_name = "hardwarestatus-smoke-secrets-" + suffix
    device_id = "ci-smoke-" + suffix
    created = []
    network_created = False
    volume_created = False
    with tempfile.TemporaryDirectory(prefix="hardwarestatus-client-smoke-") as raw_directory:
        directory = Path(raw_directory)
        token_path = _create_test_documents(directory, device_id)
        certificate, proxy_config, certificate_directory = _create_tls_material(directory)
        client_secrets = directory / "client-secrets"
        client_secrets.mkdir(mode=0o700)
        client_token = client_secrets / "device-token"
        client_token.write_bytes(token_path.read_bytes())
        client_token.chmod(0o400)
        client_ca = client_secrets / "test-ca.crt"
        client_ca.write_bytes(certificate.read_bytes())
        client_ca.chmod(0o600)
        try:
            _run(["docker", "volume", "create", secret_volume_name])
            volume_created = True
            _populate_client_secret_volume(
                arguments.client_image, client_secrets, secret_volume_name
            )
            _run(["docker", "network", "create", "--internal", network_name])
            network_created = True
            server_ip, proxy_ip = _network_addresses(network_name)

            created.append(server_name)
            _run([
                "docker", "run", "--detach", "--name", server_name,
                "--network", network_name, "--ip", server_ip,
                "--network-alias", "hardwarestatus-smoke-server",
                "--mount", "type=bind,src=" + str(directory / "registry.json") + ",dst=/ci/registry.json,readonly",
                "--mount", "type=bind,src=" + str(directory / "legacy-mapping.json") + ",dst=/ci/legacy-mapping.json,readonly",
                "--mount", "type=bind,src=" + str(directory / "credentials") + ",dst=/ci/credentials,readonly",
                arguments.server_image,
                "--device-endpoint",
                "--device-registry=/ci/registry.json",
                "--device-credentials=/ci/credentials",
                "--legacy-device-mapping=/ci/legacy-mapping.json",
                "--device-trusted-proxy",
                "--device-trusted-proxy-cidrs=" + proxy_ip + "/32",
                "--http=:80",
                "--agent=127.0.0.1:35601",
            ])
            _wait_for_server_health(server_name)

            created.append(proxy_name)
            _run([
                "docker", "run", "--detach", "--name", proxy_name,
                "--network", network_name, "--ip", proxy_ip,
                "--network-alias", "hardwarestatus-smoke-proxy",
                "--mount", "type=bind,src=" + str(proxy_config) + ",dst=/etc/nginx/conf.d/default.conf,readonly",
                "--mount", "type=bind,src=" + str(certificate_directory) + ",dst=/etc/nginx/certs,readonly",
                "nginx:1.27-alpine",
            ])
            client_env = {
                "HARDWARESTATUS_SERVER_URL": "https://hardwarestatus-smoke-proxy:8443",
                "HARDWARESTATUS_DEVICE_ID": device_id,
                "HARDWARESTATUS_DEVICE_NAME": "CI isolated runtime smoke",
                "HARDWARESTATUS_DEVICE_TOKEN_FILE": "/run/secrets/device-token",
                "HARDWARESTATUS_TLS_CA_FILE": "/run/secrets/test-ca.crt",
                "HARDWARESTATUS_COLLECTION_INTERVAL_SECONDS": "10",
                "HARDWARESTATUS_CONNECT_TIMEOUT_SECONDS": "5",
                "HARDWARESTATUS_READ_TIMEOUT_SECONDS": "10",
                "HARDWARESTATUS_CLIENT_VERSION": arguments.version,
                "HARDWARESTATUS_CLIENT_REVISION": arguments.source_sha,
                "HARDWARESTATUS_CLIENT_PROTOCOL": "device_v2",
                "HERMES_EXPORT_ENABLED": "false",
            }
            _preflight_client_runtime(
                arguments.client_image, secret_volume_name, client_env
            )
            run_client = [
                "docker", "run", "--detach", "--name", client_name,
                "--network", network_name,
                "--read-only",
                "--security-opt", "no-new-privileges:true",
                "--tmpfs", "/tmp:size=32m,mode=1777,nosuid,nodev,noexec",
                "--tmpfs", "/var/lib/hardwarestatus-client:size=16m,mode=0700",
                "--mount", "type=volume,src=" + secret_volume_name + ",dst=/run/secrets,readonly",
            ]
            for key, value in client_env.items():
                run_client.extend(["--env", key + "=" + value])
            run_client.append(arguments.client_image)
            created.append(client_name)
            _run(run_client)

            device = _wait_for_accepted_report(
                server_name, client_name, device_id, arguments
            )
            time.sleep(3)
            state = _container_state(client_name)
            if not state["running"] or state["restart_count"] != 0:
                raise SmokeFailure(
                    "Client did not remain healthy after its first report ("
                    + _safe_client_exit_summary(client_name, state)
                    + ")"
                )
            _run_unifi_fixture_in_client_image(
                arguments.client_image, network_name, client_name, device_id,
                device.get("received_at"), secret_volume_name, client_env,
                ROOT / "clients" / "unifi_fixtures", server_name, arguments,
            )
            print("CLIENT_IMAGE_SMOKE=PASS")
            print("DEVICE_V2_REPORT=ACCEPTED")
            print("DEVICE_ID=" + device_id)
            print("COLLECTED_AT=" + str(device["collected_at"]))
            print("RECEIVED_AT=" + str(device["received_at"]))
            print("ENTRYPOINT_CLIENT_RESTART_COUNT=0")
        finally:
            for name in reversed(created):
                _run(["docker", "rm", "--force", name], check=False, timeout=30)
            if network_created:
                _run(["docker", "network", "rm", network_name], check=False, timeout=30)
            if volume_created:
                _run(["docker", "volume", "rm", secret_volume_name], check=False, timeout=30)


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-image", required=True)
    parser.add_argument("--client-image", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--catalog-revision", required=True)
    parser.add_argument("--catalog-schema-version", required=True, type=int)
    parser.add_argument("--catalog-sha256", required=True)
    arguments = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", arguments.source_sha):
        parser.error("--source-sha must be a full lowercase Git SHA")
    if not re.fullmatch(r"[0-9a-f]{40}", arguments.catalog_revision):
        parser.error("--catalog-revision must be a full lowercase Git SHA")
    if not re.fullmatch(r"[0-9a-f]{64}", arguments.catalog_sha256):
        parser.error("--catalog-sha256 must be a full lowercase SHA-256")
    return arguments


def main(argv=None):
    try:
        run_smoke(parse_args(sys.argv[1:] if argv is None else argv))
    except (SmokeFailure, OSError, subprocess.TimeoutExpired) as exc:
        print("CLIENT_IMAGE_SMOKE=FAIL: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
