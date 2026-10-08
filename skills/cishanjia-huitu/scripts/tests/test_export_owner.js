// Run the actual exporter in a synthetic native-document mock. No app calls.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.argv[2],'utf8');
function fixture(name,saveAi=false){
 let calls=[],expanded=false,scale=2,bounds=[11,31,11+900*scale,31-600*scale];
 const anchor={typename:'GroupItem',name:name+' [background]',get geometricBounds(){return bounds;},get visibleBounds(){return bounds;},pageItems:[],remove(){nested.pageItems=[];}};
 const nested={typename:'GroupItem',name:'nested',pageItems:[anchor]};
 const symbol={breakLink(){expanded=true;copy.symbolItems=[];copy.pageItems=[nested];}};
 const copy={typename:'GroupItem',name:'job',symbolItems:[symbol],groupItems:[anchor],pageItems:[],resize(v){assert(expanded,'Expand before rescaling');scale*=v/100;bounds=[11,31,11+900*scale,31-600*scale];calls.push('resize');},translate(dx,dy){bounds=bounds.map((v,i)=>v+(i%2?dy:dx));calls.push('translate');}};
 const original={duplicate(){return copy;}};
 const userDoc={name:'User.ai',fullName:{fsName:'User.ai'},groupItems:{getByName(){return original;}},activate(){calls.push('activate-original');}};
 const importedNames=new Set([name.substring(0,40)+' [fixture-0]']);
 const temp={activeLayer:{},artboards:[{artboardRect:[0,600,900,0]}],rasterItems:[],symbols:{add(owner){assert.equal(owner,anchor,'Select named owner, not an ancestor');return {set name(value){assert(!importedNames.has(value),'the name is in use');assert(value.length<=63);importedNames.add(value);}};}},symbolItems:{add(def){return {get visibleBounds(){return bounds;},move(){},translate(){}};}},exportFile(file){assert.deepEqual(bounds,[0,600,900,0]);calls.push('export');},saveAs(){calls.push('save-ai');},close(){calls.push('close-temporary');}};
 const context={HUITU_EXPORT_CONFIG:{targetDocument:'User.ai',groupName:'job',width:900,height:600,scale:2,objects:[{id:'background',name}],svgSha256:'fixture',outputPng:'fixture.png',outputAi:saveAi?'Full-size.ai':'',objectMode:'symbol',antiAliasing:true},app:{activeDocument:userDoc,userInteractionLevel:0,documents:{add(){return temp;}}},DocumentColorSpace:{RGB:0},ElementPlacement:{PLACEATBEGINNING:0},Transformation:{TOPLEFT:0},UserInteractionLevel:{DONTDISPLAYALERTS:1},ExportOptionsPNG24:function(){},IllustratorSaveOptions:function(){},File:function(path){this.fsName=path;},ExportType:{PNG24:0},SaveOptions:{DONOTSAVECHANGES:0}};
 let result=JSON.parse(vm.runInNewContext(source,context));
 assert.equal(result.status,'PASS',name+': '+result.error);
 assert.deepEqual(calls,['resize','translate','export',...(saveAi?['save-ai']:[]),'close-temporary','activate-original']);
}
fixture('Background');fixture('白色背景');fixture('底色：保留原图');
fixture('Background',true);fixture('白色背景',true);fixture('复杂对象名'.repeat(12),true);
console.log('PASS|6 owner-name/collision export regressions|no Illustrator connection');
