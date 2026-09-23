"""Regression tests for worker command-line safety and setup validation."""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("worker_cli", ROOT / "scripts" / "acd_worker.py")
worker_cli = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = worker_cli
spec.loader.exec_module(worker_cli)

from bootstrap import validate_setup


class WorkerCLITests(unittest.TestCase):
    def test_validation_runs_checks_and_propagates_failure(self):
        with patch.object(sys, "argv", ["acd_worker.py", "--validate-only"]), \
             patch.object(worker_cli, "ACDWorker") as worker, \
             patch.object(validate_setup.SetupValidator, "run_all", return_value=False) as run_all, \
             patch.dict(os.environ, {"PROJECT_ROOT": str(ROOT)}):
            with self.assertRaises(SystemExit) as exit_result:
                worker_cli.main()
        self.assertEqual(exit_result.exception.code, 1)
        run_all.assert_called_once_with()
        worker.assert_not_called()

    def test_validation_success_returns_zero(self):
        with patch.object(sys, "argv", ["acd_worker.py", "--validate-only"]), \
             patch.object(validate_setup.SetupValidator, "run_all", return_value=True):
            with self.assertRaises(SystemExit) as exit_result:
                worker_cli.main()
        self.assertEqual(exit_result.exception.code, 0)

    def test_explicit_dry_run_overrides_config(self):
        with tempfile.TemporaryDirectory() as temp:
            config_file = Path(temp) / "config.json"
            config_file.write_text(json.dumps({"dry_run": False}))
            with patch.object(sys, "argv", ["acd_worker.py", "--dry-run", "--config", str(config_file), "test request"]), \
                 patch.object(worker_cli, "ACDWorker") as worker:
                worker.return_value.execute_full_workflow.return_value = True
                with self.assertRaises(SystemExit) as exit_result:
                    worker_cli.main()
        self.assertEqual(exit_result.exception.code, 0)
        self.assertTrue(worker.call_args.args[0].dry_run)

    def test_standalone_validation_defaults_to_checkout(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(validate_setup, "SetupValidator") as validator:
            validator.return_value.run_all.return_value = False
            with self.assertRaises(SystemExit) as exit_result:
                validate_setup.main()
        self.assertEqual(exit_result.exception.code, 1)
        validator.assert_called_once_with(str(ROOT))


if __name__ == "__main__":
    unittest.main()
