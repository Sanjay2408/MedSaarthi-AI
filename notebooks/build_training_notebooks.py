"""Builds the two GPU notebooks (not executed here: this laptop has no GPU).

    python notebooks/build_training_notebooks.py

notebooks/t2_lora_qwen.ipynb   LoRA fine-tune of Qwen2.5-1.5B-Instruct for prescription -> JSON
notebooks/t3_trocr_rxhandbd.ipynb   TrOCR fine-tune on handwritten medicine-name images
Both print a before/after table and write a results JSON to download into outputs/eval/.
"""
from pathlib import Path

import nbformat

HERE = Path(__file__).resolve().parent


def nb(cells):
    n = nbformat.v4.new_notebook()
    n.cells = [nbformat.v4.new_markdown_cell(c) if k == "md" else nbformat.v4.new_code_cell(c) for k, c in cells]
    n.metadata = {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                  "accelerator": "GPU"}
    return n


T2 = [
    ("md", "# T2: LoRA fine-tune of Qwen2.5-1.5B-Instruct for prescription to JSON\n\n"
           "**Run on Kaggle** (Settings: Accelerator GPU T4, Internet on) **or Colab** (T4). About 60 to 90 minutes.\n\n"
           "**What this is.** The model reads a typed prescription and returns the JSON MedSaarthi's extractor expects. "
           "It is fine-tuned on 20,000 *synthetic* prescriptions built from medicine names. It is not trained on real prescriptions, and the "
           "result must be described that way.\n\n"
           "**Before and after.** The same 200 held-out prescriptions (medicine names the model never trained on) are scored "
           "before and after training, so the improvement is measured, not assumed. Nothing here has been run on the author's laptop (no GPU); "
           "paste the printed table into `docs/EVAL.md` only after you run it.\n\n"
           "**Steps.** 1) In the repo run `python scripts/make_lora_data.py`, then upload `data/synth/t2_train.jsonl` and `t2_eval.jsonl` "
           "as a Kaggle dataset (or to Colab's file panel). 2) Run all cells. 3) Download `t2_results.json` and `t2_adapter.zip`."),
    ("code", "!pip -q install -U transformers peft accelerate datasets"),
    ("code", "import glob, json, os, re, time, random\n"
             "import torch\n"
             "from datasets import Dataset\n\n"
             "def find(name):\n"
             "    hits = glob.glob(f'/kaggle/input/**/{name}', recursive=True) + glob.glob(f'/content/**/{name}', recursive=True) + glob.glob(name)\n"
             "    assert hits, f'upload {name} first'\n"
             "    return hits[0]\n\n"
             "TRAIN, EVAL = find('t2_train.jsonl'), find('t2_eval.jsonl')\n"
             "rows = lambda p: [json.loads(l) for l in open(p, encoding='utf-8')]\n"
             "train_rows, eval_rows = rows(TRAIN), rows(EVAL)[:200]\n"
             "print(len(train_rows), 'train,', len(eval_rows), 'held-out eval')\n"
             "print(train_rows[0]['messages'][1]['content'], '\\n->', train_rows[0]['messages'][2]['content'])"),
    ("code", "from transformers import AutoModelForCausalLM, AutoTokenizer\n"
             "MODEL = 'Qwen/Qwen2.5-1.5B-Instruct'\n"
             "tok = AutoTokenizer.from_pretrained(MODEL)\n"
             "tok.padding_side = 'left'\n"
             "model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16, device_map={'': 0})\n"
             "print(sum(p.numel() for p in model.parameters()) / 1e9, 'B parameters')"),
    ("code", "FIELDS = ['name', 'dose', 'route', 'frequency', 'duration', 'instructions']\n"
             "norm = lambda v: ' '.join(str(v).lower().split()) if v not in (None, '') else None\n\n"
             "def parse(text):\n"
             "    m = re.search(r'\\{.*\\}', text, re.S)\n"
             "    try:\n"
             "        d = json.loads(m.group()) if m else None\n"
             "        return d['medications'] if isinstance(d, dict) and isinstance(d.get('medications'), list) else None\n"
             "    except Exception:\n"
             "        return None\n\n"
             "@torch.no_grad()\n"
             "def evaluate(model, rows, batch=16):\n"
             "    model.eval(); ok_json = fields_ok = fields_all = items_ok = 0\n"
             "    for i in range(0, len(rows), batch):\n"
             "        chunk = rows[i:i + batch]\n"
             "        prompts = [tok.apply_chat_template(r['messages'][:2], tokenize=False, add_generation_prompt=True) for r in chunk]\n"
             "        enc = tok(prompts, return_tensors='pt', padding=True).to(model.device)\n"
             "        out = model.generate(**enc, max_new_tokens=320, do_sample=False, pad_token_id=tok.eos_token_id)\n"
             "        for r, o in zip(chunk, out):\n"
             "            pred = parse(tok.decode(o[enc.input_ids.shape[1]:], skip_special_tokens=True))\n"
             "            gold = json.loads(r['messages'][2]['content'])['medications']\n"
             "            ok_json += pred is not None\n"
             "            pred = pred or []\n"
             "            items_ok += len(pred) == len(gold)\n"
             "            for j, g in enumerate(gold):\n"
             "                p = pred[j] if j < len(pred) and isinstance(pred[j], dict) else {}\n"
             "                for f in FIELDS:\n"
             "                    fields_all += 1\n"
             "                    fields_ok += norm(p.get(f)) == norm(g.get(f))\n"
             "    n = len(rows)\n"
             "    return {'valid_json_pct': round(100 * ok_json / n, 1), 'item_count_match_pct': round(100 * items_ok / n, 1),\n"
             "            'field_exact_pct': round(100 * fields_ok / fields_all, 1), 'n_prescriptions': n, 'n_fields': fields_all}\n\n"
             "t = time.time(); before = evaluate(model, eval_rows); print('BEFORE', before, round(time.time() - t), 's')"),
    ("code", "from peft import LoraConfig, get_peft_model\n"
             "model.gradient_checkpointing_enable(); model.enable_input_require_grads()\n"
             "model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type='CAUSAL_LM',\n"
             "    target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj']))\n"
             "for p in model.parameters():\n"
             "    if p.requires_grad: p.data = p.data.float()   # fp32 adapters under fp16 autocast\n"
             "model.print_trainable_parameters()\n\n"
             "def encode(r):\n"
             "    prompt = tok.apply_chat_template(r['messages'][:2], tokenize=False, add_generation_prompt=True)\n"
             "    p = tok(prompt, add_special_tokens=False).input_ids\n"
             "    a = tok(r['messages'][2]['content'] + '<|im_end|>', add_special_tokens=False).input_ids\n"
             "    ids, labels = (p + a)[:700], ([-100] * len(p) + a)[:700]   # loss only on the answer\n"
             "    return {'input_ids': ids, 'attention_mask': [1] * len(ids), 'labels': labels}\n\n"
             "ds = Dataset.from_list(train_rows).map(lambda r: encode(r), remove_columns=['messages'])\n"
             "print(len(ds), 'examples, longest', max(len(x) for x in ds['input_ids']), 'tokens')"),
    ("code", "from transformers import DataCollatorForSeq2Seq, Trainer, TrainingArguments\n"
             "tok.padding_side = 'right'\n"
             "args = TrainingArguments(output_dir='t2_out', per_device_train_batch_size=8, gradient_accumulation_steps=4,\n"
             "    num_train_epochs=1, learning_rate=2e-4, lr_scheduler_type='cosine', warmup_ratio=0.03, fp16=True,\n"
             "    logging_steps=25, save_strategy='no', report_to='none', gradient_checkpointing=True, remove_unused_columns=False)\n"
             "trainer = Trainer(model=model, args=args, train_dataset=ds,\n"
             "    data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100))\n"
             "t = time.time(); trainer.train(); train_s = round(time.time() - t); print('trained in', train_s, 's')"),
    ("code", "tok.padding_side = 'left'; model.gradient_checkpointing_disable(); model.config.use_cache = True\n"
             "after = evaluate(model, eval_rows); print('AFTER', after)\n"
             "results = {'model': MODEL, 'method': 'LoRA r=16', 'train_examples': len(train_rows), 'epochs': 1, 'train_seconds': train_s,\n"
             "           'eval': 'held-out medicine names, synthetic', 'before': before, 'after': after}\n"
             "json.dump(results, open('t2_results.json', 'w'), indent=1)\n"
             "model.save_pretrained('t2_adapter'); tok.save_pretrained('t2_adapter')\n"
             "!zip -qr t2_adapter.zip t2_adapter\n"
             "print(json.dumps(results, indent=1))"),
    ("md", "## Reading the result\n\n"
           "Held-out names mean the model cannot just remember a medicine. Synthetic prescriptions are cleaner than real ones, so a high score here "
           "is an upper bound, not a hospital accuracy. Compare against the prompt-only LLM in `docs/EVAL.md` (25 hand-written prescriptions) "
           "and state both numbers with their data sets."),
]

T3 = [
    ("md", "# T3: TrOCR fine-tune on handwritten medicine-name images\n\n"
           "**Run on Kaggle or Colab with a T4 GPU** (about 30 to 60 minutes).\n\n"
           "**Data.** RxHandBD (Mendeley Data, 5,578 images of handwritten medicine names) or the Doctor's Handwritten Prescription BD set. "
           "Download it yourself and read its licence before using it; this notebook does not redistribute it. Add it as a Kaggle dataset "
           "or upload to Colab.\n\n"
           "**Unverified assumption.** The folder layout of the download was not checked when this notebook was written. Cell 3 detects "
           "either a CSV (image, text) or one folder per word, prints what it found, and stops if it looks wrong. Edit only that cell.\n\n"
           "**Split.** Random 80/10/10 by image. The data has no writer identifiers that I could verify, so this does **not** test unseen "
           "writers. Do not claim that."),
    ("code", "!pip -q install -U transformers datasets accelerate jiwer pillow"),
    ("code", "import glob, os, random, time, json\n"
             "import torch, pandas as pd\n"
             "from PIL import Image\n"
             "ROOT = os.environ.get('RXHAND', '/kaggle/input')   # folder that holds the downloaded dataset\n"
             "imgs = [p for p in glob.glob(ROOT + '/**/*', recursive=True) if p.lower().endswith(('.png', '.jpg', '.jpeg'))]\n"
             "print(len(imgs), 'images under', ROOT); print(imgs[:3])"),
    ("code", "samples = []   # (path, text)\n"
             "csvs = glob.glob(ROOT + '/**/*.csv', recursive=True)\n"
             "by_name = {os.path.basename(p): p for p in imgs}\n"
             "for c in csvs:\n"
             "    df = pd.read_csv(c)\n"
             "    img_col = next((k for k in df.columns if df[k].astype(str).str.lower().str.endswith(('.png', '.jpg', '.jpeg')).mean() > .8), None)\n"
             "    txt_col = next((k for k in df.columns if k != img_col and df[k].dtype == object), None)\n"
             "    if img_col and txt_col:\n"
             "        samples += [(by_name[os.path.basename(r[img_col])], str(r[txt_col]).strip()) for _, r in df.iterrows() if os.path.basename(r[img_col]) in by_name]\n"
             "if not samples:   # fall back to one folder per word\n"
             "    samples = [(p, os.path.basename(os.path.dirname(p))) for p in imgs]\n"
             "print(len(samples), 'labelled images'); print(samples[:5])\n"
             "assert len(samples) > 1000 and len({t for _, t in samples}) > 20, 'labels look wrong: edit this cell for your folder layout'"),
    ("code", "random.seed(0); random.shuffle(samples)\n"
             "n = len(samples); tr, va, te = samples[:int(.8 * n)], samples[int(.8 * n):int(.9 * n)], samples[int(.9 * n):]\n"
             "print(len(tr), len(va), len(te))\n"
             "from transformers import TrOCRProcessor, VisionEncoderDecoderModel\n"
             "NAME = 'microsoft/trocr-base-handwritten'\n"
             "proc = TrOCRProcessor.from_pretrained(NAME)\n"
             "model = VisionEncoderDecoderModel.from_pretrained(NAME).to('cuda')\n"
             "model.config.decoder_start_token_id = proc.tokenizer.cls_token_id; model.config.pad_token_id = proc.tokenizer.pad_token_id\n"
             "model.config.vocab_size = model.config.decoder.vocab_size"),
    ("code", "import jiwer\n"
             "@torch.no_grad()\n"
             "def cer(model, rows, batch=32):\n"
             "    model.eval(); preds, refs = [], []\n"
             "    for i in range(0, len(rows), batch):\n"
             "        chunk = rows[i:i + batch]\n"
             "        px = proc([Image.open(p).convert('RGB') for p, _ in chunk], return_tensors='pt').pixel_values.to('cuda')\n"
             "        out = model.generate(px, max_new_tokens=24)\n"
             "        preds += proc.batch_decode(out, skip_special_tokens=True); refs += [t for _, t in chunk]\n"
             "    return round(jiwer.cer(refs, preds), 4), list(zip(refs[:8], preds[:8]))\n\n"
             "before, ex_before = cer(model, te); print('CER before', before); print(ex_before)"),
    ("code", "class DS(torch.utils.data.Dataset):\n"
             "    def __init__(self, rows): self.rows = rows\n"
             "    def __len__(self): return len(self.rows)\n"
             "    def __getitem__(self, i):\n"
             "        p, t = self.rows[i]\n"
             "        px = proc(Image.open(p).convert('RGB'), return_tensors='pt').pixel_values[0]\n"
             "        ids = proc.tokenizer(t, padding='max_length', max_length=24, truncation=True).input_ids\n"
             "        return {'pixel_values': px, 'labels': torch.tensor([x if x != proc.tokenizer.pad_token_id else -100 for x in ids])}\n\n"
             "from transformers import Seq2SeqTrainer, Seq2SeqTrainingArguments, default_data_collator\n"
             "args = Seq2SeqTrainingArguments(output_dir='t3_out', per_device_train_batch_size=16, num_train_epochs=4, learning_rate=4e-5,\n"
             "    fp16=True, logging_steps=50, save_strategy='no', report_to='none', remove_unused_columns=False, predict_with_generate=False)\n"
             "tr_ = Seq2SeqTrainer(model=model, args=args, train_dataset=DS(tr), data_collator=default_data_collator)\n"
             "t = time.time(); tr_.train(); train_s = round(time.time() - t); print('trained in', train_s, 's')"),
    ("code", "after, ex_after = cer(model, te); print('CER after', after); print(ex_after)\n"
             "res = {'model': NAME, 'train_images': len(tr), 'test_images': len(te), 'split': 'random by image (no writer ids)',\n"
             "       'cer_before': before, 'cer_after': after, 'train_seconds': train_s}\n"
             "json.dump(res, open('t3_results.json', 'w'), indent=1); model.save_pretrained('t3_trocr'); proc.save_pretrained('t3_trocr')\n"
             "!zip -qr t3_trocr.zip t3_trocr\n"
             "print(res)"),
    ("md", "## Reading the result\n\n"
           "Character error rate is the share of characters wrong, so lower is better. The test images share writers with the training images, so this "
           "shows the model learned these medicine words, not that it reads any doctor's hand. Report it that way."),
]

if __name__ == "__main__":
    nbformat.write(nb(T2), HERE / "t2_lora_qwen.ipynb")
    nbformat.write(nb(T3), HERE / "t3_trocr_rxhandbd.ipynb")
    print("wrote t2_lora_qwen.ipynb and t3_trocr_rxhandbd.ipynb")
