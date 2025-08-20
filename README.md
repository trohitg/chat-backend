# Chat Backend API

A simple chat program that lets you talk to AI robots. Built with Python and Docker.

## What this does

- Start new chats with AI
- Send messages and get smart replies
- Keep your chat history saved
- Upload pictures (saves the filename only)
- Handle money payments through Razorpay

## How to use it

### Easy setup with Docker

1. **Get an API key**: Go to [OpenRouter](https://openrouter.ai/) and sign up to get your API key

2. **Set up your settings**:
   ```bash
   cp .env.template .env
   # Edit the .env file and add your OPENROUTER_API_KEY
   ```

3. **Start everything**:
   ```bash
   docker-compose up -d
   ```

4. **Test it works**:
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

### What you get

- **Main API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## How to use the API

### 1. Start a chat session
```bash
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{}'
```

You get back:
```json
{
  "session_id": "sess_abc123",
  "created_at": "2025-08-23T10:30:00Z",
  "expires_in": 3600
}
```

### 2. Send a message
```bash
curl -X POST http://localhost:8000/api/v1/sessions/sess_abc123/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, how are you?"}'
```

You get back:
```json
{
  "id": "msg_xyz789",
  "content": "Hello! I'm doing well, thank you for asking. How can I help you today?",
  "role": "assistant",
  "created_at": "2025-08-23T10:31:00Z"
}
```

### 3. Get your chat history
```bash
curl http://localhost:8000/api/v1/sessions/sess_abc123/messages
```

### 4. Send image with text
```bash
curl -X POST http://localhost:8000/api/v1/images/sessions/sess_abc123/messages \
  -F "message=Tell me about this image" \
  -F "image=@photo.jpg"
```

## What's inside

- **PostgreSQL**: A database that remembers your chats
- **Redis**: Makes the app run faster by remembering things
- **Nginx**: Helps handle internet requests
- **Prometheus + Grafana**: Shows how well the app is working (you don't need this)

## Settings you can change

Put these in your `.env` file:

```bash
# Required
OPENROUTER_API_KEY=your_api_key_here

# Optional (have defaults)
DATABASE_URL=postgresql://chatuser:chatpass123@postgres:5432/chatdb
REDIS_URL=redis://redis:6379/0
DEBUG=false
LOG_LEVEL=INFO
```

## AI robots you can talk to

The app can talk to different AI robots through OpenRouter:
- `gpt-oss-120b` (this one is used by default)
- `llama3.1-8b`
- `llama-3.3-70b`  
- `qwen-3-32b`
- And many more...

You can switch between different AI robots using the app's settings

## Run without Docker

```bash
# Install Python packages
pip install -r requirements.txt

# Start database and cache
docker-compose up -d postgres redis

# Run the API
python -m uvicorn app.main:app --reload
```

## Monitor performance

If you want to see performance stats:
```bash
# Start with monitoring
docker-compose --profile monitoring up -d

# View metrics at:
# - Grafana: http://localhost:3000 (admin/admin123)
# - Prometheus: http://localhost:9090
```

## Common commands

```bash
# Check if everything is running
docker-compose ps

# View logs
docker-compose logs -f chat-api

# Stop everything
docker-compose down

# Update and restart
docker-compose up -d --build
```

## If something goes wrong

**App not working?**
- Run `docker-compose ps` - everything should say "Up"
- Look at error messages: `docker-compose logs chat-api`
- Double-check your API key in the `.env` file

**Database not working?**
- Wait 1-2 minutes for the database to start up
- Check for errors: `docker-compose logs postgres`

**Can't reach the app?**
- Make sure no other programs are using ports 8000, 5432, or 6379
- Test if it's working: `curl http://localhost:8000/api/v1/health`

## Important things to know

- Pictures get saved but the AI can't actually see them yet
- Your chat history gets saved in a database so you won't lose it
- The app uses tricks to make responses come back faster
- All smart replies come from AI robots through a service called OpenRouter
- Each message is separate - the AI doesn't remember previous messages in the same chat

## More help

- [Security Guide](docs/SECURITY.md) - How to keep your API keys safe
- [Payment Setup](docs/RAZORPAY_WEBHOOK_SETUP.md) - How to set up payments
- [Scripts](scripts/) - Helper scripts for running the system

---

Built with FastAPI, PostgreSQL, Redis, and Docker for easy setup and deployment.

## License

This project is licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) - see the [LICENSE](LICENSE) file for details.

**What this means:**
- ✅ You can use this code for personal and educational purposes
- ✅ You can modify and improve it
- ✅ You must give credit to the original creators
- ❌ You cannot use it for commercial purposes without permission
- 📢 If you share your changes, use the same license