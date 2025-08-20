FROM cloudflare/cloudflared:latest

# Copy tunnel configuration
COPY config.yml /etc/cloudflared/config.yml

# Copy credentials (will be populated by setup script)
COPY credentials.json /etc/cloudflared/credentials.json

# Copy certificate (will be populated by setup script) 
COPY cert.pem /etc/cloudflared/cert.pem

# Run the tunnel with config
CMD ["tunnel", "--config", "/etc/cloudflared/config.yml", "run"]