# Telegram Setup

This folder is the downloaded `percyitchy/pancake-pools-bot` project. It already sends Telegram alerts; the setup below connects it to your own Telegram bot and chat.

## 1. Create the Telegram bot

1. Open Telegram and message `@BotFather`.
2. Run `/newbot`.
3. Copy the bot token BotFather gives you.
4. Add the bot to the Telegram chat/channel where alerts should go.

For a private chat, run:

```powershell
python get_chat_id.py
```

For a channel, use the channel username, such as `@yourchannelname`, and make the bot an admin.

## 2. Write the env files

From this folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup-telegram.ps1
```

It will ask for:

- Telegram bot token
- Telegram chat ID or channel username

The script writes:

- `.env` for the BSC/PancakeSwap bot
- `.env_base` for the Base bot

Existing env files are backed up before they are replaced.

## 3. Install dependencies and run

First run, install dependencies:

```powershell
powershell -ExecutionPolicy Bypass -File .\run-telegram-bot.ps1 -Network bsc -Install
```

After dependencies are installed, normal starts are:

```powershell
powershell -ExecutionPolicy Bypass -File .\run-telegram-bot.ps1 -Network bsc
powershell -ExecutionPolicy Bypass -File .\run-telegram-bot.ps1 -Network base
```

Use `bsc` for PancakeSwap alerts. Use `base` for Base network alerts.
