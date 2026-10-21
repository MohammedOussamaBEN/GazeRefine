const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs');fs.mkdirSync('outputs/site-qa',{recursive:true});
(async()=>{
const browser=await chromium.launch({...(process.env.GAZEREFINE_CHROME?{executablePath:process.env.GAZEREFINE_CHROME}:{}),headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.SITE_URL||'http://127.0.0.1:8000/',{waitUntil:'networkidle'});
 await page.evaluate(async()=>{for(const image of document.querySelectorAll('figure img'))image.loading='eager';await Promise.all([...document.querySelectorAll('figure img')].map(i=>i.decode()));});
 const images=await page.evaluate(()=>[...document.querySelectorAll('figure img')].map(i=>({src:i.getAttribute('src'),width:i.naturalWidth,loaded:i.complete})));
 if(images.some(i=>!i.width))throw Error('A figure did not load');
 await page.screenshot({path:'outputs/site-qa/research-hero.png'});
 await page.screenshot({path:'outputs/site-qa/research-desktop.png',fullPage:true});
 await page.locator('[data-results=broader]').click();await page.locator('#broader-results').waitFor({state:'visible'});
 if(!(await page.locator('#broader-results').innerText()).includes('89.49'))throw Error('Broader results missing');
 await page.locator('[data-results=controlled]').click();
 await page.locator('#source-filter').selectOption('Expert');await page.locator('#weight-filter').selectOption('No');
 if(await page.locator('#ablation-table tbody tr:visible').count()!==4)throw Error('Ablation filters failed');
 await page.locator('#reset-filters').click();
 if(await page.locator('#ablation-table tbody tr:visible').count()!==16)throw Error('Reset filters failed');
 await page.locator('#ablation .zoom').first().click();await page.locator('#figure-dialog').waitFor({state:'visible'});
 await page.keyboard.press('Escape');await page.locator('#figure-dialog').waitFor({state:'hidden'});
 await page.locator('#scanpath summary').click();
 if(await page.locator('#scanpath details .figure-image img').count()!==1)throw Error('First/last analysis missing');
 const sizes=[];
 for(const width of [1440,768,390,320]){
  await page.setViewportSize({width,height:900});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  sizes.push({width,overflow});if(overflow)throw Error('Page overflows at '+width);
 }
 await page.setViewportSize({width:390,height:844});await page.goto(process.env.SITE_URL||'http://127.0.0.1:8000/');
 await page.screenshot({path:'outputs/site-qa/research-mobile.png',fullPage:true});
 await page.locator('#robustness .zoom').click();await page.screenshot({path:'outputs/site-qa/research-mobile-zoom.png'});
 await page.locator('#close-figure').click();
 console.log(JSON.stringify({figures:images.length,errors,sizes,interactiveChecks:'results scopes, ablation filters, zoom/Escape, first/last disclosure passed'}));
 if(errors.length)throw Error(errors.join('\n'));
}finally{await browser.close();}
})();
