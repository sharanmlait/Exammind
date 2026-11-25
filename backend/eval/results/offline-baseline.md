# RAG evaluation — 2026-11-25T15:57:57

LLM `mock:mock-1` · embeddings `hash-512` · reranker `lexical` · 26 questions + 5 off-topic · chunk 700 · alpha 0.6

| config | hit@1 | recall@5 | mrr | keyword_coverage | faithfulness | off_topic_refusal | retrieval_ms | generation_ms |
|---|---|---|---|---|---|---|---|---|
| BM25 only | 0.808 | 1.0 | 0.888 | 0.135 | 0.789 | 1.0 | 0.1 | 0 |
| Dense only | 0.692 | 0.962 | 0.795 | 0.115 | 0.805 | 0.0 | 0.1 | 0 |
| Hybrid | 0.769 | 1.0 | 0.875 | 0.135 | 0.801 | 0.6 | 0.2 | 0 |
| Hybrid + rerank | 0.808 | 1.0 | 0.894 | 0.135 | 0.798 | 1.0 | 0.7 | 0 |
