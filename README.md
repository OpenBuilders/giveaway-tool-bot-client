# Telegram Channel Bot

Bot for tracking channel additions and removals in Telegram.

## Features

- Track bot additions to channels
- Check admin rights
- Store channel information in Redis
- Track bot removals from channels

## Installation

### Standard Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Copy `.env.example` to `.env` and fill in the required environment variables:
- API_ID - Telegram app ID
- API_HASH - Telegram app hash
- BOT_TOKEN - Bot token
- REDIS_HOST - Redis host (default: localhost)
- REDIS_PORT - Redis port (default: 6379)
- REDIS_DB - Redis database (default: 0)

### Docker Installation

1. Clone the repository
2. Copy `.env.example` to `.env` and fill in the required environment variables
3. Build and run with Docker Compose:
```bash
docker-compose up -d
```

To view logs:
```bash
docker-compose logs -f bot
```

To stop the bot:
```bash
docker-compose down
```

## Project Structure

- `src/bot.py` - Main bot logic
- `src/config.py` - Configuration and environment variables
- `src/storage.py` - Redis storage operations
- `src/handlers/` - Event handlers
- `main.py` - Application entry point

## Docker Volumes

- `redis_data`: Persistent Redis storage
- `logs`: Bot log files

## Networks

The services are connected through a dedicated `bot_network` bridge network.