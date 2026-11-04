"""Publishes the app to a Hugging Face Space. Run `hf auth login` once first.

    python scripts/deploy_space.py [space-name]

Creates the public Space if needed, stores GROQ_API_KEY from .env as a Space secret (never in
the files), and uploads only what the Dockerfile needs. Prints the app's address.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
CARD = """---
title: MedSaarthi AI
emoji: 💊
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Explains a prescription in plain words and your language
---

# MedSaarthi AI

A student project (CS4204, RV University): a friendly helper that explains a prescription in plain
words and in Hindi, Kannada, Tamil or Telugu, and sends anything unclear to a pharmacist.

**Tested only on synthetic prescriptions. Not a medical device, and not medical advice. Please do
not enter real patient data:** extracted text is sent to the Groq API.

Source, evaluation and report: https://github.com/Sanjay2408/MedSaarthi-AI
"""
ALLOW = ["Dockerfile", ".dockerignore", "requirements-app.txt", "config.yaml", "src/**", "api/**", "data/**", "web/**"]
IGNORE = ["web/node_modules/**", "web/dist/**", "**/__pycache__/**", ".env"]


def main():
    api = HfApi()
    user = api.whoami()["name"]
    repo = f"{user}/{sys.argv[1] if len(sys.argv) > 1 else 'MedSaarthi-AI'}"
    key = os.getenv("GROQ_API_KEY")
    if not key:
        sys.exit("GROQ_API_KEY is missing from .env")
    api.create_repo(repo, repo_type="space", space_sdk="docker", exist_ok=True, private=False)
    api.add_space_secret(repo, "GROQ_API_KEY", key)
    api.upload_file(path_or_fileobj=CARD.encode("utf-8"), path_in_repo="README.md", repo_id=repo, repo_type="space")
    api.upload_folder(folder_path=ROOT, repo_id=repo, repo_type="space", allow_patterns=ALLOW, ignore_patterns=IGNORE,
                      commit_message="Deploy MedSaarthi AI")
    host = repo.lower().replace("/", "-").replace("_", "-")
    print(f"Space:  https://huggingface.co/spaces/{repo}")
    print(f"App:    https://{host}.hf.space")
    print("The first build takes about 15 minutes while it fetches the models.")


if __name__ == "__main__":
    main()
