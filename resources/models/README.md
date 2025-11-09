# Model Configurations

This directory contains pre-configured settings for popular language models.

## Available Models

### Llama 2 7B (`llama2-7b-config.json`)
- **Parameters:** 7 billion
- **Best for:** General-purpose chat and instruction following
- **GPU Memory:** 8GB+ recommended
- **Use 4-bit:** Yes (reduces memory to ~6GB)

### Mistral 7B (`mistral-7b-config.json`)
- **Parameters:** 7 billion
- **Best for:** High performance with efficiency
- **GPU Memory:** 8GB+ recommended
- **Use 4-bit:** Yes

### Phi-2 (`phi-2-config.json`)
- **Parameters:** 2.7 billion
- **Best for:** Limited GPU resources
- **GPU Memory:** 4GB+ recommended
- **Use 4-bit:** Optional

## Configuration Structure

Each configuration file contains:

```json
{
  "model_name": "huggingface/model-name",
  "display_name": "Model Display Name",
  "description": "Model description",
  "recommended_config": {
    "lora": {
      "r": 16,
      "lora_alpha": 32,
      "lora_dropout": 0.05,
      "target_modules": ["q_proj", "v_proj"]
    },
    "training": {
      "num_epochs": 3,
      "batch_size": 4,
      "learning_rate": 2e-4,
      "use_4bit": true
    }
  },
  "requirements": {
    "min_gpu_memory_gb": 8,
    "min_ram_gb": 16
  }
}
```

## Adding Custom Models

To add a new model configuration:

1. Create a new JSON file in this directory
2. Follow the structure above
3. Adjust LoRA and training parameters based on model architecture
4. Test with your hardware setup

## LoRA Parameters Guide

- **r (rank):** Controls adapter size. Higher = more parameters
  - Small models (< 3B): 8-16
  - Medium models (7B): 16-32
  - Large models (13B+): 32-64

- **lora_alpha:** Usually 2x the rank value

- **lora_dropout:** Prevents overfitting
  - Start with 0.05
  - Increase to 0.1 if overfitting occurs

- **target_modules:** Which layers to apply LoRA
  - Minimum: ["q_proj", "v_proj"]
  - Recommended: Add "k_proj", "o_proj"
  - Maximum: Include all linear layers

## Training Parameters Guide

- **num_epochs:** Number of training passes
  - Small datasets: 3-5
  - Large datasets: 1-2

- **batch_size:** Samples per training step
  - Limited GPU: 1-2
  - 8GB GPU: 4
  - 16GB+ GPU: 8-16

- **learning_rate:** Step size for optimization
  - LoRA: 2e-4 to 5e-4
  - Full fine-tune: 1e-5 to 5e-5

- **use_4bit:** Enable 4-bit quantization
  - Reduces memory by ~4x
  - Minimal impact on quality
  - Highly recommended for GPUs < 16GB

