/**
 * Knowledge Base — Sample Research Documents
 *
 * These are condensed / paraphrased summaries of influential AI/ML papers.
 * Used as the corpus for the RAG pipeline. In production you would ingest
 * real PDFs / web pages; here we ship a self-contained corpus so the demo
 * works without any external data source.
 */

export interface Document {
  id: string;
  title: string;
  authors: string;
  year: number;
  source: string;
  content: string;
}

export const KNOWLEDGE_BASE: Document[] = [
  {
    id: "doc-attention-2017",
    title: "Attention Is All You Need",
    authors: "Vaswani et al.",
    year: 2017,
    source: "NeurIPS 2017",
    content: `# Attention Is All You Need

The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism.

We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely. Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable and requiring significantly less time to train.

## Model Architecture

The Transformer follows this overall architecture using stacked self-attention and point-wise, fully connected layers for both the encoder and decoder.

### Encoder and Decoder Stacks

Encoder: The encoder is composed of a stack of N = 6 identical layers. Each layer has two sub-layers. The first is a multi-head self-attention mechanism, and the second is a simple, position-wise fully connected feed-forward network. We employ a residual connection around each of the two sub-layers, followed by layer normalization.

Decoder: The decoder is also composed of a stack of N = 6 identical layers. In addition to the two sub-layers in each encoder layer, the decoder inserts a third sub-layer, which performs multi-head attention over the output of the encoder stack.

### Attention

An attention function can be described as mapping a query and a set of key-value pairs to an output, where the query, keys, values, and output are all vectors. The output is computed as a weighted sum of the values, where the weight assigned to each value is computed by a compatibility function of the query with the corresponding key.

### Scaled Dot-Product Attention

We call our particular attention "Scaled Dot-Product Attention". The input consists of queries and keys of dimension d_k, and values of dimension d_v. We compute the dot products of the query with all keys, divide each by the square root of d_k, and apply a softmax function to obtain the weights on the values.

### Multi-Head Attention

Instead of performing a single attention function with d_model-dimensional keys, values and queries, we found it beneficial to linearly project the queries, keys and values h times with different, learned linear projections to d_k, d_k and d_v dimensions, respectively.

## Why Self-Attention

Three motivations drove our design: one is total computational complexity per layer, another is the amount of computation that can be parallelized, and the third is the path length between long-range dependencies in the network.

## Results and Training

We trained our models on the standard WMT 2014 English-German and English-French datasets. For English-German, our base model surpasses all previously published models, and our big model outperforms all by 0.5 BLEU. Training took 3.5 days on 8 P100 GPUs.`,
  },
  {
    id: "doc-bert-2019",
    title: "BERT: Pre-training of Deep Bidirectional Transformers",
    authors: "Devlin et al.",
    year: 2019,
    source: "NAACL 2019",
    content: `# BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding

We introduce a new language representation model called BERT, which stands for Bidirectional Encoder Representations from Transformers. Unlike recent language representation models, BERT is designed to pre-train deep bidirectional representations from unlabeled text by jointly conditioning on both left and right context in all layers.

## Pre-training Tasks

BERT addresses two key pre-training tasks: Masked Language Model (MLM) and Next Sentence Prediction (NSP).

### Masked Language Model (MLM)

In MLM, we mask out a percentage of the input tokens, and the model must predict the original vocabulary id of the masked words. This allows the model to fuse left and right context, producing a truly bidirectional representation.

### Next Sentence Prediction (NSP)

Many important downstream tasks such as Question Answering (QA) and Natural Language Inference (NLI) are based on understanding the relationship between two sentences. To train a model that understands sentence relationships, we pre-train for a binarized next sentence prediction task.

## Model Architecture

The BERT model architecture is a multi-layer bidirectional Transformer encoder. We release two sizes: BERT-base (12 layers, 768 hidden, 12 attention heads, 110M parameters) and BERT-large (24 layers, 1024 hidden, 16 attention heads, 340M parameters).

## Input Representation

The input representation is the sum of the token embeddings, the segmentation embeddings, and the position embeddings. We use WordPiece embeddings with a 30,000 token vocabulary.

## Fine-tuning

Fine-tuning is straightforward since the self-attention mechanism in the Transformer allows BERT to model many downstream tasks with minimal changes. For each task, we simply plug in the task-specific inputs and outputs into BERT and fine-tune all the parameters end-to-end.

## Results

BERT achieves state-of-the-art results on eleven NLP tasks, including GLUE (80.5%), SQuAD v1.1 (93.2 F1), and SQuAD v2.0 (83.1 F1). The ablation studies confirm that both pre-training tasks contribute to the model's effectiveness.`,
  },
  {
    id: "doc-gpt3-2020",
    title: "Language Models are Few-Shot Learners",
    authors: "Brown et al.",
    year: 2020,
    source: "NeurIPS 2020",
    content: `# Language Models are Few-Shot Learners (GPT-3)

Recent work has demonstrated substantial gains on many NLP tasks and benchmarks by pre-training on a large corpus of text, then fine-tuning on a specific task. We show that scaling up language models greatly improves task-agnostic, few-shot performance.

## Model Size

We trained a 175-billion parameter autoregressive language model, which we call GPT-3, and measure its in-context learning capabilities. GPT-3 is a decoder-only Transformer with 96 layers, 96 attention heads, and a hidden dimension of 12288.

## In-Context Learning

For all tasks, GPT-3 is applied without any gradient updates or fine-tuning, with tasks and few-shot demonstrations specified purely via text interaction with the model. We examine three settings:

### Zero-shot

The model is given no demonstrations, only a natural language instruction describing the task.

### One-shot

The model is given a single demonstration and a natural language description of the task.

### Few-shot

The model is given a few demonstrations of the task, in addition to a natural language description.

## Evaluation

We evaluate GPT-3 on over two dozen NLP datasets. Across all three settings, GPT-3 achieves strong performance. On traditional language modeling tasks, GPT-3 substantially improves the state of the art.

## Translation

GPT-3 achieves state-of-the-art results on several translation tasks, including XSUM, CNN/DailyMail translation. We observe that GPT-3 is able to perform translation between languages, especially in the high-resource direction.

## Question Answering

We evaluate GPT-3 on three question answering datasets: SQuAD 2.0, TriviaQA, and Natural Questions. The model performs well in few-shot settings, sometimes matching or exceeding the performance of fine-tuned models.

## Limitations

Despite strong results, GPT-3 has several limitations. It can generate untruthful content (hallucination). It has limited capability in performing arithmetic and reasoning tasks. It sometimes fails at simple tasks that humans find easy. It also has biases that can be harmful when deployed at scale.

## Broader Impacts

Language models like GPT-3 have significant broader impacts, including potential misuse for disinformation, phishing, and academic dishonesty. We recommend careful deployment and continued research into mitigations.`,
  },
  {
    id: "doc-rag-2020",
    title: "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
    authors: "Lewis et al.",
    year: 2020,
    source: "NeurIPS 2020",
    content: `# Retrieval-Augmented Generation (RAG)

Large pre-trained language models have been shown to store factual knowledge in their parameters and achieve state-of-the-art results when fine-tuned on downstream NLP tasks. However, their ability to access and precisely manipulate knowledge is limited, leading to hallucinations and errors on knowledge-intensive tasks.

## Approach

We explore a general-purpose fine-tuning recipe for retrieval-augmented generation (RAG). We retrieve documents using a pre-trained retriever and pass them to a pre-trained seq2seq generator. We build RAG models where the parametric memory is a pre-trained seq2seq model and the non-parametric memory is a dense vector index of Wikipedia.

## Architecture

RAG models use the input sequence to retrieve text passages from an external document store. The retrieved passages are then used as additional context for the generator to produce the output.

### Retriever

The retriever component is a Dense Passage Retriever (DPR), which uses two BERT models to encode the query and the document separately into dense vectors. Retrieval is performed by computing the dot product between the query vector and all document vectors.

### Generator

The generator is a BART model, a pre-trained seq2seq Transformer. The retrieved documents are concatenated with the input query and passed to the generator.

## Variants

We introduce two RAG variants:

### RAG-Sequence

In RAG-Sequence, the same retrieved document is used to generate the complete target sequence. The model marginalizes over the top-k retrieved documents.

### RAG-Token

In RAG-Token, different documents can be used to generate different tokens in the target sequence. The model can draw information from multiple retrieved documents.

## Results

We evaluate RAG on a wide variety of knowledge-intensive tasks, including Open-Domain QA, Jeopardy question generation, and Fact Verification. RAG achieves state-of-the-art on multiple benchmarks and produces more specific and factual responses than a pure parametric seq2seq model.

## Advantages over Fine-Tuning

Compared to fine-tuning, RAG offers several advantages:
1. The knowledge base can be updated without retraining the model.
2. The model's outputs are grounded in retrieved sources, reducing hallucinations.
3. Sources can be cited, improving verifiability.
4. The model size remains constant regardless of the knowledge base size.

## Limitations

RAG has limitations: retrieval latency, dependence on retriever quality, and the challenge of choosing the right number of retrieved passages.`,
  },
  {
    id: "doc-cot-2022",
    title: "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models",
    authors: "Wei et al.",
    year: 2022,
    source: "NeurIPS 2022",
    content: `# Chain-of-Thought Prompting

We explore the generation of chain of thought — a series of intermediate reasoning steps — to enable language models to perform complex reasoning. We show that chain-of-thought prompting improves the reasoning ability of large language models on arithmetic, commonsense, and symbolic reasoning tasks.

## Method

In chain-of-thought prompting, demonstrations of reasoning are provided in the prompt. Each demonstration consists of a question, a chain of thought (intermediate reasoning steps), and the final answer. The model then generates its own chain of thought when answering new questions.

## Why Chain-of-Thought Works

Chain-of-thought reasoning offers several advantages:
1. It decomposes multi-step problems into intermediate steps, allowing the model to allocate more computation to harder problems.
2. It provides interpretability into the model's reasoning process.
3. It can be elicited through few-shot prompting without requiring additional training.

## Experiments

We evaluate chain-of-thought prompting on three categories of reasoning tasks:

### Arithmetic Reasoning

On the GSM8K benchmark of grade-school math word problems, chain-of-thought prompting enables a 540B parameter model to achieve 56.9% accuracy, surpassing the prior state-of-the-art of 55%.

### Commonsense Reasoning

On CommonsenseQA and StrategyQA, chain-of-thought prompting improves performance by 6-18 percentage points over standard prompting.

### Symbolic Reasoning

On symbolic reasoning tasks like last-letter concatenation and coin flip tracking, chain-of-thought prompting enables generalization to longer sequences than seen in demonstrations.

## Model Size Effect

Chain-of-thought prompting only produces performance gains when used with models of sufficient scale (around 100B parameters). For smaller models, chain-of-thought can actually hurt performance.

## Self-Consistency

A follow-up technique called self-consistency further improves chain-of-thought by sampling multiple reasoning paths and taking a majority vote. This reduces the variance of single-sample decoding.

## Implications

Chain-of-thought prompting demonstrates that prompting alone, without parameter updates, can substantially improve reasoning. This finding has motivated many subsequent techniques including Tree-of-Thought, Graph-of-Thought, and ReAct.`,
  },
  {
    id: "doc-react-2023",
    title: "ReAct: Synergizing Reasoning and Acting in Language Models",
    authors: "Yao et al.",
    year: 2023,
    source: "ICLR 2023",
    content: `# ReAct: Synergizing Reasoning and Acting in Language Models

While large language models (LLMs) have demonstrated impressive capabilities in reasoning and acting separately, combining these abilities remains challenging. We propose ReAct, a general paradigm that combines reasoning and acting in language models.

## Motivation

Reasoning without acting can lead to hallucinations and factual errors because the model cannot ground its reasoning in external information. Acting without reasoning can lead to myopic decisions because the model cannot plan ahead or reflect on its actions.

## Method

In ReAct, the model generates both reasoning traces (Thoughts) and task-specific actions (Actions) in an interleaved manner. Reasoning traces help the model plan, track, and update goals, while actions allow the model to interact with external sources (e.g., search engines, databases) to gather information.

## Format

A typical ReAct trajectory looks like:

Thought 1: I need to find information about X.
Action 1: Search[X]
Observation 1: (search results)
Thought 2: Based on the results, I should...
Action 2: Lookup[Y]
Observation 2: (lookup results)
...
Thought N: I now have enough information to answer.
Action N: Finish[answer]

## Evaluation

We evaluate ReAct on four diverse benchmarks: HotpotQA (multi-hop question answering), FEVER (fact verification), AlfWorld (embodied decision making), and WebShop (web shopping). ReAct outperforms pure reasoning and pure acting baselines across all four tasks.

## Comparison with Chain-of-Thought

While chain-of-thought reasoning produces strong results on tasks where the model has internal knowledge, it suffers on tasks requiring external or up-to-date information. ReAct addresses this by interleaving reasoning with actions that query external sources.

## Comparison with Acting-Only

Acting-only agents (e.g., traditional RL agents or tool-use agents) lack the ability to plan and reflect. ReAct's reasoning component helps the agent plan multi-step strategies and recover from errors.

## Limitations

ReAct has several limitations:
1. It depends on the quality of external tools and APIs.
2. The number of reasoning-acting steps can grow large, increasing latency and cost.
3. Prompt engineering is required to elicit good ReAct trajectories.
4. The model can get stuck in loops without careful prompting.

## Implications

ReAct has become a foundational technique for building LLM agents. It has inspired many subsequent frameworks including LangChain agents, AutoGPT, BabyAGI, and the broader multi-agent ecosystem.`,
  },
  {
    id: "doc-constitutional-ai-2023",
    title: "Constitutional AI: Harmlessness from AI Feedback",
    authors: "Bai et al.",
    year: 2023,
    source: "Anthropic Technical Report",
    content: `# Constitutional AI: Harmlessness from AI Feedback

As AI systems become more capable, ensuring they are helpful and harmless becomes increasingly important. We propose Constitutional AI, a method for training AI assistants that are helpful and harmless through a combination of supervised learning and reinforcement learning from AI feedback.

## Motivation

Traditional RLHF (Reinforcement Learning from Human Feedback) relies on large-scale human preference data. This is expensive, slow, and can lead to inconsistent labels. Constitutional AI replaces much of the human feedback with AI feedback guided by a set of principles (a "constitution").

## Method

Constitutional AI consists of two phases:

### Supervised Phase (SL)

In the supervised phase, the model is asked to respond to harmful prompts. It then critiques its own responses using the principles in the constitution. Finally, the model revises its response based on its own critique. The revised responses are used as training data for supervised fine-tuning.

### Reinforcement Learning Phase (RLAIF)

In the reinforcement learning phase, the model generates pairs of responses to prompts. An AI evaluator (rather than a human) compares the responses using the constitution's principles and produces preference labels. These labels are used to train a preference model, which is then used as the reward signal for RL.

## The Constitution

The constitution is a set of natural-language principles that guide the model's behavior. Example principles include:
- Please choose the response that is the least demographically discriminatory.
- Please choose the response that is least intended to assist with illegal activities.
- Please choose the response that most accurately reflects the truth.

## Comparison with RLHF

Constitutional AI (RLAIF) differs from RLHF in several ways:
1. RLAIF uses AI feedback, which is cheaper and faster than human feedback.
2. RLAIF enforces explicit principles, making the training process more transparent.
3. RLAIF can scale to large datasets without proportional increases in human labor.
4. RLAIF may inherit biases from the AI evaluator, requiring careful constitution design.

## Results

We trained Claude (an earlier version) using Constitutional AI and compared it with RLHF. Constitutional AI produces assistants that both helpful and harmless, with performance comparable to or better than RLHF while requiring significantly less human feedback.

## Implications

Constitutional AI represents a paradigm shift toward scalable alignment techniques. The use of AI feedback enables training safer models at scale, but also raises questions about the reliability of AI-generated feedback and the importance of the constitution's design.`,
  },
  {
    id: "doc-langgraph-2024",
    title: "LangGraph: Building Stateful Multi-Actor Applications with LLMs",
    authors: "LangChain Team",
    year: 2024,
    source: "LangChain Documentation",
    content: `# LangGraph: Building Stateful Multi-Actor Applications

LangGraph is a framework for building stateful, multi-actor applications with LLMs. It extends the LangChain ecosystem to support the construction of agent workflows that involve cycles, state management, and multiple LLMs.

## Motivation

Traditional LLM applications are often stateless pipelines: prompt in, completion out. Real-world agent applications require more sophisticated patterns: cycles (loops), conditional branching, persistent state, and coordination between multiple actors. LangGraph provides primitives for all of these.

## Core Concepts

### State Graph

A State Graph is a directed graph where each node represents a function (an LLM call, a tool invocation, or any computation) and edges represent control flow. State is passed through the graph and can be updated by each node.

### Nodes

Nodes are functions that take the current state and return updates to the state. They can represent LLM calls, tool invocations, human-in-the-loop checkpoints, or any custom logic.

### Edges

Edges define control flow between nodes. They can be:
- Direct: always go from A to B
- Conditional: choose between B or C based on state
- Cyclic: loop back to a previous node (essential for agent reasoning loops)

### Checkpointing

LangGraph supports checkpointing, which persists the state at each node. This enables:
- Human-in-the-loop workflows (pause for approval, then resume)
- Time-travel debugging (replay from any checkpoint)
- Fault tolerance (resume after crashes)

## Common Patterns

### ReAct Agent

A ReAct agent in LangGraph is a two-node cycle: an LLM node that decides the next action, and a tool node that executes it. The conditional edge returns to the LLM node if the model wants to call another tool, or exits if the model has produced a final answer.

### Multi-Agent Supervisor

A supervisor pattern uses one LLM as a router that decides which specialist agent to invoke. Each specialist agent is itself a graph that can perform complex sub-tasks. The supervisor coordinates the overall flow.

### Hierarchical Teams

Multiple supervisors can be nested, creating hierarchical teams where a top-level supervisor delegates to mid-level supervisors, which delegate to worker agents. This pattern scales to complex applications.

## Comparison with Other Frameworks

LangGraph differs from frameworks like CrewAI and AutoGen in several ways:
1. LangGraph is graph-based, making control flow explicit and debuggable.
2. LangGraph's checkpointing enables persistence and human-in-the-loop.
3. LangGraph is lower-level than CrewAI, requiring more boilerplate but offering more flexibility.
4. LangGraph is more state-oriented than AutoGen, which is primarily conversational.

## Use Cases

LangGraph is well-suited for:
- Multi-agent research assistants
- Customer support agents with complex routing
- Code generation and review pipelines
- Document processing workflows
- Any application requiring cycles, state, and coordination`,
  },
];
