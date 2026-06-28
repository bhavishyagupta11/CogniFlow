const React = require('react');
const ReactDOMServer = require('react-dom/server');

async function test() {
  const ReactMarkdown = (await import('react-markdown')).default;
  const remarkMath = (await import('remark-math')).default;

  const markdown = "The equation is $d_k$ and $$h$$";

  const element = React.createElement(ReactMarkdown, {
    remarkPlugins: [remarkMath]
  }, markdown);

  const html = ReactDOMServer.renderToString(element);
  console.log("RENDERED HTML WITHOUT REHYPE-KATEX:", html);
}
test().catch(console.error);
