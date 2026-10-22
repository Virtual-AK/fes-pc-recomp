// Launcher music: an original loop made live with the browser's audio engine (no audio files, nothing from the game).
// Laid-back 86 BPM groove in B minor: electric piano, bass, soft pad, a short lead line, swung drums and finger snaps.
// LM.start() after the first click, LM.setVolume(0..100), LM.setPaused(true/false).  LM.build()/LM.step() are also used by the tests.
(function(){
  const BPM=86, STEP=60/BPM/4, BAR=16, BARS=16, LOOP=BAR*BARS, SWING=0.16;
  const mtof=m=>440*Math.pow(2,(m-69)/12);
  // chord per bar (8 bars, played twice): rootless voicings for the keys, bass root
  const C={
    Bm9:{k:[62,66,69,73],b:35,f:42}, G9:{k:[59,62,66,69],b:43,f:50}, Em9:{k:[55,59,62,66],b:40,f:47},
    F7s:{k:[59,64,66,73],b:42,f:49}, F7b9:{k:[58,61,64,67],b:42,f:49}, G7:{k:[55,59,66,69],b:43,f:50}, F7m:{k:[57,61,64,66],b:42,f:49}
  };
  const PROG=[['Bm9'],['G9'],['Em9'],['F7s','F7b9'],['G7'],['F7m'],['Em9'],['F7b9']];
  // lead line, per bar of the 8-bar cycle: [step, midi note, length in steps]
  const LEAD=[
    [[4,78,3],[8,76,2],[10,74,2],[12,71,4]],
    [[0,69,4],[6,71,2],[8,74,6]],
    [[2,76,2],[4,74,2],[6,71,2],[8,67,4],[12,71,4]],
    [[0,73,6],[8,70,2],[10,73,2],[12,76,4]],
    [[0,71,2],[2,74,2],[4,78,4],[8,76,2],[10,74,2],[12,71,4]],
    [[0,73,4],[6,76,2],[8,78,4],[14,76,2]],
    [[0,74,4],[4,71,2],[6,67,2],[8,71,4],[12,74,4]],
    [[0,73,3],[4,70,3],[8,79,2],[10,78,2],[12,76,4]]
  ];
  const KICK=[[0,1],[6,.7],[10,.9]], KICK_ODD=[[0,1],[6,.7],[10,.9],[15,.45]];

  function noiseBuf(ctx){const n=ctx.sampleRate|0,b=ctx.createBuffer(1,n,ctx.sampleRate),d=b.getChannelData(0);for(let i=0;i<n;i++)d[i]=Math.random()*2-1;return b;}
  function impulse(ctx,sec){const n=(ctx.sampleRate*sec)|0,b=ctx.createBuffer(2,n,ctx.sampleRate);for(let c=0;c<2;c++){const d=b.getChannelData(c);for(let i=0;i<n;i++)d[i]=(Math.random()*2-1)*Math.pow(1-i/n,2.6);}return b;}

  // build the instrument bus on any audio context (live or offline); returns {step(n,t)} and the master gain
  function build(ctx){
    const master=ctx.createGain();master.gain.value=0.55;
    const comp=ctx.createDynamicsCompressor();comp.threshold.value=-16;comp.ratio.value=3;comp.attack.value=0.01;comp.release.value=0.2;
    master.connect(comp);comp.connect(ctx.destination);
    const rev=ctx.createConvolver();rev.buffer=impulse(ctx,2.2);const revG=ctx.createGain();revG.gain.value=0.5;rev.connect(revG);revG.connect(master);
    const dly=ctx.createDelay(1);dly.delayTime.value=STEP*3;const fb=ctx.createGain();fb.gain.value=0.32;const dlp=ctx.createBiquadFilter();dlp.type='lowpass';dlp.frequency.value=2600;
    dly.connect(dlp);dlp.connect(fb);fb.connect(dly);const dlyG=ctx.createGain();dlyG.gain.value=0.5;dlp.connect(dlyG);dlyG.connect(master);dlyG.connect(rev);
    const keys=ctx.createGain();keys.gain.value=0.8;const klp=ctx.createBiquadFilter();klp.type='lowpass';klp.frequency.value=4200;
    const trem=ctx.createGain();trem.gain.value=1;const lfo=ctx.createOscillator();lfo.frequency.value=4.6;const lfoG=ctx.createGain();lfoG.gain.value=0.12;lfo.connect(lfoG);lfoG.connect(trem.gain);lfo.start();
    keys.connect(klp);klp.connect(trem);trem.connect(master);const ksend=ctx.createGain();ksend.gain.value=0.35;trem.connect(ksend);ksend.connect(rev);
    const padB=ctx.createGain();padB.gain.value=0.7;const plp=ctx.createBiquadFilter();plp.type='lowpass';plp.frequency.value=800;padB.connect(plp);plp.connect(master);const psend=ctx.createGain();psend.gain.value=0.5;plp.connect(psend);psend.connect(rev);
    const bassB=ctx.createGain();bassB.gain.value=0.42;const blp=ctx.createBiquadFilter();blp.type='lowpass';blp.frequency.value=520;bassB.connect(blp);blp.connect(master);
    const drum=ctx.createGain();drum.gain.value=0.85;drum.connect(master);const dsend=ctx.createGain();dsend.gain.value=0.22;drum.connect(dsend);dsend.connect(rev);
    const leadB=ctx.createGain();leadB.gain.value=0.75;leadB.connect(master);leadB.connect(dly);const lsend=ctx.createGain();lsend.gain.value=0.4;leadB.connect(lsend);lsend.connect(rev);
    const nb=noiseBuf(ctx);

    function env(g,t,a,peak,d,end){g.gain.setValueAtTime(0.0001,t);g.gain.linearRampToValueAtTime(peak,t+a);g.gain.exponentialRampToValueAtTime(0.0001,t+a+d);return t+a+d+(end||0.02);}
    function noise(t,dur,type,freq,q,peak,dest){const s=ctx.createBufferSource();s.buffer=nb;s.loop=true;const f=ctx.createBiquadFilter();f.type=type;f.frequency.value=freq;f.Q.value=q;const g=ctx.createGain();s.connect(f);f.connect(g);g.connect(dest);const e=env(g,t,0.002,peak,dur);s.start(t,Math.random()*0.5);s.stop(e);}
    function kick(t,v){const o=ctx.createOscillator(),g=ctx.createGain();o.type='sine';o.frequency.setValueAtTime(135,t);o.frequency.exponentialRampToValueAtTime(46,t+0.11);o.connect(g);g.connect(drum);const e=env(g,t,0.002,0.6*v,0.3);o.start(t);o.stop(e);noise(t,0.015,'highpass',1800,0.7,0.12*v,drum);}
    function snare(t,v){noise(t,0.2,'bandpass',1900,0.8,0.55*v,drum);const o=ctx.createOscillator(),g=ctx.createGain();o.type='triangle';o.frequency.setValueAtTime(215,t);o.frequency.exponentialRampToValueAtTime(150,t+0.08);o.connect(g);g.connect(drum);const e=env(g,t,0.002,0.3*v,0.1);o.start(t);o.stop(e);}
    function snap(t,v){noise(t,0.05,'bandpass',2600,3,0.5*v,drum);noise(t+0.004,0.035,'highpass',5200,0.7,0.2*v,drum);}
    function hat(t,v,open){noise(t,open?0.22:0.04,'highpass',7200,0.7,0.34*v,drum);}
    function shaker(t,v){noise(t,0.06,'bandpass',6200,1.2,0.2*v,drum);}
    function bass(t,m,len,v){const f=mtof(m),o=ctx.createOscillator(),o2=ctx.createOscillator(),g=ctx.createGain();o.type='sine';o2.type='triangle';o.frequency.value=f;o2.frequency.value=f;const g2=ctx.createGain();g2.gain.value=0.25;o.connect(g);o2.connect(g2);g2.connect(g);g.connect(bassB);
      g.gain.setValueAtTime(0.0001,t);g.gain.linearRampToValueAtTime(0.6*v,t+0.012);g.gain.setTargetAtTime(0.0001,t+len*STEP*0.9,0.06);o.start(t);o2.start(t);o.stop(t+len*STEP+0.4);o2.stop(t+len*STEP+0.4);}
    function key(t,m,len,v){const f=mtof(m),c=ctx.createOscillator(),md=ctx.createOscillator(),mg=ctx.createGain(),g=ctx.createGain();c.type='sine';md.type='sine';c.frequency.value=f;md.frequency.value=f;
      mg.gain.setValueAtTime(f*1.6,t);mg.gain.exponentialRampToValueAtTime(f*0.25,t+0.35);md.connect(mg);mg.connect(c.frequency);
      const tine=ctx.createOscillator(),tg=ctx.createGain();tine.type='sine';tine.frequency.value=f*7;tg.gain.setValueAtTime(0.08*v,t);tg.gain.exponentialRampToValueAtTime(0.0001,t+0.12);tine.connect(tg);tg.connect(g);
      c.connect(g);g.connect(keys);const dur=len*STEP;g.gain.setValueAtTime(0.0001,t);g.gain.linearRampToValueAtTime(0.2*v,t+0.006);g.gain.setTargetAtTime(0.045*v,t+0.02,0.35);g.gain.setTargetAtTime(0.0001,t+dur,0.09);
      [c,md,tine].forEach(o=>{o.start(t);o.stop(t+dur+0.6);});}
    function pad(t,ms,dur){ms.forEach(m=>{[-6,6].forEach(dt=>{const o=ctx.createOscillator(),g=ctx.createGain();o.type='sawtooth';o.frequency.value=mtof(m-12);o.detune.value=dt;o.connect(g);g.connect(padB);
      g.gain.setValueAtTime(0.0001,t);g.gain.linearRampToValueAtTime(0.045,t+0.5);g.gain.setValueAtTime(0.045,t+dur-0.3);g.gain.linearRampToValueAtTime(0.0001,t+dur+0.5);o.start(t);o.stop(t+dur+0.6);});});}
    function lead(t,m,len,v){const f=mtof(m),o=ctx.createOscillator(),o2=ctx.createOscillator(),g=ctx.createGain(),vib=ctx.createOscillator(),vg=ctx.createGain();o.type='triangle';o2.type='sine';o.frequency.value=f;o2.frequency.value=f*2;
      vib.frequency.value=5.2;vg.gain.setValueAtTime(0,t);vg.gain.linearRampToValueAtTime(f*0.006,t+0.35);vib.connect(vg);vg.connect(o.frequency);vg.connect(o2.frequency);const g2=ctx.createGain();g2.gain.value=0.12;o2.connect(g2);g2.connect(g);o.connect(g);g.connect(leadB);
      const dur=len*STEP;g.gain.setValueAtTime(0.0001,t);g.gain.linearRampToValueAtTime(0.32*v,t+0.03);g.gain.setTargetAtTime(0.2*v,t+0.05,0.2);g.gain.setTargetAtTime(0.0001,t+dur,0.07);[o,o2,vib].forEach(x=>{x.start(t);x.stop(t+dur+0.5);});}

    // schedule everything that happens on step n of the loop at time t
    function step(n,t){
      const s=n%LOOP, bar=(s/BAR)|0, st=s%BAR, cyc=bar%8, pass=(bar/8)|0, odd=bar%2===1;
      const when=t+(st%2===1?SWING*STEP:0)+(Math.random()-0.5)*0.004;   // swung sixteenths, a little human
      const hv=()=>0.8+Math.random()*0.2;
      // drums
      (odd?KICK_ODD:KICK).forEach(([k,v])=>{if(st===k)kick(when,v*hv());});
      if(st===4||st===12){snare(when,hv());snap(when,hv());}
      if(st===15&&!odd)snare(when,0.25);
      if(st%2===0)hat(when,(st%4===0?1:0.6)*hv(),false);
      if(st===14&&odd)hat(when,0.9,true);
      if(pass===1&&st%4===2)shaker(when,hv());
      if(pass===1&&bar===15&&st>=12)snare(when,0.35+0.1*(st-12));
      // harmony per half bar for the two-chord bar
      const chords=PROG[cyc], half=chords.length===2, ch=C[chords[half&&st>=8?1:0]];
      if(st===0){pad(when,C[chords[0]].k,BAR*STEP*(half?0.55:1));}
      if(half&&st===8){pad(when,C[chords[1]].k,BAR*STEP*0.5);}
      // keys comp
      const comp=half?[[0,5,1],[6,2,.6],[8,5,.9],[14,2,.55]]:[[0,6,1],[7,2,.6],[10,4,.75]];
      comp.forEach(([cs,len,v])=>{if(st===cs)ch.k.forEach((m,i)=>key(when+i*0.006,m,len,v*hv()));});
      // bass
      const bb=[[0,5,1,ch.b],[7,2,.7,ch.b+12],[10,4,.85,ch.f-12+(half&&st>=8?0:0)],[14,2,.6,ch.b]];
      if(half)bb.splice(1,3,[8,5,1,ch.b],[14,2,.6,ch.b+12]);
      bb.forEach(([bs,len,v,m])=>{if(st===bs)bass(when,m,len,v*hv());});
      // lead
      LEAD[cyc].forEach(([ls,m,len])=>{if(st===ls)lead(when,m+(pass===1&&bar===15?0:0),len,0.9+Math.random()*0.1);});
      if(pass===1)LEAD[cyc].forEach(([ls,m,len])=>{if(st===ls&&len>=4)lead(when+0.01,m+12,len,0.35);});
    }
    return {master:master,step:step,STEP:STEP,LOOP:LOOP,BAR:BAR};
  }

  const LM={BPM:BPM,LOOP:LOOP,build:build,ctx:null,eng:null,vol:70,paused:false,started:false,timer:null,next:0,n:0};
  LM.level=v=>Math.pow(Math.max(0,Math.min(100,v))/100,1.6)*0.9;
  LM.start=function(){
    if(LM.started)return;
    const AC=window.AudioContext||window.webkitAudioContext;if(!AC)return;
    try{LM.ctx=new AC();LM.eng=build(LM.ctx);LM.started=true;LM.apply();}catch(e){LM.started=false;}
  };
  LM.apply=function(){
    if(!LM.started)return;
    const c=LM.ctx,on=!LM.paused&&LM.vol>0;
    LM.eng.master.gain.setTargetAtTime(on?LM.level(LM.vol):0,c.currentTime,0.08);
    if(on&&!LM.timer){
      if(c.state==='suspended')c.resume();
      LM.next=c.currentTime+0.12;
      LM.timer=setInterval(()=>{while(LM.next<c.currentTime+0.25){LM.eng.step(LM.n,LM.next);LM.n=(LM.n+1)%LOOP;LM.next+=STEP;}},40);
    }else if(!on&&LM.timer){setTimeout(()=>{if(!(!LM.paused&&LM.vol>0)&&LM.timer){clearInterval(LM.timer);LM.timer=null;}},400);}
  };
  LM.setVolume=function(v){LM.vol=v;LM.apply();};
  LM.setPaused=function(p){LM.paused=!!p;LM.apply();};
  window.LM=LM;
})();
