"""
CogniFlow Maximal Marginal Relevance (MMR) Diversity Controller
Implements Specification Section 10:
- Balances query relevance with diversity to prevent duplicate or near-identical passages.
- Evaluates candidate pairwise redundancy:
  - If candidate passages are already diverse, skips MMR to conserve latency (returns mmr_used=False).
  - If redundant or overlapping passages are detected, applies MMR selection (returns mmr_used=True).
- Bounded, vectorized NumPy implementation operating in sub-millisecond time.
"""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np


def compute_pairwise_cosine_similarity(vectors: np.ndarray) -> np.ndarray:
    """Computes full pairwise cosine similarity matrix for L2-normalized vectors."""
    if vectors.shape[0] == 0:
        return np.zeros((0, 0), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = vectors / norms
    return np.dot(normed, normed.T)


def apply_mmr_diversity(
    candidates: List[Dict[str, Any]],
    candidate_vectors: Optional[np.ndarray],
    query_vector: Optional[np.ndarray],
    lambda_param: float = 0.7,
    top_k: int = 5,
    redundancy_threshold: float = 0.82
) -> Tuple[List[Dict[str, Any]], bool]:
    r"""
    Applies Maximal Marginal Relevance (MMR) to candidate chunks.
    Formula:
        MMR = argmax_{Di in R \ S} [ lambda * Sim(Di, Q) - (1 - lambda) * max_{Dj in S} Sim(Di, Dj) ]

    Returns:
        (selected_candidates, mmr_used)
    """
    n = len(candidates)
    if n <= 1 or candidate_vectors is None or candidate_vectors.shape[0] != n:
        return candidates[:top_k], False

    # Check pairwise redundancy among top candidates
    sub_vectors = candidate_vectors[:min(n, 8)]
    sim_matrix = compute_pairwise_cosine_similarity(sub_vectors)

    # Check off-diagonal max similarity
    np.fill_diagonal(sim_matrix, 0.0)
    max_pairwise_sim = float(np.max(sim_matrix)) if sim_matrix.size > 0 else 0.0

    # If all candidate chunks are already sufficiently diverse, skip MMR
    if max_pairwise_sim < redundancy_threshold and n <= top_k:
        return candidates[:top_k], False

    # Otherwise execute MMR selection
    selected_indices: List[int] = []
    unselected_indices = list(range(n))

    # Calculate query similarities
    if query_vector is not None:
        q_norm = np.linalg.norm(query_vector)
        q_normed = (query_vector / q_norm) if q_norm > 0 else query_vector
        cand_norms = np.linalg.norm(candidate_vectors, axis=1, keepdims=True)
        cand_norms[cand_norms == 0] = 1.0
        cand_normed = candidate_vectors / cand_norms
        relevance_scores = np.dot(cand_normed, q_normed.T).flatten()
    else:
        relevance_scores = np.array([float(c.get("score", 0.5)) for c in candidates])

    # First chunk is always the highest relevance chunk
    first_idx = int(np.argmax(relevance_scores))
    selected_indices.append(first_idx)
    unselected_indices.remove(first_idx)

    # Greedily select remaining up to top_k
    pairwise_matrix = compute_pairwise_cosine_similarity(candidate_vectors)

    while len(selected_indices) < min(top_k, n) and unselected_indices:
        best_idx = -1
        best_mmr_score = -float("inf")

        for idx in unselected_indices:
            rel = float(relevance_scores[idx])
            # Max similarity to any already selected chunk
            max_sim_to_selected = max(float(pairwise_matrix[idx, s]) for s in selected_indices)
            mmr_score = lambda_param * rel - (1.0 - lambda_param) * max_sim_to_selected

            if mmr_score > best_mmr_score:
                best_mmr_score = mmr_score
                best_idx = idx

        if best_idx != -1:
            selected_indices.append(best_idx)
            unselected_indices.remove(best_idx)
        else:
            break

    selected_chunks = [candidates[i] for i in selected_indices]
    return selected_chunks, True
