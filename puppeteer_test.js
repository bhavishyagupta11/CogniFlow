const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  await page.goto('http://localhost:3000');
  
  // Wait for the sample prompts to load
  await page.waitForSelector('.flex-wrap button');
  
  // Click the first prompt which happens to be about attention
  const buttons = await page.$$('.flex-wrap button');
  let clicked = false;
  for (const btn of buttons) {
    const text = await page.evaluate(el => el.textContent, btn);
    if (text.includes('attention')) {
      await btn.click();
      clicked = true;
      break;
    }
  }
  
  if (!clicked) {
    console.log("Could not find the prompt button");
    await browser.close();
    return;
  }
  
  // Wait for the loading indicator to appear and then disappear
  console.log("Waiting for answer...");
  await page.waitForSelector('.lucide-loader2', { hidden: true, timeout: 60000 });
  
  // Wait for the prose div
  await page.waitForSelector('.prose');
  
  // Get the HTML of the first message bubble that is not from the user
  const html = await page.evaluate(() => {
    const messages = Array.from(document.querySelectorAll('.prose'));
    // Return the last one
    return messages[messages.length - 1].innerHTML;
  });
  
  console.log("HTML EXTRACTED:\n", html);
  
  // Take a screenshot
  await page.screenshot({ path: 'screenshot.png', fullPage: true });
  
  await browser.close();
})();
