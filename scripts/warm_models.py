"""Download the local models into the Hugging Face cache, so the first demo run is not slow.

    python scripts/warm_models.py [--only nllb trocr bge easyocr]

Sizes are approximate. Licences: NLLB-200 is CC-BY-NC (non-commercial), TrOCR is MIT, BGE-M3 is MIT,
EasyOCR is Apache-2.0. Needs internet once. Re-run this if the cache is ever cleared.
"""
import argparse

MODELS = {
    "nllb": ("facebook/nllb-200-distilled-600M", "about 2.4 GB"),
    "trocr": ("microsoft/trocr-base-handwritten", "about 1.3 GB"),
    "bge": ("BAAI/bge-m3", "about 2.3 GB"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", choices=[*MODELS, "easyocr"])
    args = ap.parse_args()
    want = args.only or [*MODELS, "easyocr"]
    from huggingface_hub import snapshot_download

    for key in want:
        if key == "easyocr":
            import easyocr

            print("easyocr (about 100 MB) ...", flush=True)
            easyocr.Reader(["en"], gpu=False, verbose=False)
            continue
        repo, size = MODELS[key]
        print(f"{repo} ({size}) ...", flush=True)
        snapshot_download(repo, allow_patterns=["*.json", "*.txt", "*.model", "*.safetensors", "*.bin", "*.py"],
                          ignore_patterns=["*onnx*", "*.msgpack", "*.h5", "*.ot"])
    print("done")


if __name__ == "__main__":
    main()
