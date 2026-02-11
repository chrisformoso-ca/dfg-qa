# dfg-qa

RAG-powered Q&A bot for Calgary community data. Built for [Data for Good](https://dataforgood.ca/) Cohort 5.

Ask questions like *"Is Beltline safe?"* or *"Compare Seton and Altadore for families"* and get data-backed answers sourced from [Calgary Pulse](https://calgarypulse.ca) community profiles.

## How it works

```
Question → Embed → Search ChromaDB → Retrieve relevant chunks → Claude LLM → Answer with citations
```

1. **Chunker** splits community JSON profiles into semantic sections (safety, housing, 311, schools, etc.)
2. **Indexer** embeds chunks into ChromaDB using all-MiniLM-L6-v2 (local, free)
3. **QA bot** retrieves the most relevant chunks, builds a prompt, and calls Claude for a cited answer

Each chunk includes visualization metadata describing how the data appears on Calgary Pulse, so the bot can reference specific charts and link to the right page sections.

## Setup

```bash
# Clone and enter
git clone https://github.com/calgary-analytica/dfg-qa.git
cd dfg-qa

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Add community data

Community JSON files go in `data/communities/`. These are Calgary Pulse profile exports — one JSON per community with safety, housing, demographics, schools, transit, 311, business data.

```bash
# Example: copy from Calgary Pulse exports
mkdir -p data/communities
cp /path/to/beltline.json data/communities/
```

### Build the index

```bash
# Index all communities in data/communities/
python3 indexer.py

# Index specific communities
python3 indexer.py --communities beltline seton altadore

# Wipe and rebuild
python3 indexer.py --reindex

# Check what's indexed
python3 indexer.py --stats
```

## Usage

Requires [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (`claude` command).

### Single question

```bash
python3 qa.py "Is Beltline safe?"
python3 qa.py "Compare Seton and Altadore for families" --verbose
```

### Interactive mode

```bash
python3 qa.py --interactive
```

### Batch mode (for evaluation)

```bash
python3 qa.py --batch questions.csv --output answers.csv
```

Input CSV needs a `Question` (or `question`) column. Output includes `ai_answer`, `sources`, and `timestamp`.

## Project structure

```
dfg-qa/
├── chunker.py          # Community JSON → text chunks with viz metadata
├── indexer.py          # Chunks → ChromaDB embeddings
├── qa.py              # Q&A bot (single, batch, interactive)
├── prompts/
│   └── system.md      # System prompt for answer generation
├── requirements.txt   # chromadb, sentence-transformers
├── data/
│   └── communities/   # Community JSON profiles (gitignored)
└── chroma_db/         # Vector database (gitignored)
```

## Chunk sections

Each community profile produces ~9 chunks:

| Section | Data | Viz on Pulse |
|---------|------|-------------|
| Overview | Population, safety score, home value | Hero stat cards |
| Safety | Crime counts, rates, YoY, breakdown | Trend chart, breakdown cards |
| Housing | Assessed values by type, district benchmarks | Stat grid |
| 311 | Service request categories, trends | Bar chart, trend line |
| Schools | School list, ratings | Ordered list |
| Transit | Stop count, routes | Stat + list |
| Demographics | Age, income, tenure, diversity | Stat grid |
| Business | Licenses, permits, investment | Cards + bar chart |
| Amenities | Grocery, parks, landmarks, restaurants | Named lists |

## Tech stack

| Component | Choice |
|-----------|--------|
| Embeddings | all-MiniLM-L6-v2 via ChromaDB default (local, free) |
| Vector DB | ChromaDB (persistent, SQLite backend) |
| LLM | Claude via CLI (`claude -p`) |
| Data | Calgary Pulse community profiles (JSON) |

## License

MIT
