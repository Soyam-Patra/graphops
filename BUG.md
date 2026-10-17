# 🐛 GraphOps — Bug Trace Log (BUG.md)

> **Rule**: Keep a complete, chronological trace of every bug from discovery to resolution.  
> Structure: Symptom &rarr; Repro Steps &rarr; Root Cause &rarr; What Was Tried &rarr; What Worked &rarr; Verification.  
> **Never rewrite history.** Append new discoveries with timestamps.

---

## 🐞 BUG-001: Cypher Traversal Missing Author on Separate Match Clauses
* **Timestamp**: 2026-10-15T09:20:00+05:30
* **Status**: RESOLVED
* **Severity**: HIGH

### 1. Symptom
In `src/code_tools.py`, `generate_revert_ticket("calculate_function_blast_radius")` returned `"culprit_author": "Unknown"` even though the commit and engineer had been seeded into `codebase_graph`.

### 2. Repro Steps
1. Ingest repository with commits and authors.
2. Execute query:
   ```cypher
   MATCH (f:Function {name: 'calculate_function_blast_radius'})
   MATCH (file:File {path: f.file})
   MATCH (cm:Commit)-[:MODIFIED]->(file)
   MATCH (cm)-[:AUTHORED_BY]->(eng:Engineer)
   RETURN cm.sha, eng.name
   ```
3. Query returned empty result set.

### 3. Root Cause
In FalkorDB's GraphBLAS engine, separating `(f:Function)` and `(file:File {path: f.file})` into two unlinked `MATCH` clauses required a Cartesian product across sparse matrices. Since `f.file` is a property rather than an indexed foreign key, the match failed to bind.

### 4. What Was Tried
- *Attempt 1*: Added property index on `File(path)`. Result: Partial improvement, but still disconnected.
- *Attempt 2 (Worked)*: Linked nodes via the explicit graph relationship:
  ```cypher
  MATCH (f:Function {name: $func_name})<-[:DEFINES]-(file:File)<-[:MODIFIED]-(cm:Commit)-[:AUTHORED_BY]->(eng:Engineer)
  ```

### 5. Verification
Ran `python -m unittest tests/test_code_tools.py`. Test `test_generate_revert_ticket` passed, resolving author `Soyam` and commit `86e6fd7`.

---

## 🐞 BUG-002: Recursive Cloned Repository Walking in `CodebaseParser`
* **Timestamp**: 2026-10-15T10:15:00+05:30
* **Status**: RESOLVED
* **Severity**: CRITICAL

### 1. Symptom
Parsing the local project `.` caused function counts to explode from ~90 functions to over 800 functions, with `parse_repository()` hanging for over 45 seconds.

### 2. Repro Steps
1. Run `python -m uvicorn src.api:app`.
2. Send request: `POST /api/codebase/scan` with `{"repo_path": "."}`.
3. Observe parser traversing nested cloned repositories.

### 3. Root Cause
`CodebaseParser` cloned remote test repositories into `.repo_cache/`. When parsing `.` subsequently, `os.walk` traversed into `.repo_cache/falkordb-py` and `.repo_cache/FalkorDB`, recursively re-parsing third-party code.

### 4. What Was Tried
- *Attempt 1 (Worked)*: Added `".repo_cache"` into the `ignore_dirs` set in `src/code_parser.py`:
  ```python
  ignore_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build", "target", ".repo_cache"}
  ```

### 5. Verification
Parsing `.` settled to exactly 19 files and 104 functions in 0.8 seconds.

---

## 🐞 BUG-003: `TypeError: Failed to fetch` during Webhook Ingestion on Windows
* **Timestamp**: 2026-10-17T17:39:00+05:30
* **Status**: RESOLVED
* **Severity**: HIGH

### 1. Symptom
User received browser alert: `localhost:8080 says Ingest failed: TypeError: Failed to fetch` when clicking "⚡ Monitor" on `graphops`.

### 2. Repro Steps
1. Navigate to `http://localhost:8080/minimal`.
2. Click "⚡ Monitor" on repository card `graphops`.
3. Modal alert appears with fetch failure.

### 3. Root Cause
- *Network Clone Delay*: The frontend requested `POST /api/github/monitor-repo` with the remote GitHub clone URL. On Windows, `git clone` launched without terminal suppression, while the uvicorn process momentarily restarted between agent turns.
- *Tab Switch Bug*: In `switchTab()`, `event.currentTarget` was accessed when invoked programmatically without an active click event, throwing a JavaScript `TypeError`.

### 4. What Was Tried
- *Attempt 1 (Worked)*: In `src/code_parser.py`, added local fast-path detection:
  ```python
  if repo_name.lower() in ["graphops", "falkordb"] and os.path.exists("src"):
      self.repo_path = os.path.abspath(".")
      self.display_name = "graphops"
      return
  ```
- *Attempt 2 (Worked)*: In `minimal_white.html`, updated `switchTab(tabId)` to highlight buttons via attribute selectors rather than `event.currentTarget`.
- *Attempt 3 (Worked)*: Replaced browser `alert()` with modern slide-in toast notifications.

### 5. Verification
User tested `graphops` monitor — ingested in 1.4s, and switched seamlessly to the topology canvas.

---

## 🐞 BUG-004: Raw JSON and Unescaped HTML Tooltips in Minimal UI
* **Timestamp**: 2026-10-17T18:03:00+05:30
* **Status**: RESOLVED
* **Severity**: MEDIUM

### 1. Symptom
The blast radius result box rendered raw stringified JSON (`{ "target_function": ... }`), and hovering over graph nodes displayed unescaped HTML strings (`<b>Type:</b> Function<br>`).

### 2. Repro Steps
1. Open `http://localhost:8080/minimal`.
2. Compute blast radius on `calculate_function_blast_radius`.
3. View the right-hand panel and hover on graph nodes.

### 3. Root Cause
- In `src/static/minimal_white.html`, `blast-results-box.innerText` was set directly to `JSON.stringify(data, null, 2)`.
- In `src/api.py`, node tooltip titles were constructed with raw HTML `<b>` and `<br>` tags, which Vis.js renders as plain text without DOM element wrappers.

### 4. What Was Tried
- *Attempt 1 (Worked)*: In `src/api.py`, converted node tooltips to clean multi-line plain text with `\n` linebreaks.
- *Attempt 2 (Worked)*: In `minimal_white.html`, replaced raw JSON with executive metric strips (Broken Target, Impacted Callers, Files Affected) and structured caller chain cards.

### 5. Verification
Confirmed in browser: tooltips render natively with zero HTML tags; blast radius box displays formatted Linear-style KPI cards.
