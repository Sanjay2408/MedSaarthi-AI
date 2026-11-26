"""Builds and runs the 15 CS4204 lab notebooks.

    python labs/build_labs.py [numbers ...]      e.g. python labs/build_labs.py 1 2 3   (default: all)

Each notebook is executed here and saved WITH its outputs, so the manual shows real results.
Programs use the MedSaarthi domain (medicines, leaflets, prescriptions) where the brief allows a choice.
Programs 5, 6, 8, 12, 13, 14 and 15 call an LLM. The course manual names Cohere; no Cohere key was
available, so they use Groq unless COHERE_API_KEY is set, and each notebook prints which one ran.
"""
import re
import sys
from pathlib import Path

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

HERE = Path(__file__).resolve().parent
HEAD = "import sys\nsys.path.insert(0, '.')\nfrom common import *\n"


def lab(n, title, aim, theory, cells, conclusion):
    return n, title, aim, theory, cells, conclusion


LABS = [
    lab(1, "Pre-trained word vectors and vector arithmetic",
        "Explore word relationships in pre-trained GloVe vectors by vector arithmetic, and analyse the results.",
        "A word embedding places each word at a point in a vector space so that words used in similar contexts sit close together. "
        "GloVe is trained on global word co-occurrence counts. Differences between vectors can encode relations, "
        "so `king - man + woman` lands near `queen`. Closeness is measured by cosine similarity: cos(a, b) = a.b / (|a||b|).",
        [
            "import numpy as np\nimport gensim.downloader as api\nwv = api.load('glove-wiki-gigaword-100')   # 400,000 words, 100 dimensions\nprint(len(wv), 'words,', wv.vector_size, 'dimensions')\nprint('vector for \"medicine\" (first 8 of 100):', np.round(wv['medicine'][:8], 3))",
            "# cosine similarity by hand equals the library's value\na, b = wv['doctor'], wv['nurse']\nmanual = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))\nprint('doctor~nurse  manual', round(manual, 4), ' library', round(float(wv.similarity('doctor', 'nurse')), 4))\nprint('doctor~banana', round(float(wv.similarity('doctor', 'banana')), 4))",
            "# vector arithmetic: positive terms are added, negative terms subtracted, then the nearest words are listed\ntests = [\n  (['king', 'woman'], ['man']),\n  (['paris', 'india'], ['france']),\n  (['doctor', 'woman'], ['man']),\n  (['walking', 'swam'], ['walked']),\n  (['hospital', 'school'], ['doctor']),\n]\nfor pos, neg in tests:\n    top = wv.most_similar(positive=pos, negative=neg, topn=3)\n    print(f\"{' + '.join(pos)} - {' - '.join(neg)}  ->  \" + ', '.join(f'{w} ({s:.2f})' for w, s in top))",
            "print('odd one out:', wv.doesnt_match(['paracetamol', 'ibuprofen', 'aspirin', 'banana']))\nprint('odd one out:', wv.doesnt_match(['fever', 'cough', 'headache', 'hospital']))",
        ],
        "Analogies work when a relation is common in the training text (capital of, gender). They are weaker for rare relations, and the "
        "arithmetic returns the nearest word, which is sometimes one of the input words. Embeddings also carry the biases of their text "
        "(see `doctor + woman - man`)."),

    lab(2, "Visualising word embeddings with PCA and t-SNE",
        "Reduce embeddings of 10 domain words to two dimensions, plot them, and analyse clusters and relationships.",
        "A 100-dimensional vector cannot be drawn. PCA projects onto the directions of greatest variance and keeps global distances. "
        "t-SNE keeps local neighbourhoods and is better for showing clusters, but its axes have no meaning and it depends on the random seed and the perplexity.",
        [
            "import numpy as np, matplotlib\nmatplotlib.use('Agg')\nimport matplotlib.pyplot as plt\nfrom sklearn.decomposition import PCA\nfrom sklearn.manifold import TSNE\nimport gensim.downloader as api\nwv = api.load('glove-wiki-gigaword-100')\nmedical = ['doctor', 'nurse', 'hospital', 'medicine', 'patient', 'tablet', 'surgery', 'fever', 'pharmacy', 'vaccine']\nsports = ['cricket', 'football', 'tennis', 'stadium', 'goal', 'coach', 'match', 'player', 'tournament', 'referee']\nprint(len(medical), 'medical words;', len(sports), 'sports words for contrast')",
            "words = medical + sports\nX = np.array([wv[w] for w in words])\npca = PCA(n_components=2, random_state=0).fit(X)\nP = pca.transform(X)\nT = TSNE(n_components=2, perplexity=5, random_state=0, init='pca').fit_transform(X)\nprint('variance kept by the 2 PCA axes:', round(float(pca.explained_variance_ratio_.sum()), 3))",
            "fig, ax = plt.subplots(1, 2, figsize=(13, 5.5))\nfor a, Z, name in zip(ax, (P, T), ('PCA', 't-SNE')):\n    for i, w in enumerate(words):\n        c = '#0b6b5f' if i < 10 else '#c2410c'\n        a.scatter(*Z[i], c=c, s=40)\n        a.annotate(w, Z[i], xytext=(4, 4), textcoords='offset points', fontsize=9)\n    a.set_title(name); a.grid(alpha=.2)\nplt.tight_layout(); plt.savefig(OUT / 'lab02_embeddings.png', dpi=140); plt.show()",
            "def mean_cos(A, B, same):\n    vals = [float(wv.similarity(a, b)) for i, a in enumerate(A) for j, b in enumerate(B) if not (same and i == j)]\n    return sum(vals) / len(vals)\nwithin_m, within_s, between = mean_cos(medical, medical, True), mean_cos(sports, sports, True), mean_cos(medical, sports, False)\nprint(f'mean cosine inside medical {within_m:.3f}, inside sports {within_s:.3f}, between the two {between:.3f}')\nprint('closest medical pair:', max(((a, b) for i, a in enumerate(medical) for b in medical[i+1:]), key=lambda p: wv.similarity(*p)))\nprint('words nearest to the sports centroid among the medical list:', sorted(medical, key=lambda w: -float(wv.cosine_similarities(wv[w], [np.mean([wv[s] for s in sports], axis=0)])[0]))[:3])",
        ],
        "Words from one domain sit closer to each other than to another domain, in both plots. The numbers above back the picture. "
        "t-SNE separates the groups more sharply; PCA keeps relative distances. Changing the seed or perplexity moves t-SNE points, "
        "so cluster shapes should be read, not distances between clusters."),

    lab(3, "Five semantically similar words for any input",
        "Write a program that generates 5 semantically similar words for a given input using embeddings.",
        "Nearest neighbours in embedding space by cosine similarity are the words used in the most similar contexts. "
        "Similar here does not always mean synonym: antonyms (hot, cold) and related words (doctor, hospital) are also close.",
        [
            "import gensim.downloader as api\nwv = api.load('glove-wiki-gigaword-100')\n\ndef similar_words(word, n=5):\n    \"\"\"n nearest words, or a clear message when the word is not in the vocabulary.\"\"\"\n    w = word.strip().lower()\n    if w not in wv:\n        return None\n    return [(x, round(float(s), 3)) for x, s in wv.most_similar(w, topn=n)]\n\n# interactive use: word = input('Word: ')\nfor word in ['medicine', 'fever', 'hospital', 'cough', 'ibuprofen', 'qzxv']:\n    r = similar_words(word)\n    print(f'{word:10s}', ('not in vocabulary' if r is None else ', '.join(f'{w} ({s})' for w, s in r)))",
            "# similar is not the same as synonym: check an antonym pair\nprint('hot ~ cold', round(float(wv.similarity('hot', 'cold')), 3), '  hot ~ warm', round(float(wv.similarity('hot', 'warm')), 3))",
        ],
        "The function returns five neighbours with their cosine scores and reports unknown words instead of failing. "
        "Neighbours of a drug name are often other drugs, which is useful for suggestions but not a guarantee of equivalence, "
        "so MedSaarthi never substitutes one medicine for another."),

    lab(4, "Train a custom Word2Vec model on a domain corpus",
        "Train embeddings on a small medical corpus and analyse how they capture domain-specific meaning.",
        "Word2Vec (skip-gram) trains a shallow network to predict context words from a centre word; the learned weights are the embeddings. "
        "A small corpus gives noisy vectors, so results are compared with GloVe, which was trained on billions of words.",
        [
            "import re, random\nfrom pathlib import Path\nfrom gensim.models import Word2Vec\nfrom gensim.utils import simple_preprocess\nfrom src.tagger.synth import make_lines, split_names\n\n# corpus 1: the project's 10 synthetic patient leaflets\nleaflets = ' '.join(p.read_text(encoding='utf-8') for p in sorted((ROOT / 'data' / 'leaflets').glob('*.md')))\nsent1 = [simple_preprocess(s) for s in re.split(r'[.\\n]', leaflets) if len(s.split()) > 3]\n# corpus 2: 4,000 synthetic dosing sentences built from invented prescription lines\nnames, _ = split_names()\nsent2 = []\nfor ln in make_lines(4000, names, seed=3):\n    g = ln.gold\n    sent2.append(simple_preprocess(f\"take {g.get('name','')} {g.get('dose','')} {g.get('frequency','')} {g.get('instructions','')} for {g.get('duration','')}\"))\ncorpus = sent1 + sent2\nprint(len(sent1), 'leaflet sentences +', len(sent2), 'dosing sentences =', len(corpus), '; tokens:', sum(map(len, corpus)))",
            "model = Word2Vec(corpus, vector_size=64, window=5, min_count=3, sg=1, epochs=40, seed=1, workers=1)\nprint('vocabulary:', len(model.wv))\nfor w in ['fever', 'food', 'tablet', 'paracetamol', 'daily']:\n    if w in model.wv:\n        print(f'{w:12s}', ', '.join(f'{x} ({s:.2f})' for x, s in model.wv.most_similar(w, topn=5)))",
            "# does the model place medicine names together? share of each drug's 5 neighbours that are also drug names\nfrom src.tagger.synth import ALL_NAMES\ndrugs = {n.lower() for n in ALL_NAMES}\nrows = []\nfor d in ['paracetamol', 'amoxicillin', 'metformin', 'cetirizine', 'atorvastatin', 'pantoprazole']:\n    if d in model.wv:\n        nb = [w for w, _ in model.wv.most_similar(d, topn=5)]\n        rows.append((d, sum(w in drugs for w in nb) / 5))\nprint('share of neighbours that are medicines:', {d: v for d, v in rows}, ' mean', round(sum(v for _, v in rows) / len(rows), 2))\nimport gensim.downloader as api\nglove = api.load('glove-wiki-gigaword-100')\nrows = []\nfor d in ['paracetamol', 'amoxicillin', 'metformin', 'cetirizine', 'atorvastatin', 'pantoprazole']:\n    if d in glove:\n        rows.append(sum(w in drugs for w, _ in glove.most_similar(d, topn=5)) / 5)\nprint('GloVe, same measure, mean', round(sum(rows) / len(rows), 2), 'over', len(rows), 'drugs it knows')",
        ],
        "Even a tiny domain corpus teaches the model that medicine names behave alike (they appear in the same slots of a dosing sentence). "
        "That is partly because the dosing sentences are built from a template, so the result flatters the model; with only a few thousand sentences "
        "the vectors for rare words are unreliable. GloVe knows more words but nothing about this project's usage."),

    lab(5, "Improve a prompt with embedding-retrieved words",
        "Retrieve similar words with embeddings and use them to enrich a GenAI prompt.",
        "Prompt enrichment adds relevant terms so the model covers more of what the user means. Embeddings supply candidate terms; code filters them "
        "so the prompt does not fill with noise.",
        [
            "import gensim.downloader as api\nwv = api.load('glove-wiki-gigaword-100')\nSTOP = set('the a an of and or to in is for on with'.split())\n\ndef related(seed, n=6):\n    out = []\n    for w, s in wv.most_similar(seed, topn=40):\n        if w.isalpha() and w not in STOP and seed not in w and w not in out and len(w) > 3:\n            out.append(w)\n        if len(out) == n:\n            break\n    return out\n\nseeds = ['medicine', 'dose', 'pharmacist']\nextra = {s: related(s) for s in seeds}\nfor s, ws in extra.items():\n    print(f'{s:10s} ->', ', '.join(ws))",
            "base = 'Explain how a patient should take a new medicine.'\nterms = []\nfor ws in extra.values():\n    terms += [w for w in ws[:3] if w not in terms]\nenriched = f\"{base} Cover these related ideas where they matter: {', '.join(terms)}.\"\nprint('ORIGINAL :', base)\nprint('ENRICHED :', enriched)\nprint('added', len(terms), 'terms')\nimport json; (OUT / 'lab05_prompts.json').write_text(json.dumps({'original': base, 'enriched': enriched, 'terms': terms}), encoding='utf-8')",
        ],
        "The retrieved words are plausible but not all useful (some are generic). Filtering by length, alphabet and duplicates keeps the prompt clean, "
        "and capping the count keeps it short. Whether enrichment helps is tested in Program 6."),

    lab(6, "Compare responses to the original and the enriched prompt",
        "Generate responses with an AI model for both prompts and compare detail and relevance.",
        "Detail is measured as length and as coverage of a fixed checklist of expected topics; relevance as cosine similarity of the response to a reference answer "
        "using average GloVe vectors. Both are crude proxies and the run is one sample at temperature 0.",
        [
            "import json, re, numpy as np\nimport gensim.downloader as api\nwv = api.load('glove-wiki-gigaword-100')\nllm, label = get_llm()\nprint('model:', label)\nP = json.loads((OUT / 'lab05_prompts.json').read_text(encoding='utf-8'))\nr_orig = ask(llm, P['original'] + ' Answer in under 200 words.')\nr_enr = ask(llm, P['enriched'] + ' Answer in under 200 words.')\nprint('--- ORIGINAL ---\\n', r_orig, '\\n--- ENRICHED ---\\n', r_enr)",
            "CHECK = {'dose': ['dose', 'dosage', 'amount'], 'timing': ['time', 'daily', 'morning', 'hours'], 'food': ['food', 'meal', 'empty stomach'],\n         'side effects': ['side effect', 'reaction'], 'pharmacist or doctor': ['pharmacist', 'doctor'], 'storage': ['store', 'storage', 'cool', 'dry'],\n         'missed dose': ['missed', 'forget'], 'allergy': ['allerg']}\ndef coverage(t): return [k for k, ws in CHECK.items() if any(w in t.lower() for w in ws)]\ndef avgvec(t):\n    v = [wv[w] for w in re.findall(r'[a-z]+', t.lower()) if w in wv]\n    return np.mean(v, axis=0)\nref = 'take the dose at the right time with food, watch for side effects, ask the pharmacist or doctor, store in a cool dry place, do not double a missed dose, tell about allergy'\ncos = lambda a, b: float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))\nfor name, r in (('original', r_orig), ('enriched', r_enr)):\n    cv = coverage(r)\n    print(f'{name:9s} words {len(r.split()):4d}  checklist {len(cv)}/{len(CHECK)}  cosine to reference {cos(avgvec(r), avgvec(ref)):.3f}  missing: {[k for k in CHECK if k not in cv]}')",
        ],
        "In this run the enriched prompt covered fewer checklist topics than the plain one (see the table). The retrieved words (veterinary, dentist, internist) "
        "pulled the answer towards other professions instead of how to take a medicine. Nearest neighbours in embedding space are related words, not "
        "necessarily useful ones, so enrichment needs a relevance filter and has to be measured over many prompts, not assumed to help. This is one sample at temperature 0."),

    lab(7, "Creative sentences from similar words",
        "Use embeddings to retrieve similar words for a seed word and build meaningful sentences.",
        "Similar words are slotted into sentence templates so the output stays grammatical, and an LLM is asked for a freer version for comparison.",
        [
            "import random\nimport gensim.downloader as api\nwv = api.load('glove-wiki-gigaword-100')\nllm, label = get_llm(0.7)\nprint('model:', label)\nseed = 'healing'\nwords = [w for w, _ in wv.most_similar(seed, topn=12) if w.isalpha()][:5]\nprint('seed:', seed, '-> similar:', words)",
            "# the similar words can be nouns, verbs or adjectives, so each template quotes them as words\ntemplates = ['The word \"{w}\" always reminds me of {seed}.', 'On the ward wall, someone had painted \"{w}\" next to \"{seed}\".',\n             'She wrote \"{w}\" on the card that said \"{seed}\".', 'When we talk about {seed}, the idea of \"{w}\" is never far away.',\n             'His diary joined \"{seed}\" and \"{w}\" in a single line.']\nfor w, template in zip(words, random.Random(4).sample(templates, len(words))):\n    print('-', template.format(w=w, seed=seed))",
            "print('LLM:', ask(llm, f'Write one warm, meaningful sentence that uses all of these words: {seed}, ' + ', '.join(words) + '.'))",
        ],
        "Templates guarantee a sentence but sound repetitive; the LLM sentence is richer. Neither is checked for meaning by the program, only by reading."),

    lab(8, "A short paragraph from a seed word",
        "Write a program that takes a seed word, generates similar words and constructs a short paragraph using them.",
        "The program pipeline: seed -> similar words (embeddings) -> paragraph (LLM) -> check that every word appears.",
        [
            "import re\nimport gensim.downloader as api\nwv = api.load('glove-wiki-gigaword-100')\nllm, label = get_llm(0.7)\nprint('model:', label)\n\ndef story(seed, n=4):\n    words = [w for w, _ in wv.most_similar(seed, topn=15) if w.isalpha()][:n]\n    text = ask(llm, f'Write a 4-sentence paragraph about {seed}. Use every one of these words exactly as written: ' + ', '.join(words) + '. Output the paragraph only.')\n    missing = [w for w in words if not re.search(rf'\\b{w}\\b', text, re.I)]\n    return words, text, missing\n\nfor seed in ['medicine', 'recovery']:\n    words, text, missing = story(seed)\n    print(f'SEED {seed}: {words}\\n{text}\\nwords missing from the paragraph: {missing or \"none\"}\\n')",
        ],
        "The check step matters: an LLM may skip a word, so the program reports it instead of assuming. For safety-critical text MedSaarthi uses the same idea, "
        "checking every number in the output against the input."),

    lab(9, "Sentiment analysis with a pre-trained Hugging Face model",
        "Use a pre-trained model to analyse sentiment in text for a real-world application: patient feedback at a pharmacy counter.",
        "A sentiment pipeline tokenises the text, runs a fine-tuned transformer (DistilBERT, trained on SST-2 movie reviews) and returns POSITIVE or NEGATIVE with a probability. "
        "The model was not trained on pharmacy language, so it must be checked on this domain.",
        [
            "from transformers import pipeline\nclf = pipeline('sentiment-analysis', model='distilbert-base-uncased-finetuned-sst-2-english')\nprint(clf.model.config.architectures, clf.model.num_parameters() // 1_000_000, 'M parameters')",
            "feedback = [\n  'The pharmacist explained my tablets clearly and I felt reassured.',\n  'I waited an hour and nobody told me how to take the medicine.',\n  'The new reminder app helped my father remember his doses.',\n  'The syrup tasted terrible but it did work.',\n  'Very confusing instructions, I am worried I took the wrong dose.',\n  'The staff were polite and quick.',\n]\nfor text, r in zip(feedback, clf(feedback)):\n    print(f\"{r['label']:8s} {r['score']:.3f}  {text}\")",
            "neg = [t for t, r in zip(feedback, clf(feedback)) if r['label'] == 'NEGATIVE']\nprint(len(neg), 'of', len(feedback), 'comments flagged for the pharmacy manager to read:')\nfor t in neg: print(' -', t)",
        ],
        "The pipeline gives a label and a confidence in a few lines. Mixed comments (\"terrible but it did work\") are forced into one label, "
        "which is a limit of a two-class model."),

    lab(10, "Sentiment analysis on user-entered sentences",
        "Load the sentiment pipeline and analyse sentences supplied by the user, handling uncertainty.",
        "Real input is messy: negation, sarcasm, mixed opinions. The program reports a third answer, UNSURE, when the model's confidence is below a threshold, "
        "and is scored on a small labelled set so its accuracy is a number, not a feeling.",
        [
            "from transformers import pipeline\nclf = pipeline('sentiment-analysis', model='distilbert-base-uncased-finetuned-sst-2-english')\n\ndef analyse(text, threshold=0.90):\n    r = clf(text)[0]\n    return ('UNSURE' if r['score'] < threshold else r['label']), round(r['score'], 3)\n\n# interactive use: print(analyse(input('Sentence: ')))\nfor s in ['I love how simple this plan is.', 'This is not good at all.', 'Not bad.', 'Oh great, another pill to remember.', 'The tablet is white and round.']:\n    print(analyse(s), '<-', s)",
            "labelled = [('Excellent service and clear advice.', 'POSITIVE'), ('Terrible, I was ignored.', 'NEGATIVE'), ('The app is wonderful.', 'POSITIVE'),\n  ('I am very unhappy with the delay.', 'NEGATIVE'), ('Helpful and kind staff.', 'POSITIVE'), ('The instructions were awful.', 'NEGATIVE'),\n  ('I would recommend this pharmacy.', 'POSITIVE'), ('It made my pain worse and nobody helped.', 'NEGATIVE'), ('Very reassuring explanation.', 'POSITIVE'),\n  ('A waste of my time.', 'NEGATIVE'), ('Quick and painless process.', 'POSITIVE'), ('Rude and dismissive.', 'NEGATIVE')]\npred = [clf(t)[0]['label'] for t, _ in labelled]\nacc = sum(p == y for p, (_, y) in zip(pred, labelled)) / len(labelled)\nprint(f'accuracy on {len(labelled)} hand-written sentences: {acc:.0%}  (a tiny set: it shows the method, not the true accuracy)')",
        ],
        "The UNSURE band catches some hard cases, not all (sarcasm can still score high). A 12-sentence test cannot give a reliable accuracy; "
        "it demonstrates how to measure."),

    lab(11, "Summarising long text with a pre-trained model",
        "Summarise a long passage with a Hugging Face summarisation pipeline, and check what the summary lost.",
        "Abstractive summarisation (BART/DistilBART) generates new sentences conditioned on the input. Because it can drop or alter details, "
        "the program checks that the numbers and the medicine name survive. This is the same worry as in MedSaarthi's simplification step. "
        "Transformers 5 removed the 'summarization' pipeline named in the manual, so the program loads the same model with its tokenizer "
        "and calls generate(), which is what the pipeline did internally.",
        [
            "import torch\nfrom transformers import AutoModelForSeq2SeqLM, AutoTokenizer\nNAME = 'sshleifer/distilbart-cnn-12-6'\ntok = AutoTokenizer.from_pretrained(NAME)\nmodel = AutoModelForSeq2SeqLM.from_pretrained(NAME).eval()\nprint(type(model).__name__, model.num_parameters() // 1_000_000, 'M parameters')\n\ndef summarise(text, max_new=120, min_new=40):\n    batch = tok(text, return_tensors='pt', truncation=True, max_length=1024)\n    with torch.no_grad():\n        ids = model.generate(**batch, num_beams=4, max_new_tokens=max_new, min_new_tokens=min_new, do_sample=False)\n    return tok.decode(ids[0], skip_special_tokens=True).strip()\npassage = (ROOT / 'data' / 'leaflets' / 'amoxicillin.md').read_text(encoding='utf-8')\npassage = passage.split('\\n', 3)[3]   # drop the title and the synthetic notice\nprint(len(passage.split()), 'words in the passage')",
            "out = summarise(passage[:3500])\nprint(out)\nprint('\\ncompression:', len(out.split()), 'of', len(passage[:3500].split()), 'words')",
            "import re\nnums_src, nums_out = set(re.findall(r'\\d+', passage[:3500])), set(re.findall(r'\\d+', out))\nprint('numbers only in the summary (possible invention):', sorted(nums_out - nums_src) or 'none')\nprint('numbers in the source that the summary dropped:', sorted(nums_src - nums_out)[:10])\nprint('medicine name kept:', 'amoxicillin' in out.lower())",
        ],
        "The summary is shorter and readable, but the check shows what it dropped. For dosing text MedSaarthi does not summarise: doses, times and "
        "days are written by code from verified fields."),

    lab(12, "LangChain and the Cohere key",
        "Install langchain, cohere and langchain-community, obtain the API key, and run a first chain.",
        "LangChain composes steps with the `|` operator: prompt | model | output parser. The model object is the only part that changes between providers.",
        [
            "import importlib.metadata as md\nfor p in ['langchain', 'langchain-cohere', 'langchain-community', 'langchain-groq']:\n    print(f'{p:22s}', md.version(p))\nprint('install command: pip install langchain cohere langchain-cohere langchain-community')",
            "import os\nprint('COHERE_API_KEY set:', bool(os.getenv('COHERE_API_KEY')))\nprint('To get one: sign in at dashboard.cohere.com, open API Keys, copy a free trial key, then put COHERE_API_KEY=... in a .env file. Never paste a key into a notebook cell or a chat.')",
            "from langchain_core.prompts import ChatPromptTemplate\nfrom langchain_core.output_parsers import StrOutputParser\nllm, label = get_llm()\nprint('model used:', label)\nchain = ChatPromptTemplate.from_template('In one sentence, what is {topic}?') | llm | StrOutputParser()\nprint(chain.invoke({'topic': 'a prescription'}))",
        ],
        "No Cohere key was available when this was run, so the same chain ran on Groq. Only `get_llm()` changes when a key is set, "
        "which is the point of the common model interface."),

    lab(13, "Prompt template over a loaded document",
        "Load a text document (from Drive or disk) and create a prompt template that displays the output in a fixed layout.",
        "A `PromptTemplate` has named slots. Fixing the output layout in the template makes answers consistent and easy to parse.",
        [
            "# On Colab, mount Drive and point PATH at your file. Here the same step reads a file from disk.\ntry:\n    from google.colab import drive\n    drive.mount('/content/drive')\n    PATH = '/content/drive/MyDrive/metformin.md'\nexcept Exception:\n    PATH = ROOT / 'data' / 'leaflets' / 'metformin.md'\ndoc = open(PATH, encoding='utf-8').read()\nprint(PATH, '-', len(doc.split()), 'words')",
            "from langchain_core.prompts import PromptTemplate\nfrom langchain_core.output_parsers import StrOutputParser\ntemplate = PromptTemplate.from_template(\n  'Read the leaflet and answer in EXACTLY this layout, using only the leaflet:\\n'\n  'MEDICINE: <name>\\nUSED FOR: <one line>\\nHOW TO TAKE: <one line>\\nWARNINGS: <up to 3 short bullets>\\n\\nLEAFLET:\\n{doc}')\nprint(template.format(doc='...')[:260], '\\n')\nllm, label = get_llm()\nprint('model:', label)\nout = (template | llm | StrOutputParser()).invoke({'doc': doc})\nprint(out)\nprint('\\nlayout kept:', all(h in out for h in ['MEDICINE:', 'USED FOR:', 'HOW TO TAKE:', 'WARNINGS:']))",
        ],
        "A fixed template plus a check on the headings lets code rely on the output. Content accuracy still needs checking against the leaflet."),

    lab(14, "Structured output with Pydantic and a custom parser",
        "Take an institution name, define the output schema with Pydantic, write a custom output parser, invoke the chain and fetch details from Wikipedia.",
        "Pydantic validates types and rules. A custom `BaseOutputParser` turns model text into a validated object and raises a clear error otherwise. "
        "The model may use only the Wikipedia text it is given, and must say `not stated` for anything absent, so it cannot invent facts.",
        [
            "import json, re, wikipedia\nfrom pydantic import BaseModel, Field, field_validator\nfrom langchain_core.output_parsers import BaseOutputParser\n\nclass Institution(BaseModel):\n    founder: str = Field(description='who founded it')\n    founded: str = Field(description='when')\n    branches: list[str] = Field(description='current schools, branches or campuses')\n    employees: str = Field(description='number of employees')\n    summary: list[str] = Field(description='exactly 4 short lines')\n\n    @field_validator('summary')\n    @classmethod\n    def four_lines(cls, v):\n        if len(v) != 4:\n            raise ValueError(f'summary must have 4 lines, got {len(v)}')\n        return v\n\nclass InstitutionParser(BaseOutputParser[Institution]):\n    def parse(self, text: str) -> Institution:\n        m = re.search(r'\\{.*\\}', text, re.S)\n        if not m:\n            raise ValueError('no JSON object in the model output')\n        return Institution.model_validate(json.loads(m.group()))\n    @property\n    def _type(self): return 'institution'\nprint(list(Institution.model_fields))",
            "name = 'RV University'\nhits = wikipedia.search(name)\nprint('wikipedia search:', hits[:4])\npage = wikipedia.page(hits[0], auto_suggest=False)\nsource = page.content[:7000]\nprint('page:', page.title, '-', len(source.split()), 'words used')",
            "from langchain_core.prompts import PromptTemplate\nllm, label = get_llm()\nprint('model:', label)\nprompt = PromptTemplate.from_template(\n  'Using ONLY the text below, return JSON with keys founder, founded, branches (list), employees, summary (a list of EXACTLY 4 short lines) for {name}. '\n  'If the text does not say, write \"not stated\". Do not use outside knowledge.\\n\\nTEXT:\\n{text}')\nchain = prompt | llm | InstitutionParser()\nfor attempt in range(2):\n    try:\n        result = chain.invoke({'name': name, 'text': source}); break\n    except Exception as e:\n        print('retry after:', e)\nprint(result.model_dump_json(indent=1))",
        ],
        "Typing and the 4-line rule are enforced by code, not trusted to the prompt. \"not stated\" is an honest answer; it is better than a guess."),

    lab(15, "Retrieval chatbot for the Indian Penal Code",
        "Download the Indian Penal Code, index it, and build a chatbot that answers questions with sources and keeps the conversation.",
        "Retrieval-Augmented Generation: split the document into chunks, embed them, retrieve the chunks nearest to the question, and have the model answer using only those chunks. "
        "A rewrite step turns a follow-up like \"and the punishment?\" into a stand-alone question. Note: the IPC was replaced by the Bharatiya Nyaya Sanhita in July 2024, so this is a study exercise on the 1860 text, not legal advice.",
        [
            "import urllib.request\nfrom pypdf import PdfReader\nURL = 'https://www.mahapolice.gov.in/uploads/acts_rules/TheIndianPenalCode.pdf'   # copy published by the Maharashtra Police\nPDF = DATA / 'ipc.pdf'\nif not PDF.exists():\n    urllib.request.urlretrieve(URL, PDF)\nreader = PdfReader(str(PDF))\npages = [(i + 1, p.extract_text() or '') for i, p in enumerate(reader.pages)]\nprint(len(pages), 'pages,', sum(len(t.split()) for _, t in pages), 'words')",
            "from langchain_text_splitters import RecursiveCharacterTextSplitter\nsplit = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)\nchunks = []\nfor pg, text in pages:\n    for c in split.split_text(text):\n        chunks.append((pg, c))\nprint(len(chunks), 'chunks; first:', chunks[3][1][:160].replace('\\n', ' '))",
            "import numpy as np, faiss\nfrom sentence_transformers import SentenceTransformer\nemb = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')\nM = emb.encode([c for _, c in chunks], batch_size=64, normalize_embeddings=True, show_progress_bar=False)\nindex = faiss.IndexFlatIP(M.shape[1]); index.add(np.asarray(M, dtype='float32'))\nprint(index.ntotal, 'vectors of', M.shape[1], 'dimensions')\ndef retrieve(q, k=4):\n    s, i = index.search(emb.encode([q], normalize_embeddings=True).astype('float32'), k)\n    return [(chunks[j][0], chunks[j][1], float(x)) for x, j in zip(s[0], i[0])]\nfor pg, c, s in retrieve('What is the punishment for theft?', 2):\n    print(f'p.{pg} score {s:.2f}:', c[:200].replace('\\n', ' '))",
            "llm, label = get_llm()\nprint('model:', label)\nhistory = []\n\ndef standalone(q):\n    if not history: return q\n    ctx = '\\n'.join(f'Q: {a}\\nA: {b[:200]}' for a, b in history[-3:])\n    return ask(llm, f'Rewrite the last question so it makes sense alone. Output only the question.\\n{ctx}\\nLast question: {q}')\n\ndef chat(q):\n    sq = standalone(q)\n    hits = retrieve(sq, 4)\n    context = '\\n\\n'.join(f'[page {p}] {c}' for p, c, _ in hits)\n    ans = ask(llm, 'Answer using ONLY the context from the Indian Penal Code 1860. Cite section numbers if shown. '\n                   'If the context does not contain the answer, say \"The text I have does not say.\" This is not legal advice.\\n\\n'\n                   f'CONTEXT:\\n{context}\\n\\nQUESTION: {sq}')\n    history.append((q, ans))\n    return sq, ans, sorted({p for p, _, _ in hits})\n\nfor q in ['What is the punishment for theft?', 'And for robbery?', 'What is the capital of France?']:\n    sq, ans, pgs = chat(q)\n    print(f'USER: {q}\\n(rewritten: {sq})\\nBOT: {ans}\\n(sources: pages {pgs})\\n')",
        ],
        "The follow-up \"And for robbery?\" works because of the rewrite step. The off-topic question should be refused, which tests whether the model sticks to the context. "
        "Retrieval can return the wrong section, so answers always show their pages."),
]


def build(entry):
    n, title, aim, theory, cells, conclusion = entry
    nb = nbformat.v4.new_notebook()
    nb.metadata = {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}}
    nb.cells = [nbformat.v4.new_markdown_cell(f"# Program {n}: {title}\n\n**Aim.** {aim}\n\n**Theory.** {theory}"),
                nbformat.v4.new_code_cell(HEAD)] + [nbformat.v4.new_code_cell(c) for c in cells] + \
               [nbformat.v4.new_markdown_cell(f"## Observations\n\n{conclusion}")]
    return nb


PROGRESS = re.compile(r"MB downloaded|it/s\]|s/it\]|^(Loading weights|Downloading|Fetching \d+ files)")


def tidy(nb):
    """Drop library chatter from saved outputs: all of stderr (warnings, progress) and progress-bar
    lines in stdout. What a program prints is kept exactly, including words such as WARNINGS."""
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        keep = []
        for o in cell.get("outputs", []):
            if o.output_type == "stream":
                if o.name == "stderr":
                    continue
                lines = [l for l in o.text.replace("\r\n", "\n").split("\n") if not PROGRESS.search(l)]
                o.text = "\n".join(lines).strip("\n") + "\n"
                if not o.text.strip():
                    continue
            keep.append(o)
        cell.outputs = keep


def main():
    wanted = {int(a) for a in sys.argv[1:]} or {e[0] for e in LABS}
    for entry in LABS:
        if entry[0] not in wanted:
            continue
        nb = build(entry)
        path = HERE / f"lab{entry[0]:02d}.ipynb"
        print(f"running {path.name} ...", flush=True)
        try:
            ExecutePreprocessor(timeout=1500, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(HERE)}})
            status = "ok"
        except Exception as e:  # keep the notebook with the error so it can be read
            status = f"FAILED: {str(e)[-400:]}"
        tidy(nb)
        nbformat.write(nb, path)
        print(f"  {status}", flush=True)


if __name__ == "__main__":
    main()
