(function(){
 var c=HUITU_EXPORT_CONFIG,userDoc=capturedDocument(HUITU_EXPORT_CONFIG.targetDocument,HUITU_EXPORT_CONFIG.targetDocumentPath),tempDoc=null,oldLevel=app.userInteractionLevel;
 function capturedDocument(name,path){
  if(!name&&!path)throw new Error('Captured target document required');
  var key=String(path||'').replace(/\\/g,'/').toLowerCase(),chosen=null,count=0;
  for(var di=0;di<app.documents.length;di++){
   var candidate=app.documents[di],matched=false;
   if(key){var actual='';try{actual=String(candidate.fullName.fsName).replace(/\\/g,'/').toLowerCase();}catch(unsaved){}matched=actual===key;}
   else matched=candidate.name===name;
   if(matched){chosen=candidate;count++;}
  }
  if(!count)throw new Error('Captured target document missing: '+name);
  if(count!==1)throw new Error('Captured target document ambiguous: '+name);
  chosen.activate();return chosen;
 }
 function q(v){return '"'+String(v).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\r/g,'\\r').replace(/\n/g,'\\n')+'"';}
 function findNamed(node,name){
  if(node.name===name)return node;
  if(node.typename==='GroupItem')for(var i=0;i<node.pageItems.length;i++){
   var found=findNamed(node.pageItems[i],name);if(found)return found;
  }
  return null;
 }
 try{
  if(userDoc.name!==c.targetDocument)throw new Error('Captured figure document is not active');
  var original=userDoc.groupItems.getByName(c.groupName);
  app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;
  tempDoc=app.documents.add(DocumentColorSpace.RGB,c.width,c.height);
  var copy=original.duplicate(tempDoc.activeLayer,ElementPlacement.PLACEATBEGINNING);
  // Expand before scaling: scaling a symbol then breaking its link can apply
  // the inverse line-width factor twice. This copy is disposable.
  var symbolsBefore=copy.symbolItems.length;
  while(copy.symbolItems.length)copy.symbolItems[0].breakLink();
  copy.resize(100/c.scale,100/c.scale,true,true,true,true,100/c.scale,Transformation.TOPLEFT);
  var backgroundSpec=null;
  for(var bi=0;bi<(c.objects||[]).length;bi++)if(c.objects[bi].id==='background'){
   if(backgroundSpec)throw new Error('Duplicate declared background owner');
   backgroundSpec=c.objects[bi];
  }
  if(!backgroundSpec)throw new Error('Declared background owner missing');
  var anchor=findNamed(copy,backgroundSpec.name+' ['+backgroundSpec.id+']');
  if(!anchor)throw new Error('Expanded background owner missing');
  var b=anchor.geometricBounds,r=tempDoc.artboards[0].artboardRect;
  if(Math.abs(b[2]-b[0]-c.width)>.02||Math.abs(b[1]-b[3]-c.height)>.02)throw new Error('Native figure bounds differ from source canvas');
  copy.translate(r[0]-b[0],r[1]-b[1]);
  function countText(node){
   if(node.typename==='TextFrame')return 1;
   var count=0;if(node.typename==='GroupItem')for(var ti=0;ti<node.pageItems.length;ti++)count+=countText(node.pageItems[ti]);
   return count;
  }
  var actualText=countText(copy);
  var png=new ExportOptionsPNG24();png.antiAliasing=c.antiAliasing;png.transparency=false;png.artBoardClipping=true;png.horizontalScale=100;png.verticalScale=100;
  tempDoc.exportFile(new File(c.outputPng),ExportType.PNG24,png);
  if(c.outputAi){
   if(userDoc.fullName.fsName===(new File(c.outputAi)).fsName)throw new Error('Use a distinct source-size AI path');
   if(c.objectMode==='symbol'){
    // Reprotect the full-size editable AI after native vector scaling.
    for(var oi=0;oi<c.objects.length;oi++){
     var spec=c.objects[oi],name=spec.name+' ['+spec.id+']';
     var owner=findNamed(copy,name);
     if(!owner)throw new Error('Full-size owner missing '+spec.id);
     var vb=owner.visibleBounds,symbol=tempDoc.symbols.add(owner);
     // Duplicated instances import their previous definitions too. Full-size
     // rebuilt symbols need a distinct namespace to avoid name collisions.
     symbol.name=spec.name.substring(0,40)+' ['+c.svgSha256.substring(0,8)+'-full-'+oi+']';
     var instance=tempDoc.symbolItems.add(symbol);instance.name=name;instance.move(copy,ElementPlacement.PLACEATBEGINNING);
     var ib=instance.visibleBounds;instance.translate(vb[0]-ib[0],vb[1]-ib[1]);owner.remove();
    }
   }
   var options=new IllustratorSaveOptions();options.pdfCompatible=false;options.compressed=true;tempDoc.saveAs(new File(c.outputAi),options);
  }
  return '{"status":"PASS","svg_sha256":'+q(c.svgSha256)+',"source_size":['+c.width+','+c.height+'],"live_text":'+actualText+',"raster_items":'+tempDoc.rasterItems.length+',"anti_aliasing":'+c.antiAliasing+',"output_png":'+q(c.outputPng)+',"user_document_preserved":true}';
 }catch(error){return '{"status":"FAIL","error":'+q(error)+'}';}
 finally{
  if(tempDoc)try{tempDoc.close(SaveOptions.DONOTSAVECHANGES);}catch(ignoreClose){}
  userDoc.activate();app.userInteractionLevel=oldLevel;
 }
}());
