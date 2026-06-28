"use client";

import { CitedSource } from "@/lib/agents/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { FileText, Quote } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

export function SourcesPanel({ sources }: { sources: CitedSource[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (sources.length === 0) return null;

  return (
    <div className="mt-3 space-y-2">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <Quote className="h-3.5 w-3.5" />
        Sources ({sources.length})
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {sources.map((s, i) => {
          const isOpen = expanded === s.chunkId;
          return (
            <Card
              key={s.chunkId}
              className="overflow-hidden border-l-4 border-l-violet-400 cursor-pointer transition-shadow hover:shadow-md"
              onClick={() => setExpanded(isOpen ? null : s.chunkId)}
            >
              <CardContent className="p-3 space-y-1.5">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Badge
                      variant="secondary"
                      className="font-mono shrink-0"
                    >
                      [{i + 1}]
                    </Badge>
                    <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span className="text-xs font-medium truncate">
                      {s.documentTitle}
                    </span>
                  </div>
                  {s.llmScore !== undefined && (
                    <Badge variant="outline" className="font-mono text-[10px] shrink-0">
                      LLM {s.llmScore.toFixed(1)}
                    </Badge>
                  )}
                </div>
                <div className="text-[10px] text-muted-foreground">
                  {s.authors} · {s.year} · {s.source}
                </div>
                <div
                  className={`text-[11px] text-muted-foreground leading-relaxed prose prose-sm prose-p:my-0 prose-p:leading-relaxed prose-headings:my-1 max-w-none ${
                    isOpen ? "" : "line-clamp-3"
                  }`}
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkMath]}
                    rehypePlugins={[rehypeKatex]}
                  >
                    {s.chunkContent}
                  </ReactMarkdown>
                </div>
                <div className="text-[10px] text-muted-foreground/70 pt-1 border-t">
                  {isOpen ? "Click to collapse" : "Click to expand full chunk"} · chunk #
                  {s.chunkIndex}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
