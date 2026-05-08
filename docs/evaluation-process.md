# RAGAS-Evaluation

Dieses Projekt enthält einen kleinen lokalen Runner, mit dem der lokale Retrieval- und Antwort-Flow mit RAGAS bewertet werden kann.

Dabei handelt es sich nicht um einen `pytest`-Test, sondern um ein Skript, das:

- ein JSONL-Dataset mit Fragen einliest
- jede Frage durch die echte lokale Retrieval- und Antwort-Pipeline laufen lässt
- die gefundenen Kontexte in derselben Source-Struktur wie der Chat-Flow ausgibt
- die Ergebnisse mit RAGAS bewertet
- die Resultate als JSON-Dateien speichert

## Ausführen

```bash
uv run python -m app.evaluation.runner
```

Nützliche Varianten:

```bash
uv run python scripts/ragas_metrics.py --limit 3
uv run python scripts/ragas_metrics.py --dataset resources/datasets/test_cases.jsonl
uv run python scripts/ragas_metrics.py --judge-model gpt-4.1-nano
```

## Voraussetzungen

Vor dem Start der Evaluation sollte Folgendes vorhanden sein:

- die Projektumgebung ist installiert
- die App-Konfiguration ist verfügbar
- `OPENAI_API_KEY` ist gesetzt
- der vom System verwendete Retriever beziehungsweise Index ist lokal vorhanden
- wenn die Produktionsantworten mit LLM-Reranking verglichen werden sollen, muss der Evaluations-Runner ebenfalls um `RerankerService` erweitert werden

Wenn der normale Chat-Flow lokal keine Antworten liefern kann, schlägt auch der Evaluations-Runner aus demselben Grund fehl.

## Reranking-Hinweis

Der `/chat`-Flow kann vor der Antwortgenerierung `RerankerService` verwenden, gesteuert über:

- `RERANKER_ENABLED`
- `RERANKER_TOP_N`

Der aktuelle Evaluations-Runner ruft den Retriever direkt auf und baut daraus den Antwortkontext. Damit misst er die Qualität der Vektorsuche und Antwortgenerierung ohne den optionalen Chat-Reranker. Wenn Produktionsmetriken inklusive Reranking benötigt werden, sollte der Runner nach `matches = retriever.invoke(...)` denselben Reranking-Schritt wie `ChatService` ausführen.

## Dataset-Format

Die Dataset-Datei ist im JSONL-Format aufgebaut. Jede Zeile entspricht einem Evaluationsfall.

Minimales Beispiel:

```json
{"question": "What are the first six steps I need to do with my new account?"}
```

Beispiel mit Referenzantwort:

```json
{
  "question": "How do I set up MFA for my university account?",
  "reference_answer": "Open the account security page, register your authenticator app, scan the QR code, confirm the generated code, and save your recovery options."
}
```

Unterstützte Felder:

- `question`: erforderlich
- `reference_answer`: optional

Nur `question` ist verpflichtend.

Wenn `reference_answer` vorhanden ist, kann der Runner zusätzlich referenzbasierte Metriken berechnen.

## Testfälle generieren

Neben einem händisch gepflegten Dataset kann auch ein JSONL-Dataset mit RAGAS aus den Confluence-Seiten erzeugt werden.

Vom Repo-Root aus:

```bash
uv run python scripts/generate_testcases.py --space-id 720898 --page-limit 20 --min-chars 500
```

Nützliche Varianten:

```bash
uv run python scripts/generate_testcases.py --space-id 720898 --testset-size 10 --page-limit 20
uv run python scripts/generate_testcases.py --space-id 720898 --testset-size 20 --output resources/datasets/generated_cases.jsonl
uv run python scripts/generate_testcases.py --space-id 720898 --testset-size 20 --min-chars 500
```

Wichtige Parameter:

- `--space-id`: Confluence Space-ID, aus der Quelldokumente gelesen werden
- `--testset-size`: Anzahl der zu generierenden Testfälle
- `--page-limit`: begrenzt die Anzahl eingelesener Seiten und reduziert Laufzeit sowie Kosten
- `--output`: Zielpfad für das erzeugte JSONL-Dataset
- `--min-chars`: filtert sehr kurze Seiten vor der Generierung aus

Das Skript schreibt standardmässig nach `resources/datasets/generated_cases.jsonl`.

Hinweise:

- Für die Generierung werden `OPENAI_API_KEY` sowie eine funktionierende Confluence-Konfiguration benötigt.
- Die Generierung kann trotz kleiner `--testset-size` spürbar dauern, da RAGAS zuerst alle gewählten Quelldokumente analysiert.
- Das erzeugte Dataset kann danach direkt mit dem Evaluations-Runner verwendet werden, zum Beispiel mit `uv run python -m app.evaluation.runner --dataset resources/datasets/generated_cases.jsonl`.

## Metriken

Immer berechnet:

- `faithfulness`
- `answer_relevancy`

Nur bei vorhandener `reference_answer`:

- `factual_correctness`
- `context_precision`
- `context_recall`

## Ergebnisdateien

Jeder Lauf schreibt Artefakte nach `resources/evaluation_runs/`:

- `ragas_eval_<timestamp>.json`: vollständiger Lauf
- `ragas_eval_<timestamp>_summary.json`: nur die Zusammenfassung der Metriken
- `ragas_eval_latest.json`: letzter vollständiger Lauf

Der vollständige Lauf enthält unter anderem:

- Metadaten zum Lauf
- Modellinformationen
- Git-Revision
- Antworten pro Frage
- gefundene beziehungsweise nach Pipeline-Schritt behaltene Kontexte und Source-IDs
- Latenz
- Metrikwerte pro Fall
- Zusammenfassung
