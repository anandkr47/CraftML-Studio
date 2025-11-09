"""
Local API Deployment
Creates a FastAPI server for model inference
"""

from typing import Dict, Any, Optional, List
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class InferenceRequest(BaseModel):
    """Request model for inference"""
    prompt: str
    max_length: int = 100
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 50


class InferenceResponse(BaseModel):
    """Response model for inference"""
    generated_text: str
    prompt: str
    model_name: str


class LocalModelServer:
    """Serves a model via local FastAPI server"""
    
    def __init__(
        self,
        model_path: str,
        host: str = "127.0.0.1",
        port: int = 5001,
        device: str = "auto"
    ):
        self.model_path = model_path
        self.host = host
        self.port = port
        self.device = device
        self.model = None
        self.tokenizer = None
        self.pipeline = None
        self.app = FastAPI(title="CraftML Model Server")
        
        self._setup_routes()
        
    def load_model(self):
        """Load model and tokenizer"""
        logger.info(f"Loading model from {self.model_path}")
        
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            device_map=self.device,
            torch_dtype=torch.float16,
        )
        
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        
        # Create pipeline for easier inference
        self.pipeline = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            device_map=self.device,
        )
        
        logger.info("Model loaded successfully")
        
    def _setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.on_event("startup")
        async def startup_event():
            self.load_model()
            
        @self.app.get("/")
        async def root():
            return {
                "status": "running",
                "model": self.model_path,
                "endpoints": ["/generate", "/health"]
            }
            
        @self.app.get("/health")
        async def health():
            return {
                "status": "healthy",
                "model_loaded": self.model is not None
            }
            
        @self.app.post("/generate", response_model=InferenceResponse)
        async def generate(request: InferenceRequest):
            if self.pipeline is None:
                raise HTTPException(status_code=500, detail="Model not loaded")
                
            try:
                result = self.pipeline(
                    request.prompt,
                    max_length=request.max_length,
                    temperature=request.temperature,
                    top_p=request.top_p,
                    top_k=request.top_k,
                    num_return_sequences=1,
                )
                
                return InferenceResponse(
                    generated_text=result[0]["generated_text"],
                    prompt=request.prompt,
                    model_name=self.model_path
                )
            except Exception as e:
                logger.error(f"Generation failed: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
                
    def start(self):
        """Start the server"""
        logger.info(f"Starting model server at http://{self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port)


def deploy_local(
    model_path: str,
    port: int = 5001,
    host: str = "127.0.0.1",
    **kwargs
) -> Dict[str, Any]:
    """
    Deploy model as local API server
    
    Args:
        model_path: Path to the model
        port: Port to run server on
        host: Host address
        **kwargs: Additional configuration
        
    Returns:
        Deployment information
    """
    try:
        server = LocalModelServer(
            model_path=model_path,
            host=host,
            port=port,
            device=kwargs.get("device", "auto")
        )
        
        # Note: This will block. In production, run in separate process
        server.start()
        
        return {
            "status": "deployed",
            "url": f"http://{host}:{port}",
            "model": model_path
        }
        
    except Exception as e:
        logger.error(f"Deployment failed: {str(e)}")
        return {
            "status": "failed",
            "error": str(e)
        }

