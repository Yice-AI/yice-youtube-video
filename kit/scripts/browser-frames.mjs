import fs from 'node:fs';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {performance} from 'node:perf_hooks';

// 采集页面自己的像素。滚动可逐帧推进；网页演示按真实时间采样，不寻址/改写视频内容。
export async function recordBrowserFrames(page,file,{seconds=6,fps=15,step,realtime=false}={}){
  const part=file+'.part.mp4';let stderr='',pipeError;
  const encoder=spawn('ffmpeg',['-hide_banner','-loglevel','error','-y','-f','image2pipe','-vcodec','png','-framerate',String(fps),'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',part],{stdio:['pipe','ignore','pipe']});
  encoder.stderr.on('data',chunk=>{stderr=(stderr+chunk).slice(-2000);});
  encoder.stdin.on('error',error=>{pipeError=error;});
  const closed=new Promise((resolve,reject)=>{encoder.once('error',reject);encoder.once('close',code=>code===0?resolve():reject(new Error(stderr||`ffmpeg退出${code}`)));});closed.catch(()=>{});
  const began=performance.now(),count=Math.round(seconds*fps);
  try{
    for(let i=0;i<count;i++){
      if(realtime){const wait=began+i*1000/fps-performance.now();if(wait>0)await new Promise(r=>setTimeout(r,wait));}
      if(step)await step(i/Math.max(1,count-1));
      if(pipeError)throw pipeError;
      const pixels=await page.screenshot();
      if(!encoder.stdin.write(pixels))await once(encoder.stdin,'drain');
    }
    encoder.stdin.end();await closed;fs.renameSync(part,file);
    return {seconds,fps,sampleWallSeconds:(performance.now()-began)/1000,audio:false};
  }catch(error){encoder.kill();await closed.catch(()=>{});fs.rmSync(part,{force:true});throw error;}
}
