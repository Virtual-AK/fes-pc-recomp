// Launcher music: original loops made live with the browser's audio engine (no audio files, nothing from the game).
// Track 1 "Late Train": laid-back 86 BPM groove in B minor (electric piano, bass, soft pad, lead, swung drums, finger snaps).
// Track 2 "Rooftop Sun": bright 104 BPM D major (plucked lead, funky bass, light four-on-the-floor).
// Track 3 "Velvet Hour": slow 70 BPM A minor (wide pad, bells, brushed half-time drums).
// With the AUTO choice the tracks play one after the other; LM.setTrack(0..2) or -1 for AUTO.
// LM.start() after the first click, LM.setVolume(0..100), LM.setPaused(true/false).  LM.build()/LM.step() are also used by the tests.
(function(){
  const BPM=86, BAR=16, BARS=16;
  const TRACKS=[{name:'Late Train',bpm:86,swing:0.16},{name:'Rooftop Sun',bpm:104,swing:0.05},{name:'Velvet Hour',bpm:70,swing:0.2}];
  TRACKS.forEach(t=>{t.step=60/t.bpm/4;t.loop=BAR*BARS;});
  const STEP=TRACKS[0].step, LOOP=BAR*BARS;
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
  // track 2: D major
  const C2={
    D9:{k:[66,69,73,76],b:38,f:45}, Bm7:{k:[62,66,69,73],b:35,f:42}, Gm7:{k:[59,62,66,69],b:43,f:50}, A7s:{k:[62,64,67,69],b:45,f:40},
    F7m:{k:[57,61,64,66],b:42,f:49}, Em9:{k:[55,59,62,66],b:40,f:47}, A7:{k:[55,61,64,67],b:45,f:52}
  };
  const PROG2=[['D9'],['Bm7'],['Gm7'],['A7s'],['D9'],['F7m'],['Em9'],['A7']];
  const LEAD2=[
    [[0,81,2],[3,78,1],[4,81,2],[8,83,2],[11,81,1],[12,78,4]],
    [[0,78,2],[2,81,2],[6,83,2],[8,85,4],[14,83,2]],
    [[0,83,3],[4,81,2],[6,78,2],[8,76,4],[12,78,4]],
    [[0,81,2],[2,83,2],[4,85,4],[10,83,2],[12,81,4]],
    [[0,86,2],[3,85,1],[4,83,2],[8,81,2],[10,78,2],[12,74,4]],
    [[0,73,2],[2,76,2],[4,78,4],[10,81,2],[12,85,4]],
    [[0,83,4],[6,81,2],[8,78,2],[10,76,2],[12,74,4]],
    [[0,73,2],[2,76,2],[4,81,2],[6,85,2],[8,88,6],[14,86,2]]
  ];
  // track 3: A minor
  const C3={
    Am9:{k:[60,64,67,71],b:33,f:40}, F7M:{k:[60,64,65,69],b:41,f:48}, C7M:{k:[59,64,67,71],b:36,f:43}, Em7:{k:[59,62,67,71],b:40,f:47},
    Dm9:{k:[65,69,72,76],b:38,f:45}, G7M:{k:[59,62,66,67],b:43,f:50}, Bh7:{k:[62,65,69,71],b:35,f:42}, E7b9:{k:[56,59,62,65],b:40,f:47}
  };
  const PROG3=[['Am9'],['F7M'],['C7M'],['Em7'],['Dm9'],['G7M'],['Bh7','E7b9'],['Am9']];
  const LEAD3=[
    [[0,81,6],[8,84,4],[12,83,4]],
    [[0,81,4],[6,84,2],[8,88,8]],
    [[0,83,6],[8,79,4],[12,76,4]],
    [[0,79,4],[4,83,4],[8,86,8]],
    [[0,84,6],[8,81,4],[12,77,4]],
    [[0,79,4],[6,83,2],[8,86,6],[14,83,2]],
    [[0,77,4],[4,81,4],[8,84,4],[12,80,4]],
    [[0,81,12]]
  ];


  function noiseBuf(ctx){const n=ctx.sampleRate|0,b=ctx.createBuffer(1,n,ctx.sampleRate),d=b.getChannelData(0);for(let i=0;i<n;i++)d[i]=Math.random()*2-1;return b;}
  function impulse(ctx,sec){const n=(ctx.sampleRate*sec)|0,b=ctx.createBuffer(2,n,ctx.sampleRate);for(let c=0;c<2;c++){const d=b.getChannelData(c);for(let i=0;i<n;i++)d[i]=(Math.random()*2-1)*Math.pow(1-i/n,2.6);}return b;}

  // build the instrument bus on any audio context (live or offline); returns {step(n,t)} and the master gain
  function build(ctx,ti){
    ti=ti||0;const TR=TRACKS[ti],STEP=TR.step,SWING=TR.swing;
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
    function step0(n,t){
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

    // extra voices for tracks 2 and 3
    function pluck(t,m,len,v){const f=mtof(m),o=ctx.createOscillator(),o2=ctx.createOscillator(),g=ctx.createGain(),lp=ctx.createBiquadFilter(),g2=ctx.createGain();
      o.type='square';o2.type='sawtooth';o.frequency.value=f;o2.frequency.value=f;o2.detune.value=7;g2.gain.value=0.5;o.connect(lp);o2.connect(g2);g2.connect(lp);
      lp.type='lowpass';lp.Q.value=2;lp.frequency.setValueAtTime(5200,t);lp.frequency.exponentialRampToValueAtTime(900,t+0.22);lp.connect(g);g.connect(leadB);
      const dur=len*STEP;g.gain.setValueAtTime(0.0001,t);g.gain.linearRampToValueAtTime(0.13*v,t+0.006);g.gain.setTargetAtTime(0.06*v,t+0.02,0.12);g.gain.setTargetAtTime(0.0001,t+dur,0.06);
      [o,o2].forEach(x=>{x.start(t);x.stop(t+dur+0.4);});}
    function bell(t,m,len,v){const f=mtof(m),c=ctx.createOscillator(),md=ctx.createOscillator(),mg=ctx.createGain(),g=ctx.createGain();c.type='sine';md.type='sine';c.frequency.value=f;md.frequency.value=f*3.5;
      mg.gain.setValueAtTime(f*1.1,t);mg.gain.exponentialRampToValueAtTime(f*0.02,t+1.4);md.connect(mg);mg.connect(c.frequency);c.connect(g);g.connect(leadB);
      const dur=Math.max(len*STEP,1.6);g.gain.setValueAtTime(0.0001,t);g.gain.linearRampToValueAtTime(0.3*v,t+0.008);g.gain.exponentialRampToValueAtTime(0.0001,t+dur);[c,md].forEach(x=>{x.start(t);x.stop(t+dur+0.1);});}
    function clap(t,v){noise(t,0.012,'bandpass',1500,1.2,0.5*v,drum);noise(t+0.012,0.012,'bandpass',1500,1.2,0.4*v,drum);noise(t+0.026,0.16,'bandpass',1300,1,0.4*v,drum);}
    function brush(t,v){noise(t,0.16,'bandpass',4200,0.6,0.22*v,drum);}

    // track 2: bright, plucked, four on the floor
    function step1(n,t){
      const s=n%LOOP, bar=(s/BAR)|0, st=s%BAR, cyc=bar%8, pass=(bar/8)|0;
      const when=t+(st%2===1?SWING*STEP:0)+(Math.random()-0.5)*0.003, hv=()=>0.8+Math.random()*0.2;
      if(st%4===0)kick(when,(st===0?1:0.8)*hv());
      if(st===10&&bar%2===1)kick(when,0.6);
      if(st===4||st===12)clap(when,hv());
      if(st%2===0)hat(when,(st%4===2?1:0.5)*hv(),st===14&&bar%4===3);
      if(pass===1&&st%2===1)shaker(when,0.7*hv());
      if(pass===1&&bar===15&&st>=12)clap(when,0.3+0.1*(st-12));
      const chords=PROG2[cyc],ch=C2[chords[0]];
      if(st===0)pad(when,ch.k,BAR*STEP);
      [[0,3,1],[3,2,.7],[8,3,.9],[11,2,.6],[14,2,.7]].forEach(([cs,len,v])=>{if(st===cs)ch.k.forEach((m,i)=>key(when+i*0.004,m,len,v*0.8*hv()));});
      [[0,2,1,ch.b],[3,1,.7,ch.b+12],[6,2,.8,ch.b],[8,2,.9,ch.b+7],[11,2,.7,ch.b+12],[14,2,.7,ch.f-12]].forEach(([bs,len,v,m])=>{if(st===bs)bass(when,m,len,v*hv());});
      LEAD2[cyc].forEach(([ls,m,len])=>{if(st===ls)pluck(when,m,len,0.9+Math.random()*0.1);});
      if(pass===1)LEAD2[cyc].forEach(([ls,m,len])=>{if(st===ls&&len>=3)pluck(when+0.008,m+12,len,0.4);});
    }
    // track 3: slow, wide, bells and brushes
    function step2(n,t){
      const s=n%LOOP, bar=(s/BAR)|0, st=s%BAR, cyc=bar%8, pass=(bar/8)|0;
      const when=t+(st%2===1?SWING*STEP:0)+(Math.random()-0.5)*0.005, hv=()=>0.75+Math.random()*0.25;
      if(st===0)kick(when,0.9*hv());
      if(st===10)kick(when,0.55*hv());
      if(st===8)snare(when,0.5*hv());
      if(st===8&&pass===1)snap(when,0.7);
      if(st%2===0)hat(when,(st%4===0?0.7:0.4)*hv(),false);
      if(st%4===2)brush(when,hv());
      if(pass===1&&st%4===1)shaker(when,0.5*hv());
      const chords=PROG3[cyc],half=chords.length===2,ch=C3[chords[half&&st>=8?1:0]];
      if(st===0)pad(when,C3[chords[0]].k,BAR*STEP*(half?0.55:1.02));
      if(half&&st===8)pad(when,C3[chords[1]].k,BAR*STEP*0.5);
      const comp=half?[[0,7,1],[8,7,.9]]:[[0,8,1],[10,5,.6]];
      comp.forEach(([cs,len,v])=>{if(st===cs)ch.k.forEach((m,i)=>key(when+i*0.012,m,len,v*0.75*hv()));});
      [[0,8,1,ch.b],[10,5,.7,ch.f-12]].forEach(([bs,len,v,m])=>{if(st===bs&&!(half&&st>=8&&bs===10))bass(when,m,len,v*hv());});
      if(half&&st===8)bass(when,ch.b,6,0.9);
      LEAD3[cyc].forEach(([ls,m,len])=>{if(st===ls)bell(when,m,len,0.8+Math.random()*0.2);});
      if(pass===1)LEAD3[cyc].forEach(([ls,m,len])=>{if(st===ls&&len>=4)bell(when+0.02,m-12,len,0.4);});
    }
    const steps=[step0,step1,step2], step=steps[ti];
    return {master:master,step:step,STEP:STEP,LOOP:LOOP,BAR:BAR};
  }

  const LM={BPM:BPM,LOOP:LOOP,TRACKS:TRACKS,build:build,ctx:null,engs:[],cur:0,choice:-1,vol:70,paused:false,started:false,timer:null,next:0,n:0};
  LM.level=v=>Math.pow(Math.max(0,Math.min(100,v))/100,1.6)*0.9;
  LM.eng=function(i){if(!LM.engs[i])LM.engs[i]=build(LM.ctx,i);return LM.engs[i];};
  LM.start=function(){
    if(LM.started)return;
    const AC=window.AudioContext||window.webkitAudioContext;if(!AC)return;
    try{LM.ctx=new AC();LM.cur=LM.choice>=0?LM.choice:0;LM.eng(LM.cur);LM.started=true;LM.apply();}catch(e){LM.started=false;}
  };
  LM.apply=function(){
    if(!LM.started)return;
    const c=LM.ctx,on=!LM.paused&&LM.vol>0;
    LM.engs.forEach(e=>{if(e)e.master.gain.setTargetAtTime(on?LM.level(LM.vol):0,c.currentTime,0.08);});
    if(on&&!LM.timer){
      if(c.state==='suspended')c.resume();
      LM.next=c.currentTime+0.12;
      LM.timer=setInterval(()=>{while(LM.next<c.currentTime+0.25){
        const e=LM.eng(LM.cur);e.step(LM.n,LM.next);LM.n++;LM.next+=e.STEP;
        if(LM.n>=e.LOOP){LM.n=0;if(LM.choice<0){LM.cur=(LM.cur+1)%TRACKS.length;LM.eng(LM.cur);}}   // AUTO: the next track after each full loop
      }},40);
    }else if(!on&&LM.timer){setTimeout(()=>{if(!(!LM.paused&&LM.vol>0)&&LM.timer){clearInterval(LM.timer);LM.timer=null;}},400);}
  };
  LM.setVolume=function(v){LM.vol=v;LM.apply();};
  LM.setPaused=function(p){LM.paused=!!p;LM.apply();};
  LM.setTrack=function(i){   // -1 = AUTO (all tracks in turn), 0..2 = stay on one track; switches at the next beat
    LM.choice=(i>=0&&i<TRACKS.length)?i:-1;
    if(LM.choice>=0&&LM.started&&LM.cur!==LM.choice){LM.cur=LM.choice;LM.n=0;LM.eng(LM.cur);}
  };
  window.LM=LM;
})();
