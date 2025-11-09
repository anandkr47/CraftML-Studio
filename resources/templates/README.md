# Training Templates

Pre-configured templates for common use cases. These templates provide optimized settings for specific scenarios.

## Available Templates

### Chatbot Training (`chatbot-config.json`)

**Purpose:** Build a conversational AI chatbot

**Optimized for:**
- Natural conversation flow
- Context awareness
- Personality consistency
- Quick responses

**Recommended model:** Llama-2-7b-chat or Mistral-7B

**Dataset format:** Conversation (multi-turn dialogues)

**Key settings:**
- Higher LoRA rank for better conversation quality
- Moderate learning rate for stable training
- Gradient accumulation for effective batch size

### Q&A System (`qa-system-config.json`)

**Purpose:** Build a question-answering system

**Optimized for:**
- Accurate information retrieval
- Detailed explanations
- Factual consistency
- Domain expertise

**Recommended model:** Mistral-7B or Llama-2-13b

**Dataset format:** Instruction (question-answer pairs)

**Key settings:**
- Higher rank for complex reasoning
- Lower learning rate for precision
- Longer context window

## Using Templates

### In the UI

1. Navigate to Training Console
2. Click "Load Template"
3. Select a template
4. Adjust if needed
5. Start training

### Via API

```python
import json
from apps.backend.api import train

# Load template
with open('resources/templates/chatbot-config.json') as f:
    config = json.load(f)

# Customize
config['model']['base_model'] = 'your-preferred-model'
config['dataset']['path'] = 'path/to/your/dataset.jsonl'

# Start training
response = train.start_train(params=config)
```

### Programmatically

```python
from core.ml.training import LoRATrainer

# Load template config
with open('resources/templates/chatbot-config.json') as f:
    template = json.load(f)

# Initialize trainer
trainer = LoRATrainer(config=template)

# Train
trainer.load_model(template['model']['base_model'])
trainer.apply_lora(**template['lora'])
trainer.train(dataset, **template['training'])
```

## Creating Custom Templates

### Template Structure

```json
{
  "name": "Template Name",
  "description": "What this template is for",
  "model": {
    "base_model": "huggingface/model-name",
    "use_4bit": true
  },
  "lora": {
    "r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    "target_modules": ["q_proj", "v_proj"]
  },
  "training": {
    "num_epochs": 3,
    "batch_size": 4,
    "learning_rate": 2e-4
  },
  "dataset": {
    "format": "instruction",
    "max_length": 512
  },
  "deployment": {
    "quantize_after_training": true,
    "deploy_locally": true
  }
}
```

### Parameter Guidelines

**LoRA Rank (r):**
- 8: Fast training, lower quality
- 16: Balanced (recommended)
- 32: Higher quality, slower
- 64: Maximum quality, much slower

**Learning Rate:**
- 1e-5: Very conservative
- 2e-4: Recommended for most cases
- 5e-4: Aggressive (small datasets)

**Batch Size:**
- Depends on GPU memory
- Use gradient_accumulation_steps to simulate larger batches

**Epochs:**
- Small dataset (< 1000): 5-10
- Medium dataset (1000-10000): 3-5
- Large dataset (10000+): 1-3

## Best Practices

1. **Start with a template:** Don't configure from scratch
2. **Test on small data first:** Validate before full training
3. **Monitor loss curves:** Should decrease smoothly
4. **Save checkpoints:** Regular saves prevent data loss
5. **Document changes:** Keep track of what works

## Troubleshooting

### Training too slow
- Increase batch_size
- Reduce lora rank
- Enable gradient_checkpointing

### Out of memory
- Reduce batch_size
- Enable 4-bit quantization
- Use gradient_accumulation_steps
- Reduce max_length

### Poor quality results
- Increase lora rank
- Train for more epochs
- Lower learning rate
- Improve dataset quality

### Model not learning (loss not decreasing)
- Increase learning rate
- Check dataset format
- Verify data quality
- Try different base model

