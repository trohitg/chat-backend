@echo off
echo ============================================
echo   Creating Independent Cloudflare Tunnel
echo   for Chat Backend Payment Webhooks
echo ============================================
echo.

REM Check if cloudflared is installed
cloudflared --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: cloudflared not found!
    echo Please install Cloudflare Tunnel first:
    echo https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/
    pause
    exit /b 1
)

echo Step 1: Authenticating with Cloudflare (if needed)...
echo.
echo This will open your browser to authenticate with Cloudflare.
echo If you're already authenticated, this will be skipped.
echo.
pause
cloudflared tunnel login

echo.
echo Step 2: Creating new tunnel for chat-backend...
echo.

REM Generate a unique tunnel name
set "TUNNEL_NAME=chat-backend-%RANDOM%"
echo Creating tunnel: %TUNNEL_NAME%

cloudflared tunnel create %TUNNEL_NAME%

if %errorlevel% neq 0 (
    echo Error: Failed to create tunnel
    echo Please check your Cloudflare authentication
    pause
    exit /b 1
)

echo.
echo Step 3: Getting tunnel information...

REM List tunnels to get the ID
echo Getting tunnel ID...
for /f "tokens=1" %%i in ('cloudflared tunnel list ^| findstr "%TUNNEL_NAME%"') do set TUNNEL_ID=%%i

if "%TUNNEL_ID%"=="" (
    echo Error: Could not find created tunnel ID
    pause
    exit /b 1
)

echo Tunnel created successfully!
echo Tunnel Name: %TUNNEL_NAME%
echo Tunnel ID: %TUNNEL_ID%

echo.
echo Step 4: Creating tunnel configuration...

REM Create new config with the new tunnel ID
echo tunnel: %TUNNEL_ID% > config.yml
echo credentials-file: /etc/cloudflared/credentials.json >> config.yml
echo. >> config.yml
echo ingress: >> config.yml
echo   - hostname: api.disutopia.xyz >> config.yml
echo     service: http://chat-reverse-proxy:80 >> config.yml
echo     originRequest: >> config.yml
echo       noTLSVerify: true >> config.yml
echo       httpHostHeader: api.disutopia.xyz >> config.yml
echo   - service: http_status:404 >> config.yml

echo.
echo Step 5: Setting up DNS record...
echo.
echo Creating DNS record for api.disutopia.xyz...
echo Target: %TUNNEL_ID%.cfargotunnel.com
echo.

cloudflared tunnel route dns %TUNNEL_ID% api.disutopia.xyz

if %errorlevel% neq 0 (
    echo.
    echo ⚠ WARNING: Automatic DNS creation failed!
    echo.
    echo You MUST manually create the DNS record in Cloudflare Dashboard:
    echo.
    echo 1. Go to: https://dash.cloudflare.com/
    echo 2. Select domain: disutopia.xyz  
    echo 3. Go to DNS Records section
    echo 4. Add CNAME record:
    echo    - Name: api
    echo    - Target: %TUNNEL_ID%.cfargotunnel.com
    echo    - TTL: Auto
    echo    - Proxy status: Orange cloud (Proxied)
    echo.
    echo 5. Wait 1-2 minutes for DNS propagation
    echo.
    echo Press any key after creating the DNS record...
    pause
) else (
    echo ✓ DNS record created successfully!
    echo Waiting for DNS propagation (30 seconds)...
    timeout /t 30 /nobreak > nul
)

echo.
echo Step 6: Copying tunnel credentials...

REM Find the credentials file
set "CREDS_FILE=%USERPROFILE%\.cloudflared\%TUNNEL_ID%.json"
if exist "%CREDS_FILE%" (
    copy "%CREDS_FILE%" credentials.json >nul 2>&1
    echo ✓ Credentials copied
) else (
    echo Error: Credentials file not found at %CREDS_FILE%
    pause
    exit /b 1
)

REM Copy certificate
if exist "%USERPROFILE%\.cloudflared\cert.pem" (
    copy "%USERPROFILE%\.cloudflared\cert.pem" cert.pem >nul 2>&1
    echo ✓ Certificate copied
) else (
    echo Error: Certificate not found. Please run: cloudflared tunnel login
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Independent Tunnel Created Successfully!
echo ============================================
echo.
echo Tunnel Details:
echo   Name: %TUNNEL_NAME%
echo   ID: %TUNNEL_ID%
echo   Domain: api.disutopia.xyz
echo.
echo Webhook URL:
echo   https://api.disutopia.xyz/api/v1/payments/webhook
echo.
echo Next Steps:
echo   1. Start services: ..\scripts\start-payment-webhook.bat
echo   2. Configure Razorpay with the webhook URL above
echo   3. Test: curl https://api.disutopia.xyz/api/v1/health
echo.
echo The tunnel is now completely independent of workflow_rl!
echo.
pause