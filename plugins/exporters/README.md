# Model Exporter Plugins

Custom exporters for converting models to different formats.

## Creating an Exporter Plugin

### 1. Create Plugin File

```python
# my_exporter.py

class MyExporter:
    def __init__(self, config=None):
        self.config = config or {}
        self.name = "my_exporter"
        self.output_format = "myformat"
    
    def export(self, model_path, output_path, **kwargs):
        # Export logic here
        return {"status": "success", "format": self.output_format}
    
    def validate_export(self, export_path):
        # Validation logic
        return True

def register():
    return MyExporter()
```

### 2. Register Plugin

Add to `__init__.py`:

```python
from .my_exporter import register as register_my_exporter

PLUGINS = {
    "my_exporter": register_my_exporter,
}
```

### 3. Use in Backend

```python
from plugins.exporters import PLUGINS

# Load plugin
exporter = PLUGINS["my_exporter"]()

# Export model
result = exporter.export(
    model_path="./model",
    output_path="./model.myformat"
)
```

## Available Plugins

### ONNX Exporter (`onnx_exporter.py`)

Export models to ONNX format for deployment.

**Features:**
- Convert PyTorch/HuggingFace models to ONNX
- Validate exported models
- Optimize for inference
- FP16 support

**Usage:**
```python
from plugins.exporters.onnx_exporter import ONNXExporter

exporter = ONNXExporter()
result = exporter.export(
    model_path="./model",
    output_path="./model.onnx",
    opset_version=14,
    optimize=True
)
```

## Plugin Interface

All exporter plugins should implement:

### Required Methods

```python
def __init__(self, config: Dict = None):
    """Initialize with optional configuration"""
    pass

def export(self, model_path: str, output_path: str, **kwargs) -> Dict:
    """
    Export model to target format
    
    Returns:
        Dict with 'status', 'format', and export details
    """
    pass
```

### Optional Methods

```python
def validate_export(self, export_path: str) -> bool:
    """Validate exported model"""
    pass

def optimize(self, export_path: str, output_path: str) -> str:
    """Optimize exported model"""
    pass

def get_config_schema(self) -> Dict:
    """Get configuration options"""
    pass
```

## Supported Export Formats

### ONNX
- **Use case:** Cross-platform inference
- **Pros:** Wide compatibility, optimized runtime
- **Cons:** Limited operator support

### TensorRT
- **Use case:** NVIDIA GPU inference
- **Pros:** Maximum performance on NVIDIA hardware
- **Cons:** NVIDIA-only, complex setup

### CoreML
- **Use case:** Apple device deployment
- **Pros:** Native iOS/macOS support
- **Cons:** Apple ecosystem only

### TensorFlow Lite
- **Use case:** Mobile/edge devices
- **Pros:** Small size, fast on mobile
- **Cons:** Limited model support

## Examples

### TensorRT Export

```python
class TensorRTExporter:
    def export(self, model_path, output_path, **kwargs):
        import tensorrt as trt
        
        # Convert to TensorRT
        # ... conversion logic ...
        
        return {"status": "success", "format": "tensorrt"}
```

### CoreML Export

```python
class CoreMLExporter:
    def export(self, model_path, output_path, **kwargs):
        import coremltools as ct
        
        # Convert to CoreML
        # ... conversion logic ...
        
        return {"status": "success", "format": "coreml"}
```

### GGUF Export

```python
class GGUFExporter:
    def export(self, model_path, output_path, **kwargs):
        import subprocess
        
        # Use llama.cpp conversion
        subprocess.run([
            "python", "convert.py",
            model_path,
            "--outfile", output_path
        ])
        
        return {"status": "success", "format": "gguf"}
```

## Best Practices

1. **Validation:** Always validate exported models
2. **Optimization:** Apply format-specific optimizations
3. **Error Handling:** Handle unsupported models gracefully
4. **Documentation:** Document supported models and limitations
5. **Testing:** Test exports on target runtime

## Troubleshooting

**Export fails:**
- Check model compatibility
- Verify dependencies installed
- Review error logs

**Exported model doesn't work:**
- Validate with format checker
- Test with simple inputs
- Check operator support

**Performance issues:**
- Apply optimizations
- Use appropriate precision (FP16/INT8)
- Benchmark on target hardware

