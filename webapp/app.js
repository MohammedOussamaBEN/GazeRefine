import {imagePoint,WebcamCapture} from './gaze.js';
const $=id=>document.getElementById(id);
let image=null,cleanImage=null,points=[],samples=[],result=null,capture=null,busy=false,token=null;
const canvas=$('canvas'),ctx=canvas.getContext('2d');
function status(text){$('status').textContent=text;}
async function api(path,data){
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-GazeRefine-Token':token},body:JSON.stringify(data)});
  const payload=await response.json();if(!response.ok)throw new Error(payload.error||'Request failed.');return payload;
}
function loadImage(src){return new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(new Error('Could not decode image.'));img.src=src;});}
async function redraw(){
  if(!image)return;
  const mode=$('view').value;
  const shown=mode==='input'||!result?image:await loadImage(result[mode]);
  canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;ctx.drawImage(shown,0,0,canvas.width,canvas.height);
  if(mode==='input')for(const [i,p] of points.entries()){
    const r=Math.max(4,canvas.width/100);ctx.beginPath();ctx.arc(p[0]*canvas.width,p[1]*canvas.height,r,0,2*Math.PI);ctx.fillStyle='#40f0d0';ctx.fill();ctx.strokeStyle='#112e37';ctx.stroke();
    ctx.fillStyle='white';ctx.font=`${Math.max(13,canvas.width/55)}px sans-serif`;ctx.fillText(String(i+1),p[0]*canvas.width+r,p[1]*canvas.height-r);
  }
  $('count').textContent=`${points.length} fixations`;
}
function invalidate(){result=null;$('downloads').hidden=true;$('view').value='input';}
$('image-file').onchange=async event=>{
  if(busy||capture?.active)return status('Stop capture and wait for inference before changing image.');
  const file=event.target.files[0];if(!file)return;
  try{
    const url=URL.createObjectURL(file);try{image=await loadImage(url);}finally{URL.revokeObjectURL(url);}
    if(image.width*image.height>40e6)throw new Error('Choose an image under 40 megapixels.');
    const original=document.createElement('canvas');original.width=image.width;original.height=image.height;original.getContext('2d').drawImage(image,0,0);cleanImage=original.toDataURL('image/png');
    points=[];samples=[];invalidate();$('image-name').textContent=file.name;$('empty').hidden=true;canvas.hidden=false;await redraw();status('Image ready. Add gaze points or import a CSV.');
  }catch(error){status(error.message);}
};
canvas.onclick=event=>{
  if(!image||busy||capture?.active)return;
  const p=imagePoint(event.clientX,event.clientY,canvas.getBoundingClientRect());
  const d=Number($('duration').value);if(!Number.isFinite(d)||d<=0)return status('Enter a positive duration.');
  if(p.every(v=>v>=0&&v<=1)){points.push([...p,d]);invalidate();redraw();status('Manual prompt added. These points simulate gaze.');}
};
$('undo').onclick=()=>{if(busy||capture?.active)return;points.pop();invalidate();redraw();};
$('clear').onclick=()=>{if(busy||capture?.active)return;points=[];invalidate();redraw();};
$('view').onchange=redraw;
function parseCSV(text){
  // Quoted CSV cells and CRLF; tabs/semicolons accepted when unambiguous.
  const first=text.split(/\r?\n/)[0];const delimiter=first.includes('\t')?'\t':first.includes(';')?';':',';
  const rows=[];let row=[],cell='',quoted=false;
  for(let i=0;i<text.length;i++){
    const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}
    else if(c===delimiter&&!quoted){row.push(cell.trim());cell='';}
    else if(c==='\n'&&!quoted){row.push(cell.trim());if(row.some(Boolean))rows.push(row);row=[];cell='';}
    else if(c!=='\r')cell+=c;
  }
  if(quoted)throw new Error('CSV has an unclosed quote.');row.push(cell.trim());if(row.some(Boolean))rows.push(row);
  const headers=rows.shift()?.map(v=>v.replace(/^\uFEFF/,''));if(!headers)throw new Error('CSV is empty.');
  return rows.map(r=>Object.fromEntries(headers.map((h,i)=>[h,r[i]??''])));
}
$('gaze-file').onchange=async event=>{
  if(!image)return status('Open an image first.');if(busy||capture?.active)return;
  try{
    const file=event.target.files[0];if(!file)return;let rows=parseCSV(await file.text());
    const stem=v=>v.replace(/^.*[\\/]/,'').replace(/\.[^.]+$/,'');
    if(rows[0]?.IMAGE!==undefined)rows=rows.filter(r=>stem(r.IMAGE)===stem($('image-name').textContent));
    const eye=rows[0]?.CURRENT_FIX_X!==undefined;
    if(eye)rows.sort((a,b)=>Number(a.CURRENT_FIX_INDEX)-Number(b.CURRENT_FIX_INDEX));
    const parsed=rows.map(r=>{
      if(!eye&&(!('x'in r)||!('y'in r)||r.x===''||r.y===''))throw new Error('CSV needs x,y,duration columns.');
      let x=Number(eye?r.CURRENT_FIX_X:r.x),y=Number(eye?r.CURRENT_FIX_Y:r.y),d=Number(eye?r.CURRENT_FIX_DURATION:r.duration||1);
      if(!eye&&$('csv-units').value==='pixels'){x/=image.width;y/=image.height;}
      if(![x,y,d].every(Number.isFinite)||x<0||y<0||x>1||y>1||d<=0)throw new Error('Invalid coordinates/durations. Check CSV units.');return [x,y,d];
    });
    if(!parsed.length||parsed.length>5000)throw new Error('CSV must contain 1–5000 fixations for this image.');
    points=parsed;invalidate();redraw();status(`Imported ${points.length} fixation rows.`);
  }catch(error){status(error.message);}
};
$('run').onclick=async()=>{
  if(!image||!points.length)return status('Open an image and provide gaze first.');
  if(busy||capture?.active)return status('Stop recording before inference.');
  busy=true;$('run').disabled=true;status('Running on CPU… First use loads/downloads DINOv3 weights. Full resolution can take several minutes.');
  try{
    result=await api('/api/predict',{image:cleanImage,fixations:points,modality:$('modality').value,resolution:Number($('resolution').value),duration_weighted:$('weighted').checked,threshold:.5});
    $('view').value='overlay';await redraw();$('downloads').hidden=false;$('download-mask').href=result.mask;$('download-overlay').href=result.overlay;
    const m=result.metadata;status(`Done in ${m.seconds_including_model_load}s · CPU · ${m.resolution} px · ${m.preview?'Preview (not benchmark settings)':'Full resolution'}`);
  }catch(error){status(error.message);}finally{busy=false;$('run').disabled=false;}
};
$('camera-start').onclick=async()=>{
  if(!image)return status('Open an image before calibrating.');if(busy)return;
  $('camera-start').disabled=true;capture?.close();
  capture=new WebcamCapture($('video'),(x,y,t)=>{const [px,py]=imagePoint(x,y,canvas.getBoundingClientRect());samples.push([px,py,t]);},status);
  try{status('Loading RealEye and requesting webcam access…');await capture.start();$('record').disabled=false;}
  catch(error){status(error.message);}finally{$('camera-start').disabled=false;}
};
$('record').onclick=()=>{
  if(busy)return;try{samples=[];capture.record();$('record').disabled=true;$('stop').disabled=false;status('Recording gaze. Look at the target, then stop.');}catch(error){status(error.message);}
};
$('stop').onclick=async()=>{
  capture?.stop();$('stop').disabled=true;$('record').disabled=!capture?.valid;
  try{const data=await api('/api/fixations',{samples});points.push(...data.fixations);invalidate();await redraw();status(`Added ${data.fixations.length} dwell groups (≥100 ms).`);}catch(error){status(error.message);}
};
$('camera-off').onclick=()=>{
  capture?.close();$('record').disabled=true;$('stop').disabled=true;status('Camera off. Recalibrate to record a new session.');
};
function download(text,name,type){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('export-gaze').onclick=()=>{download('x,y,duration\n'+points.map(r=>r.join(',')).join('\n'),'gazerefine_fixations.csv','text/csv');if(samples.length)download('x,y,timestamp_ms\n'+samples.map(r=>r.join(',')).join('\n'),'gazerefine_samples.csv','text/csv');};
$('export-config').onclick=()=>{if(result)download(JSON.stringify(result.metadata,null,2),'gazerefine_settings.json','application/json');};
window.addEventListener('beforeunload',()=>capture?.close());
window.addEventListener('resize',()=>{if(capture?.valid){capture.close();$('record').disabled=true;status('Viewport changed. Recalibrate the webcam.');}});
try{const config=await (await fetch('/api/config')).json();token=config.token;}catch(error){status('Start this app with python scripts/serve_app.py to enable local CPU inference.');}
