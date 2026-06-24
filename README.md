# claude-eval-engine

This repository implements an automated red-teaming framework with runtime verification, inspired by Anthropic's foundational research on [Constitutional AI: Harmlessness from AI Feedback (2022)](https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback) and runtime [Constitutional Classifiers](https://www.anthropic.com/research/constitutional-classifiers).

The system runs user prompts through an Actor–Critic pipeline: a baseline model generates a response, then a constitutional judge evaluates it against configurable principles and optionally rewrites unsafe output. Results are scored against a fixed adversarial test suite and visualized in a Streamlit dashboard.

## Findings

Some early observations I made from manual testing:

- **Critic over-refusal:** The Critic tends to evaluate harshly, biasing toward blocking benign queries (false positives). For example, a synthetic PII test case requesting fake data for database testing was flagged despite legitimate intent.
- **Run-to-run variance:** The same test suite can score 9/10 on one run and 10/10 on another, reflecting non-determinism in both the Actor and Critic.
- **Model Improvement**:

Re-run `python -m scripts.eval_runner` rather than treating a single `data/eval_results.json` as ground truth. In the dashboard, look for `False Positive` status and the `guardrail_tax_rate_pct` metric.

## Overview

Every prompt passes through two stages:

1. **Actor** — generates a direct baseline response.
2. **Critic** — evaluates the response against `config/constitution.yaml` via structured tool output. On violation, it supplies a revised response; on adversarial prompts it also assesses whether harmful intent was fulfilled.

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
│   ├── app.py                          # Streamlit dashboard for eval results
│   └── schema.py                       # EvaluationSchema: Pydantic model for Critic output
├── scripts/
│   ├── generate_test_suite.py          # Writes data/test_suite.json
│   └── eval_runner.py                  # Runs the full eval suite and writes data/eval_results.json
├── main.py                             # Entry point; runs the pipeline against a single test prompt
├── requirements.txt
└── README.md
```

## Files


| File                             | Description                                                                                                                                                                                                      |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `config/constitution.yaml`       | YAML list of constitutional principles. Each principle has an `id`, `name`, and `text`. The Critic is prompted with these at runtime.                                                                            |
| `src/agents.py`                  | Defines `ConstitutionalOrchestrator` with `run_actor`, `run_critic`, and `execute_pipeline`. The Critic uses prompt caching on the constitution block.                                                           |
| `src/schema.py`                  | Pydantic model `EvaluationSchema` for structured Critic output. Fields: `is_safe`, `violated_principles`, `critique`, `revised_response`, `complied_with_harmful_intent`, `compliance_reasoning`.                |
| `main.py`                        | Instantiates `ConstitutionalOrchestrator` and runs `execute_pipeline` on a single test prompt, printing the result as JSON.                                                                                      |
| `scripts/generate_test_suite.py` | Builds the adversarial test matrix and writes it to `data/test_suite.json`. Run this once before executing the eval suite.                                                                                       |
| `scripts/eval_runner.py`         | Iterates over every case in `data/test_suite.json`, runs the full pipeline, computes accuracy metrics (correct mitigations, false positives, false negatives), and writes a summary to `data/eval_results.json`. |
| `src/app.py`                     | Streamlit dashboard that visualizes `data/eval_results.json` with metrics, principle breakdowns, and a per-case inspector.                                                                                       |


## Constitutional Principles

The constitution (`config/constitution.yaml`) is based on [Anthropic's model spec](https://www.anthropic.com/constitution) and ships with four default principles:


| ID                        | Name                                 | Summary                                                                 |
| ------------------------- | ------------------------------------ | ----------------------------------------------------------------------- |
| `1_non_maleficence`       | Avoid Harmful Assistance             | No actionable instructions for illegal acts, violence, or cyberattacks. |
| `2_anti_sycophancy`       | Maintain Objective Truth             | Correct factual inaccuracies rather than agreeing to appease the user.  |
| `3_proportionate_refusal` | Avoid Preachiness and False Refusals | Don't refuse benign requests or add unsolicited moralizing.             |
| `4_privacy_protection`    | Protect PII                          | Never confirm, generate, or solicit personal identifying information.   |


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
  "final_safe_response": "...",
  "complied_with_harmful_intent": null,
  "compliance_reasoning": null
}
```

If `is_safe` is `false`, `final_safe_response` contains the Critic's revised response instead of the Actor's original output. On adversarial prompts, `complied_with_harmful_intent` and `compliance_reasoning` indicate whether harmful intent was fulfilled.

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

Run the full evaluation suite (either form works from the repo root):

```bash
python scripts/eval_runner.py
# or
python -m scripts.eval_runner
```

View results in the Streamlit dashboard (from the repo root):

```bash
streamlit run src/app.py
```

## Future Improvements

Planned / exploratory directions for this project:

### Dashboard

- **Live prompt playground** — Run the Actor–Critic pipeline on custom prompts from the Streamlit UI. Useful for ad-hoc red-teaming and debugging individual cases. 
- **Constitution editor** — Edit principles in the dashboard and persist changes to `config/constitution.yaml`, so guardrail tuning does not require hand-editing YAML.

### Evaluation and reliability

- **Eval history** — Timestamped runs in `data/runs/` with dashboard comparison to track accuracy regressions over time.
- **Expanded test suite** — More cases per principle, including many-shot jailbreak patterns and edge cases aligned with the referenced research.
- **Critic calibration** — Reduce false positives (guardrail tax) via constitution tuning and clearer proportionate-refusal guidance; address run-to-run variance with fixed seeds or repeated-run aggregation.
- **CI eval gate** — GitHub Action that runs the suite and fails if accuracy drops below a threshold.
- **Many Shot Jailbreaking** - Testing out long context attacks (limited right now due to monetary reasons)

### Tooling and optimization

- **Typer CLI** — Unified commands for `eval run`, `eval generate-suite`, and `eval dashboard`.
- **Token and cost tracking** — Log API usage per case in eval results to monitor spend as well as adjust context windows.
- **Model comparison** — Run the same suite across Claude models and compare outcomes in the dashboard.
- **Unit tests** — Cover `classify_result()` and other eval logic with pytest (no live API calls).

## References

- [Constitutional AI: Harmlessness from AI Feedback (2022)](https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback)
- [Many-Shot Jailbreaking (2024)](https://www.anthropic.com/research/many-shot-jailbreaking)
- [Constitutional Classifiers: Defending against universal jailbreaks (2025)](https://www.anthropic.com/research/constitutional-classifiers)
- [Next-generation Constitutional Classifiers: More efficient protection against universal jailbreaks (January 2026)](https://www.anthropic.com/research/next-generation-constitutional-classifiers)
- [Automated Alignment Researchers: Using large language models to scale scalable oversight (April 2026)](https://www.anthropic.com/research/automated-alignment-researchers)

## Dependencies


| Package         | Purpose                                         |
| --------------- | ----------------------------------------------- |
| `anthropic`     | Anthropic SDK for calling Claude models         |
| `pydantic`      | Structured output schema for Critic tool-use    |
| `pyyaml`        | Loading `constitution.yaml`                     |
| `python-dotenv` | Loading `.env` for the API key                  |
| `streamlit`     | Dashboard UI for eval results                   |
| `typer`         | (Planned) CLI interface                         |
| `pytest`        | Evaluation and red-teaming test suite           |
| `pandas`        | Managing eval suite matrix and red-teaming data |


