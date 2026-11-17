import {spawn} from 'node:child_process';

export const FRAME_WIDTH=256,FRAME_HEIGHT=144,FRAME_FPS=24;

// 与拆解报告同口径：相邻灰度帧，差值>32且面积>=12%，按强度做±0.25秒峰抑制。
export function visualChangeTracker({width=FRAME_WIDTH,height=FRAME_HEIGHT,fps=FRAME_FPS}={}){
  let previous;const candidates=[];
  return {
    push(frame,time){if(previous){let count=0;for(let i=0;i<frame.length;i++)if(Math.abs(frame[i]-previous[i])>32)count++;const strength=count/(width*height);if(strength>=.12)candidates.push({time,strength});}previous=Buffer.from(frame);},
    finish(duration){const peaks=[];for(const candidate of [...candidates].sort((a,b)=>b.strength-a.strength||a.time-b.time))if(!peaks.some(p=>Math.abs(p.time-candidate.time)<=.25+1e-8))peaks.push(candidate);peaks.sort((a,b)=>a.time-b.time);return {fps,width,height,pixelDelta:32,changedFraction:.12,suppressionSeconds:.25,events:peaks.length,eventsPerSecond:peaks.length/duration,peaks};}
  };
}

export function soften(frame,width=FRAME_WIDTH,height=FRAME_HEIGHT){
  const out=Buffer.alloc(frame.length);
  for(let y=1;y<height-1;y++)for(let x=1;x<width-1;x++){
    let sum=0;for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++)sum+=frame[(y+dy)*width+x+dx];out[y*width+x]=Math.round(sum/9);
  }
  return out;
}

export function changedArea(a,b,{delta=10,width=FRAME_WIDTH,height=FRAME_HEIGHT,roi=[.05,.07,.95,.91]}={}){
  let changed=0,count=0;
  for(let y=Math.floor(height*roi[1]);y<Math.ceil(height*roi[3]);y++)for(let x=Math.floor(width*roi[0]);x<Math.ceil(width*roi[2]);x++){
    count++;if(Math.abs(a[y*width+x]-b[y*width+x])>delta)changed++;
  }
  return changed/count;
}

export function stillTracker(scenes,{pixelDelta=10,changedFraction=.002,width=FRAME_WIDTH,height=FRAME_HEIGHT,roi}={}){
  const results=scenes.map(s=>({id:s.id,start:s.B,end:s.E,changes:[],stillRuns:[],frames:0}));
  let current=-1,anchor,lastTime;
  function finish(){if(current>=0&&anchor)results[current].stillRuns.push({start:lastTime,end:results[current].end,seconds:results[current].end-lastTime});}
  return {
    push(frame,time){
      const index=scenes.findIndex(s=>time>=s.B-1e-8&&time<s.E-1e-8);if(index<0)return;
      const smooth=soften(frame,width,height);
      if(index!==current){finish();current=index;anchor=smooth;lastTime=scenes[index].B;}
      const row=results[index];row.frames++;
      if(changedArea(anchor,smooth,{delta:pixelDelta,width,height,roi})>=changedFraction){
        row.stillRuns.push({start:lastTime,end:time,seconds:time-lastTime});row.changes.push(time);anchor=smooth;lastTime=time;
      }
    },
    finish(){finish();return results.map(r=>({...r,longestStillSeconds:Math.max(0,...r.stillRuns.map(s=>s.seconds))}));}
  };
}

export function analyzeRendered(file,scenes,options={}){
  return new Promise((resolve,reject)=>{
    const tracker=stillTracker(scenes,options),changes=visualChangeTracker(),size=FRAME_WIDTH*FRAME_HEIGHT;
    const process=spawn('ffmpeg',['-hide_banner','-loglevel','error','-i',file,'-an','-vf',`fps=${FRAME_FPS},scale=${FRAME_WIDTH}:${FRAME_HEIGHT}:flags=area,format=gray`,'-f','rawvideo','pipe:1']);
    let pending=Buffer.alloc(0),frames=0,stderr='';
    process.stdout.on('data',chunk=>{pending=Buffer.concat([pending,chunk]);while(pending.length>=size){const frame=pending.subarray(0,size);tracker.push(frame,frames/FRAME_FPS);changes.push(frame,frames/FRAME_FPS);frames++;pending=pending.subarray(size);}});
    process.stderr.on('data',chunk=>{stderr=(stderr+chunk).slice(-1500);});process.on('error',reject);
    process.on('close',code=>{if(code!==0)return reject(new Error('成片逐帧分析失败：'+stderr));const result=tracker.finish();if(result.some(s=>!s.frames)||frames/FRAME_FPS+1/FRAME_FPS<Math.max(...scenes.map(s=>s.E)))return reject(new Error('成片没有覆盖全部镜头，不能验收全片'));resolve({fps:FRAME_FPS,width:FRAME_WIDTH,height:FRAME_HEIGHT,frames,scenes:result,visualChange:changes.finish(frames/FRAME_FPS)});});
  });
}
