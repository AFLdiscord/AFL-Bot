# AFL-Bot
Bot di utilità per il server discord AFL.
Gli obiettivi principali di sviluppo attualmente sono:
- gestione dei ruoli sul server, in particolare l'assegnamento del ruolo attivo
- filtro dei contenuti
- comandi custom

## Requisiti e installazione
Scritto in [python (3.7+)](https://www.python.org/downloads/) sfruttando le librerie [discord.py](https://github.com/Rapptz/discord.py) e dotenv.
Per installarle:
```
python3 -m pip install -U discord.py

python3 -m pip install -U dotenv
```
Per utilizzare il bot:
- clonare il repo 
- creare il file config.json seguendo le indicazioni del [template](https://github.com/AFLdiscord/AFL-Bot/blob/master/config.template)
- crare il file .env contenente il token di accesso del bot (è importante non condividerlo)
- il contenuto del .env deve essere `DISCORD_TOKEN=your_token`
- a questo punto si può avviare bot.py

## Contribuzione
Per contribuire a questo progetto occorre essere membri del server ed aver ottenuto il ruolo ["dev"](https://github.com/AFLdiscord/AFL-Rules/wiki/Progetti-del-forum). Per maggiori informazioni contattare gli admin su discord o direttamente qua:
- [Skylake](https://github.com/Skylake-dev)
- [cathartyc](https://github.com/cathartyc)

Rispettare lo stile di programmazione riportato sotto.

## Link utili
- [Linee guida sullo stile del codice](https://www.python.org/dev/peps/pep-0008/)
- [Documentazione discord.py](https://discordpy.readthedocs.io/en/latest/)
- [Come creare applicazione e ottenere il token del bot](https://www.writebots.com/discord-bot-token/)
