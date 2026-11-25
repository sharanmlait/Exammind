"""QLoRA fine-tuning of a small open LLM to write exam-style answers, then export to GGUF for Ollama.

Runs on a FREE Kaggle (T4 x1/x2) or Colab T4 GPU in ~20-40 min for ~1-2k examples.

Concepts used here (good interview material):
- 4-bit quantised base model (bitsandbytes NF4)  -> fits a 3B model in ~3 GB VRAM
- LoRA adapters (rank r) on attention + MLP projections -> trains ~1% of the weights
- Chat template + "train on responses only"   -> loss only on the answer, not on the long notes prompt
- Merge + GGUF q4_k_m export                    -> one ~2 GB file you can run on a laptop via Ollama

Kaggle setup (new notebook, GPU T4, Internet ON):
    !pip install -q unsloth
    # upload training/llm/data/train.jsonl + val.jsonl as a Kaggle dataset, then:
    !python finetune_qlora.py --train /kaggle/input/exammind/train.jsonl --val /kaggle/input/exammind/val.jsonl
Library APIs move fast: if something errors, compare with the latest official Unsloth Kaggle notebook."""
import argparse
import json
from pathlib import Path


def load_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="unsloth/Qwen2.5-3B-Instruct-bnb-4bit",
                    help="any Unsloth 4-bit instruct model, e.g. unsloth/Llama-3.2-3B-Instruct-bnb-4bit")
    ap.add_argument("--chat-template", default="qwen-2.5", help="qwen-2.5 | llama-3.1 | gemma-3 ...")
    ap.add_argument("--train", default="data/train.jsonl")
    ap.add_argument("--val", default="data/val.jsonl")
    ap.add_argument("--max-seq", type=int, default=3072)
    ap.add_argument("--epochs", type=float, default=2)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--out", default="exammind-lora")
    ap.add_argument("--gguf", default="q4_k_m", help="quantisation for export; '' to skip")
    args = ap.parse_args()

    # unsloth must be imported before transformers/trl
    from unsloth import FastLanguageModel
    from unsloth.chat_templates import get_chat_template, train_on_responses_only
    from datasets import Dataset
    from trl import SFTConfig, SFTTrainer

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base, max_seq_length=args.max_seq, load_in_4bit=True, dtype=None)
    model = FastLanguageModel.get_peft_model(
        model, r=args.rank, lora_alpha=args.rank, lora_dropout=0, bias="none",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth", random_state=3407)
    tokenizer = get_chat_template(tokenizer, chat_template=args.chat_template)

    def to_text(rows):
        return Dataset.from_list([{"text": tokenizer.apply_chat_template(r["messages"], tokenize=False)}
                                  for r in rows])

    train_ds, val_ds = to_text(load_jsonl(args.train)), to_text(load_jsonl(args.val))
    print(f"train={len(train_ds)} val={len(val_ds)}")

    cfg = SFTConfig(
        dataset_text_field="text", max_seq_length=args.max_seq, packing=False,
        per_device_train_batch_size=2, gradient_accumulation_steps=4,   # effective batch 8
        num_train_epochs=args.epochs, learning_rate=args.lr, lr_scheduler_type="cosine", warmup_ratio=0.05,
        weight_decay=0.01, optim="adamw_8bit", logging_steps=10, eval_strategy="steps", eval_steps=50,
        save_strategy="no", seed=3407, output_dir="outputs", report_to="none")
    try:
        trainer = SFTTrainer(model=model, processing_class=tokenizer, train_dataset=train_ds,
                             eval_dataset=val_ds, args=cfg)
    except TypeError:  # older TRL versions
        trainer = SFTTrainer(model=model, tokenizer=tokenizer, train_dataset=train_ds, eval_dataset=val_ds, args=cfg)

    # only learn to produce the answer: mask the system + notes prompt out of the loss
    parts = {"qwen-2.5": ("<|im_start|>user\n", "<|im_start|>assistant\n"),
             "llama-3.1": ("<|start_header_id|>user<|end_header_id|>\n\n",
                           "<|start_header_id|>assistant<|end_header_id|>\n\n"),
             "gemma-3": ("<start_of_turn>user\n", "<start_of_turn>model\n")}
    if args.chat_template in parts:
        ins, res = parts[args.chat_template]
        trainer = train_on_responses_only(trainer, instruction_part=ins, response_part=res)

    stats = trainer.train()
    print(stats)
    print("eval:", trainer.evaluate())

    model.save_pretrained(args.out)         # LoRA adapter only (~50-100 MB)
    tokenizer.save_pretrained(args.out)

    # quick sanity generation
    FastLanguageModel.for_inference(model)
    sample = load_jsonl(args.val)[0]["messages"][:2]
    ids = tokenizer.apply_chat_template(sample, add_generation_prompt=True, return_tensors="pt").to(model.device)
    out = model.generate(input_ids=ids, max_new_tokens=400, temperature=0.4, do_sample=True)
    print(tokenizer.decode(out[0][ids.shape[1]:], skip_special_tokens=True))

    if args.gguf:
        # merges LoRA into the base and writes exammind-gguf/*.gguf (download this file)
        model.save_pretrained_gguf("exammind-gguf", tokenizer, quantization_method=args.gguf)
        print("GGUF written to exammind-gguf/ — see training/llm/Modelfile to load it in Ollama")
    Path("train_summary.json").write_text(json.dumps({"base": args.base, "epochs": args.epochs,
                                                      "rank": args.rank, "train_loss": stats.training_loss}))


if __name__ == "__main__":
    main()
