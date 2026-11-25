# Training pipeline

Two models are fine-tuned for ExamMind. Both run on **free** GPUs (Kaggle gives 30 GPU-hours/week; Colab T4 also works).

| Model | What it does | Technique | Where it's used |
|---|---|---|---|
| Topic classifier | Tags each PYQ with its syllabus topic | Full fine-tune of DistilBERT / MuRIL (sequence classification) | `app/nlp/classifier.py` → hot-topic predictor, weak-topic tracking |
| Exam-answer LLM | Writes answers in Indian university exam format, sized by marks | QLoRA (4-bit + LoRA) on a 3B instruct model, distilled from a 70B teacher, exported to GGUF | `app/generation/exam.py` via `ANSWER_LLM_PROVIDER=ollama` |

---

## 1. Topic classifier

```bash
cd training/classifier
python train_classifier.py --baseline-only        # CPU, seconds: TF-IDF baselines
```

Then on Kaggle/Colab (GPU), upload the repo (or just this folder + `data/sample`) and run:

```bash
pip install -q transformers datasets accelerate scikit-learn
python train_classifier.py --model distilbert-base-uncased      # or google/muril-base-cased for Hindi/Hinglish
```

Download the `output/` folder into `training/classifier/output/`. The backend loads it automatically if its labels cover the subject's topics; otherwise it falls back to the TF-IDF baseline.

**Baseline results on the sample data** (train on 2019–2023 papers, test on 2024–2025):

| Model | Accuracy | Macro-F1 |
|---|---|---|
| TF-IDF + LogReg, real questions only | 0.839 | 0.797 |
| TF-IDF + LogReg, + synthetic augmentation | 0.935 | 0.922 |
| Fine-tuned DistilBERT | *run it and fill this in* | |

> Caveat: the sample papers are synthetic and reuse phrasings across years, so the test set is easier than it would be with real papers. Re-run this on real IKGPTU PYQs before quoting any numbers.

The augmentation (templated questions + note sentences per topic) adds training examples for rarely-asked topics, which fixes the class imbalance. It's a good thing to explain in interviews.

---

## 2. Exam-answer LLM (QLoRA)

### Step A — build the dataset (on your laptop)

Uses a big teacher model (Groq / Gemini, free tier) to write exam-format answers grounded in the notes. This is knowledge distillation.

```bash
cd backend                       # needs GROQ_API_KEY or GEMINI_API_KEY in backend/.env
python ../training/llm/build_sft_dataset.py --per-topic 6
# -> training/llm/data/train.jsonl, val.jsonl   (chat format: system / user(notes+question) / assistant)
```

Each row goes through quality filters: correct sections, word count right for the marks, has citations. Rejected rows are counted and printed. Aim for **1,000–2,000 rows**: add more subjects' notes and PYQs, or raise `--per-topic`. Free-tier rate limits apply, so the script may take a while.

### Step B — fine-tune (Kaggle GPU)

1. New Kaggle notebook → Settings → **GPU T4**, Internet **on**.
2. Upload `train.jsonl` + `val.jsonl` as a Kaggle dataset named `exammind`, plus `finetune_qlora.py`.
3. Run:

```python
!pip install -q unsloth
!python finetune_qlora.py --train /kaggle/input/exammind/train.jsonl --val /kaggle/input/exammind/val.jsonl \
        --base unsloth/Qwen2.5-3B-Instruct-bnb-4bit --chat-template qwen-2.5 --epochs 2
```

4. Download `exammind-gguf/*.gguf` (~2 GB) from the notebook's output.

Key hyperparameters: LoRA rank 16, alpha 16, lr 2e-4 cosine, effective batch 8, 2 epochs, loss on responses only. If validation loss goes up while training loss keeps falling, you're overfitting: drop to 1 epoch or add data.

### Step C — run it locally with Ollama

```bash
# put the .gguf next to training/llm/Modelfile (fix the FROM filename if needed)
cd training/llm && ollama create exammind -f Modelfile && ollama run exammind
```

In `backend/.env`:
```
ANSWER_LLM_PROVIDER=ollama
OLLAMA_MODEL=exammind
```
Chat, grading and the agent keep using Groq/Gemini; only exam answers come from your model.

### Step D — benchmark base vs fine-tuned

```bash
ollama pull qwen2.5:3b
cd backend
python ../training/llm/evaluate_finetune.py --models ollama:qwen2.5:3b ollama:exammind groq
```

This writes `training/llm/finetune_eval.md` with structure / length-fit / citation rates, ROUGE-L against the teacher, LLM-judge score and latency. Put this table in your README and resume: something like "a 3B model fine-tuned with QLoRA matches X% of a 70B teacher's judge score at Y× lower latency, running offline."

> Library APIs (Unsloth / TRL) change often. If an argument errors, compare it with the latest official Unsloth Kaggle notebook for your base model.
