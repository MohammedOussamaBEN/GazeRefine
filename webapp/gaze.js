// Optional RealEye SDK is fetched only after explicit user opt-in.
export function imagePoint(x,y,rect){return [(x-rect.left)/rect.width,(y-rect.top)/rect.height];}
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
export class WebcamCapture{
  constructor(video,onSample,onStatus){this.video=video;this.onSample=onSample;this.onStatus=onStatus;this.active=false;this.running=false;this.valid=false;this.cancelled=false;this.calibrating=false;}
  async start(){
    const sdk=await import('https://esm.sh/@realeye-io/webcam-eyetracker-light-open@1.1.0');
    this.sdk=sdk;this.tracker=new sdk.WebcamETLight({delegate:'CPU',runningMode:'IMAGE'});
    try{
      await this.tracker.initialize();
      this.stream=await navigator.mediaDevices.getUserMedia({video:{width:640,height:480},audio:false});
      this.video.srcObject=this.stream;this.video.hidden=false;await this.video.play();
      if(!this.video.videoWidth)await new Promise(resolve=>this.video.addEventListener('loadeddata',resolve,{once:true}));
      await this.calibrate();this.running=true;this.tick();
    }catch(error){this.close();throw error;}
  }
  frame(){
    if(!this.video.videoWidth||this.video.readyState<2)throw new Error('Webcam frame not ready. Check camera access and retry.');
    this.frameCanvas??=document.createElement('canvas');const canvas=this.frameCanvas;
    canvas.width=this.video.videoWidth;canvas.height=this.video.videoHeight;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(this.video,0,0);return ctx.getImageData(0,0,canvas.width,canvas.height);
  }
  async calibrate(){
    const layer=document.querySelector('#calibration'),target=document.querySelector('#target');
    const message=document.querySelector('#calibration-message');
    const size=[innerWidth,innerHeight];
    const points=this.sdk.getCalibrationPointsInPixels(this.sdk.getRecommendedPattern(),...size);
    const samples=[];this.cancelled=false;this.calibrating=true;layer.hidden=false;document.body.classList.add('calibrating');
    document.querySelector('#cancel-calibration').onclick=()=>{this.cancelled=true;};
    try{
      for(let i=0;i<points.length;i++){
        const p=points[i];target.style.left=p.x+'px';target.style.top=p.y+'px';
        message.textContent=`Look at the target · ${i+1}/${points.length} · image recording starts after calibration`;
        await pause(700);
        let collected=0;
        for(let attempt=0;attempt<25&&collected<5;attempt++){
          if(this.cancelled)throw new Error('Calibration cancelled. Your image is still loaded.');
          if(innerWidth!==size[0]||innerHeight!==size[1])throw new Error('Viewport changed; calibrate again.');
          const frame=this.frame();
          if(this.tracker.detectFace(frame)){
            samples.push({image:frame,gazeX:p.x,gazeY:p.y});collected++;
            message.textContent=`Look at the target · ${i+1}/${points.length} · ${collected}/5 camera samples`;
          }else message.textContent=`Face not detected · target ${i+1}/${points.length}. Face the camera and keep your head still.`;
          await pause(85);
        }
        if(collected<5)throw new Error('Face could not be tracked reliably. Improve lighting and camera position, then calibrate again.');
      }
      target.hidden=true;message.textContent='Fitting camera calibration… Your image will return next.';
      await pause(100);await this.tracker.calibrate(samples);
      if(this.cancelled)throw new Error('Calibration cancelled.');
      this.valid=true;this.size=size;
      this.onStatus('Calibration complete. Your image is ready. Click Start recording, look at the structure, then Stop & use fixations.');
    }finally{target.hidden=false;layer.hidden=true;this.calibrating=false;document.body.classList.remove('calibrating');}
  }
  tick(){
    if(!this.running)return;
    if(innerWidth!==this.size[0]||innerHeight!==this.size[1]){this.close();this.onStatus('Viewport changed. Recalibrate the camera.');return;}
    try{
      const p=this.tracker.predict(this.frame());
      this.onSample(p&&Number.isFinite(p.x)?p.x:null,p&&Number.isFinite(p.y)?p.y:null,performance.now(),this.active);
    }catch(error){this.close();this.onStatus(`Gaze tracker stopped: ${error.message}`);return;}
    this.timer=setTimeout(()=>this.tick(),40);
  }
  record(){if(!this.valid)throw new Error('Calibrate the camera first.');this.active=true;}
  stop(){this.active=false;}
  close(){this.active=false;this.running=false;this.valid=false;this.cancelled=true;clearTimeout(this.timer);this.stream?.getTracks().forEach(t=>t.stop());this.tracker?.dispose?.();this.video.hidden=true;}
}
