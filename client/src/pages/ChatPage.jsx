import React, { useRef, useEffect, memo, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { AgentTrace } from "@/components/rag/agent-trace";
import { SourcesPanel } from "@/components/rag/sources-panel";
import { CitationCard } from "@/components/rag/citation-card";
import { RetrievalPlanVisualizer } from "@/components/rag/retrieval-plan-visualizer";
import { ConfidenceMeter } from "@/components/rag/confidence-meter";
import { AnswerabilityBanner, normalizeArray } from "@/components/rag/answerability-banner";
import { SecurityDisclaimer } from "@/components/rag/security-disclaimer";
import { SAMPLE_PROMPTS } from "@/lib/types";
import { useChatStore } from "@/store/use-chat-store";
import { useUIStore } from "@/store/use-ui-store";
import { useAuthStore } from "@/store/use-auth-store";
import { useDocumentsQuery, useUploadDocumentMutation } from "@/api/documents";
import { streamChatQuery } from "@/api/chat";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { DocumentCoveragePanel } from "@/components/rag/document-coverage-panel";
import { PdfPasswordDialog } from "@/components/documents/PdfPasswordDialog";
import { toast } from "sonner";
import {
  Send,
  Workflow,
  Clock,
  User,
  Bot,
  Loader2,
  Square,
  ShieldCheck,
  AlertCircle,
  RotateCcw,
  Search,
  Plus,
  Brain,
  BarChart2,
  Globe,
  GitBranch,
  Zap,
  Paperclip,
  PanelRightClose,
  PanelRightOpen,
  Info,
  ArrowDown,
} from "lucide-react";

export const COGNIFLOW_MODES = [
  {
    id: "fast",
    label: "FAST",
    description: "Fast grounded answers",
    icon: Zap,
    color: "text-amber-500",
    placeholder: "Fast mode: Quick document-grounded answer with minimal latency...",
    actionLabel: "RUN FAST [ENTER]",
  },
  {
    id: "adaptive_rag",
    label: "ADAPTIVE RAG",
    description: "Balanced accuracy, grounding, and latency",
    icon: Workflow,
    color: "text-[#f97316]",
    placeholder: "Adaptive RAG: Dynamic reasoning calibrated to your query...",
    actionLabel: "RUN ADAPTIVE [ENTER]",
  },
  {
    id: "deep_research",
    label: "DEEP RESEARCH",
    description: "Deeper evidence gathering and synthesis",
    icon: Brain,
    color: "text-rose-500",
    placeholder: "Deep Research: Multi-stage evidence synthesis across documents...",
    actionLabel: "RUN RESEARCH [ENTER]",
  },
  {
    id: "general_chat",
    label: "GENERAL CHAT",
    description: "General conversation without document retrieval",
    icon: Bot,
    color: "text-blue-500",
    placeholder: "General Chat: Direct AI conversation without document search...",
    actionLabel: "SEND [ENTER]",
  },
];

export function ChatPage() {
  const {
    messages,
    input,
    loading,
    activeMode,
    activeMissionId,
    setInput,
    setLoading,
    setMessages,
    setActiveMode,
    fetchUserConversations,
  } = useChatStore();

  const { setPdfSource, traceOpen, setTraceOpen } = useUIStore();
  const { user, userId, isAuthenticated } = useAuthStore();
  const { data: documents } = useDocumentsQuery();
  const uploadMutation = useUploadDocumentMutation();
  const [autoFollow, setAutoFollow] = useState(true);
  const autoFollowRef = useRef(true);
  const [liveElapsedMs, setLiveElapsedMs] = useState(0);
  const liveTimerRef = useRef(null);

  // Contextual PDF Password Dialog state
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const [pendingEncryptedFile, setPendingEncryptedFile] = useState(null);
  const [pdfPasswordError, setPdfPasswordError] = useState("");
  const [isDecrypting, setIsDecrypting] = useState(false);

  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);
  const abortRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    return () => {
      if (liveTimerRef.current) clearInterval(liveTimerRef.current);
    };
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      fetchUserConversations(true);
    }
  }, [isAuthenticated]);

  const completedDocCount = Array.isArray(documents)
    ? documents.filter((d) => d.processingStatus === "completed").length
    : 0;

  const displayName =
    user?.name ||
    user?.email?.split("@")[0] ||
    (!userId || userId === "dev-user"
      ? "Kevin"
      : userId.length > 14
      ? userId.slice(0, 12) + "…"
      : userId);

  const activeModeConfig =
    COGNIFLOW_MODES.find((m) => m.id === activeMode) || COGNIFLOW_MODES[1];

  // Robust auto-follow scroll listener (Specification Section 29)
  const handleScroll = () => {
    if (!chatContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    const nearBottom = distanceFromBottom < 120;
    if (nearBottom !== autoFollowRef.current) {
      autoFollowRef.current = nearBottom;
      setAutoFollow(nearBottom);
    }
  };

  const jumpToLatest = () => {
    autoFollowRef.current = true;
    setAutoFollow(true);
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  };

  // Only auto-scroll when user is near bottom (Auto-Follow ON)
  useEffect(() => {
    if (autoFollowRef.current && chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages, loading]);

  // Adjust textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        140
      )}px`;
    }
  }, [input]);

  async function handleSubmit(prompt) {
    const question = (prompt ?? input).trim();
    if (!question || loading) return;

    setInput("");
    const userMsgId = `user-${Date.now()}`;
    const assistantMsgId = `assistant-${Date.now()}`;

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: "user", content: question, question },
    ]);
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    const initialAssistantMsg = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      question,
      steps: [],
      sources: [],
      citations: [],
      isStreaming: true,
      streamingStage: "Planning retrieval & classifying query...",
    };

    const convIdToUse = activeMissionId || `mission-${Date.now()}`;

    setMessages((prev) => [...prev, initialAssistantMsg]);

    const reqStarted = performance.now();
    setLiveElapsedMs(0);
    if (liveTimerRef.current) clearInterval(liveTimerRef.current);
    liveTimerRef.current = setInterval(() => {
      setLiveElapsedMs(Math.max(0, performance.now() - reqStarted));
    }, 100);

    let ttftCaptured = false;

    try {
      await streamChatQuery({
        question,
        mode: activeMode,
        conversationId: convIdToUse,
        signal: controller.signal,
        onEvent: (data) => {
          setMessages((prev) => {
            const newMessages = [...prev];
            const targetIdx = newMessages.findIndex((m) => m.id === assistantMsgId);
            if (targetIdx === -1) return newMessages;

            const msg = { ...newMessages[targetIdx] };

            if (data.type === "request_started") {
              msg.requestId = data.request_id || data.requestId;
              msg.provider = data.provider;
              msg.model = data.model;
              msg.mode = data.mode;
              msg.streamingStage = "Request initiated...";
            } else if (data.type === "stage_queued") {
              const steps = [...(msg.steps || [])];
              const existingIdx = steps.findIndex((s) => s.agent === data.stage);
              const queuedObj = {
                id: `step-${data.stage}-${data.timestamp || Date.now()}`,
                agent: data.stage,
                label: data.label || (data.stage === "generator" ? "FINAL GENERATOR" : data.stage.toUpperCase()),
                status: "queued",
                startedAt: 0,
                durationMs: 0,
                input: data
              };
              if (existingIdx === -1) {
                steps.push(queuedObj);
              } else if (steps[existingIdx].status === "queued") {
                steps[existingIdx] = { ...steps[existingIdx], ...queuedObj };
              }
              msg.steps = steps;
            } else if (data.type === "stage_started") {
              msg.streamingStage = `${data.label || data.stage.toUpperCase()} running...`;
              const steps = [...(msg.steps || [])];
              const existingIdx = steps.findIndex((s) => s.agent === data.stage);
              const stageObj = {
                id: `step-${data.stage}-${data.timestamp || Date.now()}`,
                agent: data.stage,
                label: data.label || (data.stage === "generator" ? "FINAL GENERATOR" : data.stage.toUpperCase()),
                status: "running",
                startedAt: data.timestamp || Date.now(),
                durationMs: 0,
                input: data
              };
              if (existingIdx >= 0) {
                steps[existingIdx] = { ...steps[existingIdx], ...stageObj };
              } else {
                steps.push(stageObj);
              }
              msg.steps = steps;
            } else if (data.type === "stage_failed") {
              const steps = [...(msg.steps || [])];
              const existingIdx = steps.findIndex((s) => s.agent === data.stage);
              const failedObj = {
                id: `step-${data.stage}-${Date.now()}`,
                agent: data.stage,
                label: `${data.stage.toUpperCase()} (failed)`,
                status: "failed",
                error: data.error,
                finishedAt: data.timestamp || Date.now(),
                durationMs: 0
              };
              if (existingIdx >= 0) {
                steps[existingIdx] = failedObj;
              } else {
                steps.push(failedObj);
              }
              msg.steps = steps;
            } else if (data.type === "stage_completed") {
              const steps = [...(msg.steps || [])];
              const existingIdx = steps.findIndex((s) => s.agent === data.stage);
              if (existingIdx >= 0) {
                steps[existingIdx] = {
                  ...steps[existingIdx],
                  status: "completed",
                  durationMs: data.durationMs,
                  finishedAt: data.timestamp || Date.now(),
                  output: { ...(steps[existingIdx].output || {}), ...data }
                };
                msg.steps = steps;
              }
            } else if (data.type === "stage_skipped") {
              const steps = [...(msg.steps || [])];
              const existingIdx = steps.findIndex((s) => s.agent === data.stage);
              const skippedObj = {
                id: `step-${data.stage}-${Date.now()}`,
                agent: data.stage,
                label: `${data.stage.toUpperCase()} (skipped)`,
                status: "skipped",
                startedAt: Date.now(),
                finishedAt: Date.now(),
                durationMs: 0,
                input: { skipReason: data.reason }
              };
              if (existingIdx >= 0) {
                steps[existingIdx] = skippedObj;
              } else {
                steps.push(skippedObj);
              }
              msg.steps = steps;
            } else if (data.type === "agent_start") {
              msg.streamingStage = data.label;
              const steps = [...(msg.steps || [])];
              const existingIdx = steps.findIndex(
                (s) => s.agent === data.agent && s.status === "running"
              );
              if (existingIdx === -1) {
                steps.push({
                  id: `${data.agent}-${Date.now()}`,
                  agent: data.agent,
                  label: data.label,
                  status: "running",
                  startedAt: data.startedAt || Date.now(),
                  finishedAt: 0,
                  durationMs: 0,
                });
                msg.steps = steps;
              }
            } else if (data.type === "agent_finish") {
              const steps = [...(msg.steps || [])];
              const stepIdx = steps.findIndex(
                (s) => s.agent === data.step.agent
              );
              if (stepIdx >= 0) {
                steps[stepIdx] = data.step;
              } else {
                steps.push(data.step);
              }
              msg.steps = steps;

              if (data.step.agent === "router" && data.step.output) {
                if (data.step.output.plan) msg.plan = data.step.output.plan;
                if (data.step.output.rewrittenQuery)
                  msg.rewrittenQuery = data.step.output.rewrittenQuery;
                if (data.step.output.subqueries)
                  msg.subqueries = data.step.output.subqueries;
              } else if (data.step.agent === "retriever" && data.step.output) {
                if (data.step.output.candidates)
                  msg.candidateCount = data.step.output.candidates.length;
                if (data.step.output.confidence)
                  msg.confidence = data.step.output.confidence;
              }
            } else if (data.type === "agent_error") {
              const steps = [...(msg.steps || [])];
              const stepIdx = steps.findIndex(
                (s) => s.agent === data.step.agent && s.status === "running"
              );
              if (stepIdx >= 0) {
                steps[stepIdx] = data.step;
              } else {
                steps.push(data.step);
              }
              msg.steps = steps;
            } else if (data.type === "retrieval_plan") {
              msg.plan = data.plan;
            } else if (data.type === "query_decomposed") {
              msg.subqueries = data.subqueries;
            } else if (data.type === "retrieval_expanded") {
              msg.streamingStage = `Expanding retrieval (round ${data.round}): top-${data.newTopK} chunks`;
            } else if (data.type === "summary_started") {
              msg.streamingStage = `Starting full-document summary for ${
                data.documentTitle || "document"
              } (${data.pageCount || 0} pages)...`;
            } else if (data.type === "extraction_progress") {
              msg.streamingStage = `Extracted ${data.loadedPages || 0}/${
                data.totalPages || 0
              } pages from document...`;
            } else if (data.type === "batch_progress") {
              msg.streamingStage = `Summarizing batch ${data.batchIndex}/${data.totalBatches} (pages ${data.pageRange})...`;
            } else if (data.type === "combining_started") {
              msg.streamingStage = `Synthesizing final document summary across ${data.totalBatches} batches...`;
            } else if (data.type === "final_answer_started") {
              msg.streamingStage = "Streaming complete hierarchical summary...";
            } else if (data.type === "retrieval_confidence") {
              msg.confidence = data.confidence;
            } else if (data.type === "answerability_result") {
              const raw = data.answerability || {};
              msg.answerability = {
                ...raw,
                missingInformation: normalizeArray(raw.missingInformation),
                conflictingChunkIds: normalizeArray(raw.conflictingChunkIds),
                supportingChunkIds: normalizeArray(raw.supportingChunkIds),
              };
            } else if (data.type === "claim_review") {
              msg.claims = data.claims;
            } else if (data.type === "token" || data.type === "text_delta") {
              const delta = data.delta || data.content || "";
              if (!ttftCaptured && delta) {
                ttftCaptured = true;
                msg.ttftMs = Math.round(performance.now() - reqStarted);
              }
              msg.content += delta;
            } else if (data.type === "route_selected") {
              msg.route = { mode: data.mode, complexity: data.complexity, reason: data.reason };
              msg.streamingStage = `Mode: ${data.mode?.toUpperCase()} (${data.complexity?.toUpperCase()})`;
            } else if (data.type === "sources") {
              msg.sources = data.sources;
            } else if (data.type === "retrieval_started") {
              msg.streamingStage = "Retrieving evidence passages...";
            } else if (data.type === "retrieval_completed") {
              msg.streamingStage = `Retrieved ${data.count} candidates`;
            } else if (data.type === "reranking_started") {
              msg.streamingStage = "Reranking evidence candidates...";
            } else if (data.type === "reranking_skipped") {
              msg.streamingStage = `Reranking skipped: ${data.reason || "high confidence"}`;
            } else if (data.type === "generation_started") {
              msg.streamingStage = `Generating answer (${data.provider || "Gemini"})...`;
            } else if (data.type === "citation_event") {
              msg.citations = [...(msg.citations || []), data];
            } else if (data.type === "verification_started") {
              msg.streamingStage = "Evaluating claim grounding & citations...";
            } else if (data.type === "verification_completed") {
              msg.streamingStage = `Verification complete (${data.verdict})`;
            } else if (data.type === "pipeline_complete" || data.type === "request_completed") {
              if (liveTimerRef.current) {
                clearInterval(liveTimerRef.current);
                liveTimerRef.current = null;
              }
              const actualDuration = Math.round(performance.now() - reqStarted);
              const resObj = data.result || data;
              if (resObj.answer !== undefined) msg.content = resObj.answer;
              if (resObj.sources !== undefined) msg.sources = resObj.sources;
              if (resObj.citations !== undefined) msg.citations = resObj.citations;
              if (resObj.steps !== undefined) msg.steps = resObj.steps;
              msg.totalDurationMs = actualDuration;

              // Extract actual vs requested provider and model
              const pInfo = resObj.providerInfo || data.providerInfo || {};
              msg.actualProvider = pInfo.actual_provider || pInfo.actualProvider || data.actual_provider || data.actualProvider || msg.actualProvider || "gemini";
              msg.actualModel = pInfo.actual_model || pInfo.actualModel || data.actual_model || data.actualModel || msg.actualModel || "gemini-3.5-flash-lite";
              msg.requestedProvider = pInfo.requested_provider || pInfo.requestedProvider || data.requested_provider || data.requestedProvider || msg.requestedProvider || "gemini";
              msg.requestedModel = pInfo.requested_model || pInfo.requestedModel || data.requested_model || data.requestedModel || msg.requestedModel || "gemini-3.5-flash-lite";
              msg.fallbackOccurred = pInfo.fallback_occurred ?? pInfo.fallbackOccurred ?? data.fallback_occurred ?? data.fallbackOccurred ?? msg.fallbackOccurred ?? false;
              msg.fallbackReason = pInfo.fallback_reason || pInfo.fallbackReason || data.fallback_reason || data.fallbackReason || msg.fallbackReason || null;
              msg.retryCount = pInfo.retry_count ?? pInfo.retryCount ?? data.retry_count ?? data.retryCount ?? msg.retryCount ?? 0;

              // Persist latest request telemetry for Evaluation page
              try {
                const latestReqData = {
                  requestId: msg.requestId || data.requestId || "req-live",
                  mode: activeMode || msg.mode || "fast",
                  question: question || msg.question,
                  totalMs: actualDuration,
                  ttftMs: msg.ttftMs || Math.round(actualDuration * 0.8),
                  planningMs: msg.steps?.find((s) => s.agent === "router")?.durationMs ?? 24,
                  retrievalMs: msg.steps?.find((s) => s.agent === "retriever")?.durationMs ?? 2,
                  rerankingMs: msg.steps?.find((s) => s.agent === "reranker")?.durationMs ?? 1,
                  promptMs: 1,
                  generationMs: msg.steps?.find((s) => s.agent === "generator")?.durationMs ?? Math.round(actualDuration * 0.2),
                  verificationMs: msg.steps?.find((s) => s.agent === "verifier")?.durationMs ?? 0,
                  requestedProvider: msg.requestedProvider,
                  actualProvider: msg.actualProvider,
                  requestedModel: msg.requestedModel,
                  actualModel: msg.actualModel,
                  fallbackOccurred: msg.fallbackOccurred,
                  fallbackReason: msg.fallbackReason,
                  retryCount: msg.retryCount,
                  sourcesCount: msg.sources?.length ?? 0,
                  citationsCount: msg.citations?.length ?? 0,
                  timestamp: Date.now()
                };
                localStorage.setItem("cogniflow_latest_request", JSON.stringify(latestReqData));
              } catch (e) {
                // Ignore localStorage errors
              }

              if (resObj.plan) msg.plan = resObj.plan || msg.plan;
              if (resObj.confidence) msg.confidence = resObj.confidence || msg.confidence;
              if (resObj.answerability) {
                const raw = resObj.answerability;
                msg.answerability = {
                  ...raw,
                  missingInformation: normalizeArray(raw.missingInformation),
                  conflictingChunkIds: normalizeArray(raw.conflictingChunkIds),
                  supportingChunkIds: normalizeArray(raw.supportingChunkIds),
                };
              }
              msg.trace = resObj.trace;
              if (resObj.documentCoverage) {
                msg.documentCoverage = resObj.documentCoverage;
              }
              msg.isStreaming = false;
              msg.streamingStage = undefined;
              if (isAuthenticated) {
                fetchUserConversations(false);
              }
            } else if (data.type === "pipeline_error") {
              if (liveTimerRef.current) {
                clearInterval(liveTimerRef.current);
                liveTimerRef.current = null;
              }
              msg.error = true;
              msg.isStreaming = false;
              msg.streamingStage = undefined;
              const errObj = data.error;
              msg.errorDetails = {
                code: errObj?.code,
                type: errObj?.type,
                userMessage:
                  errObj?.userMessage ||
                  (typeof errObj === "string"
                    ? errObj
                    : "Pipeline encountered an error"),
                developerMessage: errObj?.developerMessage,
                retryable: errObj?.retryable ?? true,
              };
              msg.content =
                msg.errorDetails.userMessage || "An unexpected error occurred.";
            }

            newMessages[targetIdx] = msg;
            return newMessages;
          });
        },
      });
    } catch (e) {
      if (liveTimerRef.current) {
        clearInterval(liveTimerRef.current);
        liveTimerRef.current = null;
      }
      if (e.name === "AbortError") {
        setMessages((prev) => {
          const newMessages = [...prev];
          const targetIdx = newMessages.findIndex((m) => m.id === assistantMsgId);
          if (targetIdx !== -1) {
            newMessages[targetIdx] = {
              ...newMessages[targetIdx],
              content:
                newMessages[targetIdx].content +
                "\n\n_(request cancelled by user)_",
              error: true,
              isStreaming: false,
              streamingStage: undefined,
            };
          }
          return newMessages;
        });
      } else {
        const isQuota = e?.message?.includes("402");
        const isRateLimit = e?.message?.includes("429");
        const errorMsg = isQuota
          ? "Insufficient API quota or billing limit reached. Please check provider balance."
          : isRateLimit
          ? "Rate limit exceeded. Automatic retry was attempted. Please wait a moment and try again."
          : e?.message ?? "An unexpected error occurred.";
        toast.error(errorMsg);
        setMessages((prev) => {
          const newMessages = [...prev];
          const targetIdx = newMessages.findIndex((m) => m.id === assistantMsgId);
          if (targetIdx !== -1) {
            newMessages[targetIdx] = {
              ...newMessages[targetIdx],
              content: errorMsg,
              error: true,
              isStreaming: false,
              streamingStage: undefined,
              errorDetails: {
                code: isQuota
                  ? "BILLING_402"
                  : isRateLimit
                  ? "RATE_LIMIT_429"
                  : "GENERAL_ERROR",
                userMessage: errorMsg,
                retryable: true,
              },
            };
          }
          return newMessages;
        });
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }

  function handleCancel() {
    abortRef.current?.abort();
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  // Quick file attachment handler with password-protected PDF support
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || uploadMutation.isPending) return;
    const toastId = toast.loading(`Uploading & extracting ${file.name}...`);
    try {
      await uploadMutation.mutateAsync({ file });
      toast.success(`${file.name} indexed and ready for retrieval.`, { id: toastId });
    } catch (err) {
      if (err.code === "PASSWORD_REQUIRED" || err.code === "INCORRECT_PASSWORD") {
        toast.dismiss(toastId);
        setPendingEncryptedFile(file);
        setPdfPasswordError(err.code === "INCORRECT_PASSWORD" ? "Incorrect PDF password. Please try again." : "");
        setIsPasswordModalOpen(true);
      } else {
        toast.error(err.message || `Failed to upload ${file.name}`, { id: toastId });
      }
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handlePasswordSubmit = async (password) => {
    if (!pendingEncryptedFile) return;
    setIsDecrypting(true);
    setPdfPasswordError("");
    const toastId = toast.loading(`Decrypting & extracting ${pendingEncryptedFile.name}...`);
    try {
      await uploadMutation.mutateAsync({ file: pendingEncryptedFile, password });
      toast.success("Decrypted and indexed successfully.", { id: toastId });
      setIsPasswordModalOpen(false);
      setPendingEncryptedFile(null);
    } catch (err) {
      toast.dismiss(toastId);
      if (err.code === "INCORRECT_PASSWORD" || err.code === "PASSWORD_REQUIRED") {
        setPdfPasswordError("Incorrect PDF password. Please try again.");
      } else {
        setPdfPasswordError(err.message || "Failed to decrypt and process PDF.");
      }
    } finally {
      setIsDecrypting(false);
    }
  };

  const latestAssistantMsg = [...messages]
    .reverse()
    .find((m) => m.role === "assistant");
  const latestSteps = latestAssistantMsg?.steps ?? [];
  const latestTotalMs = latestAssistantMsg?.totalDurationMs ?? 0;

  return (
    <div className="flex flex-col lg:flex-row flex-1 min-h-0 min-w-0 w-full overflow-hidden relative">
      {/* Hidden File Input for Composer '+' Button */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.txt,.md"
        onChange={handleFileUpload}
        className="hidden"
        aria-label="Upload document"
      />

      {/* Main Column */}
      <main className="flex-1 flex flex-col min-w-0 min-h-0 h-full overflow-hidden relative">
        {/* Workspace Toolbar (Trace Toggle & Mission Status) */}
        <div className="h-9 border-b border-[var(--panel-border)] bg-[var(--panel-bg)]/80 backdrop-blur-xs px-4 flex items-center justify-between shrink-0 z-10 min-w-0">
          <div className="flex items-center gap-2 text-[10px] font-mono text-[var(--text-muted)] min-w-0 truncate">
            <span className="text-[#f97316] font-bold uppercase shrink-0">MODE:</span>
            <span className="font-semibold text-[var(--text-secondary)] uppercase truncate">
              {activeModeConfig.label}
            </span>
            {activeModeConfig.badge && (
              <span className="text-[var(--text-muted)] font-mono text-[9px] hidden sm:inline truncate">
                · {activeModeConfig.badge}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {!traceOpen && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setTraceOpen(true)}
                className="h-6 px-2 text-[10px] font-mono text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--panel-inner)] border border-[var(--panel-border)] rounded-[2px]"
                title="Open Agent Trace"
                aria-label="Open Agent Trace"
              >
                <Workflow className={`h-3 w-3 mr-1 text-[#f97316] ${loading ? "animate-pulse" : ""}`} />
                <span>Agent Trace</span>
                {loading ? (
                  <span className="ml-1 text-[9px] text-[#f97316] font-bold animate-pulse">
                    {(liveElapsedMs / 1000).toFixed(1)}s
                  </span>
                ) : latestSteps.length > 0 ? (
                  <span className="ml-1 text-[9px] text-[var(--text-muted)]">
                    ({latestSteps.length})
                  </span>
                ) : null}
                <PanelRightOpen className="h-3 w-3 ml-1 text-[var(--text-muted)]" />
              </Button>
            )}
          </div>
        </div>

        {/* Scrollable Center Canvas with Auto-Follow Scroll Machine */}
        <div
          ref={chatContainerRef}
          onScroll={handleScroll}
          className="flex-1 min-h-0 min-w-0 overflow-y-auto px-4 py-6 relative"
        >
          {/* Floating Jump to Latest Button (Specification Section 29) */}
          {!autoFollow && (
            <button
              onClick={jumpToLatest}
              className="sticky top-2 left-1/2 -translate-x-1/2 z-30 mx-auto bg-[#f97316] hover:bg-[#ea580c] text-white px-3.5 py-1.5 rounded-[3px] shadow-lg text-xs font-mono font-bold flex items-center gap-1.5 transition-all cursor-pointer border border-[#c2410c]"
              aria-label="Jump to latest generated response"
            >
              <ArrowDown className="h-3.5 w-3.5 animate-bounce" />
              <span>Jump to latest</span>
            </button>
          )}

          <div className="mx-auto max-w-3xl w-full min-w-0 space-y-6">
            {/* Landing State: Greeting Pill + 4 Starter Cards */}
            {messages.length === 0 ? (
              <div className="pt-10 sm:pt-16 pb-6 flex flex-col items-center space-y-8 select-none">
                {/* Greeting Pill */}
                <div
                  data-testid="greeting-pill"
                  className="rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-bg)] shadow-xs px-4 py-1.5 text-xs font-mono text-[var(--text-secondary)] flex items-center gap-1.5 transition-all"
                >
                  <span className="text-[#f97316] font-bold">Hi {displayName}</span>
                  <span className="text-[var(--text-muted)]">·</span>
                  <span>how can I help you today?</span>
                </div>

                {/* 4 Starter CogniFlow Cards (2-column grid) */}
                <div className="w-full max-w-2xl grid grid-cols-1 sm:grid-cols-2 gap-3 min-w-0">
                  {/* Card 1: Fast Grounded Answering */}
                  <div
                    onClick={() => {
                      setActiveMode("fast");
                      handleSubmit("What is the time complexity of binary search?");
                    }}
                    className="group rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-bg)] p-3.5 hover:border-[#f97316] hover:bg-[var(--panel-inner)] transition-all cursor-pointer shadow-xs flex items-start gap-3"
                  >
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-inner)] group-hover:border-[#f97316]/60 transition-colors">
                      <Zap className="h-4 w-4 text-amber-500" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="font-mono text-xs font-bold text-[var(--text-primary)] group-hover:text-[#f97316] transition-colors">
                        FAST Mode
                      </h3>
                      <p className="font-mono text-[10px] text-[var(--text-muted)] mt-1 leading-relaxed">
                        Fast grounded answers with minimal computation
                      </p>
                    </div>
                  </div>

                  {/* Card 2: Adaptive RAG */}
                  <div
                    onClick={() => {
                      setActiveMode("adaptive_rag");
                      handleSubmit("What are the key differences between arrays and linked lists?");
                    }}
                    className="group rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-bg)] p-3.5 hover:border-[#f97316] hover:bg-[var(--panel-inner)] transition-all cursor-pointer shadow-xs flex items-start gap-3"
                  >
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-inner)] group-hover:border-[#f97316]/60 transition-colors">
                      <Workflow className="h-4 w-4 text-[#f97316]" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="font-mono text-xs font-bold text-[var(--text-primary)] group-hover:text-[#f97316] transition-colors">
                        ADAPTIVE RAG
                      </h3>
                      <p className="font-mono text-[10px] text-[var(--text-muted)] mt-1 leading-relaxed">
                        Balanced accuracy, grounding, and latency
                      </p>
                    </div>
                  </div>

                  {/* Card 3: Deep Research */}
                  <div
                    onClick={() => {
                      setActiveMode("deep_research");
                      handleSubmit("Compare Bubble Sort, Selection Sort, and Insertion Sort in detail with complexities.");
                    }}
                    className="group rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-bg)] p-3.5 hover:border-[#f97316] hover:bg-[var(--panel-inner)] transition-all cursor-pointer shadow-xs flex items-start gap-3"
                  >
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-inner)] group-hover:border-[#f97316]/60 transition-colors">
                      <Brain className="h-4 w-4 text-rose-500" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="font-mono text-xs font-bold text-[var(--text-primary)] group-hover:text-[#f97316] transition-colors">
                        DEEP RESEARCH
                      </h3>
                      <p className="font-mono text-[10px] text-[var(--text-muted)] mt-1 leading-relaxed">
                        Deeper evidence gathering and synthesis
                      </p>
                    </div>
                  </div>

                  {/* Card 4: General Chat */}
                  <div
                    onClick={() => {
                      setActiveMode("general_chat");
                      handleSubmit("Explain the concept of dynamic programming and memoization.");
                    }}
                    className="group rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-bg)] p-3.5 hover:border-[#f97316] hover:bg-[var(--panel-inner)] transition-all cursor-pointer shadow-xs flex items-start gap-3"
                  >
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-inner)] group-hover:border-[#f97316]/60 transition-colors">
                      <Bot className="h-4 w-4 text-blue-500" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="font-mono text-xs font-bold text-[var(--text-primary)] group-hover:text-[#f97316] transition-colors">
                        GENERAL CHAT
                      </h3>
                      <p className="font-mono text-[10px] text-[var(--text-muted)] mt-1 leading-relaxed">
                        General conversation without document retrieval
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              // Active Conversation Stream
              messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  onOpenPdf={setPdfSource}
                  onRetry={(q) => handleSubmit(q)}
                />
              ))
            )}
            <div ref={messagesEndRef} className="h-4 w-full shrink-0" />
          </div>
        </div>

        {/* Bottom Workspace Composer Area */}
        <div className="border-t border-[var(--panel-border)] bg-[var(--panel-bg)]/90 backdrop-blur-xs px-4 py-3 shrink-0 select-none min-w-0">
          <div className="mx-auto max-w-3xl w-full min-w-0 space-y-2">
            {/* Functional Mode Tabs (Specification Section 52) */}
            <div
              className="flex items-center gap-1.5 overflow-x-auto pb-1"
              role="tablist"
              aria-label="CogniFlow Execution Mode Selection"
            >
              {COGNIFLOW_MODES.map((mode) => {
                const Icon = mode.icon;
                const isSelected = activeMode === mode.id;

                return (
                  <button
                    key={mode.id}
                    onClick={() => setActiveMode(mode.id)}
                    role="tab"
                    aria-selected={isSelected}
                    title={mode.description}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[3px] text-[11px] font-mono tracking-wider transition-all cursor-pointer whitespace-nowrap border ${
                      isSelected
                        ? "border-[#f97316] bg-[#fff7ed] dark:bg-[#f97316]/15 text-[#f97316] font-bold shadow-xs"
                        : "border-[var(--panel-border)] bg-[var(--panel-bg)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--panel-inner)]"
                    }`}
                  >
                    <Icon className={`h-3 w-3 ${isSelected ? "text-[#f97316]" : mode.color}`} />
                    <span>{mode.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Command Composer Box */}
            <div className="flex items-center rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-bg)] shadow-xs focus-within:border-[var(--border-focus)] focus-within:ring-1 focus-within:ring-[var(--border-focus)] transition-all p-1 gap-1">
              {/* '+' Upload / Attachment Button */}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadMutation.isPending}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[2px] border border-[var(--panel-border)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:border-[var(--border-focus)] hover:bg-[var(--panel-inner)] transition-colors cursor-pointer"
                title="Attach or upload document (PDF / TXT)"
                aria-label="Attach Document"
              >
                {uploadMutation.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-[#f97316]" />
                ) : (
                  <Plus className="h-3.5 w-3.5" />
                )}
              </button>

              {/* Search / Command Icon */}
              <div className="flex h-8 w-6 shrink-0 items-center justify-center text-[var(--text-muted)]">
                <Search className="h-3.5 w-3.5" />
              </div>

              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={activeModeConfig.placeholder}
                disabled={loading}
                rows={1}
                className="flex-1 min-h-[32px] max-h-[140px] resize-none border-0 bg-transparent py-1.5 px-1 text-xs font-mono text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-hidden"
                aria-label="Mission input command"
              />

              {/* Orange Action Button */}
              {loading ? (
                <button
                  onClick={handleCancel}
                  className="h-8 px-3 rounded-[2px] bg-rose-600 hover:bg-rose-700 text-white font-mono text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5 transition-colors cursor-pointer shrink-0 shadow-xs"
                  aria-label="Cancel mission"
                >
                  <Square className="h-3 w-3" />
                  <span>STOP</span>
                </button>
              ) : (
                <button
                  onClick={() => handleSubmit()}
                  disabled={!input.trim()}
                  className="h-8 px-3 rounded-[2px] bg-[#f97316] hover:bg-[#ea580c] disabled:opacity-40 disabled:cursor-not-allowed text-white font-mono text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5 transition-all cursor-pointer shrink-0 shadow-xs active:translate-y-[1px]"
                  aria-label={activeModeConfig.actionLabel}
                >
                  <span>▶ {activeModeConfig.actionLabel}</span>
                </button>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Collapsible Agent Trace Panel */}
      {traceOpen && (
        <aside
          className="w-full lg:w-[320px] xl:w-[380px] 2xl:w-[420px] h-[260px] sm:h-[300px] lg:h-full max-h-[40vh] lg:max-h-none shrink-0 flex flex-col bg-[var(--panel-bg)] border-t lg:border-t-0 lg:border-l border-[var(--panel-border)] overflow-hidden transition-all duration-200 z-10 min-w-0"
          aria-label="Agent Trace Telemetry"
        >
          <div className="border-b border-[var(--panel-border)] px-4 py-2.5 flex items-center justify-between bg-[var(--panel-inner)] shrink-0 gap-2 font-mono min-w-0">
            <div className="flex items-center gap-2 min-w-0">
              <Workflow className="h-3.5 w-3.5 text-[#f97316] shrink-0" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] truncate">
                AGENT TRACE
              </h2>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {loading ? (
                <span data-testid="live-timer-header" className="font-mono text-[10px] text-[#f97316] font-bold shrink-0 whitespace-nowrap animate-pulse">
                  {(liveElapsedMs / 1000).toFixed(2)}s live
                </span>
              ) : latestTotalMs > 0 ? (
                <span data-testid="completed-timer-header" className="font-mono text-[10px] text-[var(--text-muted)] shrink-0 whitespace-nowrap">
                  {(latestTotalMs / 1000).toFixed(2)}s total
                </span>
              ) : null}
              <button
                onClick={() => setTraceOpen(false)}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-0.5 rounded-[2px] cursor-pointer shrink-0"
                aria-label="Close Agent Trace"
              >
                <PanelRightClose className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
          <div className="flex-1 min-h-0 overflow-hidden">
            <AgentTrace steps={latestSteps} isLoading={loading} />
          </div>
        </aside>
      )}

      {/* Contextual PDF Password Dialog */}
      <PdfPasswordDialog
        open={isPasswordModalOpen}
        onOpenChange={(open) => {
          setIsPasswordModalOpen(open);
          if (!open) {
            setPendingEncryptedFile(null);
            setPdfPasswordError("");
          }
        }}
        fileName={pendingEncryptedFile?.name || "Encrypted Document"}
        onSubmit={handlePasswordSubmit}
        isDecrypting={isDecrypting}
        errorMessage={pdfPasswordError}
      />
    </div>
  );
}

/**
 * Authoritative Centralized Citation Link Formatter
 * Supports single citations ([E1], [1], [E10]) and multi-citations ([E1, E2], [1, 2], [E1; E2])
 * Transforms them safely into Markdown links: [[E1]](#cite-1) [[E2]](#cite-2)
 * Avoids double-wrapping already formatted links and preserves partial streaming fragments.
 */
function formatCitationsForMarkdown(rawContent) {
  if (!rawContent || typeof rawContent !== "string") return "";

  // Matches bracketed citation groups not preceded by [ and not followed by (
  // e.g. [E1], [1], [E10], [E1, E2], [E1,E2], [1, 2], [E1; E2]
  return rawContent.replace(
    /(?<!\[)\[\s*(?:[CE]?\d+\s*[,;/]?\s*)+\](?!\()/gi,
    (group) => {
      const digits = group.match(/\d+/g);
      if (!digits || digits.length === 0) return group;

      const seen = new Set();
      const deduped = [];
      for (const d of digits) {
        const num = parseInt(d, 10);
        if (!isNaN(num) && !seen.has(num)) {
          seen.add(num);
          deduped.push(num);
        }
      }
      if (deduped.length === 0) return group;
      return deduped.map((num) => `[[E${num}]](#cite-${num})`).join(" ");
    }
  );
}

const MessageBubble = memo(function MessageBubble({ message, liveElapsedMs, onOpenPdf, onRetry }) {
  const isUser = message.role === "user";
  const formattedContent = useMemo(() => {
    return formatCitationsForMarkdown(message.content);
  }, [message.content]);

  // Section 5: Consistency diagnostic check (rendered citations vs validated citations)
  useEffect(() => {
    if (!isUser && !message.isStreaming && message.content) {
      const renderedMatches = message.content.match(/\[(?:\s*[CE]?\d+\s*[,;/]?\s*)+\]/gi) || [];
      let renderedCitationCount = 0;
      for (const m of renderedMatches) {
        const d = m.match(/\d+/g);
        if (d) renderedCitationCount += d.length;
      }
      const validatedCitationCount = message.citations?.length || 0;
      if (validatedCitationCount > 0 && renderedCitationCount !== validatedCitationCount) {
        console.warn(
          `[Citation Consistency Diagnostic] Message ID ${message.id}: renderedCitationCount=${renderedCitationCount} != validatedCitationCount=${validatedCitationCount}`
        );
      }
    }
  }, [isUser, message.isStreaming, message.content, message.citations, message.id]);

  return (
    <div className="flex gap-3 font-mono min-w-0 w-full">
      {/* Avatar Block */}
      <div
        className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-[2px] border ${
          isUser
            ? "border-[var(--panel-border)] bg-[var(--panel-inner)] text-[var(--text-secondary)]"
            : message.error
            ? "border-rose-500/50 bg-rose-950/40 text-rose-400"
            : "border-[#f97316]/50 bg-[#f97316]/10 text-[#f97316]"
        }`}
      >
        {isUser ? <User className="h-3 w-3" /> : <Bot className="h-3 w-3" />}
      </div>

      <div className="flex-1 min-w-0 space-y-2 overflow-hidden">
        {/* Header and Timings */}
        <div className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider flex items-center justify-between flex-wrap gap-1">
          <div className="flex items-center gap-2 min-w-0">
            <span className={isUser ? "text-[var(--text-secondary)]" : "text-[#f97316]"}>
              {isUser ? "USER" : "COGNIFLOW_CORE"}
            </span>
            {!isUser && (
              <span data-testid="live-meta-bubble" className="text-[9px] text-[var(--text-muted)] shrink-0 whitespace-nowrap font-mono">
                [{message.isStreaming
                  ? `${((liveElapsedMs || 0) / 1000).toFixed(2)}s live`
                  : `${((message.totalDurationMs || 0) / 1000).toFixed(2)}s`
                } · {message.steps?.length ?? 0} STAGES
                {message.ttftMs ? ` · TTFT: ${(message.ttftMs / 1000).toFixed(2)}s` : ""}
                {` · ${message.actualModel || message.model || "gemini-3.5-flash-lite"}`}
                {message.fallbackOccurred ? " (FALLBACK)" : ""}
                ]
              </span>
            )}
          </div>
        </div>

        {/* 1. Answerability Status Banner (RAG only) */}
        {!isUser && message.answerability && message.plan?.mode !== "general_chat" && (
          <AnswerabilityBanner answerability={message.answerability} />
        )}

        {/* 1.5 Document Coverage Verification Panel (Summary only) */}
        {!isUser && message.documentCoverage && message.plan?.mode !== "general_chat" && (
          <DocumentCoveragePanel coverage={message.documentCoverage} />
        )}

        {/* 2. Retrieval Strategy & Plan Visualizer (RAG only) */}
        {!isUser && (message.plan || message.trace) && message.plan?.mode !== "general_chat" && (
          <RetrievalPlanVisualizer
            plan={message.plan}
            trace={message.trace}
            subqueries={message.subqueries}
            sources={message.sources}
            originalQuery={message.question}
            rewrittenQuery={message.rewrittenQuery}
            candidateCount={message.candidateCount}
          />
        )}

        {/* 3. Live Streaming Stage Indicator */}
        {!isUser && message.isStreaming && message.streamingStage && (
          <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-[2px] bg-[#f97316]/10 border border-[#f97316]/30 text-[#f97316] text-[10px] uppercase tracking-wider">
            <Loader2 className="h-2.5 w-2.5 animate-spin" />
            <span>{message.streamingStage}</span>
          </div>
        )}

        {/* 4. Message Content or Error Block */}
        {message.error ? (
          <div className="rounded-[3px] border border-rose-500/40 bg-rose-950/20 p-3 text-xs text-rose-300 space-y-2 font-mono">
            <div className="flex items-center gap-2 font-bold uppercase tracking-wider text-rose-400">
              <AlertCircle className="h-3.5 w-3.5 text-rose-400 shrink-0" />
              <span>
                {message.errorDetails?.code === "BILLING_402"
                  ? "API Quota Limit (HTTP 402)"
                  : message.errorDetails?.code === "RATE_LIMIT_429"
                  ? "Rate Limit Exceeded (HTTP 429)"
                  : "Pipeline Execution Error"}
              </span>
            </div>
            <p className="text-[11px] text-rose-300/90 leading-relaxed pl-5">
              {message.content}
            </p>
            {onRetry && message.question && (
              <div className="pl-5 pt-1">
                <Button
                  size="sm"
                  variant="outline"
                  data-testid="retry-question-button"
                  className="h-6 text-xs border-rose-500/40 text-rose-300 hover:bg-rose-950/50 bg-rose-950/30 rounded-[2px] font-mono"
                  onClick={() => onRetry(message.question)}
                >
                  <RotateCcw className="h-3 w-3 mr-1" />
                  RETRY_QUERY
                </Button>
              </div>
            )}
          </div>
        ) : (
          <div
            data-testid={isUser ? "user-message-bubble" : "assistant-message-bubble"}
            className={`prose prose-sm max-w-none break-words rounded-[3px] px-3.5 py-3 border min-w-0 overflow-hidden ${
              isUser
                ? "border-[var(--panel-border)] bg-[var(--panel-inner)] text-[var(--text-primary)]"
                : "border-[var(--panel-border)] bg-[var(--panel-bg)] text-[var(--text-primary)] shadow-xs"
            }`}
          >
            <div className="text-xs leading-relaxed break-words text-[var(--text-primary)] space-y-2 min-w-0 overflow-hidden">
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeKatex]}
                components={{
                  table: ({ children }) => (
                    <div className="overflow-x-auto my-3 max-w-full rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-inner)] shadow-xs min-w-0">
                      <table className="min-w-full divide-y divide-[var(--panel-border)] text-xs font-mono text-[var(--text-primary)]">
                        {children}
                      </table>
                    </div>
                  ),
                  thead: ({ children }) => (
                    <thead className="bg-[var(--panel-bg)] border-b border-[var(--panel-border)] font-bold text-[#f97316]">
                      {children}
                    </thead>
                  ),
                  tbody: ({ children }) => (
                    <tbody className="divide-y divide-[var(--panel-border)]/40 bg-[var(--panel-inner)]">
                      {children}
                    </tbody>
                  ),
                  tr: ({ children }) => (
                    <tr className="hover:bg-[var(--panel-bg)]/60 transition-colors">
                      {children}
                    </tr>
                  ),
                  th: ({ children }) => (
                    <th className="px-3 py-1.5 text-left text-[10px] font-mono font-bold uppercase tracking-wider text-[#f97316] border-r border-[var(--panel-border)]/40 last:border-r-0 whitespace-nowrap">
                      {children}
                    </th>
                  ),
                  td: ({ children }) => (
                    <td className="px-3 py-1.5 text-[11px] font-mono text-[var(--text-secondary)] border-r border-[var(--panel-border)]/40 last:border-r-0 whitespace-nowrap">
                      {children}
                    </td>
                  ),
                  h1: ({ children }) => (
                    <h1 className="text-sm font-bold font-mono text-[#f97316] mt-3 mb-2 border-b border-[var(--panel-border)] pb-1 flex items-center gap-2">
                      {children}
                    </h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="text-xs font-bold font-mono text-[var(--text-primary)] mt-3 mb-1.5 border-b border-[var(--panel-border)]/50 pb-1 flex items-center gap-1.5">
                      {children}
                    </h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-xs font-bold font-mono text-[#f97316] mt-2 mb-1">
                      {children}
                    </h3>
                  ),
                  ul: ({ children }) => (
                    <ul className="list-disc list-inside space-y-1 my-1.5 pl-1 text-xs text-[var(--text-secondary)]">
                      {children}
                    </ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal list-inside space-y-1 my-1.5 pl-1 text-xs text-[var(--text-secondary)]">
                      {children}
                    </ol>
                  ),
                  li: ({ children }) => (
                    <li className="leading-relaxed text-xs text-[var(--text-secondary)]">
                      {children}
                    </li>
                  ),
                  p: ({ children }) => (
                    <p className="leading-relaxed my-1.5 text-xs text-[var(--text-secondary)]">
                      {children}
                    </p>
                  ),
                  hr: () => <hr className="my-2.5 border-[var(--panel-border)]" />,
                  strong: ({ children }) => (
                    <strong className="font-bold text-[var(--text-primary)]">
                      {children}
                    </strong>
                  ),
                  pre: ({ children }) => (
                    <div className="overflow-x-auto my-2 max-w-full rounded-[2px] bg-[var(--panel-inner)] border border-[var(--panel-border)] p-2.5 font-mono text-xs text-[var(--text-secondary)] min-w-0">
                      {children}
                    </div>
                  ),
                  a: ({ href, children, ...props }) => {
                    if (href?.startsWith("#cite-")) {
                      const index = parseInt(href.replace("#cite-", ""), 10);

                      // 1. Authoritative check in message.citations (validated provenance objects)
                      const validatedSource = message.citations?.find(
                        (c) =>
                          c.index === index ||
                          c.badge === `E${index}` ||
                          c.evidenceId === `E${index}` ||
                          c.id === `cite-${index}` ||
                          c.citationId === `[E${index}]`
                      );

                      // 2. Secondary check in message.sources (retrieved candidate objects)
                      const candidateSource =
                        validatedSource ||
                        message.sources?.find(
                          (s) =>
                            s.index === index ||
                            s.sourceIndex === index ||
                            s.badge === `E${index}` ||
                            s.evidenceId === `E${index}` ||
                            s.citationId === `[E${index}]` ||
                            s.badge === String(index)
                        ) ||
                        message.sources?.[index - 1];

                      const resolvedSource = validatedSource || candidateSource;

                      if (resolvedSource) {
                        return (
                          <CitationCard
                            source={resolvedSource}
                            index={`E${index}`}
                            onOpenPdf={onOpenPdf}
                          />
                        );
                      }

                      return (
                        <span
                          className="inline-flex items-center justify-center rounded-[2px] bg-[var(--panel-inner)] text-[var(--text-muted)] font-mono text-[9px] px-1 py-0.2 align-baseline mx-0.5 border border-[var(--panel-border)] cursor-not-allowed"
                          title={`Source [E${index}] not found in retrieved evidence`}
                        >
                          [E{index}]
                        </span>
                      );
                    }
                    return (
                      <a
                        href={href}
                        {...props}
                        className="text-[#f97316] underline underline-offset-2 hover:text-[#ea580c] font-mono text-xs"
                      >
                        {children}
                      </a>
                    );
                  },
                }}
              >
                {formattedContent}
              </ReactMarkdown>
            </div>
          </div>
        )}

        {/* 5. Post-Answer Metadata Panels (RAG only) */}
        {!isUser && !message.error && message.plan?.mode !== "general_chat" && (
          <div className="space-y-2 pt-1">
            {message.confidence && <ConfidenceMeter confidence={message.confidence} />}

            {message.sources && message.sources.length > 0 && (
              <SourcesPanel sources={message.sources} onOpenPdf={onOpenPdf} />
            )}

            {message.steps && <ConfidenceDashboard steps={message.steps} />}

            <SecurityDisclaimer compact />
          </div>
        )}
      </div>
    </div>
  );
});

function ConfidenceDashboard({ steps }) {
  const criticStep = steps.find((s) => s.agent === "critic");
  if (!criticStep || !criticStep.output || !criticStep.output.verdict) return null;

  const { verdict, faithfulnessScore, issues } = criticStep.output;
  const isFaithful = verdict === "faithful";

  return (
    <div className="flex flex-col gap-2 rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-inner)] p-2.5 mt-2 font-mono min-w-0 overflow-hidden">
      <div className="flex items-center justify-between flex-wrap gap-2 min-w-0">
        <div className="flex items-center gap-2 min-w-0">
          <ShieldCheck
            className={`h-3.5 w-3.5 shrink-0 ${
              isFaithful ? "text-emerald-600" : "text-rose-600"
            }`}
          />
          <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] truncate min-w-0">
            CRITIC FAITHFULNESS VERDICT
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0 font-mono text-xs">
          <span className={`font-semibold uppercase ${isFaithful ? "text-emerald-600" : "text-rose-600"}`}>
            {verdict}
          </span>
          <span className="text-[var(--text-muted)]">·</span>
          <span className="text-[var(--text-secondary)] font-mono">
            {faithfulnessScore}/100
          </span>
        </div>
      </div>
      {!isFaithful && Array.isArray(issues) && issues.length > 0 && (
        <div className="text-[10px] font-mono text-rose-400 bg-rose-950/20 p-2 rounded-[2px] border border-rose-500/30">
          <span className="font-bold uppercase tracking-wider block mb-1">
            Issues identified:
          </span>
          <ul className="list-disc pl-4 space-y-0.5">
            {issues.map((issue, i) => (
              <li key={i}>{issue}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
