"""Self-contained browser drawing: two endpoints and one junction-side click."""
from copy import deepcopy
from pathlib import Path
import base64
import json

import junction_counting_v4 as core


DRAWING_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Draw camera gates</title><style>
*{box-sizing:border-box}body{margin:0;background:#edf2f7;color:#172338;font:16px system-ui,Segoe UI,sans-serif}
main{max-width:1250px;margin:auto;padding:22px}h1{font-size:28px;margin:0 0 8px}p{line-height:1.5}
.bar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;background:white;border-radius:12px;padding:14px;margin:12px 0}
label{font-weight:600}select,input,button{font:inherit;padding:9px 12px;border:1px solid #c6d1df;border-radius:7px}
button{background:white;cursor:pointer}button.primary{background:#17633f;color:white;border-color:#17633f}button:disabled{opacity:.45;cursor:not-allowed}
select{min-width:140px}input{max-width:220px}.step{background:#102a43;color:white;padding:14px;border-radius:10px;font-size:19px;font-weight:600}
canvas{display:block;width:100%;height:auto;max-height:none;background:#111;outline:1px solid #a9b8ca;touch-action:none;cursor:crosshair}
.picture{margin:14px 0;box-shadow:0 4px 18px #17233815}.status{min-height:28px;margin:12px 0;color:#154d32;font-weight:600}.error{color:#a51d29}
.tag{background:#e6eff8;padding:5px 9px;border-radius:7px}small{color:#536278}.hint{margin:6px 0 16px}.legend{font-size:15px}
</style></head><body><main>
<h1>Draw your road gates with the mouse</h1>
<p class="hint">For each road, click <b>one end</b>, click <b>the other end</b>, then click <b>toward the junction</b>.
You can also drag a line, release it, then click its junction side. Repeat for A, B and C.</p>
<div class="bar"><label>Camera <select id="camera"></select></label><label>Gate <select id="gate"><option>A</option><option>B</option><option>C</option></select></label>
<label>Road name <input id="road" placeholder="e.g. left road"></label><button id="redraw">Redraw this gate</button><button id="undo">Undo last point</button></div>
<div id="step" class="step" aria-live="polite"></div><div class="picture"><canvas id="canvas" width="960" height="540" aria-label="Click the image to draw the selected gate"></canvas></div>
<div class="bar"><span class="legend">Yellow = counting gate &nbsp; Green dot/arrow = junction side</span>
<button id="save" class="primary">Save this camera</button><span id="progress" class="tag"></span></div>
<div class="bar"><button id="download" class="primary">Download gates_drawn.json</button>
<label>Resume a saved drawing <input id="resume" type="file" accept=".json,application/json"></label>
<button id="draft">Download unfinished draft</button></div>
<div id="status" class="status" role="status"></div>
<p>After saving every camera, download <b>gates_drawn.json</b>. Return to the notebook and use its <b>Import drawn gates</b> control.
Do not count vehicles by drawing a triangle over the grass. Put one gate across each road arm and leave visible road on both sides.</p>
<small id="scope"></small>
</main><script type="application/json" id="payload">__PAYLOAD__</script><script>
'use strict';
const payload=JSON.parse(document.getElementById('payload').textContent);
const calibration=structuredClone(payload.calibration), ids=Object.keys(calibration.cameras);
const camera=document.getElementById('camera'), gate=document.getElementById('gate'), road=document.getElementById('road');
const canvas=document.getElementById('canvas'),ctx=canvas.getContext('2d'),status=document.getElementById('status');
let image=null,points=[],pressed=null,hover=null,loadVersion=0,dirty=false;
ids.forEach(id=>{const option=document.createElement('option');option.value=id;option.textContent=id;camera.append(option)});
function record(){return calibration.cameras[camera.value]}
function selected(){return record().gates.find(g=>g.name===gate.value)}
function notice(text,error=false){status.textContent=text;status.className='status'+(error?' error':'')}
function product(a,b,p){return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])}
function crossing(a,b,p,q){const r=[q[0]-p[0],q[1]-p[1]],s=[b[0]-a[0],b[1]-a[1]],den=r[0]*s[1]-r[1]*s[0];
 if(Math.abs(den)<1e-12)return false;const d=[a[0]-p[0],a[1]-p[1]],t=(d[0]*s[1]-d[1]*s[0])/den,u=(d[0]*r[1]-d[1]*r[0])/den;
 return t>=0&&t<=1&&u>=0&&u<=1}
function validGate(g){for(const field of ['a','b','inside']){if(!Array.isArray(g[field])||g[field].length!==2||g[field].some(x=>!Number.isFinite(x)||x<0||x>1))return 'Click all three points on the picture.'}
 const length=Math.hypot(g.a[0]-g.b[0],g.a[1]-g.b[1]);
 if(length<.02)return 'The gate is too short. Choose endpoints across the road.';
 if(Math.abs(product(g.a,g.b,g.inside))/length<.005)return 'Click farther from the yellow line, on the junction side.';return ''}
function cameraError(r){const names=r.gates.map(g=>g.name).sort().join('');if(names!=='ABC')return 'Draw gates A, B and C before saving this camera.';
 for(const g of r.gates){const problem=validGate(g);if(problem)return g.name+': '+problem}
 for(let i=0;i<r.gates.length;i++)for(let k=i+1;k<r.gates.length;k++)if(crossing(r.gates[i].a,r.gates[i].b,r.gates[k].a,r.gates[k].b))return 'Gates intersect. Place them separately across the road arms.';
 return ''}
function xy(p){return [p[0]*canvas.width,p[1]*canvas.height]}
function text(t,x,y,colour){ctx.font=Math.max(14,canvas.width/55)+'px system-ui';ctx.lineWidth=4;ctx.strokeStyle='#102030';ctx.strokeText(t,x,y);ctx.fillStyle=colour;ctx.fillText(t,x,y)}
function dot(p,label,colour){const [x,y]=xy(p);ctx.beginPath();ctx.arc(x,y,Math.max(4,canvas.width/180),0,Math.PI*2);ctx.fillStyle=colour;ctx.fill();text(label,x+8,y-8,colour)}
function line(a,b,colour){const [x,y]=xy(a),[u,v]=xy(b);ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(u,v);ctx.lineWidth=Math.max(3,canvas.width/260);ctx.strokeStyle=colour;ctx.stroke()}
function drawGate(g){line(g.a,g.b,'#ffe600');dot(g.a,g.name+' a','#ffe600');dot(g.b,'b','#ffe600');
 const middle=[(g.a[0]+g.b[0])/2,(g.a[1]+g.b[1])/2];line(middle,g.inside,'#36ef66');
 const [x,y]=xy(middle),[u,v]=xy(g.inside),angle=Math.atan2(v-y,u-x),len=Math.max(10,canvas.width/70);
 ctx.beginPath();ctx.moveTo(u,v);ctx.lineTo(u-len*Math.cos(angle-.5),v-len*Math.sin(angle-.5));ctx.lineTo(u-len*Math.cos(angle+.5),v-len*Math.sin(angle+.5));ctx.closePath();ctx.fillStyle='#36ef66';ctx.fill();dot(g.inside,'inside','#36ef66')}
function render(){ctx.clearRect(0,0,canvas.width,canvas.height);if(image)ctx.drawImage(image,0,0,canvas.width,canvas.height);
 for(const g of record().gates)if(!(g.name===gate.value&&points.length))drawGate(g);
 if(points.length){dot(points[0],gate.value+' a','#ffe600');if(points[1]){line(points[0],points[1],'#ffe600');dot(points[1],'b','#ffe600')}else if(hover)line(points[0],hover,'#ffe600')}
 if(pressed&&pressed.phase===0&&hover)line(pressed.point,hover,'#ffe600');
 const ready=Boolean(selected())&&points.length===0;
 document.getElementById('step').textContent=!image?'Loading reference picture…':ready?'Gate '+gate.value+' is drawn. Choose the next gate, or Save this camera.':
 ['1 — Click the first end of gate '+gate.value+' (or drag across the road).','2 — Click the other end of gate '+gate.value+'.','3 — Click on the junction side of the yellow line.'][points.length];
 const saved=ids.filter(id=>calibration.cameras[id].reviewed&&!cameraError(calibration.cameras[id])).length;
 document.getElementById('progress').textContent=saved+' / '+ids.length+' cameras saved';document.getElementById('download').disabled=saved!==ids.length}
function loadGate(){points=[];pressed=null;hover=null;road.value=selected()?.label||'';render()}
function loadCamera(){const version=++loadVersion;image=null;const r=record();canvas.width=r.reference_size[0];canvas.height=r.reference_size[1];
 loadGate();const next=new Image();next.onload=()=>{if(version!==loadVersion)return;image=next;render()};next.onerror=()=>notice('Could not load this reference picture.',true);next.src=payload.images[camera.value]}
function normalized(event){const rect=canvas.getBoundingClientRect();return [Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))]}
function changed(){record().reviewed=false;dirty=true}
function accept(point){if(!image)return;if(selected()&&points.length===0){notice('This gate is already drawn. Choose Redraw this gate to change it.');return}
 if(points.length<2){points.push(point);changed();notice('');render();return}
 const g={name:gate.value,label:road.value.trim(),a:points[0],b:points[1],inside:point};const problem=validGate(g);
 if(problem){notice(problem,true);return}record().gates=record().gates.filter(old=>old.name!==g.name);record().gates.push(g);changed();points=[];hover=null;notice('Gate '+gate.value+' drawn. Select the next gate, or save this camera.');render()}
canvas.addEventListener('pointerdown',event=>{if(!image)return;pressed={point:normalized(event),phase:points.length,canDraw:!selected()||points.length>0};canvas.setPointerCapture(event.pointerId)});
canvas.addEventListener('pointermove',event=>{hover=normalized(event);render()});
canvas.addEventListener('pointerup',event=>{if(!pressed)return;const start=pressed,end=normalized(event);pressed=null;
 const distance=Math.hypot((end[0]-start.point[0])*canvas.width,(end[1]-start.point[1])*canvas.height);
 if(start.phase===0&&start.canDraw&&distance>=Math.max(6,canvas.width*.02)){points=[start.point,end];changed();notice('Line drawn. Now click its junction side.');render()}else accept(end)});
canvas.addEventListener('pointercancel',()=>{pressed=null;hover=null;render()});
document.getElementById('redraw').onclick=()=>{record().gates=record().gates.filter(g=>g.name!==gate.value);points=[];hover=null;changed();notice('Draw gate '+gate.value+' again.');render()};
document.getElementById('undo').onclick=()=>{if(points.length){points.pop();changed()}else if(selected()){const g=selected();points=[g.a,g.b];record().gates=record().gates.filter(x=>x.name!==gate.value);changed()}notice('');render()};
road.oninput=()=>{if(selected()){selected().label=road.value.trim();changed();render()}};
function unfinished(){return points.length>0}
function switchTo(element,oldValue){if(unfinished()&&!confirm('Discard the unfinished points for this gate?')){element.value=oldValue;return false}return true}
let previousCamera=camera.value,previousGate=gate.value;
camera.onchange=()=>{if(!switchTo(camera,previousCamera))return;previousCamera=camera.value;notice('');loadCamera()};
gate.onchange=()=>{if(!switchTo(gate,previousGate))return;previousGate=gate.value;notice('');loadGate()};
document.getElementById('save').onclick=()=>{if(unfinished()){notice('Finish the current gate by clicking its junction side first.',true);return}
 const error=cameraError(record());if(error){notice(error,true);return}record().reviewed=true;dirty=true;notice(camera.value+' saved in this drawing. Save all cameras, then download the JSON file.');render()};
function download(complete){if(complete&&ids.some(id=>!calibration.cameras[id].reviewed||cameraError(calibration.cameras[id]))){notice('Save every camera before downloading the completed gates.',true);return}
 const blob=new Blob([JSON.stringify(calibration,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');
 a.href=url;a.download=complete?'gates_drawn.json':'gates_draft.json';a.click();dirty=false;setTimeout(()=>URL.revokeObjectURL(url),1000);notice(complete?'Downloaded gates_drawn.json. Import it in the notebook.':'Downloaded an unfinished draft. Use Resume a saved drawing to continue it later.')}
document.getElementById('download').onclick=()=>download(true);document.getElementById('draft').onclick=()=>download(false);
document.getElementById('resume').onchange=async event=>{const file=event.target.files[0];if(!file)return;try{const draft=JSON.parse(await file.text());
 if(Object.keys(draft.cameras||{}).sort().join('|')!==ids.slice().sort().join('|'))throw Error('Camera list does not match this drawing page.');
 for(const id of ids){const r=draft.cameras[id],original=payload.calibration.cameras[id];if(r.reference_sha256!==original.reference_sha256||JSON.stringify(r.reference_size)!==JSON.stringify(original.reference_size))throw Error('Reference picture differs for '+id);
 const names=new Set();for(const g of r.gates||[]){if(!['A','B','C'].includes(g.name)||names.has(g.name)||validGate(g))throw Error('Invalid draft gate for '+id);names.add(g.name)}
 if(r.reviewed&&cameraError(r))throw Error('Saved camera contains incomplete/intersecting gates: '+id)}
 for(const id of ids){calibration.cameras[id].gates=draft.cameras[id].gates;calibration.cameras[id].reviewed=Boolean(draft.cameras[id].reviewed)}
 dirty=false;notice('Drawing restored.');loadCamera()}catch(error){notice(error.message,true)}finally{event.target.value=''}};
document.getElementById('scope').textContent='Images and drawing stay in this browser. '+(payload.note||'Use the original reference pictures and visually review annotated pilots before batch processing.');
window.addEventListener('beforeunload',event=>{if(dirty||unfinished()){event.preventDefault();event.returnValue=''}});
window.gateDrawing={getCalibration:()=>structuredClone(calibration),cameraError,validGate};
loadCamera();
</script></body></html>'''


def write_drawing_page(folder):
    folder=Path(folder)
    calibration=json.loads((folder/'gates.json').read_text(encoding='utf-8'))
    images={}
    for name,camera in calibration['cameras'].items():
        image=folder/(name+'.png')
        if core.file_hash(image)!=camera['reference_sha256']:
            raise ValueError('Reference picture changed: '+name)
        images[name]='data:image/png;base64,'+base64.b64encode(image.read_bytes()).decode('ascii')
    payload=json.dumps(dict(calibration=calibration,images=images),ensure_ascii=True).replace('<',chr(92)+'u003c')
    target=folder/'Draw_Camera_Gates.html'
    target.write_text(DRAWING_HTML.replace('__PAYLOAD__',payload),encoding='utf-8')
    return target


def import_drawn_gates(folder,uploaded):
    """Import geometry only, bound to the original reference hashes and dimensions."""
    folder=Path(folder);path=folder/'gates.json'
    original=json.loads(path.read_text(encoding='utf-8'))
    if isinstance(uploaded,(bytes,bytearray,memoryview)):
        drawn=json.loads(bytes(uploaded).decode('utf-8-sig'))
    elif isinstance(uploaded,str):drawn=json.loads(uploaded)
    else:drawn=deepcopy(uploaded)
    if not isinstance(drawn,dict) or set(drawn.get('cameras',{}))!=set(original['cameras']):
        raise ValueError('Drawn gates must contain the same camera references.')
    result=deepcopy(original)
    for name,old in original['cameras'].items():
        record=drawn['cameras'][name]
        if any(record.get(k)!=old[k] for k in ['reference_size','reference_sha256']):
            raise ValueError('Drawing uses another reference image: '+name)
        if core.file_hash(folder/(name+'.png'))!=old['reference_sha256']:
            raise ValueError('Original reference picture changed: '+name)
        if {g.get('name') for g in record.get('gates',[])}!={'A','B','C'}:
            raise ValueError('Draw all three gates A, B and C for '+name)
        if record.get('reviewed') is not True:raise ValueError('Save this camera in the drawing page first: '+name)
        result['cameras'][name].update(gates=deepcopy(record['gates']),reviewed=True)
        core.validate_camera(result['cameras'][name])
    # Preserve the previous calibration once per distinct geometry, including
    # pilot-compatible positions, rather than overwriting it without a copy.
    backup=folder/('gates_before_drawing_'+core.digest(original)[:12]+'.json')
    if result!=original and not backup.exists():core.atomic_json(backup,original)
    core.atomic_json(path,result)
    return result


def drawing_import_widget(folder):
    import ipywidgets as w
    from IPython.display import display,clear_output
    upload=w.FileUpload(accept='.json',multiple=False,description='Choose gates JSON')
    button=w.Button(description='Import drawn gates',button_style='success')
    out=w.Output()
    def load(button):
        with out:
            clear_output()
            if not upload.value:print('Choose the downloaded gates_drawn.json file first.');return
            try:
                value=upload.value
                item=next(iter(value.values())) if isinstance(value,dict) else value[0]
                result=import_drawn_gates(folder,item['content'])
                print('Imported reviewed gates for',len(result['cameras']),'cameras. Now run the pilot stage.')
            except (ValueError,KeyError,TypeError,OSError) as error:print('Not imported:',error)
    button.on_click(load)
    display(w.HTML('<b>After drawing:</b> choose gates_drawn.json below, then click Import drawn gates.'),upload,button,out)
