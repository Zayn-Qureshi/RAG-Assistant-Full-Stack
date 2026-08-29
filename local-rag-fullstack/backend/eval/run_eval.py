"""
Runs the golden dataset through the full RAG pipeline and reports:
1. Retrieval hit-rate: did the expected source file appear in top-k results?
2. Answer accuracy (approximate): keyword-overlap between expected and actual answer.

Can run in two modes to compare hybrid+rerank vs. vector-only:
    python eval/run_eval.py            -> hybrid search + re-ranking (current default)
    python eval/run_eval.py --vector-only  -> vector search only (old behavior, for comparison)

This lets you produce a real before/after number for the hybrid search
upgrade, instead of assuming it helped.
"""

import sys
import os
import time
import argparse

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from retrieve import retrieve
from generate import generate_answer
from golden_dataset import GOLDEN_DATASET


def keyword_overlap_score(expected: str, actual: str) -> float:
    stopwords = {
        "the", "is", "of", "a", "an", "to", "and", "in", "on", "for",
        "with", "about", "according", "documents", "document", "that",
        "this", "system", "solves", "problem", "not", "stated", "provided",
        "are", "was", "were", "be", "as", "it", "its", "by", "from",
    }
    expected_words = {
        w.strip(".,?!").lower()
        for w in expected.split()
        if w.strip(".,?!").lower() not in stopwords and len(w) > 2
    }
    if not expected_words:
        return 1.0
    actual_lower = actual.lower()
    matched = sum(1 for w in expected_words if w in actual_lower)
    return matched / len(expected_words)


def run_evaluation(use_hybrid: bool = True):
    results = []
    total = len(GOLDEN_DATASET)
    mode_label = "HYBRID + RERANK" if use_hybrid else "VECTOR-ONLY"

    print(f"Running eval in {mode_label} mode...\n")

    for i, item in enumerate(GOLDEN_DATASET, 1):
        question = item["question"]
        expected_source = item["expected_source"]
        expected_answer = item["expected_answer"]

        print(f"[{i}/{total}] {question}")

        start = time.time()
        retrieved_chunks = retrieve(question, use_hybrid=use_hybrid)
        retrieved_sources = [c["source"] for c in retrieved_chunks]

        retrieval_hit = True if expected_source is None else expected_source in retrieved_sources

        result = generate_answer(question)
        answer = result["answer"]
        elapsed = time.time() - start

        overlap_score = keyword_overlap_score(expected_answer, answer)
        answer_hit = overlap_score >= 0.5

        results.append({
            "question": question,
            "expected_source": expected_source,
            "retrieved_sources": retrieved_sources,
            "retrieval_hit": retrieval_hit,
            "expected_answer": expected_answer,
            "actual_answer": answer,
            "answer_hit": answer_hit,
            "overlap_score": round(overlap_score, 2),
            "time_seconds": round(elapsed, 1),
        })

        status_r = "✅" if retrieval_hit else "❌"
        status_a = "✅" if answer_hit else "❌"
        print(f"   Retrieval: {status_r}  Answer: {status_a} ({overlap_score:.0%} overlap)  ({elapsed:.1f}s)")

    retrieval_hits = sum(r["retrieval_hit"] for r in results)
    answer_hits = sum(r["answer_hit"] for r in results)
    avg_time = sum(r["time_seconds"] for r in results) / total

    print("\n" + "=" * 50)
    print(f"EVAL SUMMARY ({mode_label})")
    print("=" * 50)
    print(f"Retrieval hit-rate: {retrieval_hits}/{total} ({100*retrieval_hits/total:.0f}%)")
    print(f"Answer accuracy:    {answer_hits}/{total} ({100*answer_hits/total:.0f}%)")
    print(f"Avg time/question:  {avg_time:.1f}s")

    failures = [r for r in results if not r["retrieval_hit"] or not r["answer_hit"]]
    if failures:
        print(f"\n--- {len(failures)} FAILURES ---")
        for f in failures:
            print(f"\nQ: {f['question']}")
            if not f["retrieval_hit"]:
                print(f"  Expected source: {f['expected_source']}")
                print(f"  Got sources: {f['retrieved_sources']}")
            if not f["answer_hit"]:
                print(f"  Overlap score: {f['overlap_score']:.0%}")
                print(f"  Expected answer contains: {f['expected_answer']}")
                print(f"  Got: {f['actual_answer'][:150]}...")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vector-only", action="store_true", help="Run with vector search only, no hybrid/rerank")
    args = parser.parse_args()

    run_evaluation(use_hybrid=not args.vector_only)
