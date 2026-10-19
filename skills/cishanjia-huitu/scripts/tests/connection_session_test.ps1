param([string]$Helper)
$ErrorActionPreference='Stop'
. $Helper
# Fail the old implementation before it can reach any live COM backend.
if(-not (Get-Command Get-HuituActiveIllustrator).Parameters.ContainsKey('Attach')){throw 'Missing injectable connection backend'}
$script:calls=@();$script:scans=0;$script:HuituCachedProgId=$null
function Assert($test,$message){if(-not $test){throw $message}}
$attach={param($name) $script:calls+=,$name;if($name -eq 'Illustrator.Application'){return 'existing-app'};throw 'not running'}
$discover={$script:scans++;throw 'Fast path must not discover registry'}
$result=Get-HuituActiveIllustrator -Attach $attach -Discover $discover
Assert ($result -eq 'existing-app') 'wrong application'
Assert ($script:scans -eq 0) 'unnecessary registry discovery'
$script:calls=@();$script:HuituCachedProgId=$null
$fallback={param($name) $script:calls+=,$name;if($name -eq 'Illustrator.Application.99'){return 'versioned-app'};throw 'not running'}
$versions={$script:scans++;return @('Illustrator.Application.99')}
Assert ((Get-HuituActiveIllustrator -Attach $fallback -Discover $versions) -eq 'versioned-app') 'version fallback failed'
$before=$script:scans;$script:calls=@()
Assert ((Get-HuituActiveIllustrator -Attach $fallback -Discover $versions) -eq 'versioned-app') 'cached identifier failed'
Assert ($script:scans -eq $before) 'cached identifier rescanned registry'
Assert ($script:calls[0] -eq 'Illustrator.Application.99') 'successful identifier not reused'
$script:calls=@()
Assert ((Get-HuituActiveIllustrator -Attach $attach -Discover $discover) -eq 'existing-app') 'restart fallback failed'
Assert ($script:calls[0] -eq 'Illustrator.Application.99') 'stale identifier was not rechecked'
$script:scans=0;$script:HuituCachedProgId=$null
try{Get-HuituActiveIllustrator -Attach {throw 'absent'} -Discover {$script:scans++;@()} | Out-Null;throw 'Expected failure'}catch{Assert ($_.Exception.Message -like '*HUITU_ILLUSTRATOR_NOT_RUNNING*') 'wrong missing-app failure'}
Assert ($script:scans -eq 1) 'missing app discovery not bounded'
'MOCK_CONNECTION_PASS'
