# Confluence RAG Bot

Dieses Dokument beschreibt die Features und Funktionsweise unseres RAG Bots. 
Beschrieben werden auch einige Entscheide die wir bezüglich Chunking, Evaluation, Security & weitere Themen getroffen haben.

## 1. Inhaltsverzeichnis

tbd

## 2. Motivation

Viele Unternehmen (wie auch die OST) speichern enorm viele Informationen in Confluence. Je nach Inhalt wird es enorm schwierig die richtige Seite zu finden, welche die Infos beinhaltet, die man sucht.

Das Ziel dieses Projekts ist es, dieses Wissen über eine API im Chat-Style zugänglich zu machen, wobei die Antworten stets auf der ursprünglichen Dokumentation basieren sollen.

Wir haben das Projekt in vier Hauptprobleme aufgeteilt:
1. Wissen aus Confluence zuverlässig einlesen.
2. Inhalte und Anhänge für die Suche in nützliche Abschnitte umwandeln.
3. Nur die für die Frage eines Benutzers relevantesten Abschnitte abrufen.
4. Antworten generieren, die den abgerufenen Quellen treu bleiben, und diese Quellen dem User offenlegen.

## 3. Übersicht der Architektur

```
Confluence API
      │
      ▼
 ConfluenceClient          ← Confluence Seiten werden via REST API geholt
      │
      ▼
  Normalizer + Chunker     ← HTML wird normalisiert, Headings extrahiert und in Chunks aufgeteilt
      │
      ▼
 IndexingService           ← chunks werden mit text-embedding-3-small embedded
      │
      ├──► Supabase (pgvector)   ← unser Vector-Store & semantischer Cache in der "Prod"
      └──► FAISS (local)         ← wurde lokal getestet um das Chunking möglichst effizient zu testen
                │
                ▼
         RetrieverService        ← macht Similarity-Search
                │
                ▼
          RerankerService        ← Reranker filtert top N chunks nach Relevanz, kann über die Settings ausgeschaltet werden
                │
                ▼
          LLMService             ← GPT-4.1 (z.B.) antwortet mit gegebenem Kontext
                │
                ▼
         FastAPI /chat           ← durch API-Token geschützter, rate-limitierter REST Endpunkt
```

## 4. Features

| Funktion                        | Details                                                                                                                                                                              |
|---------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **RAG-Pipeline**                | Confluence-Seiten → HTML-Normalisierung → Chunking → Vektor-Embeddings → Similarity Search → LLM-Reranking → Antwort                                                                 |
| **Optionen für Vector Store**   | Supabase (pgvector) für Produktion, FAISS für lokale Nutzung                                                                                                                         |
| **LLM-Reranking**               | Chunks werden nach Fragenrelevanz und Antwortunterstützung bewertet; nur die am höchsten neu gerankten Chunks werden an den Antwort-Prompt übergeben                                 |
| **Semantischer Cache**          | Identische oder nahezu identische Fragen (≥ 0,98 Kosinusähnlichkeit) werden sofort aus dem Cache beantwortet. Cache wird invalidiert, wenn Quellseiten aktualisiert werden           |
| **Langfuse-Tracing**            | Optionale Traces für Anfrage, Retrieval, Reranking, Cache und LangChain-LLM, wenn Langfuse-Zugangsdaten konfiguriert sind                                                            |
| **Konversationsverlauf**        | Multi-Turn-Chat: Der Verlauf wird in den Prompt eingefügt. Der Cache wird umgangen, wenn ein Verlauf vorhanden ist                                                                   |
| **Schutz vor Prompt Injection** | Kontext, Fragen und Verlauf werden jeweils in Sektionen eingeschlossen, mit Systemanweisungen, die verhindern, dass das LLM Benutzerinhalte als Anweisungen behandelt                |
| **`POST /sync`-Endpunkt**       | Löst eine Indexierung eines beliebigen Confluence-Bereichs (oder einzelne Seite) aus; führt Upserts (nur auf dem Remote) auf `chunk_id` aus, sodass der Aufruf wiederholt sicher ist |
| **API-Key-Authentifizierung**   | `X-API-Key`-Header wird bei jeder Anfrage benötigt                                                                                                                                   |
| **Rate Limiting**               | `/chat` — 20 Anfragen/Min., 300 Anfragen/Tag; `/sync` — 5 Anfragen/Min., pro IP-Adresse (über SlowAPI)                                                                               |

## 5. Indexing Flow

Gestartet wird die Indexierung über ```POST /sync```, welche in ```app/services/sync_service.py``` implementiert wird.

![indexing.png](indexing.png)

Remote (auf Coolify) haben wir für die Indexierung einen Cron-Job eingerichtet, welcher regelmässig den `/sync` Endpunkt anstösst.

## 6. Confluence Ingestion

Der Confluence Client wurde in ```app/confluence/client.py``` implementiert.
Interessante Details:
- Requests teilen eine "shared authenticated" ```requests.Session```
- Confluence-API Aufrufe haben ein 60 Sekunden timeout
- Schlägt ein Request fehl, versuchen wir es dreimal erneut (Ausnahme ConfluenceAPIError)

Seiten können nach Bereich (Space) oder nach Seiten-ID geholt werden. Wenn eine Seite weitere Seiten beinhaltet werden auch diese heruntergeladen.

Wenn das Herunterladen von Anhängen für eine Seite fehlschlägt, loggt das System den Fehler und fährt mit der Indexierung der verbleibenden Seiten fort. Ein beschädigter Anhang sollte nicht verhindern, dass der Rest der Wissensbasis indexiert wird.

## 7. Inhalt Normalisierung

Der Confluence Page-Body besteht aus HTML. Der Parser `app/processing/normalize.py` konvertiert dies in normalisierten Text und Sektionen mit Headers.

Die Confluence Seiten können auch komplizierteren Inhalt beinhalten, z.B. durch Plugins. Diese Inhalte haben wir für diesen MVP ignoriert und uns auf die "standard" HTML Strukturen fokussiert, wie Headings, Paragrafen, Listen, Tabellen etc.

Der parser verwendet einen `heading_stack`, so dass der Text unter einem Heading diesem zugewiesen bleibt. Am besten ist dies anhand eines Beispiels ersichtlich:
```
<h2>Access</h2>
<h3>VPN</h3>
<p>Use the OSR VPN when accessing internal systems.</p>
```
Wird zu einer Section mit diesem Heading-Path:
```
["Access", "VPN"]
```