const OpenAI = require("openai");

const client = new OpenAI({
  baseURL: "https://router.bynara.id/v1",
  apiKey: "sk-nry-ZgddYFEFZ2Te6GXoYjA_c7_0DJRPwCaVaCI8zDwLE_A",
});

async function test() {
  try {
    const models = await client.models.list();
    console.log("Success! Found models:", models.data.map(m => m.id).slice(0, 5));
  } catch (e) {
    console.error("Failed:", e.status, e.message);
  }
}

test();
