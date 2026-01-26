"""
Test restricted_bash functionality
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.builtin_tools import restricted_bash, calculator


def test_restricted_bash():
    """Test restricted bash with various commands."""
    print("=" * 80)
    print("Testing Restricted Bash")
    print("=" * 80)
    print()

    test_cases = [
        # Safe commands (should succeed)
        ("ls", "List files", True),
        ("pwd", "Print working directory", True),
        ("whoami", "Current user", True),
        ("date", "Current date", True),
        ("echo 'hello'", "Echo text", True),
        ("cat README.md | head -n 3", "Pipe: cat and head", True),
        ("ls | grep .py", "Pipe: ls and grep", True),
        ("find . -name '*.py' -type f | head -n 5", "Complex pipe", True),
        # Dangerous commands (should be blocked)
        ("rm test.txt", "Delete file", False),
        ("rm -rf /", "Dangerous delete", False),
        ("curl http://example.com", "Network request", False),
        ("wget file.zip", "Download file", False),
        ("chmod 777 file", "Change permissions", False),
        ("sudo apt-get install", "Sudo command", False),
        ("python -c 'import os; os.system(\"ls\")'", "Python execution", False),
    ]

    passed = 0
    failed = 0

    for command, description, should_succeed in test_cases:
        result = restricted_bash(command, timeout=5)

        is_blocked = "Error" in result and "not allowed" in result
        is_success = "Error" not in result

        if should_succeed:
            # Should succeed
            if is_success:
                print(f"✓ {description}: PASSED (command executed)")
                print(f"  Command: {command}")
                print(f"  Result: {result[:60]}{'...' if len(result) > 60 else ''}")
                passed += 1
            else:
                print(f"✗ {description}: FAILED (should succeed but got error)")
                print(f"  Command: {command}")
                print(f"  Error: {result[:80]}")
                failed += 1
        else:
            # Should be blocked
            if is_blocked:
                print(f"✓ {description}: PASSED (command blocked)")
                print(f"  Command: {command}")
                print(f"  Result: {result[:80]}")
                passed += 1
            else:
                print(f"✗ {description}: FAILED (should be blocked)")
                print(f"  Command: {command}")
                print(f"  Result: {result[:80]}")
                failed += 1
        print()

    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 80)

    return failed == 0


def test_calculator():
    """Quick test of calculator."""
    print("\n" + "=" * 80)
    print("Testing Calculator")
    print("=" * 80)
    print()

    test_cases = [
        ("2 + 2", "4"),
        ("10 * 5", "50"),
        ("sqrt(16)", "4"),
        ("pi", "3.14", True),  # Partial match
        ("(5 + 3) * 2", "16"),
    ]

    passed = 0
    failed = 0

    for expression, expected, *partial in test_cases:
        is_partial = len(partial) > 0 and partial[0]
        result = calculator(expression)

        if is_partial:
            success = result.startswith(expected)
        else:
            success = result == expected

        if success:
            print(f"✓ {expression} = {result}")
            passed += 1
        else:
            print(f"✗ {expression} = {result} (expected: {expected})")
            failed += 1

    print()
    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 80)

    return failed == 0


if __name__ == "__main__":
    bash_ok = test_restricted_bash()
    calc_ok = test_calculator()

    print("\n" + "=" * 80)
    print("OVERALL RESULTS")
    print("=" * 80)

    if bash_ok and calc_ok:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)
