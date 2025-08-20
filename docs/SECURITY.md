# Security Configuration Guide

## ⚠️ CRITICAL SECURITY NOTICE

**NEVER commit API keys, secrets, or credentials to git!**

This project requires several API keys and secrets to function. All sensitive data must be stored in environment variables and never hardcoded in the source code.

## 📋 Required Environment Variables

### 1. OpenRouter API Key
```bash
OPENROUTER_API_KEY=your-openrouter-api-key-here
```
- Get your API key from: https://openrouter.ai/
- Required for AI model access

### 2. Security Keys
```bash
SECRET_KEY=your-very-strong-secret-key-here
```
- Generate a strong, random secret key (50+ characters)
- Used for JWT tokens and session security
- **NEVER** use the default placeholder value in production

### 3. Razorpay Payment Gateway
```bash
RAZORPAY_KEY_ID=your-razorpay-key-id-here
RAZORPAY_KEY_SECRET=your-razorpay-key-secret-here
RAZORPAY_WEBHOOK_SECRET=your-webhook-secret-here
```
- Get your keys from: https://razorpay.com/
- Required for payment processing

### 4. Cloudflare Tunnel Credentials (Optional)
```bash
# tunnel/credentials.json (copy from tunnel/credentials.json.template)
{
  "AccountTag": "your-cloudflare-account-tag-here",
  "TunnelSecret": "your-cloudflare-tunnel-secret-here", 
  "TunnelID": "your-cloudflare-tunnel-id-here"
}
```
- Get your credentials from: https://dash.cloudflare.com/
- Required only if using Cloudflare tunnels

## 🚀 Quick Setup

### Step 1: Copy Environment Template
```bash
cp .env.template .env
```

### Step 2: Fill in Your Credentials
Edit `.env` with your actual API keys and secrets.

### Step 3: Verify Security
- ✅ Check that `.env` is in `.gitignore`
- ✅ Never commit `.env` files
- ✅ Use strong, unique passwords
- ✅ Rotate keys regularly

## 🔒 Security Best Practices

### Environment Files
- `.env` - Local development (NEVER commit)
- `.env.production` - Production secrets (NEVER commit)
- `.env.template` - Safe template for sharing (OK to commit)

### Key Management
1. **Generate Strong Keys**: Use tools like `openssl rand -hex 32` for secret keys
2. **Rotate Regularly**: Change API keys and secrets periodically
3. **Principle of Least Privilege**: Only grant necessary permissions
4. **Monitor Usage**: Check API key usage for unusual activity

### Docker Security
The `docker-compose.yml` file reads environment variables from your `.env` file. Never put credentials directly in Docker files.

## 🚨 If You Accidentally Commit Secrets

1. **Immediately revoke** all exposed API keys
2. **Generate new keys** from the respective providers
3. **Update your `.env` files** with new credentials
4. **Consider the git history contaminated** - may need to rewrite history

## 🔍 Verification Checklist

Before committing code, verify:
- [ ] No API keys in source code
- [ ] No secrets in configuration files
- [ ] `.env*` files are in `.gitignore`
- [ ] Only placeholder values in `.env.template` and `.env.example`
- [ ] Docker compose uses environment variables (no hardcoded values)

## 📞 Security Contact

If you discover a security vulnerability, please report it responsibly:
- Create a private GitHub issue
- Do not publicly disclose until fixed
- Provide detailed reproduction steps

---

**Remember: Security is everyone's responsibility! 🛡️**