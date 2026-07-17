# AFL-Bot

Bot di utilità per il server discord AFL.
Gli obiettivi principali di sviluppo attualmente sono:

- gestione dei ruoli sul server, in particolare l'assegnamento di due ruoli speciali che indichino una certa continuità nell'attività del server
- filtro dei contenuti
- comandi custom

## Requisiti e installazione

Scritto in [python (3.8+)](https://www.python.org/downloads/) sfruttando le librerie [discord.py](https://github.com/Rapptz/discord.py) e dotenv.

Il bot va creato (seguendo [questa guida](https://www.writebots.com/discord-bot-token/) fino al punto 4, incluso) e aggiunto al proprio server usando il seguente link

`https://discord.com/api/oauth2/authorize?client_id=BOTCLIENTID&permissions=41646633118934&scope=bot%20applications.commands`

sostituendo `BOTCLIENTID` con l'user id del bot, ricavabile dal portale sviluppatori di Discord.

In pratica, dopo aver ottenuto un token, vanno seguiti questi step:

```bash
# clonare il bot
git clone https://github.com/AFLdiscord/AFL-Bot.git && cd AFL-Bot

# (consigliato) creare un virtual environment
python -m venv .venv
source .venv/bin/activate

# installare le dipendenze
pip install -r requirements.txt

# creare file di config, modificando il template
cd config
cp config.template config.json
vim config.json # o usa il tuo editor preferito
cd ..

# creare file .env per conservare il token
your_token="insert-your-token-here"
echo "DISCORD_TOKEN=$your_token" > .env

# avviare il bot
python bot.py
```

### Post dai subreddit

Ci sono dei comandi che permettono di caricare post in tendenza da dei subreddit stabiliti dai moderatori, usando la libreria [Async PRAW](https://github.com/praw-dev/asyncpraw). Per utilizzare questa funzionalità è necessario ottenere le chiavi per API di reddit. Le istruzioni per farlo sono riportate nel [quickstart](https://github.com/reddit-archive/reddit/wiki/OAuth2-Quick-Start-Example#first-steps) sull'autenticazione.

Una volta ottenute le chiavi occorre aggiungere due entrate al file .env contenente il token del bot:

- `REDDIT_APP_ID=id_app_reddit`
- `REDDIT_APP_SECRET=app_secret`

Sarà possibile usare i comandi dopo aver riavviato il bot.

## Contribuzione

Per contribuire a questo progetto occorre essere membri del server ed aver ottenuto il ruolo ["dev"](https://github.com/AFLdiscord/AFL-Rules/wiki/Progetti-del-forum). Per maggiori informazioni contattare gli admin su discord o direttamente qua:

- [Skylake](https://github.com/Skylake-dev)
- [cathartyc](https://github.com/cathartyc)

Rispettare lo stile di programmazione riportato sotto.

## Link utili

- [Linee guida sullo stile del codice](https://www.python.org/dev/peps/pep-0008/)
- [Documentazione discord.py](https://discordpy.readthedocs.io/en/latest/)
