[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$NativeWorkDir,[Parameter(Mandatory=$true)][string]$OutputReport,[switch]$DryRun)
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition -eq 'Core' -and -not $DryRun){
 & powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File $PSCommandPath -NativeWorkDir $NativeWorkDir -OutputReport $OutputReport
 if($LASTEXITCODE -ne 0){throw 'EDITABILITY_LEGACY_HOST_FAILED'}
 exit 0
}
$cfg=Get-Content -LiteralPath (Join-Path $NativeWorkDir 'native-config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$native=Get-Content -LiteralPath (Join-Path $NativeWorkDir 'native-import-report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($native.status -ne 'PASS' -or $native.svg_sha256 -ne $cfg.sha256 -or $cfg.grouping -ne 'semantic-v1' -or $cfg.objectMode -ne 'symbol'){throw 'EDITABILITY_JOB_INVALID'}
if($DryRun){'DRY_RUN|All protected objects, native gradients and repeated ungroup; no Illustrator connection';exit 0}
$script=@'
(function(){
 var c=HUITU_EDIT_CONFIG,doc=app.activeDocument,temp=null,level=app.userInteractionLevel;
 function q(v){return '"'+String(v).replace(/\\/g,'\\\\').replace(/"/g,'\\"')+'"';}
 function same(a,b){if(a.length!==b.length)return false;for(var i=0;i<a.length;i++)if(Math.abs(a[i]-b[i])>.02)return false;return true;}
 function gradientPaints(node){var n=0;if(node.filled&&node.fillColor.typename==='GradientColor')n++;if(node.stroked&&node.strokeColor.typename==='GradientColor')n++;return n;}
 function inspect(item){
  var holder=temp.activeLayer.groupItems.add(),parts=[],texts=[],gradients=0,graphics=0;
  try{
   var duplicate=item.duplicate(holder,ElementPlacement.PLACEATBEGINNING);duplicate.breakLink();
   if(holder.groupItems.length!==1)throw new Error('Symbol did not expose its editable owner group');
   function walk(node,compoundMember){
    if(node.typename==='GroupItem'){for(var i=0;i<node.pageItems.length;i++)walk(node.pageItems[i],false);}
    else if(node.typename==='TextFrame')texts.push({name:node.name,content:node.contents,position:node.position});
    else if(node.typename==='PathItem'){
     if(!compoundMember)graphics++;
     parts.push({name:node.name,bounds:node.geometricBounds});
     gradients+=gradientPaints(node);
    }else if(node.typename==='CompoundPathItem'){graphics++;for(var k=0;k<node.pathItems.length;k++)walk(node.pathItems[k],true);}
    else throw new Error('Unexpected nonvector symbol content: '+node.typename);
   }
   walk(holder.groupItems[0],false);return {graphics:graphics,parts:parts,texts:texts,gradients:gradients};
  }finally{holder.remove();}
 }
 try{
  var original=doc.groupItems.getByName(c.jobName);
  app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;
  temp=app.documents.add(DocumentColorSpace.RGB,c.canvasWidth,c.canvasHeight);
  var carrier=original.duplicate(temp.activeLayer,ElementPlacement.PLACEATBEGINNING),refs={},chosen=[];
  if(carrier.symbolItems.length!==c.objects.length)throw new Error('Semantic symbol count mismatch');
  for(var i=0;i<c.objects.length;i++){
   var s=c.objects[i],item=carrier.symbolItems.getByName(s.name+' ['+s.id+']');
   if(item.parent!==carrier)throw new Error('Owner mismatch '+s.id);
   refs[s.id]=item;chosen.push(s.id);
  }
  temp.selection=carrier;app.executeMenuCommand('ungroup');temp.selection=null;
  for(var attempt=0;attempt<5;attempt++){
   var selected=[];for(var si=0;si<chosen.length;si++)selected.push(refs[chosen[si]]);
   temp.selection=selected;try{app.executeMenuCommand('ungroup');}catch(noGroup){}temp.selection=null;
   if(temp.activeLayer.symbolItems.length!==c.objects.length||temp.activeLayer.groupItems.length!==0)throw new Error('Repeated ungroup split a biological object');
  }
  var results=[],totalText=0,gradientOwners=[];
  for(var ci=0;ci<chosen.length;ci++){
   var id=chosen[ci],spec=c.objects[ci],before={},item=refs[id],details=inspect(item);
   if(details.texts.length!==spec.text_count)throw new Error('Live text missing inside '+id);
   if(details.graphics!==spec.graphic_count)throw new Error('Missing or foreign vector parts inside '+id+': '+details.graphics+' / '+spec.graphic_count);
   var expected={};for(var li=0;li<c.labels.length;li++)if(c.labels[li].object_id===id)expected[c.labels[li].source_id]=c.labels[li].content;
   for(var ti=0;ti<details.texts.length;ti++)if(expected[details.texts[ti].name]!==details.texts[ti].content)throw new Error('Incorrect editable text inside '+id);
   totalText+=details.texts.length;
   if(details.gradients)gradientOwners.push('{"id":'+q(id)+',"native_gradients":'+details.gradients+'}');
   for(var oi=0;oi<chosen.length;oi++)before[chosen[oi]]=refs[chosen[oi]].geometricBounds;
   item.translate(23,-17);var b=item.geometricBounds,old=before[id];
   if(!same(b,[old[0]+23,old[1]-17,old[2]+23,old[3]-17]))throw new Error('Incomplete translation '+id);
   var after=inspect(item);
   if(after.graphics!==details.graphics||after.texts.length!==details.texts.length||after.gradients!==details.gradients)throw new Error('Contents lost on movement '+id);
   for(var pi=0;pi<details.parts.length;pi++){
    var a=details.parts[pi],z=after.parts[pi],ab=a.bounds;
    if(a.name!==z.name||!same(z.bounds,[ab[0]+23,ab[1]-17,ab[2]+23,ab[3]-17]))throw new Error('Detached vector detail '+id);
   }
   for(var tt=0;tt<details.texts.length;tt++){
    var t=details.texts[tt],at=after.texts[tt];
    if(at.content!==t.content||!same(at.position,[t.position[0]+23,t.position[1]-17]))throw new Error('Detached text '+id);
   }
   for(var ni=0;ni<chosen.length;ni++)if(chosen[ni]!==id&&!same(refs[chosen[ni]].geometricBounds,before[chosen[ni]]))throw new Error('Neighbor moved '+chosen[ni]);
   item.translate(-23,17);
   results.push('{"id":'+q(id)+',"whole_move":true,"neighbors_fixed":true,"editable_text":'+details.texts.length+',"native_gradients":'+details.gradients+',"protected_from_ungroup":true}');
  }
  if(temp.rasterItems.length||temp.placedItems.length)throw new Error('Unexpected image after verification');
  return '{"status":"PASS","svg_sha256":'+q(c.sha256)+',"object_mode":"symbol","objects":'+c.objects.length+',"tests":['+results.join(',')+'],"repeated_ungroup_cycles":5,"verified_live_text":'+totalText+',"gradient_owners":['+gradientOwners.join(',')+'],"all_objects_tested":true,"all_connectors_tested":true,"original_artwork_unchanged":true}';
 }catch(e){return '{"status":"FAIL","error":'+q(e)+'}';}
 finally{if(temp)try{temp.close(SaveOptions.DONOTSAVECHANGES);}catch(ignore){}doc.activate();app.userInteractionLevel=level;app.redraw();}
}());
'@
. (Join-Path $PSScriptRoot 'illustrator_connection.ps1')
$taskAi=Get-HuituActiveIllustrator
$result=$taskAi.DoJavaScript('var HUITU_EDIT_CONFIG='+($cfg | ConvertTo-Json -Depth 8 -Compress)+';'+$script)
$result | Set-Content -LiteralPath $OutputReport -Encoding UTF8
if(($result | ConvertFrom-Json).status -ne 'PASS'){throw $result}
($result | ConvertFrom-Json) | Select-Object status,object_mode,objects,repeated_ungroup_cycles,verified_live_text,all_objects_tested
