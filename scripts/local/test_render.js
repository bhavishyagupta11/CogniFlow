

async function test() {
  const React = require('react');
  const ReactDOMServer = require('react-dom/server');
  
  const ReactMarkdown = (await import('react-markdown')).default;
  const remarkMath = (await import('remark-math')).default;
  const rehypeKatex = (await import('rehype-katex')).default;

  const markdown = "The equation is $d_k$ and $$h$$";

  const element = React.createElement(ReactMarkdown, {
    remarkPlugins: [remarkMath],
    rehypePlugins: [rehypeKatex]
  }, markdown);

  const html = ReactDOMServer.renderToString(element);
  console.log("RENDERED HTML:", html);
}

test().catch(console.error);
