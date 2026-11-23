"""Consumer for the frozen versioned UniFi_Catalog bundle."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

CATALOG_SCHEMA_VERSION = 2
SUPPORTED_CATALOG_SCHEMA_VERSIONS = frozenset({1, CATALOG_SCHEMA_VERSION})
CATALOG_SOURCE_REVISION = "6a434bb795ed8a5e1bb329e7d470a86c49be22ee"
CATALOG_BUNDLE_SHA256 = "ba59930b18e88df78bef35cc51ee2ba897169fb8cdcae20465aa69878c6664fa"
CATALOG_BUNDLE_PATH = Path(__file__).with_name("unifi_catalog") / "catalog.json"
CATALOG_PROVENANCE_PATH = CATALOG_BUNDLE_PATH.with_name("catalog-provenance.json")
# Compatibility name only; this is a bundle path, not a model-table directory.
MODEL_DIRECTORY = CATALOG_BUNDLE_PATH

MODEL_TYPES = {"gateway", "switch", "ap"}
IDENTIFIER_KINDS = {"api_model", "sysid", "ssh_model"}
ALIAS_STATUSES = {"candidate", "verified"}
POE_CLASSES = {"poe", "poe+", "poe++", "poe+++"}
POWER_PROFILE_STATUSES = {"verified", "candidate", "unsupported"}
POWER_FIELD_STATUSES = {"verified", "candidate", "unknown", "not_applicable"}
INPUT_METHODS = {"ac_mains", "ac_adapter", "dc_adapter", "usb_c", "poe"}
SELECTION_MODES = {"fixed", "auto_detected", "controller_manual"}
CONNECTORS = {"rj45", "sfp", "sfp_plus", "sfp28", "qsfp28", "other"}
PORT_ROLES = {"lan", "wan", "downstream", "uplink", "data_in", "poe_passthrough"}
STORAGE_TYPES = {"emmc", "ssd", "sata_ssd", "nvme", "microsd", "tf", "other"}
STORAGE_KINDS = {"fixed_device", "user_slot", "removable_media"}
PRESENCE_STATES = {"present", "not_populated", "unknown"}
SHA256_LINE = re.compile(r"^(?P<digest>[0-9a-f]{64})  catalog[.]json$")


class ModelCatalogError(ValueError):
    """Raised when a catalog bundle cannot be trusted by the consumer."""


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ModelCatalogError(f"invalid {field}")
    return value


def _number(value, field, *, integer=False, minimum=0):
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ModelCatalogError(f"invalid {field}")
    if integer and not isinstance(value, int):
        raise ModelCatalogError(f"invalid {field}")
    if value < minimum:
        raise ModelCatalogError(f"invalid {field}")


def _exact(value, required, field, optional=()):
    if not isinstance(value, dict):
        raise ModelCatalogError(f"invalid {field}")
    required = set(required)
    allowed = required | set(optional)
    if not required <= set(value) or set(value) - allowed:
        raise ModelCatalogError(f"invalid {field}")


def _field_evidence(value, field):
    _exact(value, {"status", "evidence_ids"}, field, {"source_note"})
    if value["status"] not in POWER_FIELD_STATUSES:
        raise ModelCatalogError(f"invalid {field}.status")
    ids = value["evidence_ids"]
    if not isinstance(ids, list) or len(ids) != len(set(ids)) or any(not isinstance(item, str) or not item for item in ids):
        raise ModelCatalogError(f"invalid {field}.evidence_ids")
    source_note = value.get("source_note")
    if source_note is not None:
        _text(source_note, f"{field}.source_note")
    if not ids and source_note is None:
        raise ModelCatalogError(f"invalid {field}: evidence_ids or source_note required")


def _runtime_identifiers(model):
    identifiers = model["runtime_identifiers"]
    _exact(identifiers, IDENTIFIER_KINDS, "runtime_identifiers")
    verified = set()
    for kind in sorted(IDENTIFIER_KINDS):
        aliases = identifiers[kind]
        if not isinstance(aliases, list):
            raise ModelCatalogError(f"invalid runtime_identifiers.{kind}")
        for index, alias in enumerate(aliases):
            field = f"runtime_identifiers.{kind}[{index}]"
            _exact(alias, {"value", "status", "provenance", "evidence_id"}, field)
            _text(alias["value"], f"{field}.value")
            _text(alias["provenance"], f"{field}.provenance")
            _text(alias["evidence_id"], f"{field}.evidence_id")
            if alias["status"] not in ALIAS_STATUSES:
                raise ModelCatalogError(f"invalid {field}.status")
            if alias["status"] == "verified":
                key = (kind, alias["value"])
                if key in verified:
                    raise ModelCatalogError("duplicate verified runtime alias")
                verified.add(key)
    return verified


def _ports(model):
    ports = model["ports"]
    _exact(ports, {"complete", "items"}, "ports")
    if not isinstance(ports["complete"], bool) or not isinstance(ports["items"], list):
        raise ModelCatalogError("invalid ports")
    indexes = set()
    for index, port in enumerate(ports["items"]):
        field = f"ports.items[{index}]"
        required = {"index", "label", "connector", "roles", "max_speed_mbps", "poe_in", "poe_out", "poe_standard", "poe_max_power_w", "combo_group"}
        _exact(port, required, field)
        number = port["index"]
        if isinstance(number, bool) or not isinstance(number, int) or number < 1 or number in indexes:
            raise ModelCatalogError(f"invalid {field}.index")
        indexes.add(number)
        _text(port["label"], f"{field}.label")
        if port["connector"] not in CONNECTORS:
            raise ModelCatalogError(f"invalid {field}.connector")
        _number(port["max_speed_mbps"], f"{field}.max_speed_mbps", integer=True)
        if port["max_speed_mbps"] not in {None, 10, 100, 1000, 2500, 5000, 10000, 25000, 100000}:
            raise ModelCatalogError(f"invalid {field}.max_speed_mbps")
        if not isinstance(port["roles"], list) or len(port["roles"]) > 4 or len(set(port["roles"])) != len(port["roles"]) or any(role not in PORT_ROLES for role in port["roles"]):
            raise ModelCatalogError(f"invalid {field}.roles")
        if port["poe_in"] not in {True, False, None} or port["poe_out"] not in {True, False, None}:
            raise ModelCatalogError(f"invalid {field}.poe flags")
        if port["poe_standard"] not in POE_CLASSES | {None}:
            raise ModelCatalogError(f"invalid {field}.poe_standard")
        _number(port["poe_max_power_w"], f"{field}.poe_max_power_w")
        if port["combo_group"] is not None:
            _text(port["combo_group"], f"{field}.combo_group")


def _storage(model):
    storage = model["storage"]
    _exact(storage, {"complete", "items"}, "storage")
    if not isinstance(storage["complete"], bool) or not isinstance(storage["items"], list):
        raise ModelCatalogError("invalid storage")
    for index, item in enumerate(storage["items"]):
        field = f"storage.items[{index}]"
        _exact(item, {"type", "kind", "default_presence", "capacity_bytes", "max_capacity_bytes"}, field)
        if item["type"] not in STORAGE_TYPES or item["kind"] not in STORAGE_KINDS or item["default_presence"] not in PRESENCE_STATES:
            raise ModelCatalogError(f"invalid {field}")
        _number(item["capacity_bytes"], f"{field}.capacity_bytes", integer=True)
        _number(item["max_capacity_bytes"], f"{field}.max_capacity_bytes", integer=True)


def _power(model):
    power = model["power"]
    required = {"source_type", "psu_slots", "psu_unit_capacity_w", "controller_reference_capacity_w", "max_device_consumption_w", "absolute_max_poe_budget_w", "power_profiles"}
    _exact(power, required, "power")
    if power["source_type"] not in {"integrated_ac", "integrated_ac_with_dc_backup", "external_adapter", "external_adapter_or_poe", "poe_powered", "dc_or_external_adapter", "unknown"}:
        raise ModelCatalogError("invalid power.source_type")
    _number(power["psu_slots"], "power.psu_slots", integer=True)
    for field in ("psu_unit_capacity_w", "controller_reference_capacity_w", "max_device_consumption_w", "absolute_max_poe_budget_w"):
        _number(power[field], f"power.{field}")
    profiles = power["power_profiles"]
    if not isinstance(profiles, list) or not profiles:
        raise ModelCatalogError("invalid power.power_profiles")
    profile_ids = set()
    known_budgets = []
    for index, profile in enumerate(profiles):
        field = f"power.power_profiles[{index}]"
        required = {"id", "status", "selection_mode", "input_method", "input_poe_class", "input_capacity_w", "poe_budget_w", "field_evidence"}
        _exact(profile, required, field)
        _text(profile["id"], f"{field}.id")
        if profile["id"] in profile_ids:
            raise ModelCatalogError("duplicate power profile id")
        profile_ids.add(profile["id"])
        if profile["status"] not in POWER_PROFILE_STATUSES or profile["selection_mode"] not in SELECTION_MODES or profile["input_method"] not in INPUT_METHODS:
            raise ModelCatalogError(f"invalid {field}")
        if profile["input_poe_class"] not in POE_CLASSES | {None}:
            raise ModelCatalogError(f"invalid {field}.input_poe_class")
        _number(profile["input_capacity_w"], f"{field}.input_capacity_w")
        _number(profile["poe_budget_w"], f"{field}.poe_budget_w")
        if profile["status"] == "verified" and profile["poe_budget_w"] is not None:
            known_budgets.append(profile["poe_budget_w"])
        if profile["selection_mode"] == "auto_detected" and profile["input_method"] != "poe":
            raise ModelCatalogError(f"invalid {field}: auto_detected profiles require PoE input")
        if profile["selection_mode"] == "controller_manual" and profile["input_method"] != "dc_adapter":
            raise ModelCatalogError(f"invalid {field}: controller_manual profiles require DC adapter input")
        if profile["selection_mode"] == "fixed" and profile["input_method"] == "poe":
            raise ModelCatalogError(f"invalid {field}: fixed profiles cannot use PoE input")
        if profile["input_method"] == "poe" and profile["selection_mode"] != "auto_detected":
            raise ModelCatalogError(f"invalid {field}: PoE input must be auto_detected")
        if profile["input_method"] != "poe" and profile["input_poe_class"] is not None:
            raise ModelCatalogError(f"invalid {field}: non-PoE input cannot declare a PoE class")
        evidence = profile["field_evidence"]
        _exact(evidence, {"selection_mode", "input_method", "input_poe_class", "input_capacity_w", "poe_budget_w"}, f"{field}.field_evidence")
        values = {
            "selection_mode": profile["selection_mode"],
            "input_method": profile["input_method"],
            "input_poe_class": profile["input_poe_class"],
            "input_capacity_w": profile["input_capacity_w"],
            "poe_budget_w": profile["poe_budget_w"],
        }
        for name, item in evidence.items():
            _field_evidence(item, f"{field}.field_evidence.{name}")
            status = item["status"]
            if status in {"unknown", "not_applicable"} and values[name] is not None:
                raise ModelCatalogError(f"invalid {field}.field_evidence.{name}: {status} value must be null")
            if status in {"verified", "candidate"} and values[name] is None:
                raise ModelCatalogError(f"invalid {field}.field_evidence.{name}: {status} value must not be null")
    absolute = power["absolute_max_poe_budget_w"]
    if absolute is not None and any(budget > absolute for budget in known_budgets):
        raise ModelCatalogError("absolute_max_poe_budget_w is below a known profile budget")


def _model(model):
    required = {"schema_version", "canonical_sku", "display_name", "device_type", "official_evidence_ids", "runtime_identifiers", "ports", "storage", "power", "fans"}
    _exact(model, required, "model", {"processor"})
    if model["schema_version"] != 1:
        raise ModelCatalogError("unsupported v1 model schema_version")
    sku = _text(model["canonical_sku"], "canonical_sku")
    if re.fullmatch(r"[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*", sku) is None:
        raise ModelCatalogError("invalid canonical_sku")
    _text(model["display_name"], "display_name")
    if model["device_type"] not in MODEL_TYPES:
        raise ModelCatalogError("invalid device_type")
    evidence = model["official_evidence_ids"]
    if not isinstance(evidence, list) or not evidence or len(evidence) != len(set(evidence)) or any(not isinstance(item, str) or not item for item in evidence):
        raise ModelCatalogError("invalid official_evidence_ids")
    if "processor" in model:
        processor = model["processor"]
        _exact(processor, {"model", "architecture", "cores", "clock_mhz", "model_evidence_ids"}, "processor")
        if processor["model"] is not None:
            _text(processor["model"], "processor.model")
        _text(processor["architecture"], "processor.architecture")
        _number(processor["cores"], "processor.cores", integer=True, minimum=1)
        _number(processor["clock_mhz"], "processor.clock_mhz", integer=True, minimum=1)
        ids = processor["model_evidence_ids"]
        if not isinstance(ids, list) or len(ids) != len(set(ids)) or any(not isinstance(item, str) or not item for item in ids):
            raise ModelCatalogError("invalid processor.model_evidence_ids")
    _runtime_identifiers(model)
    _ports(model)
    _storage(model)
    _power(model)
    fans = model["fans"]
    _exact(fans, {"status", "count"}, "fans")
    if fans["status"] not in {"present", "absent", "unknown"}:
        raise ModelCatalogError("invalid fans.status")
    _number(fans["count"], "fans.count", integer=True)
    if fans["status"] == "absent" and fans["count"] not in {None, 0}:
        raise ModelCatalogError("invalid absent fan count")


def _rps_model(model):
    required = {"schema_version", "canonical_sku", "display_name", "device_type", "official_evidence_ids", "runtime_identifiers", "management_interface", "dc_outputs", "dc_power_rails"}
    _exact(model, required, "RPS model v2")
    if model["schema_version"] != 2 or model["device_type"] != "rps":
        raise ModelCatalogError("invalid RPS model schema version/type")
    _text(model["canonical_sku"], "canonical_sku")
    _text(model["display_name"], "display_name")
    evidence_ids = model["official_evidence_ids"]
    if not isinstance(evidence_ids, list) or not evidence_ids or len(evidence_ids) != len(set(evidence_ids)):
        raise ModelCatalogError("invalid RPS official evidence IDs")
    if any(not isinstance(item, str) or not re.fullmatch(r"official-[a-z0-9-]+", item) for item in evidence_ids):
        raise ModelCatalogError("invalid RPS official evidence IDs")
    identifiers = model["runtime_identifiers"]
    kinds = {"api_model", "legacy_model", "sysid", "ssh_model"}
    _exact(identifiers, kinds, "RPS runtime_identifiers")
    for kind, aliases in identifiers.items():
        if not isinstance(aliases, list):
            raise ModelCatalogError(f"invalid RPS runtime_identifiers.{kind}")
        seen_values = set()
        for alias in aliases:
            _exact(alias, {"value", "status", "provenance", "evidence_id"}, f"RPS runtime alias {kind}")
            _text(alias["value"], f"RPS runtime alias {kind}.value")
            _text(alias["provenance"], f"RPS runtime alias {kind}.provenance")
            if alias["status"] not in ALIAS_STATUSES or alias["value"] in seen_values:
                raise ModelCatalogError(f"invalid or duplicate RPS runtime alias {kind}")
            seen_values.add(alias["value"])
            if not isinstance(alias["evidence_id"], str) or not re.fullmatch(r"runtime-[a-z0-9-]+", alias["evidence_id"]):
                raise ModelCatalogError(f"invalid RPS runtime alias evidence {kind}")
    interface = model["management_interface"]
    _exact(interface, {"type", "count", "connector", "speed_mbps", "evidence_id"}, "RPS management_interface")
    try:
        _number(interface.get("count"), "RPS management_interface.count", integer=True, minimum=1)
        _number(interface.get("speed_mbps"), "RPS management_interface.speed_mbps", integer=True, minimum=1)
    except ModelCatalogError as exc:
        raise ModelCatalogError("invalid RPS Ethernet management interface") from exc
    if interface.get("type") != "ethernet" or interface.get("count") != 1 or interface.get("connector") != "rj45" or interface.get("speed_mbps") != 1000:
        raise ModelCatalogError("invalid RPS Ethernet management interface")
    if interface["evidence_id"] not in evidence_ids:
        raise ModelCatalogError("RPS management interface lacks official evidence")
    outputs = model["dc_outputs"]
    _exact(outputs, {"complete", "items"}, "RPS dc_outputs")
    if outputs["complete"] is not True or not isinstance(outputs["items"], list) or len(outputs["items"]) != 6:
        raise ModelCatalogError("RPS requires six complete DC outputs")
    rails = model["dc_power_rails"]
    expected = {"rail-11v5": (11.5, 350), "rail-52v": (52, 600)}
    if not isinstance(rails, list) or len(rails) != 2:
        raise ModelCatalogError("RPS requires two distinct static DC rails")
    rail_ids = set()
    for rail in rails:
        _exact(rail, {"id", "nominal_voltage_v", "max_capacity_w", "evidence_id"}, "RPS dc_power_rail")
        if rail["id"] not in expected or (rail["nominal_voltage_v"], rail["max_capacity_w"]) != expected[rail["id"]]:
            raise ModelCatalogError("invalid RPS static DC rail rating")
        if rail["evidence_id"] not in evidence_ids:
            raise ModelCatalogError("RPS static DC rail lacks official evidence")
        rail_ids.add(rail["id"])
    if rail_ids != set(expected):
        raise ModelCatalogError("RPS requires both distinct static DC rails")
    for index, output in enumerate(outputs["items"], 1):
        _exact(output, {"index", "kind", "label"}, f"RPS dc_outputs[{index - 1}]")
        _number(output["index"], f"RPS dc_outputs[{index - 1}].index", integer=True, minimum=1)
        if output["index"] != index or output["kind"] != "dc_power_output" or output["label"] != f"DC {index}":
            raise ModelCatalogError("invalid RPS DC output topology")


def _bundle(bundle):
    _exact(bundle, {"schema_version", "models"}, "catalog bundle")
    version = bundle["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int) or version not in SUPPORTED_CATALOG_SCHEMA_VERSIONS:
        raise ModelCatalogError(f"unsupported catalog schema_version: {version!r}")
    if not isinstance(bundle["models"], list) or not bundle["models"]:
        raise ModelCatalogError("catalog bundle is empty")
    result = {}
    aliases = {}
    canonical_skus = set()
    for item in bundle["models"]:
        if item.get("schema_version") == 2:
            if version != 2:
                raise ModelCatalogError("Catalog V1 cannot contain model schema v2")
            _rps_model(item)
        else:
            _model(item)
        sku = item["canonical_sku"]
        if sku in canonical_skus:
            raise ModelCatalogError("duplicate canonical model ownership")
        canonical_skus.add(sku)
    for item in bundle["models"]:
        sku = item["canonical_sku"]
        result[sku] = item
        for kind, values in item["runtime_identifiers"].items():
            for alias in values:
                if alias["status"] != "verified":
                    continue
                key = (kind, alias["value"])
                if key in aliases and aliases[key] != sku:
                    raise ModelCatalogError("duplicate verified runtime alias ownership")
                if alias["value"] in canonical_skus and alias["value"] != sku:
                    raise ModelCatalogError("verified runtime alias collides with canonical SKU")
                aliases[key] = sku
    return result


def _paths(path):
    candidate = Path(path)
    if candidate.is_dir():
        candidate = candidate / "catalog.json"
    return candidate, candidate.with_name("catalog.sha256")


def _validate_default_provenance() -> None:
    expected = {
        "catalog_sha256": CATALOG_BUNDLE_SHA256,
        "catalog_schema_version": CATALOG_SCHEMA_VERSION,
        "repository": "404404/UniFi_Catalog",
        "revision": CATALOG_SOURCE_REVISION,
    }
    try:
        provenance = json.loads(CATALOG_PROVENANCE_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelCatalogError("catalog provenance unavailable") from exc
    if provenance != expected:
        raise ModelCatalogError("catalog provenance does not match the pinned artifact")


def load_catalog(path=CATALOG_BUNDLE_PATH):
    """Load a checksum-verified mixed Catalog V1/V2 bundle."""
    bundle_path, digest_path = _paths(path)
    try:
        raw = bundle_path.read_bytes()
        manifest = digest_path.read_text(encoding="ascii").strip()
    except OSError as exc:
        raise ModelCatalogError(f"catalog bundle unavailable: {bundle_path}") from exc
    match = SHA256_LINE.fullmatch(manifest)
    if match is None:
        raise ModelCatalogError("invalid catalog.sha256")
    if bundle_path == CATALOG_BUNDLE_PATH and match.group("digest") != CATALOG_BUNDLE_SHA256:
        raise ModelCatalogError("catalog bundle does not match the pinned artifact")
    if bundle_path == CATALOG_BUNDLE_PATH:
        _validate_default_provenance()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != match.group("digest"):
        raise ModelCatalogError("catalog bundle checksum mismatch")
    try:
        bundle = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelCatalogError("invalid catalog JSON") from exc
    return _bundle(bundle)


def resolve_model(catalog, value, *, kind="api_model", explicit_sku=False):
    """Resolve verified runtime aliases; canonical SKU requires explicit opt-in."""
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if explicit_sku:
        model = catalog.get(value)
        if model is not None:
            return model
    if kind not in IDENTIFIER_KINDS | {"legacy_model"}:
        return None
    for model in catalog.values():
        for alias in model["runtime_identifiers"].get(kind, []):
            if alias["status"] == "verified" and alias["value"] == value:
                return model
    return None


def project_static_capabilities(model):
    """Return detached static capabilities without aliases or runtime state."""
    if not isinstance(model, dict):
        return None
    if model.get("schema_version") == 2 and model.get("device_type") == "rps":
        fields = ("schema_version", "canonical_sku", "display_name", "device_type", "management_interface", "dc_outputs", "dc_power_rails")
        return {field: copy.deepcopy(model[field]) for field in fields}
    fields = ("schema_version", "canonical_sku", "display_name", "device_type", "ports", "storage", "power", "fans")
    result = {field: copy.deepcopy(model[field]) for field in fields}
    if "processor" in model:
        result["processor"] = copy.deepcopy(model["processor"])
    return result
