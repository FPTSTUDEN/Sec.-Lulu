# Installation & Running Guide

## Prerequisites

- Python 3.8+
- Ollama (for AI features)

## Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install & Run Ollama

Download from [ollama.ai](https://ollama.ai), then run:
<!-- ollama serve -->

```bash
ollama pull qwen2.5:7b # You can change OllamaClient(model="your_preferred_model") in lib/localai.py and pull another model if you want
# Advanced: python build_modelfile.py --mode SparkleNotes --output Modelfile
ollama create xiaoxi -f Modelfile
```

**Advanced:** To combine all mode fragments into one model file:

```bash
python build_modelfile.py --all --output Modelfile
ollama create xiaoxi -f Modelfile
```

Or create the Ollama model in one step:

```bash
python build_modelfile.py --all --output Modelfile --create
```

<!-- Keep this running in a separate terminal. -->

## Running the App

### Standard Mode

```bash
python main.py
```

### Mock Database Mode (testing)

```bash
python main.py --use-mock
```

### Custom Database Path

```bash
python main.py --db-path path/to/custom.db
```

## Usage

1. Click **Start** to enable clipboard monitoring
2. Copy Chinese text to clipboard for instant explanations
3. Click **Open Main App** to review vocabulary

## Testing

### Modelfile changes

```bash
ollama rm xiaoxi ;; python build_modelfile.py --all --output Modelfile ;; ollama create xiaoxi -f Modelfile ;; ollama run xiaoxi
```
