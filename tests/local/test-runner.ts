import { runMockLlmTests } from "./mock-llm.test";

async function main() {
  try {
    console.log("Starting local test runner...");
    await runMockLlmTests();
    console.log("✅ All test suites completed successfully.");
    process.exit(0);
  } catch (error) {
    console.error("❌ Tests failed:", error);
    process.exit(1);
  }
}

// Execute if run directly
if (require.main === module) {
  main();
}
