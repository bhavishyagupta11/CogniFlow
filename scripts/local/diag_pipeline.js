/**
 * CogniFlow Forensic Diagnostic Script
 * 
 * Hits /api/chat and captures the COMPLETE response structure
 * to verify what the backend actually returns to the frontend.
 */
const http = require('http');

const payload = JSON.stringify({ question: "What is attention?" });

const options = {
  hostname: 'localhost',
  port: 3000,
  path: '/api/chat',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(payload),
  },
  timeout: 120000,
};

console.log(`[DIAG] ${new Date().toISOString()} Sending query: "What is attention?"`);
console.log(`[DIAG] Payload: ${payload}`);

const startTime = Date.now();

const req = http.request(options, (res) => {
  let body = '';
  res.on('data', (chunk) => body += chunk);
  res.on('end', () => {
    const elapsed = Date.now() - startTime;
    console.log(`\n${'='.repeat(80)}`);
    console.log(`[DIAG] Response received in ${elapsed}ms`);
    console.log(`[DIAG] HTTP Status: ${res.statusCode}`);
    console.log(`[DIAG] Headers: ${JSON.stringify(res.headers, null, 2)}`);
    console.log(`${'='.repeat(80)}\n`);

    let parsed;
    try {
      parsed = JSON.parse(body);
    } catch (e) {
      console.log(`[DIAG] FATAL: Response is not valid JSON`);
      console.log(`[DIAG] Raw body (first 2000 chars): ${body.substring(0, 2000)}`);
      return;
    }

    // Top-level structure
    console.log(`[DIAG] Response keys: ${Object.keys(parsed).join(', ')}`);
    console.log(`[DIAG] Has 'error' key: ${parsed.error !== undefined}`);
    console.log(`[DIAG] Has 'answer' key: ${parsed.answer !== undefined}`);
    console.log(`[DIAG] Has 'sources' key: ${parsed.sources !== undefined}`);
    console.log(`[DIAG] Has 'steps' key: ${parsed.steps !== undefined}`);
    console.log(`[DIAG] Has 'totalDurationMs' key: ${parsed.totalDurationMs !== undefined}`);

    if (parsed.error) {
      console.log(`\n[DIAG] *** ERROR RESPONSE ***`);
      console.log(`[DIAG] Error: ${JSON.stringify(parsed.error)}`);
      return;
    }

    // Answer analysis
    console.log(`\n--- ANSWER ---`);
    console.log(`[DIAG] Answer type: ${typeof parsed.answer}`);
    console.log(`[DIAG] Answer length: ${parsed.answer?.length ?? 'N/A'}`);
    console.log(`[DIAG] Answer starts with "I'm sorry": ${parsed.answer?.startsWith("I'm sorry") ?? 'N/A'}`);
    console.log(`[DIAG] Answer content (first 500 chars):\n${parsed.answer?.substring(0, 500)}`);

    // Sources analysis
    console.log(`\n--- SOURCES ---`);
    console.log(`[DIAG] Sources count: ${parsed.sources?.length ?? 'N/A'}`);
    if (parsed.sources?.length > 0) {
      parsed.sources.forEach((s, i) => {
        console.log(`  [${i}] title="${s.documentTitle}" chunkId=${s.chunkId} llmScore=${s.llmScore} score=${s.score}`);
      });
    }

    // Steps analysis (agent trace)
    console.log(`\n--- AGENT TRACE ---`);
    console.log(`[DIAG] Steps count: ${parsed.steps?.length ?? 'N/A'}`);
    if (parsed.steps?.length > 0) {
      parsed.steps.forEach((step, i) => {
        console.log(`  [${i}] agent=${step.agent} status=${step.status} duration=${step.durationMs}ms label="${step.label}" error=${step.error ?? 'none'}`);
        
        // Dump agent-specific output
        if (step.agent === 'router') {
          console.log(`       queryType=${step.output?.queryType} rewrittenQuery="${step.output?.rewrittenQuery}" needsRetrieval=${step.output?.needsRetrieval}`);
        }
        if (step.agent === 'retriever') {
          console.log(`       candidates=${step.output?.candidates?.length} vocabSize=${step.output?.stats?.vocabSize} numChunks=${step.output?.stats?.numChunks}`);
        }
        if (step.agent === 'reranker') {
          console.log(`       reranked=${step.output?.reranked?.length}`);
          step.output?.reranked?.forEach((r, j) => {
            console.log(`         [${j}] chunkId=${r.chunkId} llmScore=${r.llmScore} rationale="${r.rationale?.substring(0, 80)}"`);
          });
        }
        if (step.agent === 'analyzer') {
          console.log(`       answer_length=${step.output?.answer?.length} citationsUsed=${step.output?.citationsUsed} iteration=${step.input?.iteration}`);
          console.log(`       answer_starts_with_sorry=${step.output?.answer?.startsWith("I'm sorry")}`);
        }
        if (step.agent === 'critic') {
          console.log(`       verdict=${step.output?.verdict} faithfulnessScore=${step.output?.faithfulnessScore} issues=${JSON.stringify(step.output?.issues)}`);
        }
        if (step.agent === 'coordinator') {
          console.log(`       flow=${step.output?.flow?.join('→')} totalIterations=${step.output?.totalIterations} finalVerdict=${step.output?.finalVerdict}`);
        }
      });
    }

    console.log(`\n--- TIMING ---`);
    console.log(`[DIAG] Total pipeline duration: ${parsed.totalDurationMs}ms`);
    console.log(`[DIAG] Network round-trip: ${elapsed}ms`);

    // Write full response to file for inspection
    const fs = require('fs');
    fs.writeFileSync('diag_output.json', JSON.stringify(parsed, null, 2));
    console.log(`\n[DIAG] Full response written to diag_output.json`);
  });
});

req.on('error', (e) => {
  console.log(`[DIAG] Request error: ${e.message}`);
});

req.on('timeout', () => {
  console.log(`[DIAG] Request timed out after 120s`);
  req.destroy();
});

req.write(payload);
req.end();
