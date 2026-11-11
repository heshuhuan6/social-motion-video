import fs from 'node:fs';
import path from 'node:path';
import {parseArgs} from 'node:util';
const {values:v}=parseArgs({options:{out:{type:'string'},duration:{type:'string',default:'20'},bpm:{type:'string',default:'180'},fps:{type:'string',default:'30'},cuts:{type:'string',default:''},break:{type:'string'},help:{type:'boolean'}}});
if(v.help){console.log('node make-beat.mjs --out music.wav [--duration 20 --bpm 180 --fps 30 --cuts 30,60,90 --break 12.66,13]');process.exit(0);}
const duration=Number(v.duration),bpm=Number(v.bpm),fps=Number(v.fps);
if(!v.out||![duration,bpm,fps].every(x=>Number.isFinite(x)&&x>0)||duration>600)throw Error('Specify --out and positive finite duration (max 600s), bpm and fps.');
const cutFrames=v.cuts?v.cuts.split(',').map(Number):[];
if(cutFrames.some(x=>!Number.isInteger(x)||x<=0||x>=duration*fps))throw Error('Cuts must be integer frame numbers inside video.');
const gap=v.break?v.break.split(',').map(Number):null;
if(gap&&(gap.length!==2||!gap.every(Number.isFinite)||gap[0]<0||gap[1]<=gap[0]||gap[1]>duration))throw Error('Break must be start,end seconds inside video.');
const sr=48000,n=Math.round(sr*duration),spb=60/bpm;
const output=path.resolve(v.out);
if(fs.existsSync(output)||fs.existsSync(output+'.beats.json'))throw Error('Output already exists; choose a new version.');
fs.mkdirSync(path.dirname(output),{recursive:true});
const l=new Float64Array(n),r=new Float64Array(n);
let seed=180;const rand=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/2147483648-1;};
const hz=m=>440*2**((m-69)/12);
function add(at,dur,fn,amp=1,pan=0){const start=Math.round(at*sr),len=Math.round(dur*sr);for(let j=0;j<len;j++){const i=start+j;if(i<0||i>=n)continue;const v=fn(j/sr)*amp;l[i]+=v*Math.sqrt((1-pan)/2);r[i]+=v*Math.sqrt((1+pan)/2);}}
function kick(t,amp=.6){add(t,.26,s=>Math.sin(2*Math.PI*(48*s+85*.018*(1-Math.exp(-s/.018))))*Math.exp(-s*20),amp);add(t,.018,s=>rand()*Math.exp(-s*230),.1);}
function snare(t){add(t,.16,s=>(rand()*.8+Math.sin(2*Math.PI*185*s)*.2)*Math.exp(-s*30)*Math.min(1,s/.001),.25,.08);add(t+.018,.06,s=>rand()*Math.exp(-s*64),.06,-.2);}
function pluck(t,m,amp=.13,pan=0){const h=hz(m);add(t,.33,s=>Math.sin(2*Math.PI*h*s+2.7*Math.sin(2*Math.PI*h*2*s)*Math.exp(-s*20))*Math.exp(-s*14)*Math.min(1,s/.003),amp,pan);}
function bass(t,m){const h=hz(m);add(t,.28,s=>(Math.sin(2*Math.PI*h*s)+.24*Math.sin(4*Math.PI*h*s)+.1*Math.sin(6*Math.PI*h*s))*Math.exp(-s*9)*Math.min(1,s/.008),.31);}
const roots=[33,29,36,31];const arps=[[69,72,76,79],[65,69,72,76],[67,72,76,79],[67,71,74,79]];
for(let bar=0;bar<Math.ceil(duration/(4*spb));bar++){
 const t=bar*4*spb,root=roots[bar%4],arp=arps[bar%4];
 for(let b=0;b<4;b++){
  const at=t+b*spb;
  kick(at,b%2===0?.56:.39);if(b%2===1)snare(at);
  bass(at+.025,root+(b===3?12:0));
  for(let k=0;k<2;k++)add(at+k*spb/2,.045,s=>rand()*Math.exp(-s*110),k?.06:.035,k?.4:-.4);
  pluck(at+spb/2,arp[(b+bar)%4],.16,Math.sin(b+bar)*.45);
  if(b===3&&bar%2===1){snare(at+spb*.75);pluck(at+spb*.75,arp[3]+12,.09,-.4);}
 }
 // Chord stab on the first and third beat: short, rhythmic, no long pad.
 for(const b of [0,2])for(const [j,interval] of [0,7,12,15].entries()){
  const h=hz(root+24+interval);add(t+b*spb+.025,.22,s=>(Math.sin(2*Math.PI*h*s)+.12*Math.sin(2*Math.PI*h*3*s))*Math.exp(-s*14)*Math.min(1,s/.006),.07,(j-1.5)*.25);
 }
}
// A brief rhythmic air pocket makes the return at 13s hit harder.
if(gap)for(let i=Math.floor(gap[0]*sr);i<Math.min(n,Math.round(gap[1]*sr));i++){l[i]*=.22;r[i]*=.22;}
for(const t of [0,...cutFrames.map(f=>f/fps)]){add(t,.42,s=>Math.sin(2*Math.PI*(38*s+60*.03*(1-Math.exp(-s/.03))))*Math.exp(-s*9),.55);}
for(const frame of cutFrames){const t=frame/fps;add(t-.1,.2,s=>(rand()*.6+Math.sin(2*Math.PI*(160*s+1800*s*s))*.2)*Math.sin(Math.PI*s/.2),.20,-.25);kick(t,.28);}
for(const frame of [0,...cutFrames])pluck(frame/fps,frame%24?84:79,.14,.25);
// Half-beat stereo slap, then a controlled fade at the end of the final bar.
for(let i=n-1;i>=0;i--){if(i>sr*.12){l[i]+=r[i-Math.round(sr*.12)]*.1;r[i]+=l[i-Math.round(sr*.10)]*.1;}}
let peak=0;for(let i=0;i<n;i++){const t=i/sr,g=Math.max(0,Math.min(1,t/.004,(duration-t)/.24));l[i]=Math.tanh(l[i]*1.15)*g;r[i]=Math.tanh(r[i]*1.15)*g;peak=Math.max(peak,Math.abs(l[i]),Math.abs(r[i]));}
const out=Buffer.alloc(44+n*4);out.write('RIFF');out.writeUInt32LE(out.length-8,4);out.write('WAVEfmt ',8);out.writeUInt32LE(16,16);out.writeUInt16LE(1,20);out.writeUInt16LE(2,22);out.writeUInt32LE(sr,24);out.writeUInt32LE(sr*4,28);out.writeUInt16LE(4,32);out.writeUInt16LE(16,34);out.write('data',36);out.writeUInt32LE(n*4,40);
for(let i=0;i<n;i++){out.writeInt16LE(Math.round(l[i]/peak*29000),44+i*4);out.writeInt16LE(Math.round(r[i]/peak*29000),46+i*4);}
fs.writeFileSync(output,out);
fs.writeFileSync(output+'.beats.json',JSON.stringify({bpm,fps,framesPerBeat:fps*60/bpm,duration,cutFrames,beatFrames:Array.from({length:Math.ceil(duration/spb)},(_,i)=>Math.round(i*fps*spb))},null,2));
console.log(JSON.stringify({output,bpm,duration,framesPerBeat:fps*60/bpm}));
