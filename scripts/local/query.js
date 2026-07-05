(async () => {
  const q = await fetch('http://localhost:3000/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question: "Tell me about Bhavishya Gupta's skills" })
  });
  const res = await q.json();
  console.log("ANSWER:", res.answer);
  console.log("STEPS:", JSON.stringify(res.steps, null, 2));
})();
