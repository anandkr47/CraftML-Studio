"""
Hugging Face Hub Deployment
Upload and deploy models to Hugging Face
"""

from typing import Dict, Any, Optional
from huggingface_hub import HfApi, create_repo, upload_folder
import logging

logger = logging.getLogger(__name__)


class HuggingFaceDeployer:
    """Handles deployment to Hugging Face Hub"""
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize HF deployer
        
        Args:
            token: HuggingFace API token (if None, uses cached credentials)
        """
        self.api = HfApi(token=token)
        self.token = token
        
    def upload_model(
        self,
        model_path: str,
        repo_name: str,
        private: bool = False,
        commit_message: str = "Upload model"
    ) -> Dict[str, Any]:
        """
        Upload model to Hugging Face Hub
        
        Args:
            model_path: Local path to model
            repo_name: Repository name (username/model-name)
            private: Make repo private
            commit_message: Commit message
            
        Returns:
            Upload status and URL
        """
        try:
            logger.info(f"Creating repository: {repo_name}")
            
            # Create repository
            create_repo(
                repo_id=repo_name,
                private=private,
                token=self.token,
                exist_ok=True,
            )
            
            logger.info(f"Uploading model from {model_path}")
            
            # Upload model files
            url = upload_folder(
                folder_path=model_path,
                repo_id=repo_name,
                commit_message=commit_message,
                token=self.token,
            )
            
            logger.info(f"Model uploaded successfully to {url}")
            
            return {
                "status": "success",
                "url": url,
                "repo_id": repo_name,
                "private": private
            }
            
        except Exception as e:
            logger.error(f"Upload failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }
            
    def create_model_card(
        self,
        repo_name: str,
        model_description: str,
        base_model: str,
        training_details: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a model card (README.md) for the repository
        
        Args:
            repo_name: Repository name
            model_description: Description of the model
            base_model: Base model used for fine-tuning
            training_details: Training configuration details
            
        Returns:
            Model card content
        """
        card_content = f"""---
license: apache-2.0
base_model: {base_model}
tags:
- generated_from_craftml_studio
- {base_model.split('/')[0] if '/' in base_model else 'custom'}
---

# {repo_name}

{model_description}

## Model Details

- **Base Model:** {base_model}
- **Fine-tuned with:** CraftML Studio
"""

        if training_details:
            card_content += "\n## Training Configuration\n\n"
            for key, value in training_details.items():
                card_content += f"- **{key}:** {value}\n"
                
        card_content += """
## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained("{repo_name}")
tokenizer = AutoTokenizer.from_pretrained("{repo_name}")

inputs = tokenizer("Your prompt here", return_tensors="pt")
outputs = model.generate(**inputs, max_length=100)
print(tokenizer.decode(outputs[0]))
```

## License

Apache 2.0
""".format(repo_name=repo_name)

        return card_content
        
    def deploy_to_spaces(
        self,
        model_path: str,
        space_name: str,
        space_sdk: str = "gradio",
    ) -> Dict[str, Any]:
        """
        Deploy model to Hugging Face Spaces
        
        Args:
            model_path: Local model path
            space_name: Name for the space
            space_sdk: SDK to use (gradio, streamlit, static)
            
        Returns:
            Deployment status
        """
        try:
            # Create space repository
            create_repo(
                repo_id=space_name,
                repo_type="space",
                space_sdk=space_sdk,
                token=self.token,
                exist_ok=True,
            )
            
            # Upload model files to space
            upload_folder(
                folder_path=model_path,
                repo_id=space_name,
                repo_type="space",
                token=self.token,
            )
            
            logger.info(f"Space created: {space_name}")
            
            return {
                "status": "success",
                "space_url": f"https://huggingface.co/spaces/{space_name}",
                "space_name": space_name
            }
            
        except Exception as e:
            logger.error(f"Space deployment failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }


def deploy_to_huggingface(
    model_path: str,
    repo_name: str,
    hf_token: Optional[str] = None,
    private: bool = False,
    create_space: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    High-level function to deploy to Hugging Face
    
    Args:
        model_path: Path to model
        repo_name: Repository name
        hf_token: HuggingFace token
        private: Make repository private
        create_space: Also create a Spaces demo
        **kwargs: Additional parameters
        
    Returns:
        Deployment results
    """
    deployer = HuggingFaceDeployer(token=hf_token)
    
    # Upload model
    result = deployer.upload_model(
        model_path=model_path,
        repo_name=repo_name,
        private=private
    )
    
    if result["status"] == "success" and create_space:
        space_result = deployer.deploy_to_spaces(
            model_path=model_path,
            space_name=f"{repo_name}-demo"
        )
        result["space"] = space_result
        
    return result

