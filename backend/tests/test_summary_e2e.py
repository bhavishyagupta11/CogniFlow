import asyncio
import time
import json
from backend.rag.pipeline import run_rag_pipeline
from backend.services.summary_cache import summary_cache

async def main():
    question = "Give me the summary from page 0 to the last page, nothing should be missed from the summary, also outline the most important."
    print("=== Testing Cold Document Summary Run ===")
    summary_cache.invalidate_document("ad36d825-6ca9-4ad4-8b6c-60a1189afd3a")
    
    t0 = time.time()
    events = []
    tokens = []
    final_result = None

    async for sse_raw in run_rag_pipeline(
        question=question,
        mode="adaptive",
        user_id="dev-user"
    ):
        line = sse_raw.strip()
        if line.startswith("data: "):
            payload = json.loads(line[6:])
            evt_type = payload.get("type")
            events.append(evt_type)
            if evt_type == "token":
                tokens.append(payload.get("content", ""))
            elif evt_type == "pipeline_complete":
                final_result = payload.get("result")
            elif evt_type in ["summary_started", "extraction_progress", "batch_progress", "combining_started", "final_answer_started"]:
                print(f"  [SSE Progress] {evt_type}: {payload}")

    cold_time = time.time() - t0
    full_answer = "".join(tokens)
    print(f"\nCold run completed in {cold_time:.2f}s")
    print(f"Total events emitted: {len(events)}")
    print(f"Answer length: {len(full_answer)} chars")
    print(f"Answer snippet:\n{full_answer[:600]}...\n")

    # Assertions
    assert "summary_started" in events, "Missing summary_started event"
    assert "extraction_progress" in events, "Missing extraction_progress event"
    assert "batch_progress" in events, "Missing batch_progress event"
    assert "combining_started" in events, "Missing combining_started event"
    assert "final_answer_started" in events, "Missing final_answer_started event"
    assert final_result is not None, "Missing pipeline_complete result"
    assert final_result["answerability"]["status"] == "fully_answerable", f"Expected fully_answerable, got {final_result['answerability']['status']}"
    assert final_result["answerability"]["missingInformation"] == [], f"Expected empty missingInformation, got {final_result['answerability']['missingInformation']}"
    assert len(final_result["sources"]) > 0, "Expected sources covering document"

    # Check key technical concepts are present in full_answer
    concepts = ["Binary Search", "O(log n)", "Linked List", "Stack", "Queue", "Tree", "BST", "Heap", "Graph", "Sorting"]
    for c in concepts:
        assert c.lower() in full_answer.lower(), f"Concept '{c}' was missing from full document summary!"

    print("=== All Cold Run Assertions Passed! ===")

    print("\n=== Testing Warm (Cached) Document Summary Run ===")
    t1 = time.time()
    warm_events = []
    warm_tokens = []
    warm_result = None

    async for sse_raw in run_rag_pipeline(
        question=question,
        mode="adaptive",
        user_id="dev-user"
    ):
        line = sse_raw.strip()
        if line.startswith("data: "):
            payload = json.loads(line[6:])
            evt_type = payload.get("type")
            warm_events.append(evt_type)
            if evt_type == "token":
                warm_tokens.append(payload.get("content", ""))
            elif evt_type == "pipeline_complete":
                warm_result = payload.get("result")

    warm_time = time.time() - t1
    print(f"Warm run completed in {warm_time:.4f}s ({warm_time*1000:.1f}ms)")
    assert warm_time < 0.5, f"Warm cache run took too long: {warm_time:.2f}s"
    assert warm_result["answerability"]["status"] == "fully_answerable"
    assert len(warm_result["sources"]) > 0
    print("=== All Warm (Cached) Run Assertions Passed! ===")

if __name__ == "__main__":
    asyncio.run(main())
