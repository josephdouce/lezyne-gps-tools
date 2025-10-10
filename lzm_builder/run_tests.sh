#!/bin/bash
# 
# LZM Builder Test Runner
# 
# Runs all tests in the tests/ directory and provides a summary.
#

set -e  # Exit on any error

echo "🧪 LZM Builder Test Suite"
echo "========================="
echo

# Change to the lzm_builder directory (in case script is run from elsewhere)
cd "$(dirname "$0")"

# Initialize counters
total_tests=0
passed_tests=0
failed_tests=0

# Array to store failed test names
failed_test_names=()

# Run each test file
for test_file in tests/*.py; do
    # Skip __init__.py
    if [[ "$(basename "$test_file")" == "__init__.py" ]]; then
        continue
    fi
    
    total_tests=$((total_tests + 1))
    test_name=$(basename "$test_file" .py)
    
    echo "🔬 Running $test_name..."
    echo "----------------------------------------"
    
    if python "$test_file"; then
        echo "✅ PASSED: $test_name"
        passed_tests=$((passed_tests + 1))
    else
        echo "❌ FAILED: $test_name"
        failed_tests=$((failed_tests + 1))
        failed_test_names+=("$test_name")
    fi
    
    echo
done

# Print summary
echo "📊 TEST SUMMARY"
echo "==============="
echo "Total tests:  $total_tests"
echo "Passed:       $passed_tests"
echo "Failed:       $failed_tests"
echo

if [ $failed_tests -eq 0 ]; then
    echo "🎉 ALL TESTS PASSED!"
    exit 0
else
    echo "💥 SOME TESTS FAILED:"
    for failed_test in "${failed_test_names[@]}"; do
        echo "  - $failed_test"
    done
    exit 1
fi