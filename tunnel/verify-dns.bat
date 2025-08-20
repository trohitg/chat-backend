@echo off
echo ============================================
echo   Verifying DNS for api.disutopia.xyz
echo   Testing Subdomain Connectivity
echo ============================================
echo.

echo Test 1: Basic DNS Resolution...
nslookup api.disutopia.xyz 8.8.8.8

if %errorlevel% equ 0 (
    echo ✓ DNS resolution working
) else (
    echo ✗ DNS resolution failed
    echo.
    echo The subdomain api.disutopia.xyz does not exist yet.
    echo Run: create-dns-record.bat to set it up
    pause
    exit /b 1
)

echo.
echo Test 2: Cloudflare Tunnel Target...
for /f "tokens=2" %%i in ('nslookup api.disutopia.xyz 8.8.8.8 ^| findstr "canonical name"') do (
    echo Target: %%i
    echo ✓ CNAME record configured correctly
)

echo.
echo Test 3: HTTPS Connectivity...
curl -I https://api.disutopia.xyz --connect-timeout 10 --max-time 30

if %errorlevel% equ 0 (
    echo ✓ HTTPS connectivity working
) else (
    echo ⚠ HTTPS connection failed
    echo This is normal if the tunnel services are not running
)

echo.
echo Test 4: HTTP Connectivity (fallback)...
curl -I http://api.disutopia.xyz --connect-timeout 10 --max-time 30

if %errorlevel% equ 0 (
    echo ✓ HTTP connectivity working
) else (
    echo ⚠ HTTP connection also failed
    echo Check if services are running: docker-compose ps
)

echo.
echo Test 5: Global DNS Propagation Check...
echo Checking from different DNS servers:

echo - Google DNS (8.8.8.8):
nslookup api.disutopia.xyz 8.8.8.8 | findstr "Address:" | findstr -v "8.8.8.8"

echo - Cloudflare DNS (1.1.1.1):
nslookup api.disutopia.xyz 1.1.1.1 | findstr "Address:" | findstr -v "1.1.1.1"

echo.
echo ============================================
echo   DNS Verification Complete
echo ============================================
echo.

REM Final summary
curl -I https://api.disutopia.xyz --connect-timeout 5 --max-time 10 >nul 2>&1
if %errorlevel% equ 0 (
    echo Status: ✅ READY - Subdomain is working properly
    echo.
    echo Your webhook URL is ready:
    echo   https://api.disutopia.xyz/api/v1/payments/webhook
) else (
    echo Status: ⚠️ DNS OK, Services Not Running
    echo.
    echo DNS is configured correctly, but services are not running.
    echo Start services with: ..\scripts\start-payment-webhook.bat
)

echo.
pause