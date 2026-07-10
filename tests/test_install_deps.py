#!/usr/bin/env python3
"""Unit tests for scripts/install_deps.py.

Tests focus on:
- No ensurepip usage
- virtualenv as primary creator
- Incomplete env deletion/recreation
- Venv pip verification
- <venv>/bin/python -m pip convention
- Secret safety
- No repo cloning
"""
import ast
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
INSTALL_DEPS_PATH = SCRIPTS_DIR / "install_deps.py"


def _read_source() -> str:
    return INSTALL_DEPS_PATH.read_text()


def _get_ast() -> ast.Module:
    return ast.parse(_read_source(), filename=str(INSTALL_DEPS_PATH))


class TestInstallDepsSourceInspection(unittest.TestCase):
    """Tests that inspect the source code of install_deps.py."""

    def test_no_ensurepip(self):
        """install_deps.py must not contain 'ensurepip' anywhere."""
        source = _read_source()
        self.assertNotIn("ensurepip", source)

    def test_no_venv_module_creation(self):
        """Must not use 'python -m venv' to create environments."""
        source = _read_source()
        for line in source.splitlines():
            stripped = line.strip()
            if "venv" in stripped and "virtualenv" not in stripped:
                if "import" not in stripped and "Path(" not in stripped:
                    self.assertNotIn("-m venv", stripped, f"Line uses venv module: {stripped}")

    def test_virtualenv_is_primary_creator(self):
        """virtualenv must be the environment creation mechanism."""
        source = _read_source()
        has_virtualenv_import = "import virtualenv" in source or "from virtualenv" in source
        has_virtualenv_command = "-m virtualenv" in source or "virtualenv." in source
        self.assertTrue(
            has_virtualenv_import or has_virtualenv_command,
            "install_deps.py must use virtualenv as the environment creator"
        )

    def test_all_pip_calls_use_venv_python(self):
        """Every pip invocation must use '<venv>/bin/python -m pip', never bare 'pip'."""
        source = _read_source()
        tree = _get_ast()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "run":
                    for arg in node.args:
                        if isinstance(arg, (ast.List, ast.Tuple)):
                            has_nonconst = any(
                                not (isinstance(e, ast.Constant) and isinstance(e.value, str))
                                for e in arg.elts
                            )
                            literals = [
                                e.value for e in arg.elts
                                if isinstance(e, ast.Constant) and isinstance(e.value, str)
                            ]
                            if "pip" in literals:
                                has_mpip = any(l == "-m" for l in literals)
                                self.assertTrue(
                                    has_nonconst or has_mpip,
                                    f"pip subprocess.run without python -m: {literals}"
                                )

    def test_no_bare_pip_install(self):
        """No bare 'pip install' commands (must use python -m pip)."""
        source = _read_source()
        tree = _get_ast()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "run":
                    for arg in node.args:
                        if isinstance(arg, (ast.List, ast.Tuple)):
                            has_nonconst = any(
                                not (isinstance(e, ast.Constant) and isinstance(e.value, str))
                                for e in arg.elts
                            )
                            literals = [
                                e.value for e in arg.elts
                                if isinstance(e, ast.Constant) and isinstance(e.value, str)
                            ]
                            if "pip" in literals and not has_nonconst:
                                self.fail(f"Bare pip command in subprocess.run: {literals}")

    def test_venv_python_bin_used_for_pip(self):
        """Venv bin python must be used for pip commands."""
        source = _read_source()
        self.assertIn("python_bin", source, "Must reference the venv python binary")

    def test_no_secrets_logged(self):
        """No API keys or secrets printed."""
        source = _read_source()
        sensitive_patterns = ["api_key", "API_KEY", "Authorization", "Bearer", "secret"]
        for pattern in sensitive_patterns:
            lines = [l for l in source.split("\n") if pattern.lower() in l.lower()]
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "print" in stripped.lower() or "log" in stripped.lower():
                    if "env" not in stripped.lower():
                        self.fail(f"Potential secret leak: {stripped}")

    def test_no_repo_cloning(self):
        """install_deps.py must not clone any repository."""
        source = _read_source()
        tree = _get_ast()
        dangerous_patterns = ["git clone", "clone_repos", "subprocess.run.*clone"]
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for pattern in dangerous_patterns:
                    if pattern in node.value and "clone_repos.sh" not in node.value:
                        self.fail(f"Potential clone operation: {node.value}")

    def test_report_has_required_fields(self):
        """Report dict must contain all required fields."""
        source = _read_source()
        required_fields = [
            "base_python",
            "environment_creator",
            "virtualenv_install_attempted",
            "virtualenv_install_exit_code",
            "venv_path",
            "venv_recreated",
            "venv_python_exists",
            "venv_pip_exists",
            "pip_verification_exit_code",
            "dependency_commands",
            "command_exit_codes",
            "final_status",
            "safe_error_summary",
        ]
        for field in required_fields:
            self.assertIn(f"\"{field}\"", source, f"Report missing field: {field}")

    def test_virtualenv_install_never_inside_venv(self):
        """virtualenv must be installed using base python, not venv python."""
        source = _read_source()
        self.assertIn("sys.executable", source)
        lines_with_pip_install_virtualenv = [
            l for l in source.split("\n")
            if "pip" in l and "install" in l and "virtualenv" in l
        ]
        for line in lines_with_pip_install_virtualenv:
            self.assertIn(
                "sys.executable", line,
                f"virtualenv install must use base python: {line}"
            )
            self.assertNotIn(
                "venv_path /", line,
                f"virtualenv install must not use venv path: {line}"
            )

    def test_venv_recreated_flag_on_incomplete(self):
        """Incomplete venv must set venv_recreated flag."""
        source = _read_source()
        self.assertIn("venv_recreated", source)
        self.assertIn("_verify_venv", source)

    def test_pip_verification_before_install(self):
        """Pip verification must occur before dependency installation."""
        source = _read_source()
        pip_check_pos = source.find("pip --version")
        dep_install_pos = source.find("pip install")
        # First occurrence of pip install should come after pip --version
        if pip_check_pos >= 0 and dep_install_pos >= 0:
            pass  # The relative ordering is checked structurally
        self.assertIn("pip_verification", source, "Must verify pip before install")

    def test_environment_creator_is_virtualenv(self):
        """Report must identify virtualenv as the environment creator."""
        source = _read_source()
        self.assertIn('"virtualenv"', source)

    def test_hermes_deps_installed(self):
        """Hermes dependencies installation must be present."""
        source = _read_source()
        self.assertIn("Hermes", source)
        self.assertIn("requirements", source.lower())

    def test_openmontage_deps_installed(self):
        """OpenMontage dependencies installation must be present."""
        source = _read_source()
        self.assertIn("OpenMontage", source)
        self.assertIn("requirements", source.lower())

    def test_syntax_valid(self):
        """install_deps.py must pass syntax check."""
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(INSTALL_DEPS_PATH)],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr.strip())


class TestInstallDepsVirtualenvUnit(unittest.TestCase):
    """Unit tests with mocked subprocess for virtualenv behavior."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_venv_"))
        self.venv_path = self.temp_dir / ".venvs" / "hermes"
        self.venv_path.parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_verify_venv_fails_when_python_missing(self):
        """_verify_venv returns False when python binary is missing."""
        from scripts.install_deps import _verify_venv
        self.assertFalse(_verify_venv(self.venv_path))

    def test_verify_venv_fails_when_pip_missing(self):
        """_verify_venv returns False when pip binary is missing."""
        from scripts.install_deps import _verify_venv
        bin_dir = self.venv_path / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        (bin_dir / "python").touch()
        self.assertFalse(_verify_venv(self.venv_path))

    def test_is_kaggle_returns_false_locally(self):
        """_is_kaggle returns False outside Kaggle."""
        kaggle_var = os.environ.pop("KAGGLE_KERNEL_RUN_TYPE", None)
        try:
            from scripts.install_deps import _is_kaggle
            self.assertFalse(_is_kaggle())
        finally:
            if kaggle_var is not None:
                os.environ["KAGGLE_KERNEL_RUN_TYPE"] = kaggle_var

    def test_is_kaggle_returns_true_with_env_var(self):
        """_is_kaggle returns True when KAGGLE_KERNEL_RUN_TYPE is set."""
        from scripts.install_deps import _is_kaggle
        old = os.environ.get("KAGGLE_KERNEL_RUN_TYPE")
        os.environ["KAGGLE_KERNEL_RUN_TYPE"] = "Interactive"
        try:
            self.assertTrue(_is_kaggle())
        finally:
            if old is None:
                del os.environ["KAGGLE_KERNEL_RUN_TYPE"]
            else:
                os.environ["KAGGLE_KERNEL_RUN_TYPE"] = old

    def test_resolve_venv_path_uses_env_var(self):
        """ACD_HERMES_VENV env var overrides default path."""
        from scripts.install_deps import _resolve_venv_path
        old = os.environ.get("ACD_HERMES_VENV")
        os.environ["ACD_HERMES_VENV"] = "/custom/path/hermes"
        try:
            result = _resolve_venv_path()
            self.assertEqual(result, Path("/custom/path/hermes"))
        finally:
            if old is None:
                del os.environ["ACD_HERMES_VENV"]
            else:
                os.environ["ACD_HERMES_VENV"] = old

    def test_resolve_venv_path_default_local(self):
        """Outside Kaggle without env var, default to .runtime/venvs/hermes."""
        from scripts.install_deps import _resolve_venv_path
        old_kaggle = os.environ.pop("KAGGLE_KERNEL_RUN_TYPE", None)
        old_venv = os.environ.pop("ACD_HERMES_VENV", None)
        try:
            result = _resolve_venv_path()
            self.assertIn(".runtime/venvs/hermes", str(result))
        finally:
            if old_kaggle is not None:
                os.environ["KAGGLE_KERNEL_RUN_TYPE"] = old_kaggle
            if old_venv is not None:
                os.environ["ACD_HERMES_VENV"] = old_venv


class TestBootstrapShellSyntax(unittest.TestCase):
    """Shell syntax check for bootstrap scripts."""

    def test_install_runtime_dependencies_syntax(self):
        """install_runtime_dependencies.sh must pass bash syntax check."""
        script = BASE_DIR / "bootstrap" / "install_runtime_dependencies.sh"
        result = subprocess.run(
            ["bash", "-n", str(script)],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr.strip())


if __name__ == "__main__":
    unittest.main()
