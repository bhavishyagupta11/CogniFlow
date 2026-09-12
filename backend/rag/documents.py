"""
Foundational AI/ML Research Papers Knowledge Base
Default indexed documents available immediately out-of-the-box.
"""

from typing import List, Dict, Any

KNOWLEDGE_BASE: List[Dict[str, Any]] = [
    {
        "id": "doc-attention-2017",
        "title": "Attention Is All You Need",
        "authors": "Vaswani et al.",
        "year": 2017,
        "source": "NeurIPS 2017",
        "content": """# Attention Is All You Need
The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder.
We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.

## Model Architecture
The Transformer follows an overall architecture using stacked self-attention and point-wise, fully connected layers for both encoder and decoder.

### Attention Function
An attention function maps a query and a set of key-value pairs to an output. The output is computed as a weighted sum of values.
In Scaled Dot-Product Attention:
Attention(Q, K, V) = softmax(Q * K^T / sqrt(d_k)) * V
The input consists of queries and keys of dimension d_k, and values of dimension d_v. We divide by sqrt(d_k) to prevent dot products from growing excessively large for large dimensions.

### Multi-Head Attention
Instead of performing a single attention function with d_model-dimensional keys, values, and queries, we project queries, keys, and values h times with different learned linear projections to d_k, d_k, and d_v dimensions.

### Advantages of Self-Attention
1. Total computational complexity per layer is O(n * d) which is smaller than recurrent layers when sequence length n is smaller than representation dimensionality d.
2. Amount of computation that can be parallelized, measured by the minimum number of sequential operations required: O(1) for self-attention vs O(n) for recurrent.
3. Path length between long-range dependencies: O(1) maximum path length enables learning long-range dependencies easily."""
    },
    {
        "id": "doc-bert-2019",
        "title": "BERT: Pre-training of Deep Bidirectional Transformers",
        "authors": "Devlin et al.",
        "year": 2019,
        "source": "NAACL 2019",
        "content": """# BERT: Pre-training of Deep Bidirectional Transformers
We introduce BERT (Bidirectional Encoder Representations from Transformers). Unlike previous representation models, BERT pre-trains deep bidirectional representations from unlabeled text by jointly conditioning on left and right context in all layers.

## Pre-training Tasks
1. Masked Language Model (MLM): 15% of input tokens are masked at random; the model predicts original vocabulary IDs.
2. Next Sentence Prediction (NSP): Binarized task predicting whether sentence B immediately follows sentence A.

## Architecture & Sizes
BERT-base: 12 layers, 768 hidden units, 12 attention heads, 110M parameters.
BERT-large: 24 layers, 1024 hidden units, 16 attention heads, 340M parameters.
Input representations combine WordPiece token embeddings (30k vocab), segment embeddings, and position embeddings."""
    },
    {
        "id": "doc-gpt3-2020",
        "title": "Language Models are Few-Shot Learners",
        "authors": "Brown et al.",
        "year": 2020,
        "source": "NeurIPS 2020",
        "content": """# Language Models are Few-Shot Learners (GPT-3)
We demonstrate that scaling up language models greatly improves task-agnostic few-shot performance without gradient updates or fine-tuning.

## Model Size & Architecture
GPT-3 is a 175-billion parameter autoregressive language model (decoder-only Transformer) featuring 96 layers, 96 attention heads, and a hidden dimension of 12,288.

## In-Context Learning Modes
- Zero-shot: Model is given only a natural language prompt describing the task.
- One-shot: Model is given one demonstration example followed by the task.
- Few-shot: Model is given typically 10 to 100 demonstrations within context.

## Findings
GPT-3 achieves competitive or state-of-the-art results across translation, question answering (TriviaQA, Natural Questions), cloze tasks, and on-the-fly arithmetic."""
    },
    {
        "id": "doc-rag-2020",
        "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "authors": "Lewis et al.",
        "year": 2020,
        "source": "NeurIPS 2020",
        "content": """# Retrieval-Augmented Generation (RAG)
Large pre-trained language models store factual knowledge in parametric memory, but struggle with factual precision and updates. RAG combines parametric memory (a pre-trained seq2seq generator like BART) with non-parametric memory (a dense vector index of Wikipedia retrieved via Dense Passage Retriever / DPR).

## Architecture
- Retriever: Dense Passage Retriever (DPR) utilizing dual BERT encoders to map queries and passages to dense 768-dim vectors.
- Generator: Pre-trained seq2seq BART model.
- Formulation: RAG-Sequence marginalizes over top-k passages across the whole sequence; RAG-Token allows different passages to generate different tokens.

## Advantages Over Fine-Tuning
1. External knowledge base updates without costly model retraining.
2. Direct inline citation and factual verification against retrieved passages.
3. Substantially reduced hallucinations on open-domain knowledge benchmarks."""
    },
    {
        "id": "doc-react-2023",
        "title": "ReAct: Synergizing Reasoning and Acting in Language Models",
        "authors": "Yao et al.",
        "year": 2023,
        "source": "ICLR 2023",
        "content": """# ReAct: Synergizing Reasoning and Acting in Language Models
We propose ReAct, a general paradigm that synergizes reasoning and acting in language models.

## Concept & Interleaved Execution
Reasoning without acting suffers from hallucinations because the model cannot verify assertions against external environments. Acting without reasoning suffers from lack of planning.
ReAct generates interleaved trajectories:
Thought: Intermediate reasoning step tracking goals and plans.
Action: Execution step interacting with external environments (Search[x], Lookup[y], Finish[z]).
Observation: Feedback returned by external environment.

## Benchmark Results
On HotpotQA and Fever, ReAct overcomes false reasoning paths and reduces hallucination rates compared to pure chain-of-thought prompting."""
    },
    {
        "id": "doc-cai-2022",
        "title": "Constitutional AI: Harmlessness from AI Feedback",
        "authors": "Bai et al.",
        "year": 2022,
        "source": "arXiv 2022",
        "content": """# Constitutional AI: Harmlessness from AI Feedback (RLAIF)
We introduce Constitutional AI (CAI), a method for training harmless AI assistants without requiring human feedback labels for harmful queries.

## Methodology
The training consists of two phases:
1. Supervised Learning (SL): The model critiques and revises its own responses using a written set of principles (the Constitution).
2. Reinforcement Learning (RL): Model generates paired responses, an AI evaluates which response best adheres to constitutional principles, and preference labels train a preference model (RLAIF).

## Constitutional Principles
Principles mandate transparency, non-violence, ethical integrity, and objective discourse without human feedback on sensitive topics."""
    }
]
