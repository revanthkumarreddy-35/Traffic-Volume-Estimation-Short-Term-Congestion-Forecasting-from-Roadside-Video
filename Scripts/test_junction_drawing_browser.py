"""Exercise actual mouse clicks/dragging/download/import in an isolated headless Chrome."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'CP-1/Program'))
import junction_counting_v4 as core
import junction_drawing_v4 as drawing

NODE_TEST=r'''
const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url');
const folder=process.argv[2],profile=path.join(folder,'profile');
const port=fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0];
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let ws,seq=0;const pending=new Map();
function call(method,params={}){return new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))})}
function check(value,message){if(!value)throw Error(message)}
async function evaluate(expression){const out=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(out.exceptionDetails)throw Error(JSON.stringify(out.exceptionDetails));return out.result.value}
async function select(id,value){await evaluate(`(()=>{const e=document.getElementById(${JSON.stringify(id)});e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('change'));return true})()`);await delay(40)}
async function point(x,y,type='click',end=null){const r=await evaluate(`(()=>{const r=document.getElementById('canvas').getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})()`);
 const a={x:r.x+x*r.w,y:r.y+y*r.h};await call('Input.dispatchMouseEvent',{type:'mouseMoved',...a});await call('Input.dispatchMouseEvent',{type:'mousePressed',...a,button:'left',buttons:1,clickCount:1});
 const b=end?{x:r.x+end[0]*r.w,y:r.y+end[1]*r.h}:a;
 if(end)await call('Input.dispatchMouseEvent',{type:'mouseMoved',...b,button:'left',buttons:1});
 await call('Input.dispatchMouseEvent',{type:'mouseReleased',...b,button:'left',buttons:0,clickCount:1});await delay(15)}
async function waitLoaded(){for(let i=0;i<100;i++){if(await evaluate(`Boolean(window.gateDrawing)&&!document.getElementById('step').textContent.includes('Loading')`))return;await delay(50)}throw Error('Reference picture did not load')}
(async()=>{
 const targets=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();const target=targets.find(t=>t.type==='page');
 ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true})});
 ws.addEventListener('message',event=>{const m=JSON.parse(event.data);if(m.id){const p=pending.get(m.id);if(!p)return;pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}
  if(m.method==='Page.javascriptDialogOpening')call('Page.handleJavaScriptDialog',{accept:true}).catch(()=>{})});
 await call('Page.enable');await call('Runtime.enable');await call('Emulation.setDeviceMetricsOverride',{width:1400,height:1300,deviceScaleFactor:1,mobile:false});
 await call('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:path.join(folder,'downloads')});
 await call('Page.navigate',{url:pathToFileURL(path.join(folder,'Draw_Camera_Gates.html')).href});await waitLoaded();
 check(await evaluate(`document.getElementById('download').disabled`),'Incomplete calibration must not download as complete');
 const ids=['normanniles1','normanniles2','normanniles3','normanniles4'];
 for(let i=0;i<ids.length;i++){
  await select('camera',ids[i]);await waitLoaded();await select('gate','A');
  await point(.2,.3);await point(.2,.8);await point(.5,.5);
  await select('gate','B');await point(.3,.2,'drag',[.7,.2]);await point(.5,.2);
  check(await evaluate(`document.getElementById('status').textContent.includes('farther')`),'Inside point on the gate must be rejected');
  await point(.5,.5);await select('gate','C');
  if(i===0)await call('Emulation.setDeviceMetricsOverride',{width:950,height:1250,deviceScaleFactor:1,mobile:false});
  await point(.8,.3);await point(.8,.8);await point(.5,.5);
  if(i===0){await evaluate(`document.getElementById('undo').click()`);await evaluate(`document.getElementById('save').click()`);
   check(await evaluate(`document.getElementById('status').textContent.includes('Finish')`),'Partial gate must block saving');await point(.55,.5)}
  await evaluate(`document.getElementById('save').click()`);
  check(await evaluate(`window.gateDrawing.getCalibration().cameras[${JSON.stringify(ids[i])}].reviewed`),'Camera not saved: '+ids[i]);
 }
 check(!(await evaluate(`document.getElementById('download').disabled`)),'Completed calibration download should be enabled');
 const calibration=await evaluate(`window.gateDrawing.getCalibration()`);
 for(const id of ids){check(Math.abs(calibration.cameras[id].gates.find(g=>g.name==='A').a[0]-.2)<.002,'Resized click coordinates changed');check(calibration.cameras[id].gates.length===3,'Expected three gates')}
 await evaluate(`document.getElementById('download').click()`);
 const downloaded=path.join(folder,'downloads','gates_drawn.json');for(let i=0;i<100&&!fs.existsSync(downloaded);i++)await delay(50);
 check(fs.existsSync(downloaded),'JSON did not download');check(JSON.stringify(JSON.parse(fs.readFileSync(downloaded,'utf8')))===JSON.stringify(calibration),'Downloaded coordinates differ');
 await evaluate(`document.getElementById('redraw').click()`);check(await evaluate(`document.getElementById('download').disabled`),'Redraw must invalidate camera review');
 const dom=await call('DOM.getDocument');const input=await call('DOM.querySelector',{nodeId:dom.root.nodeId,selector:'#resume'});
 await call('DOM.setFileInputFiles',{nodeId:input.nodeId,files:[downloaded]});await delay(150);await waitLoaded();
 check(!(await evaluate(`document.getElementById('download').disabled`)),'Saved drawing did not restore');
 const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(folder,'browser_preview.png'),Buffer.from(shot.data,'base64'));
 const report={actual_mouse_clicks:true,actual_mouse_drag:true,resized_coordinates:true,invalid_inside_rejected:true,partial_gate_blocked:true,undo_redraw:true,four_cameras_saved:true,json_download:true,resume_saved_drawing:true};
 fs.writeFileSync(path.join(folder,'browser_report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 await call('Browser.close').catch(()=>{});ws.close();process.exit(0);
})().catch(async error=>{console.error(error.stack);if(ws){await call('Browser.close').catch(()=>{});ws.close()}process.exit(1)});
'''


def main():
    browser=next((p for p in [shutil.which('google-chrome'),shutil.which('chromium'),
        'C:/Program Files/Google/Chrome/Application/chrome.exe',
        'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'] if p and Path(p).is_file()),None)
    if not browser or not shutil.which('node'):raise RuntimeError('This optional browser test requires Chrome/Edge and Node 22+.')
    folder=ROOT/('.junction_browser_'+uuid.uuid4().hex);folder.mkdir()
    assert folder.resolve().parent==ROOT.resolve() and folder.name.startswith('.junction_browser_')
    proc=None
    try:
        calibration=dict(version=core.VERSION,cameras={})
        for index,camera in enumerate(core.CAMERAS):
            image=np.full((540,960,3),200,dtype=np.uint8)
            cv2.rectangle(image,(0,200),(960,450),(90,90,90),-1)
            cv2.rectangle(image,(300,0),(650,450),(90,90,90),-1)
            cv2.putText(image,'SYNTHETIC BROWSER TEST '+camera,(25,505),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,0,0),2)
            target=folder/(camera+'.png');cv2.imwrite(str(target),image)
            calibration['cameras'][camera]=dict(reference_size=[960,540],reference_sha256=core.file_hash(target),gates=[],reviewed=False)
        core.atomic_json(folder/'gates.json',calibration);drawing.write_drawing_page(folder)
        profile=folder/'profile';profile.mkdir();(folder/'downloads').mkdir()
        args=[browser,'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
              '--disable-background-networking','--disable-component-update','--disable-sync',
              '--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',
              '--user-data-dir='+str(profile),'about:blank']
        proc=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        for _ in range(100):
            if (profile/'DevToolsActivePort').is_file():break
            if proc.poll() is not None:raise RuntimeError('Headless browser exited before test.')
            time.sleep(.1)
        else:raise RuntimeError('Headless browser did not start.')
        script=folder/'test.cjs';script.write_text(NODE_TEST,encoding='utf-8')
        completed=subprocess.run(['node',str(script),str(folder)],capture_output=True,text=True,timeout=75)
        print(completed.stdout)
        if completed.returncode:raise RuntimeError(completed.stderr)
        drawn=drawing.import_drawn_gates(folder,(folder/'downloads/gates_drawn.json').read_bytes())
        assert all(c['reviewed'] for c in drawn['cameras'].values())
        reports=ROOT/'Local_Only/Gate_Drawing_Check';reports.mkdir(parents=True,exist_ok=True)
        for name in ['browser_preview.png','browser_report.json']:
            shutil.copyfile(folder/name,reports/name)
        print('Browser drawing and Python import passed. Test reports:',reports)
    finally:
        if proc is not None:
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # This Popen handle belongs only to the isolated test profile.
                proc.terminate();proc.wait(timeout=10)
        assert folder.resolve().parent==ROOT.resolve() and folder.name.startswith('.junction_browser_')
        for attempt in range(30):
            try:shutil.rmtree(folder);break
            except PermissionError:
                if attempt==29:raise
                time.sleep(.2)


if __name__=='__main__':main()
