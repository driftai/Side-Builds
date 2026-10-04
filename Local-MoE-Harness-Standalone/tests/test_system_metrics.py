from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.services import system_metrics


class SystemMetricsTests(unittest.TestCase):
    def setUp(self):
        system_metrics._host_storage_cache = None
        system_metrics._host_storage_cache_at = 0.0

    def test_wsl_virtual_disk_reports_linux_filesystem_geometry(self):
        usage = SimpleNamespace(total=100 * 1024**3, used=25 * 1024**3, free=75 * 1024**3)
        with patch.object(system_metrics.shutil, "disk_usage", return_value=usage):
            result = system_metrics._wsl_virtual_disk_snapshot("/tmp/models")

        self.assertEqual(result["total_gb"], 100.0)
        self.assertEqual(result["used_gb"], 25.0)
        self.assertEqual(result["free_gb"], 75.0)
        self.assertEqual(result["total_bytes"], 100 * 1024**3)
        self.assertEqual(result["used_bytes"], 25 * 1024**3)
        self.assertEqual(result["free_bytes"], 75 * 1024**3)
        self.assertEqual(result["display_unit"], "GiB")
        self.assertEqual(result["source"], "wsl-virtual-filesystem")

    def test_powershell_host_storage_maps_backing_volume_json(self):
        payload = {
            "distro": "Ubuntu",
            "base_path": "C:\\Users\\User\\AppData\\Local\\Ubuntu",
            "vhd_path": "C:\\Users\\User\\AppData\\Local\\Ubuntu\\ext4.vhdx",
            "volume": "C:",
            "total_bytes": 500 * 1024**3,
            "free_bytes": 125 * 1024**3,
            "vhd_file_bytes": 80 * 1024**3,
        }
        completed = subprocess.CompletedProcess(
            args=["powershell.exe"],
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )
        with patch.object(system_metrics.subprocess, "run", return_value=completed):
            result = system_metrics._powershell_host_storage("Ubuntu")

        self.assertEqual(result["volume"], "C:")
        self.assertEqual(result["total_gb"], 500.0)
        self.assertEqual(result["used_gb"], 375.0)
        self.assertEqual(result["free_gb"], 125.0)
        self.assertEqual(result["vhd_file_gb"], 80.0)
        self.assertEqual(result["total_bytes"], 500 * 1024**3)
        self.assertEqual(result["used_bytes"], 375 * 1024**3)
        self.assertEqual(result["free_bytes"], 125 * 1024**3)
        self.assertEqual(result["vhd_file_bytes"], 80 * 1024**3)
        self.assertEqual(result["display_unit"], "GiB")
        self.assertEqual(result["source"], "windows-wsl-backing-volume")

    def test_powershell_query_normalizes_import_in_place_base_path(self):
        payload = {
            "distro": "Ubuntu",
            "base_path": "E:\\WSL\\Ubuntu",
            "vhd_path": "E:\\WSL\\Ubuntu\\ext4.vhdx",
            "volume": "E:",
            "total_bytes": 500 * 1024**3,
            "free_bytes": 125 * 1024**3,
        }
        completed = subprocess.CompletedProcess(
            args=["powershell.exe"],
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )
        with patch.object(
            system_metrics.subprocess, "run", return_value=completed
        ) as mock_run:
            system_metrics._powershell_host_storage("Ubuntu")

        script = mock_run.call_args.args[0][-1]
        self.assertIn("$base.StartsWith('\\\\?\\'", script)
        self.assertIn("$base = $base.Substring(4)", script)

    def test_windows_host_storage_gracefully_handles_missing_powershell(self):
        with patch.dict(system_metrics.os.environ, {"WSL_DISTRO_NAME": "Ubuntu"}, clear=False):
            with patch.object(
                system_metrics,
                "_powershell_host_storage",
                side_effect=FileNotFoundError("powershell.exe not found"),
            ):
                result = system_metrics._windows_host_storage_snapshot(force_refresh=True)

        self.assertEqual(result["source"], "windows-wsl-backing-volume")
        self.assertEqual(result["wsl_distro"], "Ubuntu")
        self.assertIn("powershell.exe not found", result["error"])
        self.assertNotIn("free_gb", result)

    def test_windows_host_storage_gracefully_handles_missing_distro_name(self):
        with patch.dict(system_metrics.os.environ, {}, clear=True):
            result = system_metrics._windows_host_storage_snapshot(force_refresh=True)

        self.assertEqual(result["source"], "windows-wsl-backing-volume")
        self.assertIn("WSL_DISTRO_NAME", result["error"])
        self.assertNotIn("free_gb", result)

    def test_stale_host_storage_uses_short_retry_backoff(self):
        system_metrics._host_storage_cache = {
            "volume": "E:",
            "total_gb": 1000.0,
            "used_gb": 900.0,
            "free_gb": 100.0,
            "source": "windows-wsl-backing-volume",
        }
        system_metrics._host_storage_cache_at = 0.0

        with patch.dict(system_metrics.os.environ, {"WSL_DISTRO_NAME": "Ubuntu"}, clear=False):
            with patch.object(system_metrics.time, "monotonic", return_value=1000.0):
                with patch.object(
                    system_metrics,
                    "_powershell_host_storage",
                    side_effect=RuntimeError("interop down"),
                ) as query:
                    first = system_metrics._windows_host_storage_snapshot(force_refresh=True)
                    query.assert_called_once_with("Ubuntu")

            self.assertTrue(first["stale"])
            self.assertEqual(first["free_gb"], 100.0)
            self.assertIn("interop down", first["refresh_error"])

            with patch.object(system_metrics.time, "monotonic", return_value=1001.0):
                with patch.object(system_metrics, "_powershell_host_storage") as query:
                    second = system_metrics._windows_host_storage_snapshot()
                    query.assert_not_called()
            self.assertTrue(second["stale"])

            with patch.object(system_metrics.time, "monotonic", return_value=1003.0):
                with patch.object(
                    system_metrics,
                    "_powershell_host_storage",
                    side_effect=RuntimeError("still down"),
                ) as query:
                    third = system_metrics._windows_host_storage_snapshot()
                    query.assert_called_once_with("Ubuntu")
            self.assertTrue(third["stale"])
            self.assertIn("still down", third["refresh_error"])

    def test_malformed_powershell_output_is_not_promoted_to_capacity(self):
        completed = subprocess.CompletedProcess(
            args=["powershell.exe"],
            returncode=0,
            stdout="not json",
            stderr="",
        )
        with patch.object(system_metrics.subprocess, "run", return_value=completed):
            with self.assertRaises(json.JSONDecodeError):
                system_metrics._powershell_host_storage("Ubuntu")

    def test_system_snapshot_uses_host_storage_for_legacy_model_disk_key(self):
        host = {
            "volume": "D:",
            "total_gb": 1000.0,
            "used_gb": 900.0,
            "free_gb": 100.0,
            "source": "windows-wsl-backing-volume",
        }
        virtual = {
            "path": "/models",
            "total_gb": 1000.0,
            "used_gb": 200.0,
            "free_gb": 800.0,
            "source": "wsl-virtual-filesystem",
        }
        memory = SimpleNamespace(
            total=64 * 1024**3,
            used=20 * 1024**3,
            available=44 * 1024**3,
            percent=31.25,
        )
        with patch.object(system_metrics, "_windows_host_storage_snapshot", return_value=host):
            with patch.object(system_metrics, "_wsl_virtual_disk_snapshot", return_value=virtual):
                with patch.object(system_metrics.psutil, "virtual_memory", return_value=memory):
                    with patch.object(system_metrics.psutil, "cpu_percent", return_value=5.0):
                        result = system_metrics.system_snapshot("/models")

        self.assertEqual(result["host_storage"]["free_gb"], 100.0)
        self.assertEqual(result["wsl_virtual_disk"]["free_gb"], 800.0)
        self.assertEqual(result["model_disk"]["free_gb"], 100.0)
        self.assertEqual(result["model_disk"]["source"], "windows-wsl-backing-volume")


class WSLInteropResolutionTests(unittest.TestCase):
    def test_valid_inherited_interop_is_retained(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            interop_dir = os.path.join(tmpdir, "WSL")
            proc_dir = os.path.join(tmpdir, "proc")
            os.makedirs(interop_dir)
            os.makedirs(os.path.join(proc_dir, "42"))

            socket_path = os.path.join(interop_dir, "42_interop")
            Path(socket_path).touch()

            env = {"WSL_INTEROP": socket_path, "OTHER_VAR": "keep"}
            resolved = system_metrics._resolve_wsl_interop_environment(
                env, interop_dir=interop_dir, proc_dir=proc_dir
            )
            self.assertEqual(resolved["WSL_INTEROP"], socket_path)
            self.assertEqual(resolved["OTHER_VAR"], "keep")

    def test_stale_inherited_interop_is_replaced(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            interop_dir = os.path.join(tmpdir, "WSL")
            proc_dir = os.path.join(tmpdir, "proc")
            os.makedirs(interop_dir)
            os.makedirs(os.path.join(proc_dir, "1"))

            # Stale inherited socket exists on disk, but its process /proc/999 is dead
            stale_socket = os.path.join(interop_dir, "999_interop")
            Path(stale_socket).touch()

            live_socket = os.path.join(interop_dir, "1_interop")
            Path(live_socket).touch()

            env = {"WSL_INTEROP": stale_socket}
            resolved = system_metrics._resolve_wsl_interop_environment(
                env, interop_dir=interop_dir, proc_dir=proc_dir
            )
            self.assertEqual(resolved["WSL_INTEROP"], live_socket)

    def test_nonexistent_inherited_interop_is_replaced(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            interop_dir = os.path.join(tmpdir, "WSL")
            proc_dir = os.path.join(tmpdir, "proc")
            os.makedirs(interop_dir)
            os.makedirs(os.path.join(proc_dir, "1"))

            live_socket = os.path.join(interop_dir, "1_interop")
            Path(live_socket).touch()

            env = {"WSL_INTEROP": os.path.join(interop_dir, "nonexistent_interop")}
            resolved = system_metrics._resolve_wsl_interop_environment(
                env, interop_dir=interop_dir, proc_dir=proc_dir
            )
            self.assertEqual(resolved["WSL_INTEROP"], live_socket)

    def test_known_good_1_interop_selected_when_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            interop_dir = os.path.join(tmpdir, "WSL")
            proc_dir = os.path.join(tmpdir, "proc")
            os.makedirs(interop_dir)
            os.makedirs(os.path.join(proc_dir, "1"))
            os.makedirs(os.path.join(proc_dir, "2"))

            socket_1 = os.path.join(interop_dir, "1_interop")
            socket_2 = os.path.join(interop_dir, "2_interop")
            Path(socket_1).touch()
            Path(socket_2).touch()

            resolved = system_metrics._resolve_wsl_interop_environment(
                {}, interop_dir=interop_dir, proc_dir=proc_dir
            )
            self.assertEqual(resolved["WSL_INTEROP"], socket_1)

    def test_alternate_live_pid_selected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            interop_dir = os.path.join(tmpdir, "WSL")
            proc_dir = os.path.join(tmpdir, "proc")
            os.makedirs(interop_dir)
            # Neither 1 nor 2 exists; only PID 789 is live
            os.makedirs(os.path.join(proc_dir, "789"))

            alt_socket = os.path.join(interop_dir, "789_interop")
            Path(alt_socket).touch()

            resolved = system_metrics._resolve_wsl_interop_environment(
                {}, interop_dir=interop_dir, proc_dir=proc_dir
            )
            self.assertEqual(resolved["WSL_INTEROP"], alt_socket)

    def test_dead_pid_does_not_outrank_live_candidate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            interop_dir = os.path.join(tmpdir, "WSL")
            proc_dir = os.path.join(tmpdir, "proc")
            os.makedirs(interop_dir)

            # PID 1 is present on disk but dead in /proc
            socket_1 = os.path.join(interop_dir, "1_interop")
            Path(socket_1).touch()

            # PID 456 is present on disk AND live in /proc
            os.makedirs(os.path.join(proc_dir, "456"))
            socket_456 = os.path.join(interop_dir, "456_interop")
            Path(socket_456).touch()

            resolved = system_metrics._resolve_wsl_interop_environment(
                {}, interop_dir=interop_dir, proc_dir=proc_dir
            )
            self.assertEqual(resolved["WSL_INTEROP"], socket_456)

    def test_unrelated_files_in_interop_dir_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            interop_dir = os.path.join(tmpdir, "WSL")
            proc_dir = os.path.join(tmpdir, "proc")
            os.makedirs(interop_dir)

            for name in ("README.txt", "interop", "abc_interop", "1_interop.bak", ".dotfile"):
                Path(os.path.join(interop_dir, name)).touch()

            resolved = system_metrics._resolve_wsl_interop_environment(
                {}, interop_dir=interop_dir, proc_dir=proc_dir
            )
            self.assertNotIn("WSL_INTEROP", resolved)

    def test_no_candidates_safe_fallback_no_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            interop_dir = os.path.join(tmpdir, "nonexistent_wsl")
            proc_dir = os.path.join(tmpdir, "proc")

            initial_env = {"EXISTING_KEY": "existing_value"}
            resolved = system_metrics._resolve_wsl_interop_environment(
                initial_env, interop_dir=interop_dir, proc_dir=proc_dir
            )
            self.assertEqual(resolved, initial_env)

    def test_subprocess_receives_resolved_environment(self):
        fake_payload = {
            "distro": "Ubuntu",
            "base_path": "C:\\Ubuntu",
            "vhd_path": "C:\\Ubuntu\\ext4.vhdx",
            "volume": "E:",
            "total_bytes": 1000 * 1024**3,
            "free_bytes": 100 * 1024**3,
        }
        completed = subprocess.CompletedProcess(
            args=["powershell.exe"],
            returncode=0,
            stdout=json.dumps(fake_payload),
            stderr="",
        )
        fake_resolved_env = {"WSL_INTEROP": "/run/WSL/1_interop", "CUSTOM_VAR": "42"}

        with patch.object(
            system_metrics,
            "_resolve_wsl_interop_environment",
            return_value=fake_resolved_env,
        ) as mock_resolve:
            with patch.object(system_metrics.subprocess, "run", return_value=completed) as mock_run:
                system_metrics._powershell_host_storage("Ubuntu")
                mock_resolve.assert_called_once()
                mock_run.assert_called_once()
                _, kwargs = mock_run.call_args
                self.assertEqual(kwargs["env"], fake_resolved_env)

    def test_stale_relay_process_is_treated_as_dead(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            interop_dir = os.path.join(tmpdir, "WSL")
            proc_dir = os.path.join(tmpdir, "proc")
            os.makedirs(interop_dir)

            # PID 100 exists as a relay process, but its target PID 200 is dead
            relay_proc = os.path.join(proc_dir, "100")
            os.makedirs(relay_proc)
            with open(os.path.join(relay_proc, "status"), "w", encoding="utf-8") as f:
                f.write("Name:\tRelay(200)\nState:\tS\n")

            relay_socket = os.path.join(interop_dir, "100_interop")
            Path(relay_socket).touch()

            # PID 1 is alive and a normal process
            os.makedirs(os.path.join(proc_dir, "1"))
            live_socket = os.path.join(interop_dir, "1_interop")
            Path(live_socket).touch()

            # Inheriting the stale relay socket should result in replacement
            resolved = system_metrics._resolve_wsl_interop_environment(
                {"WSL_INTEROP": relay_socket},
                interop_dir=interop_dir,
                proc_dir=proc_dir,
            )
            self.assertEqual(resolved["WSL_INTEROP"], live_socket)


if __name__ == "__main__":
    unittest.main()
