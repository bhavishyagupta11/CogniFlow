const React = require('react');
const ReactDOMServer = require('react-dom/server');

async function test() {
  const ReactMarkdown = (await import('react-markdown')).default;
  const remarkMath = (await import('remark-math')).default;
  const rehypeKatex = (await import('rehype-katex')).default;

  const markdownRaw = "If the LLM outputs plain d_k, d_v, and *h*.";
  const markdownKaTeX = "If the LLM outputs properly formatted $d_k$, $d_v$, $d_{model}$, and $h$.";
  
  const elementRaw = React.createElement(ReactMarkdown, {
    remarkPlugins: [remarkMath],
    rehypePlugins: [rehypeKatex]
  }, markdownRaw);

  const elementKaTeX = React.createElement(ReactMarkdown, {
    remarkPlugins: [remarkMath],
    rehypePlugins: [rehypeKatex]
  }, markdownKaTeX);

  console.log("--- OUTPUT WITHOUT DOLLAR SIGNS ---");
  console.log(ReactDOMServer.renderToString(elementRaw));
  
  console.log("\n--- OUTPUT WITH DOLLAR SIGNS ---");
  console.log(ReactDOMServer.renderToString(elementKaTeX));
}

test().catch(console.error);
