FROM python:3.11-slim
WORKDIR /bot
COPY . /bot
# entrypoint pipes TELEGRAM_TOKEN env var to the bot via stdin
ENTRYPOINT ["sh", "-c", "echo \"$TELEGRAM_TOKEN\" | exec python3 bot.py --token-stdin"]
