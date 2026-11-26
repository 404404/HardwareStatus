import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "clients"))
sys.path.insert(0, str(ROOT / "scripts"))

from client_image_unifi_fixture import collect_unifi_fixture


class ClientImageUniFiFixtureTests(unittest.TestCase):
    def test_full_mixed_site_collection_keeps_rps_and_ethernet_separate(self):
        normalized, _ = collect_unifi_fixture(ROOT / "clients" / "unifi_fixtures")
        self.assertFalse(normalized["stale"])
        self.assertEqual(normalized["transport"]["status"], "available")
        self.assertEqual(normalized["api"]["status"], "available")
        self.assertTrue(all(item["status"] == "ok" for item in normalized["api"]["endpoints"]))

        rps = normalized["rps"]
        self.assertEqual(rps["collection_status"], "available")
        self.assertEqual(len(rps["devices"][0]["ports"]), 6)
        self.assertEqual(rps["devices"][0]["total_output_power_w"], 101)
        telemetry = normalized["api"]["telemetry"]
        self.assertNotIn("rps-device-01", {port["device_id"] for port in telemetry["ports"]})
        self.assertEqual(telemetry["port_summary"]["poe_total_power_w"], 3.25)

        models = {item["device_id"]: item for item in telemetry["devices"]["items"]}
        self.assertEqual(models["fixture-ucg-max"]["model_id"], "UCG-Max")
        self.assertEqual(models["fixture-udw"]["model_id"], "UDW")
        self.assertEqual(models["fixture-pro-hd"]["model_id"], "USW-Pro-HD-24")
        self.assertEqual(models["fixture-u6-mesh"]["model_id"], "U6-Mesh")
        self.assertEqual(models["fixture-unknown"]["model_profile_status"], "unknown")
        promax_ports = [port for port in telemetry["ports"] if port["device_id"] == "fixture-promax24"]
        self.assertEqual(len(promax_ports), 26)
        self.assertEqual({port["model_id"] for port in promax_ports}, {"USW-Pro-Max-24-PoE"})

    def test_synthetic_99w_same_snapshot_vector_is_summed_without_mutating_capture(self):
        normalized, _ = collect_unifi_fixture(
            ROOT / "clients" / "unifi_fixtures", total_power_override=99
        )
        self.assertEqual(normalized["rps"]["devices"][0]["total_output_power_w"], 99)


if __name__ == "__main__":
    unittest.main()
