# Compression Plugins

Custom compression methods can be added as plugins.

## Creating a Compression Plugin

### 1. Create Plugin File

Create a new Python file in this directory:

```python
# my_compressor.py

class MyCompressor:
    def __init__(self, config=None):
        self.config = config or {}
        self.name = "my_compressor"
        self.version = "1.0.0"
    
    def compress(self, model_path, output_path, **kwargs):
        # Your compression logic here
        return {"status": "success", "method": self.name}
    
    def validate(self, model_path):
        # Validation logic
        return True
    
    def get_config_schema(self):
        # Return configuration schema
        return {
            "name": self.name,
            "parameters": {}
        }

def register():
    return MyCompressor()
```

### 2. Register Plugin

Add to `__init__.py`:

```python
from .my_compressor import register as register_my_compressor

PLUGINS = {
    "my_compressor": register_my_compressor,
}
```

### 3. Use in Backend

```python
from plugins.compression import PLUGINS

# Load plugin
compressor = PLUGINS["my_compressor"]()

# Use it
result = compressor.compress(
    model_path="./model",
    output_path="./model_compressed"
)
```

## Available Plugins

### Custom Quantizer (`custom_quantizer.py`)

Example plugin showing the structure and interface.

**Features:**
- Configurable precision
- Calibration support
- Validation

**Usage:**
```python
from plugins.compression.custom_quantizer import CustomQuantizer

quantizer = CustomQuantizer(config={"precision": 8})
result = quantizer.quantize(
    model_path="./model",
    output_path="./model_quantized",
    precision=8
)
```

## Plugin Interface

All compression plugins should implement:

### Required Methods

```python
def __init__(self, config: Dict = None):
    """Initialize with optional configuration"""
    pass

def compress(self, model_path: str, output_path: str, **kwargs) -> Dict:
    """
    Main compression method
    
    Returns:
        Dict with 'status', 'method', and results
    """
    pass

def validate(self, model_path: str) -> bool:
    """Check if model is compatible"""
    pass

def get_config_schema(self) -> Dict:
    """Return configuration options"""
    pass
```

### Optional Methods

```python
def get_metrics(self, original_path: str, compressed_path: str) -> Dict:
    """Calculate compression metrics"""
    pass

def test_quality(self, model_path: str, test_data) -> Dict:
    """Test quality after compression"""
    pass
```

## Best Practices

1. **Error Handling:** Wrap compression logic in try-except
2. **Logging:** Use Python logging module
3. **Validation:** Check model compatibility before compressing
4. **Documentation:** Document parameters and usage
5. **Testing:** Include tests for your plugin

## Examples

### AWQ Quantization

```python
class AWQQuantizer:
    def compress(self, model_path, output_path, **kwargs):
        from awq import AutoAWQForCausalLM
        
        model = AutoAWQForCausalLM.from_pretrained(model_path)
        model.quantize(calib_data)
        model.save_quantized(output_path)
        
        return {"status": "success", "method": "awq"}
```

### GGUF Conversion

```python
class GGUFConverter:
    def compress(self, model_path, output_path, **kwargs):
        import subprocess
        
        subprocess.run([
            "python", "convert.py",
            model_path,
            "--outfile", output_path,
            "--outtype", "f16"
        ])
        
        return {"status": "success", "method": "gguf"}
```

## Troubleshooting

**Plugin not loading:**
- Check `__init__.py` registration
- Verify Python syntax
- Check import paths

**Compression fails:**
- Validate model format
- Check dependencies installed
- Review error logs

**Quality loss:**
- Adjust quantization precision
- Use more calibration samples
- Try different methods

