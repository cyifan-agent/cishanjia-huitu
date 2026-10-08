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
if($native.status -ne 'PASS' -or $native.svg_sha256 -ne $cfg.sha256 -or $cfg.grouping -ne 'semantic-v1'){throw 'EDITABILITY_JOB_INVALID'}
if($DryRun){'DRY_RUN|All connectors and representative object types; no Illustrator connection';exit 0}
if($cfg.objectMode -eq 'symbol'){
 & (Join-Path $PSScriptRoot 'verify_symbol_editability.ps1') -NativeWorkDir $NativeWorkDir -OutputReport $OutputReport
 exit $LASTEXITCODE
}
$script=@'
(function(){
 var c=HUITU_EDIT_CONFIG,doc=app.activeDocument,temp=null,level=app.userInteractionLevel;
 function q(v){return '"'+String(v).replace(/\\/g,'\\\\').replace(/"/g,'\\"')+'"';}
 function same(a,b){if(a.length!==b.length)return false;for(var i=0;i<a.length;i++)if(Math.abs(a[i]-b[i])>.02)return false;return true;}
 function snapshot(g){return {bounds:g.geometricBounds,items:g.pageItems.length,text:g.textFrames.length};}
 try{
  var original=doc.groupItems.getByName(c.jobName);
  app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;
  temp=app.documents.add(DocumentColorSpace.RGB,c.canvasWidth,c.canvasHeight);
  var carrier=original.duplicate(temp.activeLayer,ElementPlacement.PLACEATBEGINNING),refs={},chosen=[],kinds={};
  if(carrier.groupItems.length!==c.objects.length)throw new Error('Object group count mismatch');
  for(var i=0;i<c.objects.length;i++){
   var s=c.objects[i],g=carrier.groupItems.getByName(s.name+' ['+s.id+']');
   if(g.parent!==carrier||g.textFrames.length!==s.text_count)throw new Error('Owner mismatch '+s.id);
   refs[s.id]=g;
   if(s.kind==='connector'||(!kinds[s.kind]&&/^(cell|organelle|dna|molecule|protein|complex)$/.test(s.kind)))chosen.push(s.id);
   kinds[s.kind]=true;
  }
  temp.selection=carrier;app.executeMenuCommand('ungroup');temp.selection=null;
  if(temp.activeLayer.groupItems.length!==c.objects.length)throw new Error('Outer ungroup split objects');
  var results=[];
  for(var ci=0;ci<chosen.length;ci++){
   var id=chosen[ci],before={},item=refs[id],textPositions=[];
   for(var oi=0;oi<c.objects.length;oi++)before[c.objects[oi].id]=snapshot(refs[c.objects[oi].id]);
   for(var ti=0;ti<item.textFrames.length;ti++)textPositions.push(item.textFrames[ti].position);
   item.translate(23,-17);var b=item.geometricBounds,expected=before[id].bounds;
   if(!same(b,[expected[0]+23,expected[1]-17,expected[2]+23,expected[3]-17]))throw new Error('Incomplete translation '+id);
   for(var nt=0;nt<textPositions.length;nt++)if(!same(item.textFrames[nt].position,[textPositions[nt][0]+23,textPositions[nt][1]-17]))throw new Error('Detached text '+id);
   for(var ni=0;ni<c.objects.length;ni++){
    var nid=c.objects[ni].id,now=snapshot(refs[nid]);
    if(now.items!==before[nid].items||now.text!==before[nid].text||(nid!==id&&!same(now.bounds,before[nid].bounds)))throw new Error('Neighbor/contents altered '+nid);
   }
   item.translate(-23,17);results.push('{"id":'+q(id)+',"whole_move":true,"neighbors_fixed":true,"text_follows":true}');
  }
  return '{"status":"PASS","svg_sha256":'+q(c.sha256)+',"objects":'+c.objects.length+',"tests":['+results.join(',')+'],"all_connectors_tested":true,"original_artwork_unchanged":true,"limitation":"Review isolated arrow contents and old footprints separately"}';
 }catch(e){return '{"status":"FAIL","error":'+q(e)+'}';}
 finally{if(temp)try{temp.close(SaveOptions.DONOTSAVECHANGES);}catch(ignore){}doc.activate();app.userInteractionLevel=level;app.redraw();}
}());
'@
. (Join-Path $PSScriptRoot 'illustrator_connection.ps1')
$taskAi=Get-HuituActiveIllustrator
$result=$taskAi.DoJavaScript('var HUITU_EDIT_CONFIG='+($cfg | ConvertTo-Json -Depth 8 -Compress)+';'+$script)
$result | Set-Content -LiteralPath $OutputReport -Encoding UTF8
if(($result | ConvertFrom-Json).status -ne 'PASS'){throw $result}
$result
