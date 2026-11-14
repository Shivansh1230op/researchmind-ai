$ErrorActionPreference = 'Stop'
try {
    Write-Host 'ResearchMind - Gmail email setup' -ForegroundColor Cyan
    Write-Host 'Use a Google App Password, not your normal Gmail password.'
    Write-Host 'Create one at https://myaccount.google.com/apppasswords (requires Google 2-Step Verification).'
    do {
        $senderAddress = (Read-Host 'Sender Gmail address, e.g. yourname@gmail.com').Trim().ToLowerInvariant()
        $validSender = $senderAddress -match '^[a-z0-9.!#$%&''*+/=?^_`{|}~-]+@(gmail|googlemail)\.com$'
        if (-not $validSender) { Write-Host 'Enter only the Gmail address, without a label or quotes.' -ForegroundColor Yellow }
    } until ($validSender)
    do {
        Write-Host 'Paste the 16-character App Password. Nothing will appear while you type; press Enter afterwards.'
        $secureAppPassword = Read-Host 'Google App Password (hidden)' -AsSecureString
        $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureAppPassword)
        try { $gmailAppPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer) -replace '\s','' }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer) }
        $validPassword = $gmailAppPassword -match '^[a-zA-Z0-9]{16}$'
        if (-not $validPassword) {
            $secureAppPassword.Dispose()
            Write-Host 'That was not 16 characters. Create an App Password at the Google link above and try again.' -ForegroundColor Yellow
        }
    } until ($validPassword)
    $envFilePath = Join-Path $PSScriptRoot '.env'
    $contents = if (Test-Path -LiteralPath $envFilePath) { [IO.File]::ReadAllText($envFilePath) } else { '' }
    $settingsToSave = [ordered]@{
        SMTP_HOST='smtp.gmail.com'; SMTP_PORT='587'; SMTP_USERNAME=$senderAddress
        SMTP_PASSWORD=$gmailAppPassword; SMTP_FROM_EMAIL=$senderAddress
        SMTP_STARTTLS='true'; SMTP_USE_SSL='false'
    }
    foreach ($setting in $settingsToSave.GetEnumerator()) {
        $pattern = '(?m)^' + [regex]::Escape($setting.Key) + '\s*=.*$'
        $replacement = $setting.Key + '=' + $setting.Value
        if ([regex]::IsMatch($contents,$pattern)) {
            $contents = [regex]::Replace($contents,$pattern,[System.Text.RegularExpressions.MatchEvaluator]{ param($match) $replacement })
        } else { $contents = $contents.TrimEnd() + "`r`n" + $replacement + "`r`n" }
    }
    [IO.File]::WriteAllText($envFilePath,$contents,(New-Object System.Text.UTF8Encoding($false)))
    $gmailAppPassword=$null; $contents=$null; $settingsToSave=$null; $replacement=$null
    $secureAppPassword.Dispose()
    Write-Host 'SUCCESS: Gmail settings saved privately in .env.' -ForegroundColor Green
    Write-Host 'Restart the ResearchMind backend to activate them, then use Sign up to send a real verification code.'
} catch {
    # Avoid printing exception contents that could contain credential values.
    Write-Host 'Setup did not complete. Check the sender address and use a 16-letter Google App Password.' -ForegroundColor Red
}
Read-Host 'Press Enter to close' | Out-Null
