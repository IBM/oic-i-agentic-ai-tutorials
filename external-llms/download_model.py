#!/usr/bin/env python3
"""Download the model during Docker build to avoid runtime downloads."""
import os
import sys
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_NAME = os.getenv("MODEL_NAME", "ibm-granite/granite-4.0-h-1b")

print(f"Downloading model: {MODEL_NAME}")
print("This may take several minutes...")

try:
    # Download tokenizer
    print("Downloading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    print(f"Tokenizer downloaded to: {tokenizer.name_or_path}")

    # Download model
    print("Downloading model weights...")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        device_map="cpu",  # Don't load to GPU during build
    )
    print(f"Model downloaded successfully!")
    print(f"Model saved to HuggingFace cache")

except Exception as e:
    print(f"ERROR: Failed to download model: {e}", file=sys.stderr)
    sys.exit(1)

print("Model download complete!")
