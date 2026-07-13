# 🗣️ Communication Assessment Agent

A Streamlit web app that assesses written and spoken communication skills, gives actionable feedback, and tracks improvement over time. Text or audio is scored on **grammar, clarity, vocabulary, and tone**, scoring adapts to context (Job Interview, Casual Chat, Presentation, Email), and every submission is logged to a local database so you can see your progress on a dashboard.

## Features

- **✍️ Written Assessment** — paste or type text and get scored on grammar, clarity, vocabulary, and tone, plus the top 3 action items to improve.
- **🎙️ Spoken Assessment** — upload a `.wav` recording; the app transcribes it, scores it the same way, and also reports filler-word count and words-per-minute (WPM). It shows a "filler-free" score so you can see how much fillers are dragging your score down.
- **🎯 Context-Aware Scoring** — choose Job Interview, Casual Chat, Presentation, or Email, and tone scoring adjusts accordingly (e.g. casual language is only penalized in formal contexts).
- **📈 History / Dashboard** — every assessment is saved to a local SQLite database, with a score trend chart, written vs. spoken averages, and an auto-generated insight comparing the two.

## How Scoring Works

| Category | Method |
|---|---|
| Grammar | [LanguageTool](https://github.com/jxmorris12/language_tool_python) checks for spelling/grammar/style issues; score starts at 100 and deducts 5 points per issue found. |
| Clarity | [Flesch Reading Ease](https://en.wikipedia.org/wiki/Flesch%E2%80%93Kincaid_readability_tests) score via `textstat`. |
| Vocabulary | Based on average sentence length, with an ideal range of 10–20 words. |
| Tone | Rule-based: casual words (e.g. "gonna", "kinda") are penalized in formal contexts; excessive passive voice is penalized in casual contexts. |
| Overall | Average of the four sub-scores. |

Spoken submissions are also checked for filler words (um, uh, like, you know, actually, basically) and words-per-minute, calculated from the audio's duration.

## Tech Stack

- [Streamlit](https://streamlit.io/) — web UI
- [SQLite](https://www.sqlite.org/) — local storage for submission history
- [language-tool-python](https://pypi.org/project/language-tool-python/) — grammar checking
- [textstat](https://pypi.org/project/textstat/) — readability/clarity scoring
- [SpeechRecognition](https://pypi.org/project/SpeechRecognition/) — audio transcription (via Google's free speech API)
- Pandas — data handling for the history dashboard

## Getting Started

### Prerequisites

- Python 3.9+
- Java Runtime Environment (JRE) — required by `language-tool-python`, which runs LanguageTool locally

### Installation

```bash
git clone https://github.com/Dharhiniperiyasamy/communication-assessment-agent.git
cd communication-assessment-agent
pip install -r requirements.txt
```

> **Note:** `language-tool-python` will download the LanguageTool Java package on first run, so the first grammar check may take a bit longer while it sets up.

### Running the App

```bash
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`) in your browser.

## Usage

1. Pick a **context** from the dropdown (Job Interview, Casual Chat, Presentation, or Email) — this tunes the tone scoring.
2. Go to the **Written Assessment** tab to paste text, or the **Spoken Assessment** tab to upload a `.wav` file.
3. Click **Assess** to get your overall score, sub-scores, and top 3 action items.
4. Check the **History / Dashboard** tab to track your score trend over time and compare written vs. spoken performance.

## Project Structure

```
communication-assessment-agent/
├── app.py              # Main Streamlit application
├── app_backup.py        # Backup/previous version of the app
├── requirements.txt     # Python dependencies
├── packages.txt          # System-level packages (e.g. for deployment)
└── .devcontainer/        # Dev container configuration
```

## Data & Privacy

All assessments (text, scores, and transcripts) are stored locally in a SQLite file (`assessments.db`) created in the project directory. Nothing is sent anywhere except the audio sent to Google's speech recognition API for transcription during spoken assessments.

## License

No license has been specified yet for this project. Consider adding one (e.g. MIT) if you plan to share or accept contributions.
