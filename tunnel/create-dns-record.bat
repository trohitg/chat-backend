@echo off
echo ============================================
echo   Creating DNS Record for api.disutopia.xyz
echo   Independent Script for DNS Management
echo ============================================
echo.

REM Check if we have a tunnel configuration
if not exist "config.yml" (
    echo Error: No tunnel configuration found!
    echo Please run create-independent-tunnel.bat first
    pause
    exit /b 1
)

REM Extract tunnel ID from config
for /f "tokens=2" %%i in ('findstr "tunnel:" config.yml') do set TUNNEL_ID=%%i

if "%TUNNEL_ID%"=="" (
    echo Error: Could not find tunnel ID in config.yml
    pause
    exit /b 1
)

echo Found Tunnel ID: %TUNNEL_ID%
echo Target: %TUNNEL_ID%.cfargotunnel.com
echo.

echo Attempting automatic DNS record creation...
cloudflared tunnel route dns %TUNNEL_ID% api.disutopia.xyz

if %errorlevel% neq 0 (
    echo.
    echo ============================================
    echo   MANUAL DNS SETUP REQUIRED
    echo ============================================
    echo.
    echo Automatic DNS creation failed. Please create manually:
    echo.
    echo 1. Open Cloudflare Dashboard: https://dash.cloudflare.com/
    echo 2. Select your domain: disutopia.xyz
    echo 3. Go to: DNS > Records
    echo 4. Click "Add record"
    echo 5. Configure:
    echo    - Type: CNAME
    echo    - Name: api
    echo    - Target: %TUNNEL_ID%.cfargotunnel.com
    echo    - TTL: Auto
    echo    - Proxy status: Proxied (Orange cloud)
    echo.
    echo 6. Click "Save"
    echo 7. Wait 1-2 minutes for propagation
    echo.
    echo Press any key after creating the record...
    pause
    echo.
    echo Testing DNS resolution...
) else (
    echo ✓ DNS record created automatically!
    echo Waiting for DNS propagation...
    timeout /t 30 /nobreak > nul
)

echo.
echo Testing DNS resolution for api.disutopia.xyz...
nslookup api.disutopia.xyz 8.8.8.8 >nul 2>&1

if %errorlevel% equ 0 (
    echo ✓ DNS record is working!
    echo.
    echo Testing HTTP connectivity...
    timeout /t 5 /nobreak > nul
    
    REM Try to connect to the subdomain
    curl -I https://api.disutopia.xyz --connect-timeout 10 >nul 2>&1
    if %errorlevel% equ 0 (
        echo ✓ HTTPS connectivity working!
    ) else (
        echo ⚠ HTTPS not yet available (tunnel may not be running)
        echo This is normal if you haven't started the services yet.
    )
) else (
    echo ⚠ DNS resolution not working yet
    echo This may take up to 5 minutes to propagate globally
)

echo.
echo ============================================
echo   DNS Setup Complete!
echo ============================================
echo.
echo Your subdomain: api.disutopia.xyz
echo Tunnel target: %TUNNEL_ID%.cfargotunnel.com
echo.
echo Next steps:
echo   1. Start services: ..\scripts\start-payment-webhook.bat
echo   2. Test webhook: https://api.disutopia.xyz/api/v1/health
echo   3. Configure Razorpay: https://api.disutopia.xyz/api/v1/payments/webhook
echo.
pause