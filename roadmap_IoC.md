# Roadmap IoC (Inception-of-Context) – équipe de 2

> Estimation : **50 à 80 h cumulées** pour le mandatory (≈ 25–40 h par personne), soit **2 à 3 semaines** à rythme soutenu. Le bonus est en plus, et n'est évalué que si le mandatory est parfait.

---

## 1. Le projet en une phrase

Construire un **mini assistant de code 100 % local** : il indexe un petit projet, répond à des questions dessus (RAG), puis génère des patchs de code qu'il applique, valide, et **annule (rollback) si ça casse**.

Règle absolue : **aucun appel à un LLM distant** (sinon note de 0). Tout tourne en local : Ollama + ChromaDB, dans Docker.

## 2. Architecture globale

```
Projet cible (demo app)  ──►  Indexer (p1)  ──►  ChromaDB (persistant, HORS du dossier cible)
                                  ▲                      │
                          Watcher (incrémental)          ▼
                                              API FastAPI (p2) : /context, /ask, /status ...
                                                         │
                                                         ▼
                                      Boucle de patch (p3) : LLM coder → sanity → apply → validate → rollback
                                                         │
                                                         ▼
                                          Dashboard web (Overview / Files / Chroma / Ask / Patch Loop)
```

Dépendances : **p1 alimente p2, p2 porte p3**. Il faut donc figer les interfaces tôt (voir §5).

## 3. Livrables obligatoires

- Dossiers `p1/`, `p2/`, `p3/` (+ `bonus/` optionnel) à la racine du repo.
- `README.md` (comment lancer) et `Makefile` (`make up`, `make down`…, basé sur `docker compose`).
- `.gitignore` : **jamais** de poids de modèles, d'archive d'embeddings ou de dossier ChromaDB peuplé (rejet immédiat sinon).
- Une **demo app** (3–4 fichiers, 1 classe avec 4–5 méthodes, un point d'entrée, des tests) + `ioc.config.yml` à sa racine.

## 4. Détail des exigences par partie

### Part 1 – Indexation et synchronisation
- Parcourir le dossier cible, **chunker par structure logique** (1 chunk = fonction / classe / bloc de config). Chunker à taille fixe = échec.
  - Python : module `ast` (méthodes imbriquées, décorateurs inclus). Regex en fallback (fichiers non-Python, Python qui ne parse pas).
- Embeddings locaux (`all-MiniLM-L6-v2`), téléchargés une fois, puis **fonctionnement 100 % hors-ligne**.
- **Réindexation incrémentale** : modifier un fichier ne touche que ses chunks ; supprimer un fichier supprime ses chunks. Hash par chunk.
- Ignorer : `node_modules`, `.git`, `dist`, `build`, `venv`, `.venv`, `__pycache__`, dossiers cachés, binaires. **Ne jamais indexer/watcher le dossier ChromaDB** (sinon boucle infinie).
- Watcher avec **fallback polling** (inotify perd des événements sur les bind mounts Docker).
- Dashboard : onglet **Overview** (nb de chunks, chemin cible, modèles, chunks par fichier, flux d'activité live).

### Part 2 – API et RAG
- Serveur HTTP (FastAPI), **un seul client Chroma par process**, partagé avec le watcher.
- Endpoints de base : `GET /status`, `/files`, `/file?path=`, `/chunks` (pagination), `POST /context` (top-k + score), `POST /ask`, `GET /events` (SSE).
- **Re-ranking BM25** (`rank_bm25`) par-dessus Chroma, car les embeddings sont faibles sur les identifiants exacts.
- **/ask ne doit jamais halluciner** : cas pièges « existe-t-il une fonction X ? » et « quelles fonctions dans ce fichier ? ». Solution : **pré-résoudre à partir de l'index** (lookup déterministe des symboles en métadonnées, puis injecter la liste exacte / répondre sans laisser le LLM inventer), pas « corriger dans le prompt ».
- Dashboard : onglet **Ask & Retrieve** (question, choix de k, bouton Retrieve et bouton Ask LLM, sources avec scores).

### Part 3 – Génération, application, validation
Boucle : intent → retrieval → LLM coder → **JSON** `{summary, files:[{path, op, content}]}` (op = create/modify/delete, content = fichier complet) → **sanity checks** → snapshot → écriture atomique → validation → retry ou rollback.

Sanity checks (refus durs, avant toute écriture) :
1. Pas de marqueurs de retrieval dans le contenu.
2. Pas de `create` sur un fichier existant.
3. Pas de remplacement d'un fichier non vide par `""`, `"None"`, `"null"`.
4. Pas de fonction-stub (`pass`, `...`, `return None`).
5. Pas de réduction de fichier > 60 %.
6. Pas plus de 3 fichiers touchés.

Application : fichiers `*.ioc.tmp` puis `os.replace` seulement quand **tous** les temporaires sont prêts. Validation via la commande de `ioc.config.yml` (ex. `python -m py_compile {files}`, ou pytest). En cas d'échec, renvoyer le log d'erreur au LLM ; **3 itérations max**, puis **rollback exact** (fichiers modifiés restaurés, fichiers créés supprimés, fichiers supprimés recréés). Après succès : réindexation silencieuse des fichiers touchés.
- Dashboard : onglet **Patch Loop** (intent, k, max attempts, historique des tentatives, patch final).

### Bonus (seulement si tout est parfait)
`POST /reindex`, commit Git auto avec message généré par le LLM, intégration Docker SDK, dry-run avec diff, dashboard enrichi (diff visuel, SSE de validation).

## 5. Phase 0 – À faire ENSEMBLE (≈ 0,5 à 1 jour)

Pour pouvoir travailler en parallèle sans se bloquer, figer :
1. **Structure du repo** et `docker-compose.yml` (services : app + ollama), `Makefile`, `.gitignore`.
2. **Schéma d'un chunk** : `id`, `path`, `symbol_name`, `kind` (function/class/method/config), `start_line`, `end_line`, `hash`, `document`.
3. **Contrat des endpoints** (routes, corps JSON, réponses).
4. **Schéma du patch JSON** et du format d'une « tentative » (pour le dashboard).
5. **Choix de la demo app** (idéalement une petite app « notes » : `service.py`, `storage.py`, `cli.py`, `main.py`, `tests/`).
6. **Modèles Ollama** : `qwen2.5:3b` (/ask) et `qwen2.5-coder:3b` (patch).

## 6. Répartition équitable (≈ 35 h chacun)

| | **Personne A – « Données & Moteur »** | **Personne B – « LLM & API »** |
|---|---|---|
| **Infra** | Docker, Makefile, README, `.gitignore`, config Ollama | – |
| **Demo app** | Écrit la demo app + `ioc.config.yml` + tests | – |
| **Part 1** | Chunker (AST + regex), embeddings, Chroma, incrémental + hash, watcher + polling, exclusions | – |
| **Part 2** | Endpoints d'état : `/status`, `/files`, `/file`, `/chunks`, `/events` (SSE) | Serveur FastAPI, `/context` (+ BM25), `/ask`, anti-hallucination (pré-résolution symboles), prompts |
| **Part 3** | **Moteur d'application** : snapshot, écriture atomique `.ioc.tmp`/`os.replace`, runner de validation, rollback exact, réindexation silencieuse | **Génération** : prompt coder, parsing/réparation du JSON, **sanity checks**, boucle de retry avec feedback d'erreur (3 max), orchestration |
| **Dashboard** | Overview, Files, ChromaDB Explorer | Ask & Retrieve, Patch Loop |

**Pourquoi c'est équilibré** : A porte la partie « systèmes » (fichiers, Docker, watcher, atomicité), B la partie « IA » (retrieval, prompts, robustesse du LLM). A démarre en premier (p1 est le socle), B peut en parallèle prototyper `/ask` sur un index factice puis brancher le vrai index. Le point de jonction est la **boucle de patch** : A fournit `apply(patch)` / `rollback()` / `validate()`, B fournit `generate(intent)` / `sanity_check(patch)`, et l'orchestration finale se fait à deux.

> Règle d'or : **chacun doit être capable d'expliquer TOUT le projet** lors de la défense. Faites des relectures croisées (code review de la PR de l'autre) à chaque jalon.

## 7. Planning proposé (≈ 3 semaines)

### Semaine 1 – Fondations
- **Ensemble (jours 1–2)** : Phase 0, repo, Docker qui démarre, Ollama qui répond, demo app.
- **A** : chunker AST + embeddings + Chroma, indexation initiale. *Jalon : `make up` indexe la demo app.*
- **B** : squelette FastAPI, `/status`, `/context` sur l'index, premiers essais de prompts avec Ollama.

### Semaine 2 – Indexation complète et RAG
- **A** : incrémental + hash, watcher + polling, exclusions, suppression de fichiers, SSE `/events`, Overview + Files. *Jalon : Part 1 complète.*
- **B** : BM25, `/ask`, anti-hallucination (cas « fonction X existe ? » / « fonctions du fichier ? »), onglet Ask & Retrieve. *Jalon : Part 2 complète.*
- **Fin de semaine – ensemble** : tests croisés, correction des bugs.

### Semaine 3 – Boucle de patch + finition
- **A** : snapshot / apply atomique / validation / rollback / réindexation.
- **B** : génération JSON, sanity checks, retry, onglet Patch Loop.
- **Jours finaux – ensemble** : intégration de la boucle, tests « méchants » (JSON invalide, patch qui casse volontairement, fichier supprimé pendant le loop, intent absurde), README, Makefile, nettoyage repo (`.gitignore`), répétition de la démo.

### Après (si mandatory parfait) – Bonus
`/reindex` et dry-run (faciles), puis commit Git auto.

## 8. Checklist de défense

- [ ] `make up` fonctionne depuis un clone propre, sans lire le code.
- [ ] Aucun appel réseau vers un LLM distant ; indexation OK hors-ligne après premier téléchargement.
- [ ] Chunks alignés sur les fonctions/classes (visible dans l'onglet Files).
- [ ] Modifier / créer / supprimer un fichier → seuls ses chunks changent, activité live visible.
- [ ] Le dossier Chroma n'est jamais indexé ni watché.
- [ ] `/ask` : « la fonction `inexistante` existe-t-elle ? » → réponse **non**, sans invention.
- [ ] `/ask` : « quelles fonctions dans `service.py` ? » → liste exacte.
- [ ] Les 6 sanity checks refusent bien un patch fautif (testés un par un).
- [ ] Un patch qui casse la validation → 3 tentatives → **rollback exact** (vérifier avec `git diff` / hash des fichiers).
- [ ] Patch réussi → fichiers touchés réindexés automatiquement.
- [ ] Repo : pas de poids de modèles, pas de dossier Chroma committé.

## 9. Pièges fréquents

- Le watcher qui réagit à ses propres écritures (Chroma dans le dossier cible, fichiers `.ioc.tmp`) → **exclure aussi `*.ioc.tmp`**.
- Un petit modèle 3B qui renvoie du JSON mal formé ou entouré de texte/markdown → prévoir extraction + retry.
- Contexte limité (quelques milliers de tokens) : garder la demo app **petite** et `k` raisonnable.
- Rollback incomplet : penser aux fichiers **créés** (à supprimer) et **supprimés** (à restaurer), pas seulement aux modifiés.
- inotify muet sous Docker → polling de secours.
