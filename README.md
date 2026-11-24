# X Quote-Tweet & Creator Discovery Pipeline

An autonomous Python discovery and network-traversal pipeline for uncovering brand-partnered creators on X (Twitter) using GraphQL query execution, 2nd-degree quote-tweet expansion, NLP bio/timezone geo-inference, and multi-tier JSON disk caching.

## Architecture Overview
1. **Direct GraphQL Query Execution** (`gql_endpoints.json`, `discover_search.py`, `phase2_discovery.py`): Executes `SearchTimeline` and profile enrichment queries using an active Safari browser session without paid enterprise API subscriptions.
2. **2nd-Degree Network Traversal** (`expand_network.py`, `phase3_expand_and_verify.py`): Recursively traverses quote-tweet and sponsor mention graphs from seed creators to uncover high-signal peers.
3. **Original Post & About Enrichment** (`fetch_originals.py`, `phase4a_fetch_originals.py`, `phase4b_fetch_about.py`): Verifies authentic original authorship vs. repost noise and gathers account-origin metadata.
4. **NLP Geo-Inference & Filtering** (`geo_and_filters.py`, `enrich_and_verify.py`): Evaluates bios, location strings, and posting timezone heuristics for strict US/EU creator qualification.
5. **QA & Deliverable Export** (`analyze_pool.py`, `qa_review.py`, `build_deliverables.py`): Deduplicates verified creator pools and generates structured CSV/Excel deliverables.

> **Note:** Runtime cache JSON files and exported creator rosters are intentionally excluded via `.gitignore` to keep third-party profile data out of version control.

## Author
**Krishna Dixit** — [GitHub](https://github.com/krishnadixit444) · [Portfolio](https://krishna-portfolio-hazel-theta.vercel.app)
