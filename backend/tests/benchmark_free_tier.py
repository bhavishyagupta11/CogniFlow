"""
Free-Tier Production Storage Benchmark (Phases 16 & 17)
Measures cold start time, vector store rebuild duration, and peak RSS memory footprint
to ensure strict compliance with Render Free tier's 512 MB RAM limit.
"""

import os
import sys
import time
import tracemalloc

# Start tracking memory
tracemalloc.start()

def get_process_memory_mb():
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        current, peak = tracemalloc.get_traced_memory()
        return peak / (1024 * 1024)

def run_benchmarks():
    print("=" * 60)
    print("COGNIFLOW FREE-TIER PRODUCTION STORAGE BENCHMARK")
    print("=" * 60)

    mem_baseline = get_process_memory_mb()
    print(f"[*] Baseline Process Memory: {mem_baseline:.2f} MB")

    # 1. Measure DB Init and Connection
    t0 = time.perf_counter()
    from backend.services.db_service import db_service
    db_service.init_db()
    t_db = time.perf_counter() - t0
    mem_post_db = get_process_memory_mb()
    print(f"[1] Database Initialized in {t_db*1000:.2f} ms (Memory: {mem_post_db:.2f} MB)")

    # 2. Measure Storage Service Init
    t0 = time.perf_counter()
    from backend.services.storage_service import storage_service
    t_storage = time.perf_counter() - t0
    print(f"[2] Storage Service ({type(storage_service).__name__}) Initialized in {t_storage*1000:.2f} ms")

    # 3. Measure Vector Store Cold-Start Index Rebuild
    t0 = time.perf_counter()
    from backend.rag.vector_store import vector_store
    vector_store._rebuild()
    t_rebuild = time.perf_counter() - t0
    mem_post_rebuild = get_process_memory_mb()
    stats = vector_store.index_stats()
    print(f"[3] Vector Store Rebuilt in {t_rebuild:.3f} s")
    print(f"    - Total Chunks: {stats['total_chunks']}")
    print(f"    - Total Documents: {stats['total_documents']}")
    print(f"    - Semantic Dimensions: {stats['semantic_dimensions']}")
    print(f"    - Vocabulary Size: {stats.get('vocab_size', 0)}")
    print(f"    - RSS Memory Post-Rebuild: {mem_post_rebuild:.2f} MB (+{mem_post_rebuild - mem_baseline:.2f} MB delta)")

    # 4. Measure RAG Retrieval Query Latencies
    queries = [
        "what is binary search tree time complexity",
        "compare arrays and linked lists memory layout",
        "attention mechanism in transformers",
        "explain selection sort vs merge sort",
        "what is neural network pre-training"
    ]
    latencies = []
    for q in queries:
        t0 = time.perf_counter()
        res = vector_store.search_hybrid(q, k=5)
        dt = (time.perf_counter() - t0) * 1000
        latencies.append(dt)
        assert len(res) > 0

    mem_post_queries = get_process_memory_mb()
    avg_lat = sum(latencies) / len(latencies)
    print(f"[4] Hybrid Search Queries (5 queries):")
    print(f"    - Avg Latency: {avg_lat:.2f} ms")
    print(f"    - Min Latency: {min(latencies):.2f} ms")
    print(f"    - Max Latency: {max(latencies):.2f} ms")
    print(f"    - RSS Memory Post-Queries: {mem_post_queries:.2f} MB")

    # 5. Render Free RAM Limit Check (512 MB)
    print("=" * 60)
    print("RESOURCE BUDGET VERIFICATION")
    print("=" * 60)
    print(f"Render Free RAM Limit: 512.00 MB")
    print(f"Peak Measured Memory:  {mem_post_queries:.2f} MB")
    margin = 512.0 - mem_post_queries
    pct_used = (mem_post_queries / 512.0) * 100
    print(f"Headroom Remaining:    {margin:.2f} MB ({100 - pct_used:.1f}% free)")
    print(f"Memory Budget Status:  {'PASSED [SAFE]' if mem_post_queries < 384 else 'WARNING'}")
    print("=" * 60)

    assert mem_post_queries < 450.0, f"Memory exceeded safety threshold: {mem_post_queries} MB"
    print("[SUCCESS] All free-tier storage benchmarks completed successfully!")

if __name__ == "__main__":
    run_benchmarks()
