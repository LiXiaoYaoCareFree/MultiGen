import argparse
import json
import resource
import statistics
import subprocess
import time
from typing import Any, Dict, List

from app.domain.models.app_config import LLMConfig
from app.infrastructure.external.llm.openai_llm import OpenAILLM


def _build_messages(chars: int) -> List[Dict[str, Any]]:
    payload = "x" * chars
    return [{"role": "user", "content": payload}]


def _run_budget_benchmark(llm: OpenAILLM, chars: int, rounds: int) -> Dict[str, Any]:
    messages = _build_messages(chars)
    latencies_ms: List[float] = []
    resolved_tokens: List[int] = []
    safe_limits: List[int] = []
    context_limits: List[int] = []

    for _ in range(rounds):
        begin = time.perf_counter()
        request_max_tokens, _, context_limit = llm._resolve_request_max_tokens(messages)  # noqa: SLF001
        cost_ms = (time.perf_counter() - begin) * 1000
        latencies_ms.append(cost_ms)
        resolved_tokens.append(request_max_tokens)
        context_limits.append(context_limit)
        safe_limits.append(llm.get_safe_prompt_token_limit())

    mean_ms = statistics.mean(latencies_ms)
    p95_ms = statistics.quantiles(latencies_ms, n=20)[18] if len(latencies_ms) >= 20 else max(latencies_ms)
    throughput = rounds / max(sum(latencies_ms) / 1000, 1e-6)

    return {
        "chars": chars,
        "rounds": rounds,
        "context_limit": context_limits[0],
        "resolved_max_tokens": resolved_tokens[0],
        "safe_prompt_limit": safe_limits[0],
        "latency_mean_ms": round(mean_ms, 3),
        "latency_p95_ms": round(p95_ms, 3),
        "throughput_ops_s": round(throughput, 2),
        "rss_memory_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
    }


def _query_gpu_memory_mb() -> float | None:
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True,
            timeout=2,
        )
    except Exception:
        return None
    values = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            values.append(float(line))
        except ValueError:
            continue
    if not values:
        return None
    return round(sum(values), 2)


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepSeek context-window benchmark (budget resolver level).")
    parser.add_argument("--chars", type=int, default=300000, help="Single message char length for token estimation.")
    parser.add_argument("--rounds", type=int, default=200, help="Benchmark rounds.")
    args = parser.parse_args()

    old_llm = OpenAILLM(
        LLMConfig(
            base_url="https://api.deepseek.com",
            api_key="benchmark",
            model_name="deepseek-v4-flash",
            max_tokens=8192,
            max_prompt_tokens=122000,
        ),
    )
    new_llm = OpenAILLM(
        LLMConfig(
            base_url="https://api.deepseek.com",
            api_key="benchmark",
            model_name="deepseek-v4-flash",
            max_tokens=384000,
            max_prompt_tokens=1000000,
        ),
    )

    old_metrics = _run_budget_benchmark(old_llm, chars=args.chars, rounds=args.rounds)
    new_metrics = _run_budget_benchmark(new_llm, chars=args.chars, rounds=args.rounds)
    gpu_memory_mb = _query_gpu_memory_mb()

    result = {
        "baseline_old": old_metrics,
        "updated_new": new_metrics,
        "gpu_memory_used_mb": gpu_memory_mb,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
