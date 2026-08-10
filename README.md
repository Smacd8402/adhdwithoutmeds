# Story Board Bot

A Discord bot that turns a channel into a living mind map for a story. Anyone
in the server can drop in **beats** (actual story/plot events) or **thoughts**
(notes, questions, ideas), attached to any existing node. `/storyboard show`
renders the whole thing as an image — blue solid boxes for beats, amber
dashed boxes for thoughts — so you can watch the story branch out.

One board lives per channel, saved to a small JSON file, so nothing is lost
between restarts.

## Commands

| Command | What it does |
|---|---|
| `/storyboard start title:"..."` | Starts a fresh board in this channel (wipes any existing one) |
| `/storyboard add parent:<id> text:"..." type:beat/thought` | Adds a node under an existing node |
| `/storyboard edit id:<id> text:"..."` | Edits a node's text |
| `/storyboard remove id:<id> cascade:True/False` | Removes a node. By default its children reattach to its parent; `cascade:True` deletes the whole branch |
| `/storyboard show` | Renders and posts the current board as an image |
| `/storyboard list` | Text-only outline version, in case you're on mobile and just want a quick read |
| `/storyboard reset` | Wipes the board for this channel (requires Manage Messages permission) |

Every node gets a short numeric ID when it's created (shown in the
confirmation message and in `/storyboard list`) — that's what you reference
as the `parent` or `id` in later commands.

## 1. Create the bot on Discord

1. Go to https://discord.com/developers/applications → **New Application**.
2. Under **Bot**, click **Add Bot**, then **Reset Token** and copy it — this
   goes in `DISCORD_TOKEN`.
3. Still under **Bot**, no privileged intents are needed for this bot (it
   only uses slash commands).
4. Under **OAuth2 → URL Generator**, check scopes `bot` and
   `applications.commands`, and under bot permissions check **Send
   Messages**, **Attach Files**, and **Use Slash Commands**. Open the
   generated URL to invite the bot to your server.

## 2. Run it locally (quickest way to test)

```bash
pip install -r requirements.txt
cp .env.example .env      # then paste your token into .env
python bot.py
```

The first run can take a few seconds to sync slash commands — if they don't
show up in Discord immediately, wait a minute or restart your Discord
client.

## 3. Hosting it so it stays online

Since you weren't sure yet — the simplest low-effort option is
**[Railway](https://railway.app)**:

1. Push this folder to a GitHub repo.
2. On Railway: **New Project → Deploy from GitHub repo**, pick it.
3. Add an environment variable `DISCORD_TOKEN` with your bot token.
4. Railway auto-detects `requirements.txt` and runs `python bot.py`. Give it
   a **Start Command** of `python bot.py` explicitly if it doesn't guess it.
5. Railway's free tier covers a small bot like this comfortably — it just
   needs to stay running, no web traffic involved.

Other easy options if you'd rather: **Render.com** (Background Worker
service, same idea), or if you already have a Raspberry Pi / home server /
old laptop running, just running `python bot.py` in a `screen` or `tmux`
session there works fine too — this bot has no heavy resource needs.

One thing to know either way: the `data/` folder is where boards are saved.
If you redeploy on a platform that doesn't persist disk between deploys
(some free tiers wipe it), you'll want to either mount a persistent volume
or point `DATA_DIR` at one — worth checking your host's docs if you want
boards to survive redeploys.

## Notes / things you might want to extend later

- Right now type defaults to `beat` if you don't specify. Easy to flip the
  default in `bot.py` if your group leans more toward brainstorming/thoughts.
- Diagram layout is a simple top-down tree — for very wide boards (lots of
  siblings) the image will get wide rather than wrapping, so it stays
  readable at the cost of needing to scroll/zoom on huge boards.
- Want per-user colors instead of per-type colors, or multiple boards per
  channel (e.g. a `/storyboard start name:"arc2"` alongside an existing
  one)? Both are straightforward additions to `storyboard.py` if you want
  me to build them in.
