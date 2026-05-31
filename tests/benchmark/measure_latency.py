"""
Latency measurement script for the LLM Security Proxy.

Measures end-to-end round-trip time across different configurations:
- Direct LLM API call (baseline)
- Proxy with input-only scanning
- Proxy with full pipeline (no code response)
- Proxy with full pipeline (code response with package validation)
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from statistics import median, quantiles
from typing import Dict, List, Tuple

import httpx


# Configuration
PROXY_URL = "http://localhost:8080/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "gpt-4o"
RESULTS_PATH = Path(__file__).parent / "latency_results.json"
REQUEST_TIMEOUT = 60.0


def get_percentile_95(values: List[float]) -> float:
    """Calculate 95th percentile from a list of values."""
    if len(values) < 2:
        return values[0] if values else 0.0
    # quantiles(data, n=100) returns 99 cut points for percentiles
    percentiles = quantiles(values, n=100)
    return percentiles[94]  # 95th percentile (0-indexed)


def measure_request(url: str, payload: dict, headers: dict, client: httpx.Client) -> Tuple[float, int, bool]:
    """
    Measure the latency of a single request.
    
    Returns:
        Tuple of (latency_seconds, status_code, success)
    """
    start = time.perf_counter()
    try:
        response = client.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        latency = time.perf_counter() - start
        return latency, response.status_code, response.status_code in [200, 400]
    except httpx.TimeoutException:
        latency = time.perf_counter() - start
        print(f"  ⚠ Request timed out after {latency:.2f}s")
        return latency, 0, False
    except httpx.ConnectError as e:
        latency = time.perf_counter() - start
        print(f"  ✗ Connection failed: {e}")
        return latency, 0, False
    except Exception as e:
        latency = time.perf_counter() - start
        print(f"  ✗ Request failed: {e}")
        return latency, 0, False


def run_configuration(
    name: str,
    url: str,
    prompt: str,
    headers: dict,
    num_requests: int,
    client: httpx.Client
) -> Dict:
    """
    Run multiple requests for a single configuration and collect latency metrics.
    
    Returns:
        Dictionary with configuration results
    """
    print(f"\n{name}")
    print(f"  URL: {url}")
    print(f"  Requests: {num_requests}")
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 150,
        "temperature": 0.7
    }
    
    latencies = []
    successful = 0
    
    for i in range(num_requests):
        latency, status_code, success = measure_request(url, payload, headers, client)
        latencies.append(latency)
        
        if success:
            successful += 1
            status = "✓"
        else:
            status = "✗"
        
        print(f"  [{i+1}/{num_requests}] {status} {latency*1000:.0f}ms (HTTP {status_code})")
    
    # Calculate metrics
    if latencies:
        median_latency = median(latencies)
        p95_latency = get_percentile_95(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        avg_latency = sum(latencies) / len(latencies)
    else:
        median_latency = p95_latency = min_latency = max_latency = avg_latency = 0.0
    
    results = {
        "name": name,
        "url": url,
        "num_requests": num_requests,
        "successful": successful,
        "latencies_ms": [round(lat * 1000, 2) for lat in latencies],
        "median_ms": round(median_latency * 1000, 2),
        "p95_ms": round(p95_latency * 1000, 2),
        "min_ms": round(min_latency * 1000, 2),
        "max_ms": round(max_latency * 1000, 2),
        "avg_ms": round(avg_latency * 1000, 2)
    }
    
    print(f"  → Median: {results['median_ms']}ms | P95: {results['p95_ms']}ms")
    
    return results


def get_api_key() -> str:
    """Get API key from environment."""
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY or OPENAI_API_KEY environment variable not set")
        print("Set one of these to enable direct API testing (Configuration A)")
        sys.exit(1)
    return api_key


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(
        description="Measure latency across different proxy configurations"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run only 3 requests per configuration for quick validation"
    )
    args = parser.parse_args()
    
    num_requests = 3 if args.dry_run else 20
    
    print("=" * 80)
    print("LLM PROXY LATENCY MEASUREMENT")
    print("=" * 80)
    
    if args.dry_run:
        print("⚠ DRY RUN MODE: 3 requests per configuration")
    
    # Get API key for direct calls
    api_key = get_api_key()
    
    # Define test prompts
    simple_prompt = "What is the capital of France? Answer in one sentence."
    code_prompt = "Write a simple Python function that uses the requests library to make a GET request. Just show the code, no explanation."
    
    all_results = []
    
    with httpx.Client() as client:
        # Configuration A: Direct API call (baseline)
        print("\n" + "=" * 80)
        print("CONFIGURATION A: Direct LLM API (Baseline - No Proxy)")
        print("=" * 80)
        
        direct_headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        result_a = run_configuration(
            name="A: Direct API Call",
            url=OPENROUTER_URL,
            prompt=simple_prompt,
            headers=direct_headers,
            num_requests=num_requests,
            client=client
        )
        all_results.append(result_a)
        
        # Configuration B: Proxy with input scanning only
        print("\n" + "=" * 80)
        print("CONFIGURATION B: Proxy with Input Scanning Only")
        print("=" * 80)
        print("Note: This requires temporarily disabling output scanning.")
        print("      Set VULN_SCAN_ENABLED=false, DEPENDENCY_SCAN_ENABLED=false,")
        print("      SANDBOX_ENABLED=false, GUARDRAILS_ENABLED=false in proxy environment.")
        
        proxy_headers = {
            "Content-Type": "application/json"
        }
        
        result_b = run_configuration(
            name="B: Proxy - Input Only",
            url=PROXY_URL,
            prompt=simple_prompt,
            headers=proxy_headers,
            num_requests=num_requests,
            client=client
        )
        all_results.append(result_b)
        
        # Configuration C: Full pipeline with simple prompt (no code block)
        print("\n" + "=" * 80)
        print("CONFIGURATION C: Proxy - Full Pipeline (No Code Response)")
        print("=" * 80)
        print("Note: Ensure all output scanning features are enabled in proxy environment.")
        
        result_c = run_configuration(
            name="C: Proxy - Full Pipeline (No Code)",
            url=PROXY_URL,
            prompt=simple_prompt,
            headers=proxy_headers,
            num_requests=num_requests,
            client=client
        )
        all_results.append(result_c)
        
        # Configuration D: Full pipeline with code prompt
        print("\n" + "=" * 80)
        print("CONFIGURATION D: Proxy - Full Pipeline (Code with Package Validation)")
        print("=" * 80)
        
        result_d = run_configuration(
            name="D: Proxy - Full Pipeline (Code)",
            url=PROXY_URL,
            prompt=code_prompt,
            headers=proxy_headers,
            num_requests=num_requests,
            client=client
        )
        all_results.append(result_d)
    
    # Print summary table
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"{'Configuration':<40} {'Median':<12} {'P95':<12} {'Success Rate':<15}")
    print("-" * 80)
    
    for result in all_results:
        success_rate = f"{result['successful']}/{result['num_requests']}"
        print(f"{result['name']:<40} {result['median_ms']:>8}ms   {result['p95_ms']:>8}ms   {success_rate:>15}")
    
    print("=" * 80)
    
    # Calculate overhead
    if all_results[0]['median_ms'] > 0:
        overhead_b = ((all_results[1]['median_ms'] - all_results[0]['median_ms']) / all_results[0]['median_ms']) * 100
        overhead_c = ((all_results[2]['median_ms'] - all_results[0]['median_ms']) / all_results[0]['median_ms']) * 100
        overhead_d = ((all_results[3]['median_ms'] - all_results[0]['median_ms']) / all_results[0]['median_ms']) * 100
        
        print(f"\nProxy Overhead vs Direct API:")
        print(f"  Config B (Input Only):     +{overhead_b:.1f}%")
        print(f"  Config C (Full - No Code): +{overhead_c:.1f}%")
        print(f"  Config D (Full - Code):    +{overhead_d:.1f}%")
    
    # Save results
    output = {
        "test_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "num_requests_per_config": num_requests,
        "configurations": all_results
    }
    
    with open(RESULTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\nDetailed results saved to {RESULTS_PATH}")
    
    # Check if any configuration had failures
    total_failed = sum(result['num_requests'] - result['successful'] for result in all_results)
    if total_failed > 0:
        print(f"\n⚠ WARNING: {total_failed} requests failed")
        sys.exit(1)
    
    print("\n✓ Latency measurement complete!")


if __name__ == "__main__":
    main()
