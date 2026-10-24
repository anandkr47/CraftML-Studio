"""
Hugging Face Hub export
Uploads a model (safetensors folder / LoRA adapter, or a single GGUF file)
together with a generated model card.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from huggingface_hub import HfApi, create_repo, upload_file, upload_folder

logger = logging.getLogger(__name__)

USAGE_SNIPPETS = {
    "full": '''```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained("{repo}")
tokenizer = AutoTokenizer.from_pretrained("{repo}")

inputs = tokenizer("Your prompt here", return_tensors="pt")
outputs = model.generate(**inputs, max_new_tokens=100)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```''',
    "lora": '''This repository contains a LoRA adapter. Load it on top of the base model:

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained("{base}")
model = PeftModel.from_pretrained(base, "{repo}")
tokenizer = AutoTokenizer.from_pretrained("{repo}")
```''',
    "gguf": '''This repository contains a GGUF file for llama.cpp-compatible runtimes:

```python
from llama_cpp import Llama

llm = Llama.from_pretrained(repo_id="{repo}", filename="{filename}")
print(llm.create_chat_completion(messages=[{{"role": "user", "content": "Hello"}}]))
```''',
}


def build_model_card(
    repo_name: str,
    kind: str,
    base_model: Optional[str] = None,
    description: Optional[str] = None,
    training_details: Optional[Dict[str, Any]] = None,
    filename: Optional[str] = None,
) -> str:
    """
    Render a README.md model card.

    Args:
        kind: "full", "lora" or "gguf"
        base_model: Hugging Face id of the model that was fine-tuned/converted
        training_details: label -> value pairs listed under "Training"
        filename: GGUF filename (used in the usage snippet)
    """
    library = {"full": "transformers", "lora": "peft", "gguf": "gguf"}.get(kind, "transformers")
    front = ["---", f"library_name: {library}"]
    if base_model:
        front.append(f"base_model: {base_model}")
    front += ["tags:", "- craftml-studio"]
    if kind == "lora":
        front.append("- lora")
    if kind == "gguf":
        front.append("- gguf")
    front.append("---")

    lines = ["\n".join(front), "", f"# {repo_name.split('/')[-1]}", ""]
    lines.append(description.strip() if description and description.strip() else "A model exported from CraftML Studio.")
    lines += ["", "## Model details", ""]
    lines.append(f"- **Format:** {'GGUF' if kind == 'gguf' else 'LoRA adapter (safetensors)' if kind == 'lora' else 'safetensors'}")
    if base_model:
        lines.append(f"- **Base model:** [{base_model}](https://huggingface.co/{base_model})")

    if training_details:
        lines += ["", "## Training", ""]
        lines += [f"- **{label}:** {value}" for label, value in training_details.items()]

    snippet = USAGE_SNIPPETS.get(kind, USAGE_SNIPPETS["full"]).format(
        repo=repo_name, base=base_model or "BASE_MODEL", filename=filename or "model.gguf"
    )
    lines += ["", "## Usage", "", snippet, "", "## License", "",
              "Check the license of the base model; it also applies to this export.", ""]
    return "\n".join(lines)


class HuggingFaceDeployer:
    """Handles uploads to the Hugging Face Hub"""

    def __init__(self, token: Optional[str] = None):
        """token: HF API token (if None, huggingface_hub's cached credentials are used)"""
        self.api = HfApi(token=token)
        self.token = token

    def upload_model(
        self,
        model_path: str,
        repo_name: str,
        private: bool = False,
        commit_message: str = "Upload model from CraftML Studio",
        model_card: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload a model directory or a single file (e.g. a .gguf) and an optional model card.

        The card is only added when the folder doesn't already ship a README.md.
        """
        try:
            path = Path(model_path)
            create_repo(repo_id=repo_name, private=private, token=self.token, exist_ok=True)

            if path.is_file():
                upload_file(
                    path_or_fileobj=str(path), path_in_repo=path.name, repo_id=repo_name,
                    commit_message=commit_message, token=self.token,
                )
                has_readme = False
            else:
                upload_folder(
                    folder_path=str(path), repo_id=repo_name,
                    commit_message=commit_message, token=self.token,
                )
                has_readme = (path / "README.md").exists()

            if model_card and not has_readme:
                upload_file(
                    path_or_fileobj=model_card.encode("utf-8"), path_in_repo="README.md",
                    repo_id=repo_name, commit_message="Add model card", token=self.token,
                )

            return {
                "status": "success",
                "url": f"https://huggingface.co/{repo_name}",
                "repo_id": repo_name,
                "private": private,
            }
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return {"status": "failed", "error": str(e)}


def deploy_to_huggingface(
    model_path: str,
    repo_name: str,
    hf_token: Optional[str] = None,
    private: bool = False,
    model_card: Optional[str] = None,
) -> Dict[str, Any]:
    """Upload ``model_path`` to ``repo_name`` and return ``{status, url, ...}``."""
    return HuggingFaceDeployer(token=hf_token).upload_model(
        model_path=model_path, repo_name=repo_name, private=private, model_card=model_card
    )
