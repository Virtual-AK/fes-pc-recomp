#!/usr/bin/env python3
"""Round-trip test for the PS2 native texture decoder in p3fes_rmd.py (synthetic data)."""
import sys,struct,random,os
sys.path.insert(0,os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'tools'))
import p3fes_rmd as R
V=0x1C020037
def ch(t,p,ver=V): return struct.pack('<III',t,len(p),ver)+p
def packet(stream,rrw,rrh):
    tag=struct.pack('<QQ',3,0x0E)  # NLOOP=3, REGS=A+D (flags unused by reader)
    ad=struct.pack('<QQ',0,0x51)+struct.pack('<QQ',rrw|(rrh<<32),0x52)+struct.pack('<QQ',0,0x53)
    img=struct.pack('<QQ',len(stream)//16|(2<<58),0)
    return tag+ad+img+stream
def to_stream(mem_words, rrw, rrh):
    tbw=max(1,(rrw+63)//64); out=bytearray()
    for k in range(rrw*rrh):
        a=R.ct32_word(k%rrw,k//rrw,tbw)*4
        out+=mem_words[a:a+4]
    return bytes(out)
def build(w,h,depth,pix,pal):
    tbw=max(1,w//64)
    mem=bytearray(1<<20)
    for y in range(h):
        for x in range(w):
            v=pix[y*w+x]
            if depth==8: mem[R.t8_index(x,y,tbw)]=v
            else:
                n=R.t4_index(x,y,tbw); mem[n>>1]|=v<<((n&1)*4)
    rrw,rrh=(w//2,h//2) if depth==8 else ((16,16) if (w,h)==(64,32) else (w//2,h//4))   # 4-bit: w*h/2 bytes = (w/2)*(h/4)*4
    stream=to_stream(mem,rrw,rrh)
    pk=packet(stream,rrw,rrh)
    ncol=256 if depth==8 else 16
    pw,ph=(16,16) if depth==8 else (8,2)
    def sw(i): return ((i&~0x18)|((i&8)<<1)|((i&16)>>1)) if depth==8 else i
    pst=b"".join(bytes((pal[sw(k)][0],pal[sw(k)][1],pal[sw(k)][2],0x80)) for k in range(ncol))   # file order, swizzled
    ppk=packet(pst,pw,ph)
    raster=struct.pack('<4I',w,h,depth,0x22504)+struct.pack('<QQQQ',(tbw<<14)|(0x13<<20),0,0,0)+struct.pack('<4I',len(pk),len(ppk),0x1000,0xFC0)
    data=ch(1,ch(1,raster)+ch(1,pk+ppk))
    return ch(0x15,ch(1,struct.pack('<II',6,0x1102))+ch(2,b'tex\0')+ch(2,b'\0\0\0\0')+data+ch(3,b''))
random.seed(5)
ok=True
for (w,h,depth) in [(128,64,8),(64,64,8),(128,128,8),(64,32,8),(256,64,8),(64,32,4),(128,128,4),(32,32,4),(64,64,4),(256,128,4)]:
    n=256 if depth==8 else 16
    pal=[(random.randrange(256),random.randrange(256),random.randrange(256)) for _ in range(n)]
    pix=[random.randrange(n) for _ in range(w*h)]
    blob=build(w,h,depth,pix,pal)
    top=R.parse_chunks(blob,0,len(blob))
    W,H,rgba=R.decode_native_texture(blob,top[0])
    exp=b"".join(bytes(pal[v])+b"\xff" for v in pix)
    good=(W,H,rgba)==(w,h,exp)
    print(w,h,depth,"ok" if good else "MISMATCH")
    ok&=good
print("ok   PS2 native texture decoder round-trips 8-bit and 4-bit pictures" if ok else "FAIL texture decoder")
if not ok: raise SystemExit(1)
