# RouterSense Project Task

This repository contains a complete two-part workflow for evaluating AI companion platforms and automating controlled browser-based interactions with one selected platform.

For clarity in this repository:

- **evaluation** refers to the app evaluation pipeline
- **automation** refers to the browser automation workflow

The folder names on disk remain:

- `q1_app_evaluation`
- `q2_automation_poc`

Those folder names are kept for compatibility with the existing submission structure, but throughout this README they are described as **evaluation** and **automation**.

## Repository Overview

This project starts with raw metadata from the iOS App Store and Google Play Store, processes that data into a structured evaluation dataset, and then uses the evaluated results to select one suitable platform for live browser automation.

The repository is designed to be reproducible, modular, and auditable.

It includes:

- source code for the evaluation pipeline
- source code for the automation workflow
- raw input JSON files
- generated CSV, JSON, and log outputs
- submission helper scripts for end-to-end runs

## Project Structure

```text
trex/
├── app_store_apps_details.json
├── google_play_apps_details.json
├── q1_app_evaluation/
│   ├── data/
│   ├── outputs/
│   ├── src/
│   ├── requirements.txt
│   ├── run_q1_evaluation.py
│   └── run_submission.sh
├── q2_automation_poc/
│   ├── outputs/
│   ├── src/
│   ├── config.env
│   ├── config.example.env
│   ├── input_messages.txt
│   ├── requirements.txt
│   ├── run_poc.py
│   └── run_submission.sh
└── run_full_submission.sh
```

## Part 1: evaluation

The **evaluation** part builds a structured dataset of candidate AI companion apps from raw iOS and Android metadata.

It:

- loads both source JSON files
- validates the data structure under the top-level `results` key
- preserves every original source field
- combines iOS and Android records into one unified output schema
- classifies each app as `companion`, `general_purpose`, `mixed`, or `other`
- derives fields such as web accessibility, login hints, age verification, subscription behavior, languages supported, evidence notes, evidence URLs, confidence, and manual-review status
- optionally performs bounded public web verification using official public pages
- writes a final CSV plus audit and evidence artifacts

### evaluation source modules

- `load_data.py`
  - loads the raw JSON files and validates structure
- `normalize.py`
  - preserves original fields and aligns iOS and Android rows into a common schema
- `classify.py`
  - applies evidence-based classification rules for app type
- `evaluate_fields.py`
  - derives metadata-based evaluation fields
- `web_check.py`
  - performs optional public website checks using `requests` and `BeautifulSoup`
- `evidence.py`
  - creates structured evidence records for important fields
- `audit.py`
  - generates the audit report, manual-review file, and QC summary
- `utils.py`
  - shared helpers for text cleaning, URL normalization, serialization, and parsing

### evaluation outputs

The main outputs are written to:

- `q1_app_evaluation/outputs/ai_companion_app_evaluation.csv`
- `q1_app_evaluation/outputs/evidence_log.csv`
- `q1_app_evaluation/outputs/manual_review_candidates.csv`
- `q1_app_evaluation/outputs/evaluation_audit.md`
- `q1_app_evaluation/outputs/qc_summary.json`
- `q1_app_evaluation/outputs/run_log.txt`

### Important note about empty columns

Some columns in the final CSV will appear empty for many rows. This is expected.

The reason is that the iOS and Android source files have different schemas, and the evaluation pipeline preserves all original fields from both sources. As a result:

- Android-specific fields are blank for iOS rows
- iOS-specific fields are blank for Android rows
- some fields are sparse or empty in the original source data itself

This is a consequence of source-data differences, not a broken export.

## Part 2: automation

The **automation** part uses the evaluated dataset to select one suitable platform and then runs a browser automation workflow against that platform.

It:

- reads the evaluated CSV from the evaluation stage
- ranks candidate platforms
- selects a suitable browser-accessible target
- launches a browser using Playwright
- opens the selected character/chat page
- handles visible public onboarding steps when needed
- sends predefined test messages
- waits for responses to render
- captures the visible response text
- writes transcripts and supporting artifacts

The selected platform in the current implementation is:

- `Talkie: Creative AI Community`

### automation source modules

- `config.py`
  - loads runtime configuration from environment variables or a local config file
- `message_loader.py`
  - loads the predefined message set
- `platform_selector.py`
  - ranks and selects a candidate platform from the evaluation output
- `browser_runner.py`
  - launches and manages Playwright browser sessions
- `platform_adapter_base.py`
  - defines the shared adapter interface
- `selected_platform_adapter.py`
  - contains platform-specific browser interaction logic
- `transcript_writer.py`
  - saves transcript outputs to CSV and JSON
- `recorder.py`
  - manages traces, video, and artifact paths
- `q1_update_checker.py`
  - compares live automation findings against the evaluation results
- `utils.py`
  - shared logging, file-writing, and path helpers

### automation outputs

The main outputs are written to:

- `q2_automation_poc/outputs/chat_transcript.csv`
- `q2_automation_poc/outputs/chat_transcript.json`
- `q2_automation_poc/outputs/platform_selection_table.csv`
- `q2_automation_poc/outputs/run_log.txt`
- `q2_automation_poc/outputs/run_summary.json`
- `q2_automation_poc/outputs/q2_automation_poc_report.md`
- `q2_automation_poc/outputs/q1_updates_from_q2.md`
- `q2_automation_poc/outputs/screenshots/`
- `q2_automation_poc/outputs/traces/`
- `q2_automation_poc/outputs/video/`

## Technology Used

### evaluation

- Python
- pandas
- requests
- beautifulsoup4
- python-dateutil

### automation

- Python
- Playwright
- python-dotenv
- pandas

## Ethical and Technical Boundaries

This repository is designed around normal, user-facing interaction only.

It does **not**:

- bypass CAPTCHA
- bypass paywalls
- bypass login protections
- bypass age verification systems
- use stolen credentials
- scrape private user data
- reverse-engineer private APIs

If a platform requires login, the intended workflow is to use only a user-owned test account supplied through environment variables or a local config file. If the login flow triggers barriers such as CAPTCHA or phone verification that should not be bypassed, the platform should be rejected for the automation stage.

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/DipeshK47/RouterSense_Project-Task.git
cd RouterSense_Project-Task
```

### 2. evaluation setup

```bash
cd q1_app_evaluation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. automation setup

```bash
cd ../q2_automation_poc
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Run Commands

### Run evaluation

From the repository root:

```bash
cd q1_app_evaluation
bash run_submission.sh
```

Direct command:

```bash
cd q1_app_evaluation
python run_q1_evaluation.py --max-web-checks 100 --web-timeout 10
```

Metadata-first run without web checks:

```bash
cd q1_app_evaluation
python run_q1_evaluation.py --skip-web
```

### Run automation

From the repository root:

```bash
cd q2_automation_poc
bash run_submission.sh
```

Direct command:

```bash
cd q2_automation_poc
python run_poc.py --env-file config.env --headed --skip-login --max-messages 10
```

Headless run:

```bash
cd q2_automation_poc
python run_poc.py --env-file config.env --headless --skip-login --max-messages 10
```

### Run both parts end to end

From the repository root:

```bash
bash run_full_submission.sh
```

## Expected Outputs

After running both parts, the key outputs should include:

### evaluation

- `q1_app_evaluation/outputs/ai_companion_app_evaluation.csv`
- `q1_app_evaluation/outputs/evidence_log.csv`
- `q1_app_evaluation/outputs/manual_review_candidates.csv`
- `q1_app_evaluation/outputs/qc_summary.json`

### automation

- `q2_automation_poc/outputs/chat_transcript.csv`
- `q2_automation_poc/outputs/chat_transcript.json`
- `q2_automation_poc/outputs/run_log.txt`
- `q2_automation_poc/outputs/run_summary.json`
- `q2_automation_poc/outputs/platform_selection_table.csv`

## Notes

- The repository uses the original submission folder names on disk for compatibility.
- In documentation and presentation language, those two parts are referred to as **evaluation** and **automation**.
- If you want to include Markdown files in version control, you will need to adjust the current `.gitignore`, which is configured to ignore `*.md`.
