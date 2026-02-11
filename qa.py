#!/usr/bin/env python3
"""
Calgary Community Q&A Bot.

Uses ChromaDB for retrieval and Claude headless for answer generation.

Usage:
    python3 qa.py "Is Beltline safe?"
    python3 qa.py --batch questions.csv --output answers.csv
    python3 qa.py --interactive
"""

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import chromadb


CHROMA_DIR = Path(__file__).parent / "chroma_db"
COLLECTION_NAME = "communities"
SYSTEM_PROMPT = Path(__file__).parent / "prompts" / "system.md"
TOP_K = 8


def get_collection():
    """Get the ChromaDB collection."""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(COLLECTION_NAME)


def retrieve(collection, question, top_k=TOP_K):
    """Retrieve relevant chunks for a question."""
    results = collection.query(
        query_texts=[question],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        viz = json.loads(meta.get("viz", "[]")) if meta.get("viz") else []
        chunks.append({
            "text": doc,
            "community": meta["community"],
            "section": meta["section"],
            "url": meta["url"],
            "viz": viz,
            "distance": dist,
        })

    return chunks


def build_prompt(question, chunks):
    """Build the full prompt with system instructions and retrieved context."""
    system = SYSTEM_PROMPT.read_text() if SYSTEM_PROMPT.exists() else ""

    context = "RETRIEVED DATA:\n\n"
    for i, chunk in enumerate(chunks, 1):
        context += f"[{i}] ({chunk['community']} - {chunk['section']}) {chunk['url']}\n"
        context += f"{chunk['text']}\n"
        if chunk.get("viz"):
            viz_desc = ", ".join(f"{v['type']} ({v['component']})" for v in chunk["viz"])
            context += f"Visualizations available: {viz_desc}\n"
        context += "\n"

    prompt = f"{system}\n\n{context}\n\nQUESTION: {question}\n\nAnswer the question using the retrieved data above. When relevant, mention which visualizations are available on Calgary Pulse for the user to explore."
    return prompt


def ask_claude(prompt):
    """Call Claude headless via subprocess."""
    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Error: {result.stderr.strip()}"
    except FileNotFoundError:
        return "Error: 'claude' command not found. Install Claude Code CLI."
    except subprocess.TimeoutExpired:
        return "Error: Claude timed out after 60 seconds."


def ask(question, collection=None, verbose=False):
    """Full Q&A pipeline: retrieve → build prompt → generate answer."""
    if collection is None:
        collection = get_collection()

    chunks = retrieve(collection, question)

    if verbose:
        print(f"\nRetrieved {len(chunks)} chunks:")
        for c in chunks:
            print(f"  [{c['distance']:.3f}] {c['community']}-{c['section']}")
        print()

    prompt = build_prompt(question, chunks)
    answer = ask_claude(prompt)

    # Collect source URLs
    sources = list(dict.fromkeys(c["url"] for c in chunks))

    return {
        "question": question,
        "answer": answer,
        "sources": sources,
        "chunks_used": len(chunks),
    }


def run_batch(input_csv, output_csv):
    """Run batch of questions from CSV."""
    collection = get_collection()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(input_csv) as f:
        reader = csv.DictReader(f)
        questions = list(reader)

    print(f"Processing {len(questions)} questions...\n")

    results = []
    for i, row in enumerate(questions, 1):
        question = row.get("Question") or row.get("question", "")
        if not question.strip():
            continue

        print(f"[{i}/{len(questions)}] {question[:60]}...")
        result = ask(question, collection)
        results.append({
            "id": row.get("id", i),
            "question": question,
            "ai_answer": result["answer"],
            "sources": " | ".join(result["sources"][:3]),
            "timestamp": timestamp,
        })

    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "question", "ai_answer", "sources", "timestamp"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nDone. {len(results)} answers written to {output_csv}")


def run_interactive(collection):
    """Interactive Q&A loop."""
    print("Calgary Community Q&A (type 'quit' to exit)\n")

    while True:
        try:
            question = input("Ask: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not question or question.lower() in ("quit", "exit", "q"):
            break

        result = ask(question, collection, verbose=True)
        print(f"\n{result['answer']}\n")
        print(f"Sources: {', '.join(result['sources'][:3])}\n")
        print("-" * 60)


def main():
    parser = argparse.ArgumentParser(description="Calgary Community Q&A Bot")
    parser.add_argument("question", nargs="?", help="Question to ask")
    parser.add_argument("--batch", help="Input CSV with questions")
    parser.add_argument("--output", default="answers.csv", help="Output CSV for batch mode")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show retrieval details")
    args = parser.parse_args()

    if args.batch:
        run_batch(args.batch, args.output)
    elif args.interactive:
        collection = get_collection()
        run_interactive(collection)
    elif args.question:
        result = ask(args.question, verbose=args.verbose)
        print(result["answer"])
        if args.verbose:
            print(f"\nSources: {', '.join(result['sources'][:3])}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
