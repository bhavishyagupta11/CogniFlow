const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  await page.goto('http://localhost:3000');
  
  // Wait for the sample prompts to load
  await page.waitForSelector('.flex-wrap button');
  
  // Click the first prompt which happens to be about attention
  const buttons = await page.$$('.flex-wrap button');
  for (const btn of buttons) {
    const text = await page.evaluate(el => el.textContent, btn);
    if (text.includes('attention')) {
      await btn.click();
      break;
    }
  }
  
  console.log("Waiting for answer...");
  await page.waitForSelector('.lucide-loader2', { hidden: true, timeout: 60000 });
  
  // Wait for the sources panel to appear
  // The sources panel has chunks
  const sourcesPanel = await page.$('.lucide-file-text');
  if (sourcesPanel) {
    console.log("Sources panel found.");
    // We want the inner HTML of the ReactMarkdown in sources-panel
    const html = await page.evaluate(() => {
      // Find the element with text-[11px] and leading-relaxed which contains the react markdown
      const chunks = Array.from(document.querySelectorAll('.prose-sm'));
      return chunks.map(c => c.innerHTML).join('\n---\n');
    });
    console.log("HTML EXTRACTED:\n", html);
  } else {
    console.log("No sources panel found.");
  }
  
  await browser.close();
})();
