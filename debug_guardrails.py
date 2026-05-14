#!/usr/bin/env python3

import asyncio
from src.output_security.guardrails import (
    ToxicityChecker,
    HallucinationChecker,
    PromptLeakageChecker,
    ContentSafetyChecker
)

async def main():
    text = "Hello world"
    print(f"Testing with text: '{text}'")

    toxicity = ToxicityChecker()
    hallucination = HallucinationChecker()
    prompt_leakage = PromptLeakageChecker()
    content_safety = ContentSafetyChecker()

    print("\nIndividual results:")
    tox_result = toxicity.check(text)
    print(f"Toxicity: passed={tox_result.passed}, risk={tox_result.risk_level}, score={tox_result.score}")

    hall_result = hallucination.check(text)
    print(f"Hallucination: passed={hall_result.passed}, risk={hall_result.risk_level}, score={hall_result.score}")

    leak_result = prompt_leakage.check(text)
    print(f"Prompt leakage: passed={leak_result.passed}, risk={leak_result.risk_level}, score={leak_result.score}")

    safety_result = content_safety.check(text)
    print(f"Content safety: passed={safety_result.passed}, risk={safety_result.risk_level}, score={safety_result.score}")

if __name__ == "__main__":
    asyncio.run(main())