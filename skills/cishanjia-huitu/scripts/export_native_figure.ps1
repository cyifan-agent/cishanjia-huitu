[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$NativeWorkDir,
 [Parameter(Mandatory=$true)][string]$QaReport,
 [Parameter(Mandatory=$true)][string]$OutputPng,
 [string]$OutputAi,
 [switch]$NoAntialias,
 [switch]$DryRun
)
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition -eq 'Core' -and -not $DryRun){
 $forward=@('-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',$PSCommandPath)
 foreach($key in $PSBoundParameters.Keys){
  if($PSBoundParameters[$key] -is [Management.Automation.SwitchParameter]){if($PSBoundParameters[$key]){$forward+=('-'+$key)}}
  else{$forward+=@(('-'+$key),[string]$PSBoundParameters[$key])}
 }
 & powershell.exe @forward
 if($LASTEXITCODE -ne 0){throw 'NATIVE_EXPORT_HOST_FAILED'}
 exit 0
}
$native=Get-Content -LiteralPath (Join-Path $NativeWorkDir 'native-import-report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$inputConfig=Get-Content -LiteralPath (Join-Path $NativeWorkDir 'native-config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$qa=Get-Content -LiteralPath $QaReport -Raw -Encoding UTF8 | ConvertFrom-Json
if($native.status -ne 'PASS' -or $qa.status -ne 'PASS' -or $native.svg_sha256 -ne $qa.svg_sha256 -or $native.svg_sha256 -ne $inputConfig.sha256){throw 'NATIVE_EXPORT_REVIEW_INVALID'}
[xml]$graphics=Get-Content -LiteralPath $inputConfig.input -Raw -Encoding UTF8
$taskWidth=[double]$graphics.DocumentElement.GetAttribute('width')
$taskHeight=[double]$graphics.DocumentElement.GetAttribute('height')
if($taskWidth -lt 1 -or $taskHeight -lt 1 -or $taskWidth -gt 20000 -or $taskHeight -gt 20000 -or $native.scale -le 0){throw 'NATIVE_EXPORT_GEOMETRY_INVALID'}
if(($inputConfig.canvasWidth -and $inputConfig.canvasWidth -ne $taskWidth) -or ($inputConfig.canvasHeight -and $inputConfig.canvasHeight -ne $taskHeight)){throw 'NATIVE_EXPORT_CANVAS_MISMATCH'}
$config=@{targetDocument=$native.target_document;groupName=$inputConfig.jobName;scale=$native.scale;width=$taskWidth;height=$taskHeight;svgSha256=$native.svg_sha256;outputPng=[IO.Path]::GetFullPath($OutputPng).Replace('\','/');outputAi='';antiAliasing=(-not [bool]$NoAntialias)}
$config.objectMode=[string]$inputConfig.objectMode
$config.objects=@($inputConfig.objects)
if($OutputAi){$config.outputAi=[IO.Path]::GetFullPath($OutputAi).Replace('\','/')}
if($DryRun){$config | ConvertTo-Json -Compress; 'DRY_RUN|No Illustrator connection';exit 0}
. (Join-Path $PSScriptRoot 'illustrator_connection.ps1')
$taskAi=Get-HuituActiveIllustrator
$runtime=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'export_native_figure.jsx') -Raw -Encoding UTF8
$result=$taskAi.DoJavaScript('var HUITU_EXPORT_CONFIG='+($config | ConvertTo-Json -Compress)+';'+$runtime)
$result | Set-Content -LiteralPath ($OutputPng+'.report.json') -Encoding UTF8
if($result -notlike '{"status":"PASS"*'){throw ('NATIVE_EXPORT_FAILED|'+$result)}
$result
