import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra import device_manager


class DeviceManagerTest(unittest.TestCase):
    def setUp(self):
        device_manager._probe_requested_device.cache_clear()

    def tearDown(self):
        device_manager._probe_requested_device.cache_clear()

    def test_cuda_request_falls_back_when_torch_has_no_cuda_build(self):
        with patch.object(device_manager.torch.version, "cuda", None):
            info = device_manager.get_device_info(force_device="cuda")

        self.assertEqual(info["requested_device"], "cuda")
        self.assertEqual(info["selected_device"], "cpu")
        self.assertTrue(info["fallback_applied"])
        self.assertIn("CPU build", info["fallback_reason"])

    def test_loader_failure_retries_on_cpu(self):
        def fake_loader(device: str) -> str:
            if device == "cuda":
                raise RuntimeError("boom")
            return f"loaded:{device}"

        with patch("infra.device_manager.get_device_info", return_value={"selected_device": "cuda", "requested_device": "cuda"}):
            resource, info = device_manager.load_with_device_fallback(
                fake_loader,
                component="unit_test",
                force_device="cuda",
            )

        self.assertEqual(resource, "loaded:cpu")
        self.assertEqual(info["selected_device"], "cpu")
        self.assertTrue(info["fallback_applied"])
        self.assertIn("unit_test", info["fallback_reason"])


if __name__ == "__main__":
    unittest.main()
