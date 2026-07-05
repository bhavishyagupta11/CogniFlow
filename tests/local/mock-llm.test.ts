import assert from "node:assert";
import { runMultiAgentPipeline } from "../../src/lib/agents/coordinator";

export async function runMockLlmTests() {
  console.log("Running mock-llm tests...");
  const originalFetch = global.fetch;

  try {
    process.env.OPENROUTER_API_KEY = "test-mock-key";

    // Test 1: Simulate HTTP 402 (Payment Required)
    console.log("Test: Simulate HTTP 402...");
    global.fetch = async (url: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      if (url.toString().includes("openrouter.ai")) {
        return new Response(JSON.stringify({ error: { message: "Insufficient quota" } }), { 
          status: 402, 
          statusText: "Payment Required" 
        });
      }
      return originalFetch(url, init);
    };

    let result = await runMultiAgentPipeline("Test query 402");
    // Router catches LLM errors and returns a fallback output with status = "error"
    assert.strictEqual(result.steps[0].status, "error");
    
    // Test 2: Simulate HTTP 429 (Too Many Requests)
    console.log("Test: Simulate HTTP 429...");
    global.fetch = async (url: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      if (url.toString().includes("openrouter.ai")) {
        return new Response(JSON.stringify({ error: { message: "Rate limit exceeded" } }), { 
          status: 429, 
          statusText: "Too Many Requests" 
        });
      }
      return originalFetch(url, init);
    };

    result = await runMultiAgentPipeline("Test query 429");
    assert.strictEqual(result.steps[0].status, "error");

    // Test 3: Simulate Success (200)
    console.log("Test: Simulate Success...");
    global.fetch = async (url: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      if (url.toString().includes("openrouter.ai")) {
        // Router agent expects a JSON response in the content
        const mockResponse = {
          queryType: "factual",
          rewrittenQuery: "mocked success query",
          intentSummary: "mocked intent",
          needsRetrieval: false // Setting to false so coordinator stops after router
        };
        return new Response(
          JSON.stringify({
            choices: [{ message: { content: JSON.stringify(mockResponse) } }]
          }), 
          { status: 200, statusText: "OK" }
        );
      }
      return originalFetch(url, init);
    };

    result = await runMultiAgentPipeline("Test query success");
    assert.strictEqual(result.steps[0].status, "completed");
    
    // Verify that the mocked output was successfully parsed and returned
    const routerOutput = result.steps[0].output as any;
    assert.strictEqual(routerOutput.rewrittenQuery, "mocked success query");
    
    console.log("✅ All mock-llm tests passed!");
  } finally {
    global.fetch = originalFetch;
  }
}
