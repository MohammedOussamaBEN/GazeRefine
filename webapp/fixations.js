// Incremental live counter matching the server's documented dwell grouping.
export class DwellCounter {
  constructor(radius=.035,minDuration=100,maxGap=150){this.radius=radius;this.minDuration=minDuration;this.maxGap=maxGap;this.groups=[];this.group=null;}
  flush(){
    const g=this.group;
    if(g&&g.n>=2&&g.last-g.first>=this.minDuration)this.groups.push([g.x/g.n,g.y/g.n,g.last-g.first]);
    this.group=null;
  }
  push(x,y,t){
    if(!Number.isFinite(x)||!Number.isFinite(y)||!Number.isFinite(t)||x<0||x>1||y<0||y>1){this.flush();return;}
    let g=this.group;
    if(g&&(t-g.last>this.maxGap||Math.hypot(x-g.x/g.n,y-g.y/g.n)>this.radius)){this.flush();g=null;}
    if(!g)this.group={x,y,n:1,first:t,last:t};
    else{g.x+=x;g.y+=y;g.n++;g.last=t;}
  }
  get count(){const g=this.group;return this.groups.length+(g&&g.n>=2&&g.last-g.first>=this.minDuration?1:0);}
}
