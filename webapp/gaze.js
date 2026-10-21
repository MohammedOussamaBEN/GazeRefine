// Original integration code. The optional RealEye SDK is fetched only on opt-in.
export function imagePoint(x,y,rect){
  return [(x-rect.left)/rect.width,(y-rect.top)/rect.height];
}
export class WebcamCapture{
  constructor(video,onSample,onStatus){this.video=video;this.onSample=onSample;this.onStatus=onStatus;this.active=false;this.valid=false;this.cancelled=false;}
  async start(){
    // API verified against RealEye's 1.1.0 source; third-party license applies.
    const sdk=await import('https://esm.sh/@realeye-io/webcam-eyetracker-light-open@1.1.0');
    this.sdk=sdk;this.tracker=new sdk.WebcamETLight({delegate:'CPU',runningMode:'IMAGE'});
    try{
      await this.tracker.initialize();
      this.stream=await navigator.mediaDevices.getUserMedia({video:{width:640,height:480},audio:false});
      this.video.srcObject=this.stream;
      await this.video.play();
      await this.calibrate();
    }catch(error){this.close();throw error;}
  }
  frame(){
    const canvas=document.createElement('canvas');canvas.width=this.video.videoWidth;canvas.height=this.video.videoHeight;
    const ctx=canvas.getContext('2d');ctx.drawImage(this.video,0,0);return ctx.getImageData(0,0,canvas.width,canvas.height);
  }
  async calibrate(){
    const layer=document.querySelector('#calibration'),target=document.querySelector('#target');
    const size=[innerWidth,innerHeight];
    const points=this.sdk.getCalibrationPointsInPixels(this.sdk.getRecommendedPattern(),...size);
    const samples=[];this.cancelled=false;layer.hidden=false;
    const cancel=()=>{this.cancelled=true;};document.querySelector('#cancel-calibration').onclick=cancel;
    try{
      for(let i=0;i<points.length;i++){
        const p=points[i];target.style.left=p.x+'px';target.style.top=p.y+'px';
        document.querySelector('#calibration-message').textContent=`Look at the target · ${i+1}/${points.length}`;
        await new Promise(r=>setTimeout(r,700));
        for(let j=0;j<5;j++){
          if(this.cancelled)throw new Error('Calibration cancelled.');
          if(innerWidth!==size[0]||innerHeight!==size[1])throw new Error('Viewport changed; calibrate again.');
          samples.push({image:this.frame(),gazeX:p.x,gazeY:p.y});
          await new Promise(r=>setTimeout(r,85));
        }
      }
      await this.tracker.calibrate(samples);this.valid=true;this.size=size;this.onStatus('Calibrated. Keep your head and window still, then record gaze.');
    }finally{layer.hidden=true;}
  }
  record(){
    if(!this.valid)throw new Error('Calibrate the camera first.');
    this.active=true;
    const tick=()=>{
      if(!this.active)return;
      if(innerWidth!==this.size[0]||innerHeight!==this.size[1]){this.close();this.onStatus('Viewport changed. Recalibrate before recording.');return;}
      try{const p=this.tracker.predict(this.frame());if(p&&Number.isFinite(p.x)&&Number.isFinite(p.y))this.onSample(p.x,p.y,performance.now());}
      catch(error){this.close();this.onStatus(error.message);return;}
      this.timer=setTimeout(tick,40);
    };tick();
  }
  stop(){this.active=false;clearTimeout(this.timer);}
  close(){this.stop();this.valid=false;this.cancelled=true;this.stream?.getTracks().forEach(t=>t.stop());this.tracker?.dispose?.();}
}
