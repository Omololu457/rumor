# Rumor

A social deduction party game about gossip and reputation. One computer runs
the server; everyone else joins from their phone's browser over the same
WiFi network.

## Requirements

- Python 3.10+
- Everyone's device on the **same WiFi network** as the host computer

## Setup

```bash
git clone <your-repo-url>
cd rumor-game
pip install -r requirements.txt
```

## Running a game

```bash
python run.py
```

This prints something like:

```
On THIS computer, open:   http://localhost:8000/display
Everyone ELSE, open:      http://192.168.1.42:8000
```

- Open `/display` on the host computer (or cast it to a TV) — it shows a QR
  code and the address so everyone else can join from their phone.
- Everyone else opens that address on their phone and creates a character.
- The **first person to join is automatically the Host** and gets extra
  controls (start the game, end a round early, end the game, reset the
  lobby) right on their own phone screen.
- Game data is saved to `rumor_game.db` (SQLite) as it goes, so if the
  server restarts mid-game, restarting `python run.py` picks back up where
  it left off.

## Project layout

```
rumor-game/
├── run.py                  entry point — run this
├── requirements.txt
├── app/
│   ├── server.py            FastAPI routes + WebSocket
│   ├── game_state.py         core game engine: phases, actions, voting
│   ├── scoring.py             tunable numbers (influence gains, odds, etc.)
│   ├── rumors.py               rumor pool + severity escalation
│   ├── objectives.py            secret objective assignment + checking
│   ├── db.py                     SQLite persistence
│   ├── net.py                     local IP lookup for the QR code
│   └── data/
│       ├── rumor_pool.json        the rumor templates
│       └── objective_pool.json    the secret objective templates
├── static/
│   ├── css/style.css        the whole visual design
│   ├── js/app.js             all client-side logic (single page app)
│   └── uploads/               player photos land here
└── templates/
    ├── join.html             character creation
    ├── display.html           QR code / address screen for a TV or laptop
    └── game.html               the main phone screen (all phases)
```

## Tuning the game

- **Rumors:** add or edit entries in `app/data/rumor_pool.json`. Each needs
  a `text` (use `{subject}` / `{subject2}`), `truth_status`
  (`"True"` / `"Semi-True"` / `"False"`), `base_severity`, `category`, and
  `subjects_needed` (1 or 2).
- **Secret objectives:** edit `app/data/objective_pool.json`.
- **Scoring/odds:** every tunable number (influence gains, investigation
  odds, vote point caps, timers) lives in `app/scoring.py` and
  `app/game_state.py`'s `DEFAULT_ACTION_SECONDS` / `DEFAULT_VOTE_SECONDS`.

## Notes on what's included vs. left for later

This is a working end-to-end build: joining, the host role, the
action/vote/reset loop with live timers pushed over WebSocket, rumor
spreading/investigating with severity escalation, two-category voting,
secret objectives, and the final reveal screen are all implemented and
tested. Not yet built (per the design doc, this was flagged as a future
feature): selecting from a bank of pre-written personas instead of a fully
custom character.
