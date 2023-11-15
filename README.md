# AFL-Bot

Bot di utilità per il server discord AFL.
Gli obiettivi principali di sviluppo attualmente sono:

- gestione dei ruoli sul server, in particolare l'assegnamento di due ruoli speciali che indichino una certa continuità nell'attività del server
- filtro dei contenuti
- comandi custom

## Requisiti e installazione

Scritto in [python (3.8+)](https://www.python.org/downloads/) sfruttando le librerie [discord.py](https://github.com/Rapptz/discord.py) e dotenv.

Per utilizzare il bot:

- clonare il repo
- installare le dipendenze

```bash
pip install -r requirements.txt
```

- creare il file config.json seguendo le indicazioni del [template](https://github.com/AFLdiscord/AFL-Bot/blob/master/config.template)
- creare il file .env contenente il token di accesso del bot (è importante non condividerlo)
- il contenuto del .env deve essere `DISCORD_TOKEN=your_token`
- a questo punto si può avviare bot.py

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
- [Come creare applicazione e ottenere il token del bot](https://www.writebots.com/discord-bot-token/)
