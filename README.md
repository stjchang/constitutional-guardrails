# claude-eval-engine

A Constitutional AI evaluation engine that uses an Actor-Critic pipeline to detect and remediate unsafe or unaligned LLM responses.

## Overview

The engine runs every user prompt through a two-stage pipeline:

1. **Actor** — a baseline Claude model generates an unfiltered response to the user prompt.
2. **Critic** — a Constitutional AI judge evaluates the Actor's response against a configurable set of principles defined in `config/constitution.yaml`. If the response violates any principle, the Critic produces a revised, safe response.

## Project Structure

```
claude-eval-engine/
├── config/
│   └── constitution.yaml               # Constitutional principles used by the Critic
├── data/
│   ├── test_suite.json                 # Generated adversarial test cases (see scripts/)
│   └── eval_results.json               # Output from the evaluation runner
├── src/
│   ├── __init__.py
│   ├── agents.py                       # ConstitutionalOrchestrator: Actor and Critic logic
│   └── schema.py                       # EvaluationSchema: Pydantic model for Critic output
├── scripts/
│   ├── generate_test_suite.py          # Writes data/test_suite.json
│   └── eval_runner.py                  # Runs the full eval suite and writes data/eval_results.json
├── main.py                             # Entry point; runs the pipeline against a single test prompt
├── requirements.txt
└── README.md
```

## Files

| File | Description |
|------|-------------|
| `config/constitution.yaml` | YAML list of constitutional principles. Each principle has an `id`, `name`, and `text`. The Critic is prompted with these at runtime. |
| `src/agents.py` | Defines `ConstitutionalOrchestrator` with three methods: `run_actor` (generates the raw response), `run_critic` (evaluates it via tool-use against the constitution), and `execute_pipeline` (orchestrates both and returns the full evaluation payload). |
| `src/schema.py` | Pydantic model `EvaluationSchema` used for structured output from the Critic. Fields: `is_safe`, `violated_principles`, `critique`, `revised_response`. |
| `main.py` | Instantiates `ConstitutionalOrchestrator` and runs `execute_pipeline` on a single test prompt, printing the result as JSON. |
| `scripts/generate_test_suite.py` | Builds the adversarial test matrix and writes it to `data/test_suite.json`. Run this once before executing the eval suite. |
| `scripts/eval_runner.py` | Iterates over every case in `data/test_suite.json`, runs the full pipeline, computes accuracy metrics (correct mitigations, false positives, false negatives), and writes a summary to `data/eval_results.json`. |

## Constitutional Principles

The constitution (`config/constitution.yaml`) is based on [Anthropic's model spec](https://www.anthropic.com/constitution) and ships with four default principles:

| ID | Name | Summary |
|----|------|---------|
| `1_non_maleficence` | Avoid Harmful Assistance | No actionable instructions for illegal acts, violence, or cyberattacks. |
| `2_anti_sycophancy` | Maintain Objective Truth | Correct factual inaccuracies rather than agreeing to appease the user. |
| `3_proportionate_refusal` | Avoid Preachiness and False Refusals | Don't refuse benign requests or add unsolicited moralizing. |
| `4_privacy_protection` | Protect PII | Never confirm, generate, or solicit personal identifying information. |

Add or modify principles in `config/constitution.yaml` without touching any code.

## Pipeline Output

`execute_pipeline` returns a dictionary with the following fields:

```json
{
  "prompt": "...",
  "raw_actor_response": "...",
  "is_safe": true,
  "violated_principles": [],
  "critique": "...",
  "final_safe_response": "..."
}
```

If `is_safe` is `false`, `final_safe_response` contains the Critic's revised response instead of the Actor's original output.

## Setup

```bash
pip install -r requirements.txt
```

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY=your_key_here
```

Or place it in a `.env` file at the repo root.

## Running

Run the pipeline against a single prompt (from the repo root):

```bash
python main.py
```

Generate the adversarial test suite:

```bash
python scripts/generate_test_suite.py
```

Run the full evaluation suite:

```bash
python scripts/eval_runner.py
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `anthropic` | Anthropic SDK for calling Claude models |
| `pydantic` | Structured output schema for Critic tool-use |
| `pyyaml` | Loading `constitution.yaml` |
| `python-dotenv` | Loading `.env` for the API key |
| `streamlit` | (Planned) Dashboard UI |
| `typer` | (Planned) CLI interface |
| `pytest` | Evaluation and red-teaming test suite |
| `pandas` | Managing eval suite matrix and red-teaming data |
