import { chromium } from '@playwright/test';
const deadline = setTimeout(() => { console.error('Visual capture timed out.'); process.exit(1); }, 60000);
let browser;
try {
  browser = await chromium.launch({ channel: 'msedge', timeout: 15000, args: ['--disable-gpu'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1050 }, reducedMotion: 'reduce' });
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    const body = path.endsWith('/auth/me') ? {id:'preview',name:'Ada',email:'preview@example.com'}
      : path.endsWith('/workspaces') ? [{id:'preview',name:'Research workspace',documents:0}]
      : path.endsWith('/documents') ? {documents:[],total:0}
      : path.endsWith('/analytics/overview') ? {documents:0,questions:0,sessions:0,chunks:0,storage_bytes:0,activity:[]}
      : {messages:[],total:0};
    return route.fulfill({json:body});
  });
  await page.goto('http://localhost:3000/dashboard', {waitUntil:'domcontentloaded',timeout:15000});
  await page.getByRole('heading',{name:/Welcome back, Ada/}).waitFor({timeout:10000});
  await page.waitForFunction(() => [...document.querySelectorAll('.metric-card')].length === 4 && [...document.querySelectorAll('.metric-card')].every(card => getComputedStyle(card).opacity === '1'), {timeout:10000});
  await page.screenshot({path:'../docs/screenshots/overview.png',animations:'disabled',timeout:15000});
  await page.getByRole('button',{name:'Toggle theme'}).click();
  await page.screenshot({path:'../docs/screenshots/overview-light.png',animations:'disabled',timeout:15000});
  await page.setViewportSize({width:390,height:844});
  if (!await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)) throw new Error('Mobile overflow detected');
  await page.screenshot({path:'../docs/screenshots/overview-mobile.png',animations:'disabled',timeout:15000});
  console.log('Production dashboard captured.');
} finally {
  if (browser) await browser.close();
  clearTimeout(deadline);
}
