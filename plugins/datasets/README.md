# Dataset Loader Plugins

Custom dataset loaders for special data formats or sources.

## Creating a Dataset Loader Plugin

### 1. Create Plugin File

```python
# my_loader.py

class MyDatasetLoader:
    def __init__(self, config=None):
        self.config = config or {}
        self.name = "my_loader"
        self.supported_formats = [".myformat"]
    
    def load(self, file_path, **kwargs):
        # Load and parse your custom format
        samples = []
        # ... parsing logic ...
        return samples
    
    def validate(self, file_path):
        # Validate file format
        return True
    
    def get_metadata(self, file_path):
        # Return dataset metadata
        return {"name": "My Dataset", "num_samples": 100}

def register():
    return MyDatasetLoader()
```

### 2. Register Plugin

Add to `__init__.py`:

```python
from .my_loader import register as register_my_loader

PLUGINS = {
    "my_loader": register_my_loader,
}
```

### 3. Use in Backend

```python
from plugins.datasets import PLUGINS

# Load plugin
loader = PLUGINS["my_loader"]()

# Load dataset
samples = loader.load("./data.myformat")
```

## Available Plugins

### Custom Loader (`custom_loader.py`)

Example plugin showing the structure and interface.

**Features:**
- Load custom formats
- Stream large datasets
- Convert to standard formats
- Extract metadata

**Usage:**
```python
from plugins.datasets.custom_loader import CustomDatasetLoader

loader = CustomDatasetLoader()
samples = loader.load("./dataset.custom")
metadata = loader.get_metadata("./dataset.custom")
```

## Plugin Interface

All dataset loader plugins should implement:

### Required Methods

```python
def __init__(self, config: Dict = None):
    """Initialize with optional configuration"""
    pass

def load(self, file_path: str, **kwargs) -> List[Dict]:
    """
    Load dataset from file
    
    Returns:
        List of samples in standard format:
        [
            {"instruction": "...", "input": "...", "output": "..."},
            ...
        ]
    """
    pass

def validate(self, file_path: str) -> bool:
    """Check if file is valid"""
    pass
```

### Optional Methods

```python
def stream(self, file_path: str, batch_size: int) -> Iterator[List[Dict]]:
    """Stream dataset in batches for large files"""
    pass

def get_metadata(self, file_path: str) -> Dict:
    """Get dataset metadata"""
    pass

def convert_format(self, file_path: str, output_path: str, output_format: str) -> str:
    """Convert to standard format"""
    pass
```

## Standard Output Format

All loaders should convert data to one of these formats:

### Instruction Format

```json
{
  "instruction": "The task to perform",
  "input": "Optional context",
  "output": "Expected response"
}
```

### Conversation Format

```json
{
  "messages": [
    {"role": "user", "content": "User message"},
    {"role": "assistant", "content": "Assistant response"}
  ]
}
```

## Examples

### CSV Loader

```python
class CSVLoader:
    def load(self, file_path, **kwargs):
        import csv
        samples = []
        
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                samples.append({
                    "instruction": row["question"],
                    "input": "",
                    "output": row["answer"]
                })
        
        return samples
```

### SQL Database Loader

```python
class SQLLoader:
    def load(self, connection_string, **kwargs):
        import sqlite3
        
        conn = sqlite3.connect(connection_string)
        cursor = conn.execute("SELECT question, answer FROM qa_table")
        
        samples = []
        for row in cursor:
            samples.append({
                "instruction": row[0],
                "input": "",
                "output": row[1]
            })
        
        conn.close()
        return samples
```

### Web API Loader

```python
class APILoader:
    def load(self, api_url, **kwargs):
        import requests
        
        response = requests.get(api_url)
        data = response.json()
        
        samples = []
        for item in data["items"]:
            samples.append({
                "instruction": item["prompt"],
                "input": "",
                "output": item["completion"]
            })
        
        return samples
```

## Best Practices

1. **Streaming:** Implement `stream()` for large datasets
2. **Validation:** Check file format before loading
3. **Error Handling:** Handle corrupt or invalid data gracefully
4. **Metadata:** Provide useful metadata (size, samples, etc.)
5. **Conversion:** Support conversion to standard formats

## Troubleshooting

**Plugin not loading:**
- Check registration in `__init__.py`
- Verify Python syntax
- Check dependencies

**Loading fails:**
- Validate input file
- Check file encoding
- Review error logs

**Memory issues:**
- Use `stream()` for large files
- Process in batches
- Clear data after processing

