$body = @{ query = 'ಕಾಮಲೆ ಎಂದರೇನು?'; mode = 'P2'; target_lang = 'auto' } | ConvertTo-Json
$r = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/ask' -Method Post -Body $body -ContentType 'application/json'
Write-Host "Detected lang:" $r.detected_language
Write-Host "Target lang:" $r.target_language
Write-Host "Detected term:" $r.detected_term
Write-Host "Abstained:" $r.abstained
Write-Host "Generator used:" $r.generator_used
Write-Host "Citations:" $r.citations.Count
Write-Host "Answer:" $r.answer
