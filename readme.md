# Game of Life AI

Una sandbox sociale deterministica in cui gli abitanti combinano comportamenti locali e decisioni
generate da un modello Ollama. La simulazione continua a funzionare anche senza AI; il modello viene
usato per obiettivi di alto livello e per proporre nuove professioni, ricette, edifici e regole.

## Stato attuale

Il progetto è stato rilanciato su Python 3.12 con un nuovo core event-driven. Sono disponibili:

- mondo Pygame con inspector degli agenti, timeline, pausa e controllo della velocità;
- umani, mucche, alberi, rocce, laghi ed edifici;
- fame, sete, energia, salute, ciclo vitale e riproduzione;
- raccolta, inventari, cibo consumabile, combattimento, sonno, dialogo, commercio e costruzione;
- professioni iniziali e lavoro basato sulle risorse;
- temperamenti ereditabili, umore e obiettivi persistenti;
- fazioni, reclutamento, guerre, successione dei leader, pace e dissoluzione dei gruppi;
- azioni emergenti come aiutare, rubare, esplorare, innovare e sabotare;
- crisi ambientali periodiche: siccità, incendi, epidemie, raccolti e boom minerari;
- cognizione ibrida con fallback deterministico;
- generazione di regole data-only con validazione, shadow check, monitoraggio e rollback;
- snapshot ed event log in SQLite;
- esecuzione headless riproducibile tramite seed.

L'output del modello non viene mai eseguito come codice: tutte le azioni e le regole passano attraverso
schemi e validatori.

## Requisiti

- [uv](https://docs.astral.sh/uv/)
- Python 3.12 (può essere gestito direttamente da `uv`)
- [Ollama](https://ollama.com/) con `qwen3:8b` per le funzioni generative

```powershell
ollama pull qwen3:8b
uv sync --all-groups
```

## Avvio

```powershell
uv run game-of-life
```

Comandi UI:

- clic su un'entità: apre l'inspector;
- `Spazio`: pausa/riprendi;
- `+` e `-`: velocità della simulazione.

Gli agenti in attesa di Ollama mostrano `...` sotto lo sprite. L'inspector visualizza temperamento,
umore, fazione, obiettivo e azione corrente; il pannello generale mostra fazioni e guerre attive.

Il mondo viene salvato in `saves/world.db`. Per riprendere l'ultimo snapshot:

```powershell
uv run game-of-life --load
```

Le decisioni AI sono interrogabili direttamente nella tabella SQLite `events`:

```sql
SELECT tick, actor_id, action, target_id, payload_json
FROM events
WHERE event_type = 'ai_decision' AND action = 'talk'
ORDER BY sequence DESC;
```

Esecuzione deterministica senza Pygame o Ollama:

```powershell
uv run game-of-life --headless --no-ai --ticks 10000 --seed 42
```

Configurazione tramite variabili d'ambiente:

- `GOL_OLLAMA_MODEL` (default `qwen3:8b`);
- `GOL_OLLAMA_ENDPOINT` (default `http://127.0.0.1:11434`);
- `GOL_AI_ENABLED` (`true`/`false`);
- `GOL_SEED`.

## Sviluppo

```powershell
uv run ruff check .
uv run pytest --basetemp=.pytest-tmp --cov=game_of_life
```

I moduli principali sono:

- `engine.py`: tick, azioni e sistemi simulativi;
- `models.py`: stato tipizzato del mondo;
- `ai/`: client Ollama e worker in background;
- `innovation.py` e `rules.py`: generazione e governance delle regole;
- `persistence.py`: snapshot, eventi e versioni delle regole;
- `ui.py`: rendering e pannelli Pygame.

## Prossime evoluzioni

- mercato con prezzi emergenti e proprietà collettive;
- insediamenti, istituzioni e leggi generate entro effetti sicuri;
- memoria episodica più ricca e dialoghi multi-turno;
- stagioni, clima e impatto ecologico;
- tecnologia, cultura e diplomazia tra comunità.
