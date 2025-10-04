#!/usr/bin/env python3
"""Test suite runner for Python code quality validation.

Runs Ruff, mypy, and pytest to ensure code quality.
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import Any


class ValidationTestRunner:
    """Runs all validation tests and reports results."""

    def __init__(self, project_dir: str = "."):
        """Initialize the test runner."""
        self.project_dir = Path(project_dir).resolve()
        self.venv_dir = self.project_dir / "venv"
        self.results: dict[str, dict[str, Any]] = {}

    def get_python_executable(self) -> str:
        """Get the Python executable from venv if available."""
        venv_python = self.venv_dir / "bin" / "python"
        if venv_python.exists():
            return str(venv_python)
        return sys.executable

    def run_validator(
        self, command: list[str], description: str
    ) -> tuple[bool, str, str, float]:
        """Run a single validator command."""
        start_time = time.time()
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=120, cwd=self.project_dir
            )
            end_time = time.time()
            duration = end_time - start_time

            return (
                result.returncode == 0,
                result.stdout,
                result.stderr,
                duration,
            )

        except subprocess.TimeoutExpired:
            end_time = time.time()
            duration = end_time - start_time
            return (
                False,
                "",
                "Validator timed out after 120 seconds",
                duration,
            )

        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            return (False, "", f"Failed to run validator: {e}", duration)

    def run_all_tests(self) -> bool:
        """Run all validation tests."""
        python_exe = self.get_python_executable()

        validators = [
            (
                [python_exe, "-m", "ruff", "check", "."],
                "Ruff Linting",
                True,
            ),  # blocking
            (
                [python_exe, "-m", "ruff", "format", "--check", "."],
                "Ruff Formatting Check",
                True,
            ),  # blocking
            (
                [python_exe, "-m", "mypy", "."],
                "Mypy Type Checking",
                False,
            ),  # non-blocking
            (
                [python_exe, "-m", "pytest"],
                "Pytest Test Suite",
                True,
            ),  # blocking
        ]

        all_passed = True
        total_duration = 0.0

        print("🔍 Running Python Code Quality Validation")
        print("=" * 60)
        print()

        for command, description, blocking in validators:
            print(f"Running {description}...")

            passed, stdout, stderr, duration = self.run_validator(command, description)
            total_duration += duration

            self.results[description] = {
                "description": description,
                "passed": passed,
                "stdout": stdout,
                "stderr": stderr,
                "duration": duration,
                "blocking": blocking,
            }

            if passed:
                print(f"  ✅ PASSED ({duration:.2f}s)")
            else:
                if blocking:
                    print(f"  ❌ FAILED ({duration:.2f}s)")
                    all_passed = False
                else:
                    print(f"  ⚠️  FAILED (non-blocking - {duration:.2f}s)")

            print()

        print(f"Total execution time: {total_duration:.2f}s")
        print("=" * 60)

        return all_passed

    def print_detailed_results(self) -> None:
        """Print detailed results for each validator."""
        for result in self.results.values():
            print(f"\n📋 {result['description']}")
            print("-" * 50)

            if result["passed"]:
                print("Status: ✅ PASSED")
            else:
                print("Status: ❌ FAILED")

            print(f"Duration: {result['duration']:.2f}s")

            if result["stdout"].strip():
                print("\nOutput:")
                for line in result["stdout"].strip().split("\n"):
                    print(f"  {line}")

            if result["stderr"].strip():
                print("\nErrors:")
                for line in result["stderr"].strip().split("\n"):
                    print(f"  {line}")

            print()

    def print_summary(self) -> None:
        """Print test summary."""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results.values() if r["passed"])
        failed_tests = total_tests - passed_tests

        print("\n📊 TEST SUMMARY")
        print("=" * 30)
        print(f"Total tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")

        if failed_tests == 0:
            print("\n🎉 All tests passed! Your code quality is excellent.")
        else:
            print(
                f"\n⚠️  {failed_tests} test(s) failed. " "Please review the errors above."
            )

        print()

    def check_dependencies(self) -> bool:
        """Check if all required dependencies are available."""
        python_exe = self.get_python_executable()

        required_modules = ["ruff", "mypy", "pytest"]
        missing_modules = []

        for module in required_modules:
            try:
                result = subprocess.run(
                    [python_exe, "-m", module, "--version"],
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    missing_modules.append(module)
            except Exception:
                missing_modules.append(module)

        if missing_modules:
            modules_str = ", ".join(missing_modules)
            print(f"❌ Missing required Python modules: {modules_str}")
            print("Please install them with:")
            print(f"  {python_exe} -m pip install {' '.join(missing_modules)}")
            return False

        return True

    def run(self) -> bool:
        """Run the complete test suite."""
        if not self.check_dependencies():
            return False

        all_passed = self.run_all_tests()

        self.print_detailed_results()
        self.print_summary()

        return all_passed


def main() -> None:
    """Run main function for command line usage."""
    project_dir = sys.argv[1] if len(sys.argv) > 1 else "."

    runner = ValidationTestRunner(project_dir)
    success = runner.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
