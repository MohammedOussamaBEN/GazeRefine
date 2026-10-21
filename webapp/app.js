import {imagePoint,WebcamCapture} from './gaze.js';
import {DwellCounter} from './fixations.js';
const $=id=>document.getElementById(id);
let image=null,cleanImage=null,points=[],samples=[],result=null,capture=null,busy=false,token=null;
let sessionRevision=null,recording=false,stopping=false,live=new DwellCounter(),outside=0,missing=0,inside=0;
let captureBase=[];
function dwellSettings(){return $('dwell-profile').value==='strict'?{radius:.035,max_gap_ms:150}:{radius:.08,max_gap_ms:400};}
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
  $('export-gaze').disabled=!points.length&&!samples.length;
}
function invalidate(){result=null;$('downloads').hidden=true;$('view').value='input';}
$('image-file').onchange=async event=>{
  if(busy||recording||capture?.calibrating)return status('Stop capture and wait for inference before changing image.');
  const file=event.target.files[0];if(!file)return;
  try{
    const url=URL.createObjectURL(file);try{image=await loadImage(url);}finally{URL.revokeObjectURL(url);}
    if(image.width*image.height>40e6)throw new Error('Choose an image under 40 megapixels.');
    const original=document.createElement('canvas');original.width=image.width;original.height=image.height;original.getContext('2d').drawImage(image,0,0);cleanImage=original.toDataURL('image/png');
    points=[];samples=[];sessionRevision=null;invalidate();$('image-name').textContent=file.name;$('empty').hidden=true;canvas.hidden=false;await redraw();status('Image ready. Add gaze points or import a CSV.');
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
function trackingSample(x,y,t,isRecording){
  const finite=Number.isFinite(x)&&Number.isFinite(y);
  let px=-1,py=-1;
  if(finite){[px,py]=imagePoint(x,y,canvas.getBoundingClientRect());}
  const onImage=finite&&px>=0&&px<=1&&py>=0&&py<=1;
  $('tracking-state').textContent=!finite?'Face not detected':onImage?'Gaze on image':'Gaze outside image';
  $('tracking-state').dataset.state=onImage?'ok':'warning';
  const cursor=$('gaze-cursor');cursor.hidden=!finite;
  if(finite){cursor.style.left=x+'px';cursor.style.top=y+'px';cursor.dataset.state=onImage?'ok':'warning';}
  if(isRecording&&recording){
    // Invalid-face sentinel ends a dwell; do not bridge over missing tracking.
    samples.push([px,py,t]);live.push(px,py,t);
    if(!finite)missing++;else if(!onImage)outside++;else{
      inside++;ctx.beginPath();ctx.arc(px*canvas.width,py*canvas.height,Math.max(2,canvas.width/230),0,Math.PI*2);ctx.fillStyle='#69efcb88';ctx.fill();
    }
    $('capture-stats').textContent=`${samples.length} samples · ${live.count} live fixations`;
    $('tracking-counts').textContent=`${inside} on image · ${outside} outside · ${missing} without face`;
    $('export-gaze').disabled=false;
    if(samples.length>=100000)stopRecording('Recording stopped at the sample limit.');
  }
}
function trackerStatus(message){
  status(message);
  if(capture&&!capture.valid&&!capture.calibrating&&recording)stopRecording(message);
}
$('camera-start').onclick=async()=>{
  if(!image)return status('Open an image before calibrating.');if(busy||recording)return;
  $('camera-start').disabled=true;$('record').disabled=true;$('start-record').disabled=true;capture?.close();
  capture=new WebcamCapture($('video'),trackingSample,trackerStatus);
  try{
    status('Step 1/2: loading camera calibration. Fixations on the image are recorded only after calibration.');
    await capture.start();
    $('record').disabled=false;$('start-record').disabled=false;$('capture-bar').hidden=false;$('tracking-feedback').hidden=false;
    $('capture-title').textContent='Step 2 of 2 · Image ready for gaze recording';
    $('view').value='input';await redraw();$('stage').scrollIntoView({block:'center',behavior:'instant'});
  }catch(error){status(error.message);$('capture-bar').hidden=true;$('gaze-cursor').hidden=true;}
  finally{$('camera-start').disabled=false;}
};
function startRecording(){
  if(busy||recording||stopping)return;
  try{
    if(!image)throw new Error('Open an image first.');
    if(!capture?.valid)throw new Error('Calibrate the camera first.');
    captureBase=points.map(p=>p.slice());samples=[];const settings=dwellSettings();live=new DwellCounter(settings.radius,100,settings.max_gap_ms);$('dwell-profile').disabled=true;inside=outside=missing=0;invalidate();recording=true;
    document.body.classList.add('capture-mode');redraw();capture.record();
    $('record').disabled=true;$('start-record').disabled=true;$('stop').disabled=false;$('stop-record').disabled=false;
    $('capture-title').textContent='Recording gaze on this image';$('capture-stats').textContent='0 samples · 0 live fixations';
    status('Recording. Look at the target structure. The gaze cursor and trace show incoming samples; press Stop & use fixations when finished.');
  }catch(error){recording=false;document.body.classList.remove('capture-mode');status(error.message);}
}
async function stopRecording(reason=''){
  if(!recording||stopping)return;
  stopping=true;recording=false;capture?.stop();live.flush();document.body.classList.remove('capture-mode');$('gaze-cursor').hidden=true;
  $('stop').disabled=true;$('stop-record').disabled=true;$('record').disabled=!capture?.valid;$('start-record').disabled=!capture?.valid;
  try{
    const data=await api('/api/fixations',{samples,...dwellSettings()});points=[...captureBase,...data.fixations];$('reprocess').disabled=!samples.length;invalidate();await redraw();
    $('capture-title').textContent=`Recording saved · ${data.fixations.length} new fixations`;
    $('capture-stats').textContent=`${samples.length} samples · ${data.fixations.length} derived fixations`;
    let sync='';
    if(sessionRevision!==null){
      try{await api('/api/capture',{revision:sessionRevision,fixations:points,samples});sync=data.fixations.length?' Fixations also sent to the desktop app.':' Raw samples also sent to the desktop app.';}
      catch(error){sync=' '+error.message;}
    }
    const message=data.fixations.length?`Collected ${data.fixations.length} fixations from ${samples.length} samples. They are plotted on the image; ready to segment.`:
      `Collected ${samples.length} raw samples but no ≥100 ms dwell groups. On image: ${inside}; outside: ${outside}; face missing: ${missing}. Keep gaze steady on the image, or export raw gaze to inspect it.`;
    status((reason?reason+' ':'')+message+sync);
  }catch(error){status(`Raw gaze remains available to export. ${error.message}`);$('export-gaze').disabled=!samples.length&&!points.length;}
  finally{stopping=false;$('dwell-profile').disabled=false;}
}
$('reprocess').onclick=async()=>{
  if(recording||busy||stopping||!samples.length)return;
  // Reuse the same replace-and-sync path; never duplicate previously derived points.
  recording=true;await stopRecording('Reprocessed saved gaze.');
};
$('record').onclick=startRecording;$('start-record').onclick=startRecording;
$('stop').onclick=()=>stopRecording();$('stop-record').onclick=()=>stopRecording();
$('camera-off').onclick=async()=>{
  if(recording)await stopRecording();capture?.close();$('record').disabled=true;$('start-record').disabled=true;$('stop').disabled=true;$('stop-record').disabled=true;
  $('gaze-cursor').hidden=true;document.body.classList.remove('capture-mode');$('tracking-state').textContent='Camera off';$('tracking-state').dataset.state='warning';status('Camera off. Saved gaze can still be exported or used for segmentation.');
};
function download(text,name,type){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('export-gaze').onclick=()=>{download('x,y,duration\n'+points.map(r=>r.join(',')).join('\n'),'gazerefine_fixations.csv','text/csv');if(samples.length)download('x,y,timestamp_ms\n'+samples.map(r=>r.join(',')).join('\n'),'gazerefine_samples.csv','text/csv');};
$('export-config').onclick=()=>{if(result)download(JSON.stringify(result.metadata,null,2),'gazerefine_settings.json','application/json');};
window.addEventListener('beforeunload',()=>capture?.close());
window.addEventListener('resize',()=>{if(capture?.valid&&(innerWidth!==capture.size[0]||innerHeight!==capture.size[1])){capture.close();$('gaze-cursor').hidden=true;$('record').disabled=true;$('start-record').disabled=true;if(recording)stopRecording('Viewport changed; recalibrate before recording again.');else status('Viewport changed. Recalibrate the webcam.');}});
try{
  const config=await (await fetch('/api/config')).json();token=config.token;
  const response=await fetch('/api/session',{headers:{'X-GazeRefine-Token':token}});
  if(response.ok){
    const data=await response.json();
    if(data.session){
      const session=data.session;image=await loadImage(session.image);cleanImage=session.image;points=session.fixations;sessionRevision=session.revision;
      $('image-name').textContent=session.name;$('empty').hidden=true;canvas.hidden=false;await redraw();
      status('Desktop image loaded automatically. Check the modality setting, then calibrate and record gaze on this image.');
    }
  }
}catch(error){status('Start this app with python scripts/serve_app.py to enable local CPU inference.');}
