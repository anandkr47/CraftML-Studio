# Dataset Templates

This directory contains example dataset formats for training language models.

---

## 🚀 Quick Start Datasets

### **NEW: Ready-to-Use Training Datasets**

We've created production-ready sample datasets optimized for fast training:

#### 1. **ultra-fast-sample.jsonl** (20 examples)
- ⚡ **Training time:** 2-5 minutes
- 🎯 **Best for:** Testing your training pipeline
- 📝 **Content:** Basic Python programming concepts
- 💡 **Use case:** Quick validation and proof-of-concept

#### 2. **quick-train-sample.jsonl** (50 examples)
- ⚡ **Training time:** 5-15 minutes
- 🎯 **Best for:** Fast training with good quality
- 📝 **Content:** Comprehensive Python programming assistance
- 💡 **Use case:** Small-scale fine-tuning and experimentation

> **👉 See [QUICK_START_TRAINING.md](QUICK_START_TRAINING.md) for complete training guide!**

---

## Available Templates

### Instruction Format (`instruction-template.jsonl`)

Used for instruction-following models. Each line contains:

```json
{
  "instruction": "The task to perform",
  "input": "Optional context or input",
  "output": "Expected response"
}
```

**Best for:**
- Question answering
- Task completion
- General instruction following

**Example use cases:**
- Customer support chatbots
- Task assistants
- Educational tutors

### Conversation Format (`conversation-template.jsonl`)

Used for multi-turn dialogue. Each line contains:

```json
{
  "messages": [
    {"role": "user", "content": "User message"},
    {"role": "assistant", "content": "Assistant response"}
  ]
}
```

**Best for:**
- Chat applications
- Conversational AI
- Multi-turn interactions

## Creating Your Own Dataset

### 1. Choose a Format

- **Instruction format:** For single-turn Q&A or task completion
- **Conversation format:** For multi-turn dialogues
- **Text format:** For language modeling (simple text file, one document per line)

### 2. Collect Data

You can create datasets by:
- Manual curation
- Using the built-in web crawler
- Converting existing datasets
- Scraping structured data

### 3. Clean and Format

Use the CraftML Studio data processing pipeline:

```python
from core.data.cleaner import clean_dataset
from core.data.formatter import format_dataset

# Clean your data
cleaned = clean_dataset(
    texts=raw_texts,
    remove_duplicates=True,
    language="en"
)

# Format for training
format_dataset(
    data=cleaned,
    output_path="./my_dataset.jsonl",
    format_type="instruction"
)
```

### 4. Validate

Before training, ensure:
- No duplicate samples
- Consistent formatting
- Appropriate length (not too short or long)
- Balanced distribution of topics
- Quality responses

## Dataset Quality Guidelines

### Good Examples

✅ Clear, specific instructions
✅ Contextual and detailed outputs
✅ Diverse topics and scenarios
✅ Natural language patterns
✅ Proper grammar and formatting

### Bad Examples

❌ Vague or ambiguous instructions
❌ Generic or low-quality outputs
❌ Repetitive content
❌ Incorrect information
❌ Poor grammar or formatting

## Recommended Dataset Sizes

| Model Size | Min Samples | Recommended | Max Benefit |
|------------|-------------|-------------|-------------|
| 2-3B       | 100         | 500-1000    | 5000        |
| 7B         | 500         | 1000-5000   | 20000       |
| 13B+       | 1000        | 5000-10000  | 50000+      |

**Note:** Quality > Quantity. 500 high-quality examples often outperform 5000 low-quality ones.

## Privacy and Ethics

When creating datasets:

1. **Respect copyright:** Don't use copyrighted content without permission
2. **Protect privacy:** Remove personal information (names, emails, addresses)
3. **Avoid bias:** Ensure diverse and balanced representation
4. **Check quality:** Review samples manually
5. **Document sources:** Keep track of where data came from

## Format Conversion

CraftML Studio supports conversion between formats:

### Instruction → Conversation

```python
from core.data.formatter import DatasetFormatter

formatter = DatasetFormatter()
formatter.to_conversation_format(
    data=instruction_data,
    user_key="instruction",
    assistant_key="output"
)
```

### Crawled Data → Any Format

```python
formatter.crawled_to_training_format(
    crawled_pages=pages,
    format_type="instruction"  # or "conversation", "text"
)
```

## Storage Location

By default, datasets are stored in:
- `resources/datasets/` - Template and example datasets
- `apps/backend/datasets/` - User-generated datasets

You can change this in the settings (`core/config/settings.py`).

