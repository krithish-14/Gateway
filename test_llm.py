import os
import sys
import time
import requests
import json

# Setup django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_year_project.settings')
import django
django.setup()

from project_review.services.verification import verify_patent, calculate_similarity

def test_ollama_status():
    """Check if Ollama is running and has the mistral model."""
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            models = [m['name'] for m in response.json().get('models', [])]
            return "mistral" in models or "mistral:latest" in models
    except:
        return False
    return False

def run_test(name, fn, args, expected_check, expect_msg):
    print("\n" + "-" * 60)
    print(f"[{name}]")
    print("-" * 60)
    print(f"  Inputs: {args}")
    print(f"  Expect: {expect_msg}")
    
    start = time.time()
    result = fn(*args)
    duration = time.time() - start
    
    print(f"  Result: {result}")
    print(f"  Time:   {duration:.2f}s")
    
    if expected_check(result):
        print("  ✅ PASSED")
        return True
    else:
        print("  ❌ FAILED")
        return False

def test_llm():
    print("=" * 60)
    print("  OLLAMA (MISTRAL) ENHANCED ACCURACY TEST ENGINE")
    print("  Mode: Few-Shot Calibrated Prompting")
    print("=" * 60)

    if not test_ollama_status():
        print("\nERROR: Ollama is not running or 'mistral' model is not pulled yet.")
        return

    passed_count = 0
    total_tests = 0

    # ── SIMILARITY TESTS ──
    
    # Test 1: Unique
    res = run_test(
        "SIMILARITY: UNIQUE BIO-TECH",
        calculate_similarity,
        ["A device that converts cellular radiation into pure drinking water using molecular condensation.", []],
        lambda x: x < 3.0,
        "Score < 3.0 (Highly Unique)"
    )
    if res: passed_count += 1
    total_tests += 1

    # Test 2: Duplicate
    res = run_test(
        "SIMILARITY: DIRECT CLONE",
        calculate_similarity,
        ["An online bookstore platform that sells physical books and ships them globally via a warehouse network.", []],
        lambda x: x > 7.5,
        "Score > 7.5 (Direct Amazon Clone)"
    )
    if res: passed_count += 1
    total_tests += 1

    # Test 3: Moderate
    res = run_test(
        "SIMILARITY: MODERATE (Common AI Use)",
        calculate_similarity,
        ["An AI-powered recipe generator that takes photos of your fridge and suggests meals.", []],
        lambda x: 3.0 <= x <= 7.0,
        "Score 3.0 - 7.0 (Existing but specialized)"
    )
    if res: passed_count += 1
    total_tests += 1

    # ── PATENT TESTS ──
    print("\n(Note: Patent tests now use real API lookups and may take longer.)")

    # Test 4: Real US Patent
    res = run_test(
        "PATENT: REAL US (USPTO)",
        verify_patent,
        ["US10123456B2", "TechCorp Inc"],
        lambda x: x.get('verified') == True,
        "verified = True"
    )
    if res: passed_count += 1
    total_tests += 1
    time.sleep(2)

    # Test 5: Real Indian Patent
    res = run_test(
        "PATENT: REAL INDIAN (IPO)",
        verify_patent,
        ["202341065432", "AgriTech India"],
        lambda x: x.get('verified') == True,
        "verified = True"
    )
    if res: passed_count += 1
    total_tests += 1
    time.sleep(2)

    # Test 6: Fake (New Pattern)
    res = run_test(
        "PATENT: FAKE (Placeholder)",
        verify_patent,
        ["00000000TEST", "Mock Startup"],
        lambda x: x.get('verified') == False,
        "verified = False"
    )
    if res: passed_count += 1
    total_tests += 1
    time.sleep(2)

    # ── Summary ──
    print("\n" + "=" * 60)
    print(f"  ENHANCED TEST RESULTS: {passed_count}/{total_tests} Passed")
    accuracy = (passed_count / total_tests * 100) if total_tests > 0 else 0
    print(f"  SYSTEM ACCURACY:       {accuracy:.0f}%")
    print("=" * 60)

if __name__ == "__main__":
    test_llm()
