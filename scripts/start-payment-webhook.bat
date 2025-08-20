@echo off
echo ============================================
echo   Starting Chat Backend Payment Webhooks
echo   Self-Contained Cloudflare Tunnel Setup
echo ============================================
echo.

REM Check if we're in the right directory
if not exist "docker-compose.yml" (
    echo Error: docker-compose.yml not found!
    echo Please run this script from the chat-backend directory
    pause
    exit /b 1
)

echo Step 1: Setting up Cloudflare Tunnel Credentials...
echo.

REM Check if tunnel credentials are set up
if not exist "tunnel\credentials.json" (
    echo Tunnel directory not found! Setting up tunnel credentials...
    if not exist "tunnel" mkdir tunnel
)

REM Check if credentials are properly configured
findstr "placeholder" tunnel\credentials.json >nul 2>&1
if %errorlevel% equ 0 (
    echo Cloudflare credentials not configured!
    echo.
    echo You need to create an independent tunnel first.
    echo This will create a separate tunnel from workflow_rl.
    echo.
    echo Running independent tunnel creation...
    cd tunnel
    call create-independent-tunnel.bat
    cd ..
    echo.
) else (
    echo ✓ Cloudflare credentials already configured
)

echo.
echo Step 1.5: Verifying DNS configuration...
echo.

REM Check if api.disutopia.xyz exists
echo Checking if api.disutopia.xyz exists...
nslookup api.disutopia.xyz 8.8.8.8 >nul 2>&1

if %errorlevel% neq 0 (
    echo ⚠ DNS record for api.disutopia.xyz does not exist!
    echo Creating DNS record now...
    echo.
    cd tunnel
    call create-dns-record.bat
    cd ..
    echo.
) else (
    echo ✓ DNS record exists for api.disutopia.xyz
)

echo.
echo Step 2: Building Docker Images...
echo.

echo Building tunnel image...
docker-compose build cloudflared

echo Building reverse proxy...
docker-compose build reverse-proxy

echo.
echo Step 3: Starting Services...
echo.

echo Starting database and cache services...
docker-compose up -d postgres redis

echo Waiting for database to be ready...
timeout /t 10 /nobreak > nul

echo Starting main application...
docker-compose up -d chat-api

echo Starting reverse proxy...
docker-compose up -d reverse-proxy

echo Starting Cloudflare tunnel...
docker-compose up -d cloudflared

echo.
echo Step 4: Waiting for services to be ready...
timeout /t 15 /nobreak > nul

echo Checking service status...
docker-compose ps

echo.
echo Step 5: Running tunnel dependency check...
docker-compose up tunnel-check

echo.
echo Step 6: Testing Webhook URLs...
echo.

echo Testing local health endpoint...
curl -f http://localhost:8000/api/v1/health 2>nul && (
    echo ✓ Local API health check passed
) || (
    echo ✗ Local API health check failed
    docker logs chat-api --tail 5
)

echo.
echo Testing reverse proxy...
curl -f http://localhost:8080/api/v1/health 2>nul && (
    echo ✓ Reverse proxy health check passed  
) || (
    echo ✗ Reverse proxy health check failed
    docker logs chat-reverse-proxy --tail 5
)

echo.
echo Testing public webhook URL...
timeout /t 5 /nobreak > nul
curl -f https://api.disutopia.xyz/api/v1/health 2>nul && (
    echo ✓ Public API health check passed
) || (
    echo ✗ Public API health check failed - tunnel may still be connecting
    docker logs chat-cloudflared --tail 5
)

echo.
echo ============================================
echo   Chat Backend Payment Webhooks Ready!
echo ============================================
echo.
echo Primary Webhook URL:
echo   https://api.disutopia.xyz/api/v1/payments/webhook
echo.
echo Alternative Webhook URLs:
echo   https://api.disutopia.xyz/webhook  
echo.
echo Service URLs:
echo   - Health Check: https://api.disutopia.xyz/api/v1/health
echo   - Local API: http://localhost:8000/api/v1/health
echo   - Reverse Proxy: http://localhost:8080/api/v1/health
echo.
echo Configure in Razorpay Dashboard:
echo   - URL: https://api.disutopia.xyz/api/v1/payments/webhook
echo   - Secret: webhook_secret_123 (from .env)
echo   - Events: payment.captured, payment.failed, payment.authorized
echo.
echo Monitoring Commands:
echo   - View chat logs: docker logs -f chat-api
echo   - View tunnel logs: docker logs -f chat-cloudflared
echo   - View proxy logs: docker logs -f chat-reverse-proxy
echo   - View all services: docker-compose ps
echo   - Stop all services: docker-compose down
echo.
echo Troubleshooting:
echo   - If tunnel fails: Check credentials in tunnel/credentials.json
echo   - If API fails: Check docker logs chat-api
echo   - If proxy fails: Check docker logs chat-reverse-proxy
echo.
pause