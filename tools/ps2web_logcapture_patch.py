"""Browser debugging aid: with ?capture=SECONDS in the address, everything the game prints (including PS2_TRACE_* lines) is collected in memory instead
of flooding the browser console, and after SECONDS seconds the page downloads it as ps2web_log.txt. Without ?capture the page prints as before.
Example: http://localhost:8620/?state=cut.state&capture=20&PS2_TRACE_PRIM=25077,25078   (the page already turns every PS2_ address parameter into an environment switch)
Usage (in the ps2-web-recomp folder): python3 ps2web_logcapture_patch.py [web/shell.html]
Safe to run twice. Rebuild afterwards: scripts/build_web.sh p3fes
"""
import re, sys
p = sys.argv[1] if len(sys.argv) > 1 else 'web/shell.html'
s = open(p).read()
if '__out(' in s:
    print("already patched"); raise SystemExit
mod = re.compile(r'var Module\s*=\s*\{')
pr = re.compile(r'\bprint:\s*\(?(\w+)\)?\s*=>\s*console\.log\(\(?\1\)?\)')
pe = re.compile(r'\bprintErr:\s*\(?(\w+)\)?\s*=>\s*console\.\w+\(\(?\1\)?\)')
if len(mod.findall(s)) != 1 or len(pr.findall(s)) != 1 or len(pe.findall(s)) != 1:
    print("PATCH NOT APPLIED: Module/print/printErr"); raise SystemExit(1)
HELP = ('var __L=[],__N=0,__c=new URLSearchParams(location.search).get("capture");'
        'function __out(e,x){e=String(e);if(__c!==null){if(__N<8e7){__L.push(e);__N+=e.length+1}}else if(x)console.error(e);else console.log(e)}'
        'function __dl(){var b=new Blob([__L.join("\\n")],{type:"text/plain"}),a=document.createElement("a");a.href=URL.createObjectURL(b);'
        'a.download="ps2web_log.txt";document.body.appendChild(a);a.click()}'
        'if(__c!==null)setTimeout(__dl,(parseFloat(__c)||20)*1000);')
s = pr.sub('print: (text) => __out(text)', s, 1)
s = pe.sub('printErr: (text) => __out(text, 1)', s, 1)
s = mod.sub(lambda m: HELP + m.group(0), s, 1)
open(p, 'w').write(s)
print("patched (?capture=SECONDS)")
