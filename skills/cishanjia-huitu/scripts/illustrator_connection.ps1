# Attach only to the user's already-running Illustrator. Never start an app.
function Get-HuituPython {
 $configPath=Join-Path $PSScriptRoot '..\runtime.local.json'
 if(Test-Path -LiteralPath $configPath){
  $config=Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
  if($config.python -and (Test-Path -LiteralPath $config.python)){return [string]$config.python}
 }
 if($env:HUITU_PYTHON -and (Test-Path -LiteralPath $env:HUITU_PYTHON)){return $env:HUITU_PYTHON}
 $found=Get-Command python -ErrorAction SilentlyContinue
 if($found){return $found.Source}
 throw 'HUITU_PYTHON_MISSING|Run setup_runtime.py with your local Python 3.11+ first.'
}
function Get-HuituActiveIllustrator {
 $candidates=@()
 $configPath=Join-Path $PSScriptRoot '..\runtime.local.json'
 if(Test-Path -LiteralPath $configPath){
  $config=Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
  if($config.illustrator_progid){$candidates += [string]$config.illustrator_progid}
 }
 if($env:HUITU_ILLUSTRATOR_PROGID){$candidates += $env:HUITU_ILLUSTRATOR_PROGID}
 $candidates += 'Illustrator.Application'
 $registered=Get-ChildItem -LiteralPath 'Registry::HKEY_CLASSES_ROOT' -ErrorAction SilentlyContinue |
  Where-Object {$_.PSChildName -match '^Illustrator\.Application\.\d+$'} |
  Sort-Object { [int]($_.PSChildName.Split('.')[-1]) } -Descending
 foreach($entry in $registered){$candidates += $entry.PSChildName}
 foreach($name in ($candidates | Select-Object -Unique)){
  try {return [Runtime.InteropServices.Marshal]::GetActiveObject($name)} catch {}
 }
 throw 'HUITU_ILLUSTRATOR_NOT_RUNNING|Open Illustrator and a target document. For custom registration set HUITU_ILLUSTRATOR_PROGID.'
}
