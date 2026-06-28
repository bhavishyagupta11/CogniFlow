const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.toString()));
  
  await page.goto('http://localhost:3000/test');
  
  await page.waitForSelector('#test-container');
  
  const html = await page.evaluate(() => {
    return document.querySelector('#test-container').innerHTML;
  });
  
  console.log("HTML EXTRACTED:\n", html);
  await page.screenshot({ path: 'test_render_browser.png' });
  
  await browser.close();
})();
