const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const dir=process.argv[2],source=fs.readFileSync(path.join(dir,'native_svg_import.jsx'),'utf8');
function extract(code,name){
 const start=code.indexOf(' function '+name+'(');assert(start>=0,'Missing '+name);let brace=code.indexOf('{',start),depth=0,end=brace;
 for(;end<code.length;end++){if(code[end]==='{')depth++;else if(code[end]==='}'&&--depth===0)break;}
 return code.slice(start,end+1);
}
const fonts=[{name:'NotoSansSC-Light',family:'Noto Sans SC',style:'Light'},{name:'NotoSansSC-DemiLight',family:'Noto Sans SC',style:'DemiLight'},{name:'NotoSansSC-Regular',family:'Noto Sans SC',style:'Regular'},{name:'NotoSansSC-Bold',family:'Noto Sans SC',style:'Bold'},{name:'NotoSansSC-SemiBold',family:'Noto Sans SC',style:'SemiBold'}];
let lookups=0;const collection=new Proxy(fonts,{get(t,p){if(/^\d+$/.test(String(p)))lookups++;return t[p];}});
const intended={name:'Chosen.ai',activate(){this.activated=true;}},wrong={name:'Other.ai',activate(){throw Error('Wrong target');}};
const context={app:{textFonts:collection,activeDocument:wrong,documents:[wrong,intended]},c:{targetDocument:'Chosen.ai'},Error,isFinite};
vm.createContext(context);vm.runInContext(extract(source,'actualFamily')+extract(source,'fontFor'),context);
const normal={family:'Noto Sans SC',weight:'400',style:'normal'},bold={...normal,weight:'700'};
assert.strictEqual(context.fontFor(normal).name,'NotoSansSC-Regular');assert.strictEqual(context.fontFor(bold).name,'NotoSansSC-Bold');
assert.strictEqual(context.fontFor({...normal,weight:'300'}).name,'NotoSansSC-Light');assert.strictEqual(context.fontFor({...normal,weight:'600'}).name,'NotoSansSC-SemiBold');
const before=lookups;for(let i=0;i<50;i++)context.fontFor(normal);assert(lookups-before<=60,'Repeated full font scans');
context.app.textFonts=[{name:'VendorFace-300',family:'Synthetic CJK',style:'Light'},{name:'VendorFace-400',family:'Synthetic CJK',style:'Regular'},{name:'VendorFace-700',family:'Synthetic CJK',style:'Bold'},{name:'VendorFace-600',family:'Synthetic CJK',style:'SemiBold'}];
assert.strictEqual(context.fontFor({family:'Synthetic CJK',weight:'400',style:'normal'}).name,'VendorFace-400');assert.strictEqual(context.fontFor({family:'Synthetic CJK',weight:'600',style:'normal'}).name,'VendorFace-600');
for(const name of ['native_svg_import.jsx','export_native_figure.jsx','verify_symbol_editability.ps1','verify_native_editability.ps1']){
 const code=fs.readFileSync(path.join(dir,name),'utf8');vm.runInContext(extract(code,'capturedDocument'),context);
 assert.strictEqual(context.capturedDocument('Chosen.ai'),intended);assert.throws(()=>context.capturedDocument('Missing.ai'),/missing/i);
 assert.throws(()=>context.capturedDocument(''),/captured|target/i);
}
vm.runInContext(extract(source,'fitLiveText'),context);
let probes=0,removed=0;
const attrs={size:10,horizontalScale:100};
const text={contents:'A+',position:[0,0],textRange:{characterAttributes:attrs},characters:[{characterAttributes:{}},{characterAttributes:{}}],translate(x,y){this.position[0]+=x;this.position[1]+=y;},duplicate(){probes++;return {createOutline(){const w=attrs.size*attrs.horizontalScale/100,h=attrs.size;return {visibleBounds:[text.position[0],text.position[1]+h,text.position[0]+w,text.position[1]],remove(){removed++;}};},remove(){removed++;}};}};
context.fitLiveText(text,{rotation:0,nativeFit:{bbox_px:[20,30,40,20],tracking:[{start:1,length:1,value:50}]}},[0,0]);
assert.strictEqual(text.contents,'A+');assert.strictEqual(attrs.size,20);assert.strictEqual(attrs.horizontalScale,200);assert.strictEqual(text.characters[1].characterAttributes.tracking,50);assert.deepStrictEqual(text.position,[20,-50]);assert.strictEqual(probes,removed);
assert.throws(()=>context.fitLiveText(text,{rotation:30,nativeFit:{bbox_px:[20,30,40,20]}},[0,0]),/rotat/i);
console.log('NATIVE_SESSION_PASS');
