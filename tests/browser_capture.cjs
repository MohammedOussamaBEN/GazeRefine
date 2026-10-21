// This test uses a fake camera + simulated SDK; it does not validate gaze accuracy.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const path=require('path'),{spawn}=require('child_process');
const root=path.resolve(__dirname,'..'),out=path.join(root,'outputs','capture-qa');
require('fs').mkdirSync(out,{recursive:true});
const fs=require('fs');
const fakeSDK=`export class WebcamETLight {async initialize(){} detectFace(){return window.__noFace?null:{};} calibrate(samples){if(samples.length!==85)throw Error('Expected 85 calibration samples');} predict(){if(window.__noFace)return null;const r=document.querySelector('#canvas').getBoundingClientRect();return {x:r.left+r.width*.5,y:r.top+r.height*.5};} dispose(){}} export function getRecommendedPattern(){return 17;} export function getCalibrationPointsInPixels(_,w,h){return Array.from({length:17},(_,i)=>({x:(.15+.175*(i%5))*w,y:(.15+.2*Math.floor(i/5))*h}));}`;
(async()=>{
 const server=spawn(process.env.PYTHON||'python',[path.join(root,'tests','capture_test_server.py')],{cwd:root,stdio:['ignore','pipe','inherit']});
 let browser;
 try{
 const port=await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(Error('Fixture server did not start')),30000);server.on('error',reject);server.stdout.on('data',data=>{const match=String(data).match(/READY (\d+)/);if(match){clearTimeout(timeout);resolve(match[1]);}});});
 browser=await chromium.launch({...(process.env.GAZEREFINE_CHROME?{executablePath:process.env.GAZEREFINE_CHROME}:{}),headless:true,args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[],captures=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().endsWith('/api/capture'))captures.push(r.postDataJSON());});
 await page.route('https://esm.sh/@realeye-io/webcam-eyetracker-light-open@1.1.0',route=>route.fulfill({contentType:'text/javascript',body:fakeSDK}));
 await page.goto(`http://127.0.0.1:${port}/`,{waitUntil:'networkidle'});
 await page.waitForFunction(()=>document.querySelector('#image-name').textContent==='desktop-test.jpg'&&!document.querySelector('#canvas').hidden);
 await page.locator('summary').click();await page.locator('#camera-start').click();
 await page.waitForFunction(()=>!document.querySelector('#calibration').hidden);
 await page.screenshot({path:path.join(out,'capture-calibration.png')});
 await page.waitForFunction(()=>!document.querySelector('#start-record').disabled,{timeout:45000});
 if(await page.locator('#calibration').isVisible())throw Error('Calibration layer did not close');
 await page.locator('#start-record').click();
 await page.waitForFunction(()=>parseInt(document.querySelector('#capture-stats').textContent)>8,{timeout:10000});
 await page.screenshot({path:path.join(out,'capture-recording.png')});
 await page.locator('#stop-record').click();
 await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('also sent to the desktop app'),{timeout:10000});
 await page.screenshot({path:path.join(out,'capture-saved.png')});
 const firstStatus=await page.locator('#status').textContent();
 const data=captures[0];
 if(data.fixations.length<1)throw Error('No fixations returned to desktop');
 // A short no-face run must show a useful zero-fixation message and keep raw export.
 await page.evaluate(()=>window.__noFace=true);await page.locator('#start-record').click();
 await page.waitForFunction(()=>parseInt(document.querySelector('#capture-stats').textContent)>5);
 await page.locator('#stop-record').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('no ≥100 ms dwell groups'));
 const noFaceStatus=await page.locator('#status').textContent();
 if(await page.locator('#export-gaze').isDisabled())throw Error('Raw export disabled after zero-fixation recording');
 await page.locator('#camera-off').click();await page.evaluate(()=>window.__noFace=false);await page.locator('#camera-start').click();await page.waitForFunction(()=>!document.querySelector('#calibration').hidden,null,{timeout:10000});await page.locator('#cancel-calibration').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('cancelled'));if(await page.locator('#calibration').isVisible())throw Error('Cancel did not restore image');
 console.log(JSON.stringify({errors,calibrationTargets:17,fixationsReturned:data.fixations.length,rawSamples:data.samples.length,status:firstStatus,noFaceStatus}));
 if(errors.length)throw Error(errors.join('\n'));
 }catch(error){for(const p of browser?.contexts()[0]?.pages()||[]){console.error(await p.evaluate(()=>({status:document.querySelector('#status')?.textContent,calibrationHidden:document.querySelector('#calibration')?.hidden,cameraDisabled:document.querySelector('#camera-start')?.disabled,videoReady:document.querySelector('#video')?.readyState})));await p.screenshot({path:path.join(out,'failure.png')});}throw error;}finally{await browser?.close();server.kill();}
})();
