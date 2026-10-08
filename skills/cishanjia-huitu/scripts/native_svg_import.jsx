(function(){
 var c=HUITU_NATIVE_CONFIG, source=null, target=null, layer=null, root=null, tempBoard=null,smokeDocument=null,userDocument=null;
 var oldLevel=app.userInteractionLevel, oldBoard=0, completed=false,phase='attach';
 function quoted(v){return '"'+String(v).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\r/g,'\\r').replace(/\n/g,'\\n')+'"';}
 function writeReport(status,detail,extra){
  var f=new File(c.report);f.encoding='UTF-8';if(!f.open('w'))throw new Error('Cannot write native report');
  f.write('{"status":'+quoted(status)+',"svg_sha256":'+quoted(c.sha256)+',"detail":'+quoted(detail)+(extra||'')+'}');f.close();
 }
 function actualFamily(font){return String(font.family).toLowerCase().replace(/\s+/g,' ');}
 function definitionName(spec){
  var index=-1;for(var i=0;i<c.objects.length;i++)if(c.objects[i].id===spec.id){index=i;break;}
  // Illustrator limits definition names to 63 characters. Keep a readable
  // prefix and a compact unique suffix even for long pathway captions.
  return spec.name.substring(0,40)+' ['+c.sha256.substring(0,8)+'-'+index+']';
 }
 function wholeObject(group,spec){
  if(c.objectMode!=='symbol')return group;
  // Symbol bounds include painted strokes; align visible artwork rather than
  // assuming the group's geometric bounds survive conversion unchanged.
  var b=group.visibleBounds,name=group.name;
  var definition=target.symbols.add(group);definition.name=definitionName(spec);
  var item=target.symbolItems.add(definition);item.name=name;
  item.note='cishanjia-huitu semantic object: '+spec.id+'; double-click to edit internal vectors and live text';
  item.move(root,ElementPlacement.PLACEATBEGINNING);
  var ib=item.visibleBounds;item.translate(b[0]-ib[0],b[1]-ib[1]);group.remove();
  var now=item.visibleBounds;
  for(var k=0;k<4;k++)if(Math.abs(now[k]-b[k])>.02)throw new Error('Symbol placement changed geometry: '+spec.id);
  return item;
 }
 function objectContainers(carrier){
  var result={},objects=c.objects||[];
  for(var oi=0;oi<objects.length;oi++){
   var object=objects[oi],group=null;
   try{group=carrier.groupItems.getByName(object.svg_id);}catch(missingGroup){}
   if(!group){
    if(object.graphic_count>0)throw new Error('Imported object group missing: '+object.id);
    group=carrier.groupItems.add();group.name=object.svg_id;
   }
   if(group.parent!==carrier)throw new Error('Object group is not a direct figure child: '+object.id);
   result[object.id]=group;
  }
  return result;
 }
 function textContainer(wanted,carrier,containers){
  if(c.grouping!=='semantic-v1')return carrier;
  if(!wanted.object_id||!containers[wanted.object_id])throw new Error('Live text lacks a declared object owner: '+wanted.content);
  return containers[wanted.object_id];
 }
 function fontFor(label){
  var token=label.family.replace(/[^A-Za-z0-9]/g,''),bold=String(label.weight).toLowerCase()==='bold'||Number(label.weight)>=600;
  var italic=label.style==='italic'||label.style==='oblique',suffix='';
  if(bold&&italic)suffix='-BoldItalic';else if(bold)suffix='-Bold';else if(italic)suffix='-Italic';
  var candidates=[token+suffix+'MT',token+suffix,label.family+suffix+'MT',label.family+suffix];
  for(var i=0;i<candidates.length;i++)for(var k=0;k<app.textFonts.length;k++){
   var f=app.textFonts[k];if(f.name!==candidates[i])continue;
   var s=String(f.style).toLowerCase();
   if(bold===/bold|demi|black|heavy/.test(s)&&italic===/italic|oblique/.test(s))return f;
  }
  for(var j=0;j<app.textFonts.length;j++){
   var face=app.textFonts[j],style=String(face.style).toLowerCase();
   if(actualFamily(face)===label.family.toLowerCase()&&bold===/bold|demi|black|heavy/.test(style)&&italic===/italic|oblique/.test(style))return face;
  }
  throw new Error('Requested native font unavailable: '+label.family+' / '+label.weight+' / '+label.style);
 }
 if(c.preflight){
  var fontNames=[];for(var pf=0;pf<c.labels.length;pf++)fontNames.push(quoted(fontFor(c.labels[pf]).name));
  return '['+fontNames.join(',')+']';
 }
 try{
  if(!app.documents.length)throw new Error('No existing Illustrator document');
  userDocument=app.activeDocument;
  if(c.smoke){smokeDocument=app.documents.add(DocumentColorSpace.RGB,320,220);target=smokeDocument;}
  else target=userDocument;
  oldBoard=target.artboards.getActiveArtboardIndex();
  var before=target.pageItems.length, priorLayers=[];
  for(var k=0;k<target.layers.length;k++){
   if(target.layers[k].name===c.jobName)throw new Error('This job already exists; inspect before retry');
   priorLayers.push({layer:target.layers[k],count:target.layers[k].pageItems.length});
  }
  writeReport('STARTED','Native SVG import into captured existing document');
  app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;
  phase='open-svg';source=app.open(new File(c.input));source.activate();
  if(source.rasterItems.length||source.placedItems.length)throw new Error('Unexpected raster/placed items');
  if(source.textFrames.length!==0)throw new Error('Graphics-only import contains text');
  var fontEvidence=[],sourceRect=source.artboards[0].artboardRect;
  phase='collect-top-items';writeReport('STARTED',phase);
  var r=source.artboards[0].artboardRect, fullWidth=r[2]-r[0], fullHeight=r[1]-r[3];
  // The preparer wraps all graphics once. Avoid enumerating Illustrator's
  // flattened collection: repeated native indexing is extremely expensive.
  phase='create-carrier';writeReport('STARTED',phase);var carrier;
  if(source.pageItems.length){
   carrier=source.pageItems[0];
   while(carrier.parent.typename!=='Layer')carrier=carrier.parent;
   if(carrier.typename!=='GroupItem')throw new Error('Expected one prepared graphics root');
  }else carrier=source.groupItems.add();
  carrier.name=c.jobName;
  phase='verify-object-groups';var containers=objectContainers(carrier);
  for(var ti=0;ti<c.labels.length;ti++){
   var wanted=c.labels[ti];phase='create-text:'+wanted.content;
   var created=source.textFrames.pointText([sourceRect[0]+wanted.x,sourceRect[1]-wanted.y]);
   created.contents=wanted.content;
   var range=created.textRange;
   range.characterAttributes.textFont=app.textFonts.getByName(wanted.nativeFont);
   range.characterAttributes.size=wanted.size;
   range.characterAttributes.horizontalScale=wanted.horizontalScale;
   var rgb=new RGBColor();rgb.red=wanted.color[0];rgb.green=wanted.color[1];rgb.blue=wanted.color[2];
   range.characterAttributes.fillColor=rgb;
   if(wanted.letterSpacing)range.characterAttributes.tracking=Math.round(wanted.letterSpacing/wanted.size*1000);
   if(wanted.anchor==='middle')range.paragraphAttributes.justification=Justification.CENTER;
   else if(wanted.anchor==='end')range.paragraphAttributes.justification=Justification.RIGHT;
   else range.paragraphAttributes.justification=Justification.LEFT;
   var destination=textContainer(wanted,carrier,containers);
   var inheritedOpacity=c.grouping==='semantic-v1'?(destination.opacity/100)*(carrier.opacity/100):1;
   if(inheritedOpacity<=0||wanted.opacity/inheritedOpacity>100.001)throw new Error('Native object opacity cannot preserve canonical text: '+wanted.content);
   created.opacity=wanted.opacity/inheritedOpacity;
   if(wanted.rotation)created.rotate(-wanted.rotation);
   created.move(destination,ElementPlacement.PLACEATBEGINNING);
   created.name=wanted.source_id||wanted.content;
   fontEvidence.push(wanted.nativeFont);
  }
  var objectEvidence=[],sourceBounds={},verifiedTextCount=0;
  for(var ov=0;ov<(c.objects||[]).length;ov++){
   var object=c.objects[ov],objectGroup=containers[object.id];
   if(objectGroup.textFrames.length!==object.text_count)throw new Error('Native object text count mismatch: '+object.id);
   objectGroup.name=object.name+' ['+object.id+']';
   sourceBounds[object.id]=objectGroup.geometricBounds;
   verifiedTextCount+=objectGroup.textFrames.length;
   objectEvidence.push('{"id":'+quoted(object.id)+',"name":'+quoted(object.name)+',"live_text":'+objectGroup.textFrames.length+'}');
  }
  writeReport('STARTED','created-native-text:'+c.labels.length);
  target.activate();
  phase='target-layer';layer=target.layers.add();layer.name=c.jobName;
  var board=target.artboards[oldBoard].artboardRect;
  var scale=Math.min((board[2]-board[0])*c.maxFraction/fullWidth,(board[1]-board[3])*c.maxFraction/fullHeight);
  if(before>0){
   var right=board[2];for(var ai=0;ai<target.artboards.length;ai++)right=Math.max(right,target.artboards[ai].artboardRect[2]);
   board=[right+40,board[1],right+40+(board[2]-board[0]),board[3]];
   target.artboards.add(board).name=c.jobName;
   target.artboards.setActiveArtboardIndex(target.artboards.length-1);
  }
  var left=board[0]+((board[2]-board[0])-fullWidth*scale)/2,top=board[1]-((board[1]-board[3])-fullHeight*scale)/2;
  if(c.liveDraw){
   root=layer.groupItems.add();root.name=c.jobName;
   target.activate();target.selection=null;
   app.executeMenuCommand('fitall');app.redraw();
   var steps=[];
   for(var moved=0;moved<c.objects.length;moved++){
    var spec=c.objects[moved],original=containers[spec.id],originalBounds=sourceBounds[spec.id];
    phase='draw-object:'+(moved+1)+'/'+c.objects.length+':'+spec.id;
    writeReport('DRAWING',phase,',"completed_objects":'+moved+',"total_objects":'+c.objects.length);
    var copied=original.duplicate(layer,ElementPlacement.PLACEATBEGINNING);
    copied.move(root,ElementPlacement.PLACEATBEGINNING);
    copied.resize(scale*100,scale*100,true,true,true,true,scale*100,Transformation.TOPLEFT);
    var copiedBounds=copied.geometricBounds;
    var wantedLeft=left+(originalBounds[0]-sourceRect[0])*scale;
    var wantedTop=top+(originalBounds[1]-sourceRect[1])*scale;
    copied.translate(wantedLeft-copiedBounds[0],wantedTop-copiedBounds[1]);
    if(copied.parent!==root||copied.textFrames.length!==spec.text_count)throw new Error('Whole-object duplication failed: '+spec.id);
    copied=wholeObject(copied,spec);
    target.activate();target.selection=null;app.redraw();
    steps.push('{"index":'+(moved+1)+',"id":'+quoted(spec.id)+',"whole_group":true}');
    writeReport('DRAWING',phase,',"completed_objects":'+(moved+1)+',"total_objects":'+c.objects.length);
    if(c.delayMs)$.sleep(c.delayMs);
   }
   var progress=new File(c.report.replace(/native-import-report\.json$/,'drawing-steps.json'));
   progress.encoding='UTF-8';progress.open('w');progress.write('['+steps.join(',')+']');progress.close();
  }else{
   phase='duplicate-carrier';root=carrier.duplicate(layer,ElementPlacement.PLACEATBEGINNING);root.name=c.jobName;
   root.resize(scale*100,scale*100,true,true,true,true,scale*100,Transformation.TOPLEFT);
   var bounds=root.geometricBounds;root.translate(left-bounds[0],top-bounds[1]);
   if(c.objectMode==='symbol')for(var si=0;si<c.objects.length;si++){
    var sp=c.objects[si];wholeObject(root.groupItems.getByName(sp.name+' ['+sp.id+']'),sp);
   }
  }
  var finalBounds=root.geometricBounds;
  tempBoard=target.artboards.add([left,top,left+fullWidth*scale,top-fullHeight*scale]);
  target.artboards.setActiveArtboardIndex(target.artboards.length-1);
  var png=new ExportOptionsPNG24();png.antiAliasing=true;png.transparency=false;png.artBoardClipping=true;
  png.horizontalScale=100*c.canvasWidth/(fullWidth*scale);png.verticalScale=png.horizontalScale;
  phase='export';writeReport('STARTED',phase);target.exportFile(new File(c.outputPng),ExportType.PNG24,png);
  tempBoard.remove();tempBoard=null;target.artboards.setActiveArtboardIndex(oldBoard);
  for(var check=0;check<priorLayers.length;check++)if(priorLayers[check].layer.pageItems.length!==priorLayers[check].count)throw new Error('Prior artwork count changed');
  var save=new IllustratorSaveOptions();save.pdfCompatible=false;save.compressed=true;
  phase='save';writeReport('STARTED',phase);target.saveAs(new File(c.outputAi),save);
  if(!(new File(c.outputAi)).exists||!(new File(c.outputPng)).exists)throw new Error('Output missing');
  completed=true;
  var fontJson=[];for(var fi=0;fi<fontEvidence.length;fi++)fontJson.push(quoted(fontEvidence[fi]));
  writeReport('PASS','Native editable artwork appended; inspect exported PNG',',"target_document":'+quoted(target.name)+',"prior_items":'+before+',"prior_artwork_preserved":true,"live_text":'+verifiedTextCount+',"raster_items":0,"placed_items":0,"imported_items":'+root.pageItems.length+',"scale":'+scale+',"native_fonts":['+fontJson.join(',')+'],"object_mode":'+quoted(c.objectMode||'group')+',"symbol_items":'+root.symbolItems.length+',"object_grouping":'+quoted(c.grouping||'flat-legacy')+',"object_groups":['+objectEvidence.join(',')+']');
  return 'PASS|live_text='+verifiedTextCount+'|items='+root.pageItems.length+'|prior_items='+before;
 }catch(error){
  try{writeReport('FAIL',String(error)+'|phase='+phase+'|line='+error.line);}catch(ignoreWrite){}
  return 'ERROR|'+String(error)+'|phase='+phase+'|line='+error.line;
 }finally{
  if(tempBoard)try{tempBoard.remove();}catch(ignoreBoard){}
  // A failed export/save retains this job for inspection rather than duplicating it.
  if(source)try{source.close(SaveOptions.DONOTSAVECHANGES);}catch(ignoreSource){}
  if(smokeDocument)try{smokeDocument.close(SaveOptions.DONOTSAVECHANGES);}catch(ignoreSmoke){}
  if(c.smoke)target=userDocument;
  if(target)try{target.activate();target.artboards.setActiveArtboardIndex(oldBoard);app.redraw();}catch(ignoreTarget){}
  app.userInteractionLevel=oldLevel;
 }
}());
