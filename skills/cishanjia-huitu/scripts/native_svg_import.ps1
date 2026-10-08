[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$InputSvg,
 [Parameter(Mandatory=$true)][string]$QaReport,
 [Parameter(Mandatory=$true)][string]$WorkDir,
 [Parameter(Mandatory=$true)][string]$OutputAi,
 [Parameter(Mandatory=$true)][string]$OutputPng,
 [ValidateRange(0.1,1)][double]$MaxFraction=0.92,
 [ValidateSet('symbol','group')][string]$ObjectMode='symbol',
 [switch]$SmokeTest,
 [switch]$AllowFlatLegacy,
 [switch]$DryRun,
 [switch]$LiveDraw,
 [ValidateRange(0,10000)][int]$DelayMs=250
)
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition -eq 'Core' -and -not $DryRun){
 $forward=@('-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',$PSCommandPath)
 foreach($key in $PSBoundParameters.Keys){
  if($PSBoundParameters[$key] -is [Management.Automation.SwitchParameter]){if($PSBoundParameters[$key]){$forward+=('-'+$key)}}
  else{$forward+=@(('-'+$key),[string]$PSBoundParameters[$key])}
 }
 & powershell.exe @forward
 if($LASTEXITCODE -ne 0){throw 'NATIVE_LEGACY_HOST_FAILED'}
 exit 0
}
$resolvedInput=(Resolve-Path -LiteralPath $InputSvg).Path
$qa=Get-Content -LiteralPath $QaReport -Raw -Encoding UTF8 | ConvertFrom-Json
$stream=[IO.File]::OpenRead($resolvedInput);$provider=[Security.Cryptography.SHA256]::Create()
try{$hash=[BitConverter]::ToString($provider.ComputeHash($stream)).Replace('-','').ToLowerInvariant()}
finally{$stream.Dispose();$provider.Dispose()}
if($qa.status -ne 'PASS' -or $qa.svg_sha256 -ne $hash){throw 'HUITU_QA_INVALID|Missing, failed or stale SVG review.'}
if($qa.construction -ne 'vector-redraw-v1' -or $qa.connector_geometry_passed -ne $true){throw 'HUITU_REDRAW_REQUIRED|Authored vector drawing and clean independent connectors required.'}
# Native import is restricted to the same simple editable SVG contract.
[xml]$svg=Get-Content -LiteralPath $resolvedInput -Raw -Encoding UTF8
if(-not $AllowFlatLegacy -and $svg.DocumentElement.GetAttribute('data-huitu-grouping') -ne 'semantic-v1'){throw 'HUITU_OBJECT_GROUPS_REQUIRED|Assemble complete movable object groups before importing.'}
$forbidden=$svg.SelectNodes('//*[local-name()="image" or local-name()="tspan" or local-name()="use" or local-name()="filter" or local-name()="foreignObject" or local-name()="script" or local-name()="style"]')
if($forbidden.Count){throw 'SVG_NATIVE_CONTRACT_FAILED|Raster/resources/unsupported elements.'}
$nodes=$svg.SelectNodes('//*[local-name()="text"]')
$labels=@()
foreach($node in $nodes){
 $labels+=@{content=$node.InnerText;family=$node.GetAttribute('font-family');weight=$node.GetAttribute('font-weight');style=$node.GetAttribute('font-style');x=[double]$node.GetAttribute('x');y=[double]$node.GetAttribute('y')}
}
$jobPath=[IO.Path]::GetFullPath($WorkDir)
New-Item -ItemType Directory -Path $jobPath -Force | Out-Null
$reportPath=Join-Path $jobPath 'native-import-report.json'
. (Join-Path $PSScriptRoot 'illustrator_connection.ps1')
$taskPython=Get-HuituPython
$nativeInput=Join-Path $jobPath 'native-graphics.svg'
$nativeLabels=Join-Path $jobPath 'native-text.json'
& $taskPython -X utf8 (Join-Path $PSScriptRoot 'prepare_native_svg.py') --input $resolvedInput --graphics $nativeInput --labels $nativeLabels
if($LASTEXITCODE -ne 0){throw 'NATIVE_GEOMETRY_PREPARE_FAILED'}
$nativePayload=Get-Content -LiteralPath $nativeLabels -Raw -Encoding UTF8 | ConvertFrom-Json
$labels=$nativePayload.labels
if($null -eq $labels){$labels=@()}
$config=@{input=$resolvedInput.Replace('\','/');outputAi=[IO.Path]::GetFullPath($OutputAi).Replace('\','/');outputPng=[IO.Path]::GetFullPath($OutputPng).Replace('\','/');report=$reportPath.Replace('\','/');jobName=('cishanjia-huitu_'+$hash.Substring(0,12));sha256=$hash;labels=$labels;maxFraction=$MaxFraction;canvasWidth=[double]$svg.DocumentElement.GetAttribute('width');canvasHeight=[double]$svg.DocumentElement.GetAttribute('height');smoke=[bool]$SmokeTest}
$config.liveDraw=[bool]$LiveDraw
$config.objectMode=$ObjectMode
$config.delayMs=$DelayMs
$config.objects=@($nativePayload.objects)
$config.grouping=[string]$nativePayload.grouping
if($DryRun){$config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $jobPath 'native-dry-run.json') -Encoding UTF8; 'DRY_RUN|No Illustrator connection';exit 0}
if(Test-Path -LiteralPath $reportPath){throw 'NATIVE_IMPORT_ALREADY_ATTEMPTED|Inspect the existing job/report before retrying.'}
$config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $jobPath 'native-config.json') -Encoding UTF8
. (Join-Path $PSScriptRoot 'illustrator_connection.ps1')
$taskAi=Get-HuituActiveIllustrator
$runtime=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'native_svg_import.jsx') -Raw -Encoding UTF8
$config.preflight=$true
$preflight=$taskAi.DoJavaScript('var HUITU_NATIVE_CONFIG='+($config | ConvertTo-Json -Depth 8 -Compress)+';'+$runtime)
$preflight | Set-Content -LiteralPath (Join-Path $jobPath 'native-font-preflight.json') -Encoding UTF8
$fontNames=ConvertFrom-Json -InputObject $preflight
if($fontNames.Count -ne $nodes.Count){throw ('NATIVE_FONT_PREFLIGHT_FAILED|fonts='+$fontNames.Count+'|labels='+$nodes.Count)}
# Text is recreated as point text; do not mutate imported SVG text frames.
for($i=0;$i -lt $nodes.Count;$i++){
 $labels[$i] | Add-Member -MemberType NoteProperty -Name nativeFont -Value ([string]$fontNames[$i]) -Force
}
$config.input=$nativeInput.Replace('\','/');$config.preflight=$false
$config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $jobPath 'native-config.json') -Encoding UTF8
$literal=$config | ConvertTo-Json -Depth 8 -Compress
$result=$taskAi.DoJavaScript('var HUITU_NATIVE_CONFIG='+$literal+';'+$runtime)
$result
if($result -notlike 'PASS|*'){throw ('NATIVE_IMPORT_FAILED|'+$result)}
