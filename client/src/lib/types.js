import { z } from "zod";
// --- Query Complexity Enum ---
export const QueryTypeEnum = z.enum([
    "simple_fact",
    "definition",
    "explanation",
    "summarization",
    "comparison",
    "multi_part",
    "multi_hop",
    "analytical",
    "contradictory",
    "unanswerable",
    "unknown",
]);
// --- Subquery & Decomposition ---
export const SubquerySchema = z.object({
    id: z.string(),
    query: z.string(),
    purpose: z.string(),
});
export const QueryDecompositionSchema = z.object({
    originalQuery: z.string(),
    subqueries: z.array(SubquerySchema).max(3),
});
// --- Retrieval Plan ---
export const RetrievalPlanSchema = z.object({
    queryType: QueryTypeEnum.catch("unknown"),
    searchStrategy: z.enum(["lexical", "semantic", "hybrid"]).catch("hybrid"),
    initialTopK: z.number().int().min(2).max(12).catch(5),
    maxTopK: z.number().int().min(2).max(12).catch(8),
    rewriteRequired: z.boolean().catch(false),
    decompositionRequired: z.boolean().catch(false),
    parentExpansionRequired: z.boolean().catch(false),
    rerankingRequired: z.boolean().catch(true),
    citationRequired: z.boolean().catch(true),
    maxSubqueries: z.number().int().min(1).max(3).catch(3),
    reasoning: z.string().catch(""),
    confidence: z.number().min(0).max(1).catch(0.8),
});
// --- Router Output ---
export const RouterOutputSchema = z.object({
    queryType: z.string().catch("factual"),
    rewrittenQuery: z.string().catch(""),
    intentSummary: z.string().catch(""),
    needsRetrieval: z.boolean().catch(true),
    filters: z
        .object({
        pageNumber: z.number().nullish().transform((v) => v ?? undefined),
        chapter: z.string().nullish().transform((v) => v ?? undefined),
        section: z.string().nullish().transform((v) => v ?? undefined),
        heading: z.string().nullish().transform((v) => v ?? undefined),
        documentTitle: z.string().nullish().transform((v) => v ?? undefined),
    })
        .optional(),
    plan: RetrievalPlanSchema.optional(),
    subqueries: z.array(SubquerySchema).optional(),
});
// --- Reranker Output ---
export const RerankerOutputSchema = z.object({
    reranked: z.array(z.object({
        chunkId: z.string(),
        documentTitle: z.string(),
        originalRank: z.number().int().min(1),
        newRank: z.number().int().min(1),
        lexicalScore: z.number(),
        llmScore: z.number().min(0).max(10),
        combinedScore: z.number(),
        rationale: z.string(),
    })),
    rejected: z
        .array(z.object({
        chunkId: z.string(),
        documentTitle: z.string(),
        lexicalScore: z.number(),
        llmScore: z.number(),
        combinedScore: z.number(),
        rationale: z.string(),
        reason: z.string(),
    }))
        .optional(),
});
export const AnswerabilityStatusEnum = z.enum([
    "fully_answerable",
    "partially_answerable",
    "not_answerable",
    "contradictory",
]);

export const safeArrayPreprocessing = (val) => {
    if (val === null || val === undefined) return [];
    if (Array.isArray(val)) {
        return val.map((item) => (item !== null && item !== undefined ? String(item).trim() : "")).filter(Boolean);
    }
    if (typeof val === "string") {
        const trimmed = val.trim();
        return trimmed ? [trimmed] : [];
    }
    if (typeof val === "object") {
        return Object.values(val).map((item) => (item !== null && item !== undefined ? String(item).trim() : "")).filter(Boolean);
    }
    return [String(val).trim()].filter(Boolean);
};

export const safeStringArraySchema = z.preprocess(
    safeArrayPreprocessing,
    z.array(z.string()).default([])
);

export const AnswerabilityResultSchema = z.object({
    status: AnswerabilityStatusEnum.catch("fully_answerable"),
    answerable: z.boolean().catch(true),
    confidence: z.number().min(0).max(1).catch(0.8),
    supportingChunkIds: safeStringArraySchema,
    missingInformation: safeStringArraySchema,
    conflictingChunkIds: safeStringArraySchema,
    reason: z.string().catch(""),
});
export const ClaimReviewSchema = z.object({
    claim: z.string(),
    status: z.enum(["supported", "partially_supported", "unsupported", "contradictory"]),
    supportingChunkIds: z.array(z.string()),
    explanation: z.string(),
});
export const CriticOutputSchema = z.object({
    verdict: z.enum(["faithful", "needs_revision"]),
    faithfulnessScore: z.number().min(0).max(100),
    issues: z.array(z.string()),
    revisionNotes: z.string().optional(),
    claims: z.array(ClaimReviewSchema).optional(),
    contradictionsDetected: z.boolean().optional(),
});
export const ARCHETYPE_DISPLAY_MAP = {
    simple_fact: {
        key: "simple_fact",
        label: "Simple Fact",
        badgeVariant: "secondary",
        description: "Single specific factual lookup (parameter count, date, benchmark)",
    },
    definition: {
        key: "definition",
        label: "Definition",
        badgeVariant: "secondary",
        description: "Concept or terminology definition",
    },
    explanation: {
        key: "explanation",
        label: "Explanation",
        badgeVariant: "secondary",
        description: "Detailed mechanism or architectural explanation",
    },
    summarization: {
        key: "summarization",
        label: "Summarization",
        badgeVariant: "secondary",
        description: "High-level overview across a document or section",
    },
    comparison: {
        key: "comparison",
        label: "Comparison",
        badgeVariant: "outline",
        description: "Contrasting two or more models, methods, or systems",
    },
    multi_hop: {
        key: "multi_hop",
        label: "Multi-Hop",
        badgeVariant: "outline",
        description: "Multi-step reasoning across multiple sections or papers",
    },
    multi_part: {
        key: "multi_part",
        label: "Multi-Part",
        badgeVariant: "outline",
        description: "Multiple distinct sub-questions in a single inquiry",
    },
    analytical: {
        key: "analytical",
        label: "Analytical",
        badgeVariant: "outline",
        description: "In-depth architectural analysis or evaluation",
    },
    contradictory: {
        key: "contradictory",
        label: "Contradictory",
        badgeVariant: "destructive",
        description: "Opposing claims detected across retrieved sources",
    },
    unanswerable: {
        key: "unanswerable",
        label: "Unanswerable",
        badgeVariant: "destructive",
        description: "Query outside the knowledge base domain",
    },
    unknown: {
        key: "unknown",
        label: "Exploratory",
        badgeVariant: "secondary",
        description: "Ambiguous query requiring broad exploratory search",
    },
};
export function getArchetypeMeta(rawType) {
    const normalized = (rawType || "unknown").toLowerCase();
    return (ARCHETYPE_DISPLAY_MAP[normalized] || {
        key: normalized,
        label: rawType || "Unknown",
        badgeVariant: "secondary",
        description: "Heuristically classified query type",
    });
}
export function classifyConfidence(score) {
    if (typeof score !== "number" || isNaN(score) || !isFinite(score)) {
        return {
            score: 0,
            percentage: 0,
            tier: "Low",
            colorClass: "text-slate-600",
            bgClass: "bg-slate-100",
            borderClass: "border-slate-200",
            matchLabel: "No Retrieval Alignment",
            metricLabel: "No Retrieval Alignment",
            disclaimer: "No matching evidence chunks retrieved from the knowledge base. This is an Alignment Score, not a probability of correctness unless empirically calibrated.",
        };
    }
    const boundedScore = Math.max(0, Math.min(1, score));
    const percentage = Math.round(boundedScore * 100);
    if (boundedScore >= 0.7) {
        return {
            score: boundedScore,
            percentage,
            tier: "High",
            colorClass: "text-emerald-700",
            bgClass: "bg-emerald-50",
            borderClass: "border-emerald-200",
            matchLabel: "High Alignment Score",
            metricLabel: "High Alignment Score",
            disclaimer: "Retrieved document chunks demonstrate strong lexical and semantic overlap with the query. This value is an Alignment Score, not a probability of correctness.",
        };
    }
    if (boundedScore >= 0.4) {
        return {
            score: boundedScore,
            percentage,
            tier: "Moderate",
            colorClass: "text-amber-700",
            bgClass: "bg-amber-50",
            borderClass: "border-amber-200",
            matchLabel: "Moderate Alignment Score",
            metricLabel: "Moderate Alignment Score",
            disclaimer: "Retrieved document chunks demonstrate partial semantic alignment with the query. This value is an Alignment Score, not a probability of correctness.",
        };
    }
    return {
        score: boundedScore,
        percentage,
        tier: "Low",
        colorClass: "text-rose-700",
        bgClass: "bg-rose-50",
        borderClass: "border-rose-200",
        matchLabel: "Limited Alignment Score",
        metricLabel: "Limited Alignment Score",
        disclaimer: "Retrieved document chunks have limited lexical overlap. This value is an Alignment Score, not a probability of correctness unless empirically calibrated.",
    };
}
// --- Zod Runtime Validation for SSE Messages ---
export const SSEEventSchema = z.discriminatedUnion("type", [
    z.object({ type: z.literal("connected"), timestamp: z.any().optional() }),
    z.object({ type: z.literal("agent_start"), agent: z.string(), label: z.string() }),
    z.object({ type: z.literal("agent_finish"), step: z.any() }),
    z.object({ type: z.literal("agent_error"), step: z.any() }),
    z.object({ type: z.literal("document_target"), target: z.any() }),
    z.object({ type: z.literal("retrieval_scope"), scope: z.string(), documentId: z.string().nullish(), filename: z.string().nullish() }),
    z.object({ type: z.literal("sources"), sources: z.array(z.any()) }),
    z.object({ type: z.literal("retrieval_started"), queries: z.array(z.any()).optional() }),
    z.object({ type: z.literal("retrieval_completed"), count: z.number().optional() }),
    z.object({ type: z.literal("reranking_skipped"), reason: z.string().optional() }),
    z.object({ type: z.literal("token"), content: z.string() }),
    z.object({ type: z.literal("pipeline_complete"), result: z.any() }),
    z.object({ type: z.literal("pipeline_error"), error: z.any() }),
    z.object({ type: z.literal("retrieval_plan"), plan: z.any() }),
    z.object({ type: z.literal("query_decomposed"), subqueries: z.array(z.any()) }),
    z.object({
        type: z.literal("retrieval_expanded"),
        round: z.number(),
        previousTopK: z.number(),
        newTopK: z.number(),
        reason: z.string(),
    }),
    z.object({ type: z.literal("retrieval_confidence"), confidence: z.any() }),
    z.object({ type: z.literal("answerability_result"), answerability: z.any() }),
    z.object({ type: z.literal("claim_review"), claims: z.array(z.any()) }),
    z.object({ type: z.literal("summary_started"), documentId: z.any().optional(), documentTitle: z.any().optional(), pageCount: z.any().optional(), cached: z.any().optional() }),
    z.object({ type: z.literal("extraction_progress"), loadedPages: z.any().optional(), totalPages: z.any().optional(), cached: z.any().optional() }),
    z.object({ type: z.literal("batch_progress"), batchIndex: z.any().optional(), totalBatches: z.any().optional(), pageRange: z.any().optional(), cached: z.any().optional() }),
    z.object({ type: z.literal("combining_started"), totalBatches: z.any().optional() }),
    z.object({ type: z.literal("final_answer_started"), cached: z.any().optional() }),
]);
export function safeParseSSEEvent(rawLine) {
    if (!rawLine.startsWith("data: "))
        return null;
    const jsonStr = rawLine.slice(6).trim();
    if (!jsonStr)
        return null;
    try {
        const rawObj = JSON.parse(jsonStr);
        const parsed = SSEEventSchema.safeParse(rawObj);
        if (parsed.success) {
            return parsed.data;
        }
        if (rawObj && typeof rawObj === "object" && "type" in rawObj) {
            return rawObj;
        }
        return null;
    }
    catch {
        return null;
    }
}
// --- Sample Prompts ---
export const SAMPLE_PROMPTS = [
    "How does attention work in transformers?",
    "Compare BERT and GPT-3 in terms of architecture and use cases.",
    "What are the advantages of RAG over fine-tuning?",
    "Explain the ReAct pattern and when it outperforms chain-of-thought.",
    "How does Constitutional AI differ from RLHF?",
    "What is LangGraph and when would you use it?",
];
