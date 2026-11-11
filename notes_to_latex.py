import argparse
import base64
import mimetypes
import os
import sys
from pathlib import Path
from loguru import logger
from openai import OpenAI
from tqdm import tqdm
import subprocess

PROMPT = """
Transcribe this page of handwritten notes into LaTeX.
Output a complete document: \\documentclass{article}, \\usepackage{amsmath, amssymb, tikz} then the body.
Use no other packages.
Output raw LaTeX only, with no Markdown code fences. 
Put everything on its own line, make it clear to read, no visual clutter.
"""

def encode_image(image_path: Path) -> str:
    mime = mimetypes.guess_type(image_path)[0]
    data = base64.b64encode(image_path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"

def transcribe(client: OpenAI, model: str, image_path: Path, max_tokens:int, effort:str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": encode_image(image_path)}},
        ]}],
        max_tokens=max_tokens,
        temperature=0,
        reasoning_effort=effort
    )
    message = response.choices[0].message
    content = message.content
    if len(content)==0:
        try:
            reasoning = message.reasoning
            logger.info(f"reasoning:\n{reasoning}")
            logger.info(f"ran out of tokens reasoning, reasoning length {len(reasoning)}...")
        except:
            logger.info("Ran out of tokens, but no reasoning.")
    return content

def compile_output(out_path: Path) -> None:
    # latex compiler we added through uv add
    # avoid markdown fences
    out_path.write_text(
        out_path.read_text().replace("```latex", "").replace("```", "")
    )
    subprocess.run(["tectonic", str(out_path)], check=True)

def notes_to_latex(args: argparse.Namespace) -> None:
    client = OpenAI(
        base_url=args.base_url,
        api_key=os.environ.get("OPENAI_API_KEY", "local")
    )
    image_paths = sorted(
        p for p in args.image_dir.iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for image_path in tqdm(image_paths):
        out_path = args.out_dir / f"{image_path.stem}.tex"
        output = transcribe(
            client, args.model,
            image_path, args.max_tokens, args.effort
        )
        out_path.write_text(output)
        logger.info(f"wrote {out_path}")
        compile_output(out_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image_dir", type=Path, required=True)
    parser.add_argument("--out_dir", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base_url", required=True)
    parser.add_argument("--log_level", default="DEBUG")
    parser.add_argument("--max_tokens", type=int, default=4096)
    # The context window is frequently filled, avoid thinking
    # try using a instruct variant if the model disobeys the no think instruction
    parser.add_argument("--effort", default="none")
    args = parser.parse_args()
    logger.remove()
    logger.add(sys.stderr, level=args.log_level)
    logger.add("logs/notes_to_latex_{time}.log", level=args.log_level)
    notes_to_latex(args)