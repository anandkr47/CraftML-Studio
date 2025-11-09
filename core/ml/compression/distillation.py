"""
Knowledge Distillation Engine
Transfer knowledge from teacher model to smaller student model
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class KnowledgeDistiller:
    """Handles knowledge distillation from teacher to student model"""
    
    def __init__(
        self,
        teacher_model,
        student_model,
        temperature: float = 2.0,
        alpha: float = 0.7
    ):
        """
        Initialize distillation
        
        Args:
            teacher_model: Large pre-trained model
            student_model: Smaller model to train
            temperature: Softmax temperature for distillation
            alpha: Weight for distillation loss vs. hard label loss
        """
        self.teacher = teacher_model
        self.student = student_model
        self.temperature = temperature
        self.alpha = alpha
        
        # Set teacher to eval mode
        self.teacher.eval()
        for param in self.teacher.parameters():
            param.requires_grad = False
            
    def distillation_loss(
        self,
        student_logits: torch.Tensor,
        teacher_logits: torch.Tensor,
        labels: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Calculate distillation loss
        
        Args:
            student_logits: Logits from student model
            teacher_logits: Logits from teacher model
            labels: Ground truth labels (optional)
            
        Returns:
            Combined loss
        """
        # Soft targets from teacher
        soft_targets = F.softmax(teacher_logits / self.temperature, dim=-1)
        soft_student = F.log_softmax(student_logits / self.temperature, dim=-1)
        
        # Distillation loss (KL divergence)
        distillation_loss = F.kl_div(
            soft_student,
            soft_targets,
            reduction='batchmean'
        ) * (self.temperature ** 2)
        
        # If labels provided, combine with hard label loss
        if labels is not None:
            hard_loss = F.cross_entropy(student_logits, labels)
            loss = self.alpha * distillation_loss + (1 - self.alpha) * hard_loss
        else:
            loss = distillation_loss
            
        return loss
        
    def train_step(
        self,
        batch: Dict[str, torch.Tensor],
        optimizer: torch.optim.Optimizer
    ) -> float:
        """
        Single training step
        
        Args:
            batch: Input batch with 'input_ids', 'attention_mask', etc.
            optimizer: Optimizer for student model
            
        Returns:
            Loss value
        """
        self.student.train()
        
        # Forward pass through both models
        with torch.no_grad():
            teacher_outputs = self.teacher(**batch)
            teacher_logits = teacher_outputs.logits
            
        student_outputs = self.student(**batch)
        student_logits = student_outputs.logits
        
        # Calculate loss
        labels = batch.get('labels', None)
        loss = self.distillation_loss(student_logits, teacher_logits, labels)
        
        # Backward pass
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        return loss.item()
        
    def distill(
        self,
        train_dataloader,
        num_epochs: int = 3,
        learning_rate: float = 5e-5,
        output_path: str = "./distilled_model"
    ) -> Dict[str, Any]:
        """
        Run full distillation training
        
        Args:
            train_dataloader: DataLoader with training data
            num_epochs: Number of training epochs
            learning_rate: Learning rate for student
            output_path: Where to save distilled model
            
        Returns:
            Training statistics
        """
        optimizer = torch.optim.AdamW(self.student.parameters(), lr=learning_rate)
        
        total_loss = 0
        num_steps = 0
        
        logger.info(f"Starting distillation for {num_epochs} epochs")
        
        for epoch in range(num_epochs):
            epoch_loss = 0
            for batch in train_dataloader:
                loss = self.train_step(batch, optimizer)
                epoch_loss += loss
                num_steps += 1
                
                if num_steps % 100 == 0:
                    logger.info(f"Step {num_steps}, Loss: {loss:.4f}")
                    
            avg_epoch_loss = epoch_loss / len(train_dataloader)
            total_loss += avg_epoch_loss
            logger.info(f"Epoch {epoch+1}/{num_epochs}, Avg Loss: {avg_epoch_loss:.4f}")
            
        # Save distilled model
        self.student.save_pretrained(output_path)
        logger.info(f"Distilled model saved to {output_path}")
        
        return {
            "status": "success",
            "num_epochs": num_epochs,
            "final_loss": total_loss / num_epochs,
            "output_path": output_path,
        }


def distill_model(
    teacher_model_path: str,
    student_model_path: str,
    train_dataset,
    output_path: str,
    **kwargs
) -> Dict[str, Any]:
    """
    High-level function to distill knowledge
    
    Args:
        teacher_model_path: Path to teacher model
        student_model_path: Path to student model
        train_dataset: Training dataset (path, HF dataset, or list of samples)
        output_path: Where to save distilled model
        **kwargs: Additional distillation parameters
            - temperature: Distillation temperature (default: 2.0)
            - alpha: Weight for distillation loss (default: 0.7)
            - num_epochs: Number of training epochs (default: 3)
            - learning_rate: Learning rate (default: 5e-5)
            - batch_size: Batch size (default: 4)
            - max_length: Maximum sequence length (default: 512)
        
    Returns:
        Training results
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from torch.utils.data import DataLoader
    
    logger.info("Loading teacher and student models...")
    
    # Load models
    teacher = AutoModelForCausalLM.from_pretrained(teacher_model_path)
    student = AutoModelForCausalLM.from_pretrained(student_model_path)
    tokenizer = AutoTokenizer.from_pretrained(teacher_model_path)
    
    # Move to GPU if available
    import torch
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    teacher = teacher.to(device)
    student = student.to(device)
    
    # Create distiller
    distiller = KnowledgeDistiller(
        teacher_model=teacher,
        student_model=student,
        temperature=kwargs.get("temperature", 2.0),
        alpha=kwargs.get("alpha", 0.7),
    )
    
    # Prepare dataset
    logger.info("Preparing training dataset...")
    
    if isinstance(train_dataset, str):
        # Load from file path
        from core.data import DatasetLoader
        loader = DatasetLoader()
        samples = loader.load_from_path(train_dataset)
        dataset = loader.prepare_for_training(
            samples=samples,
            tokenizer=tokenizer,
            max_length=kwargs.get("max_length", 512)
        )
    elif hasattr(train_dataset, "__iter__"):
        # List of samples
        from core.data import DatasetLoader
        loader = DatasetLoader()
        dataset = loader.prepare_for_training(
            samples=list(train_dataset),
            tokenizer=tokenizer,
            max_length=kwargs.get("max_length", 512)
        )
    else:
        # Assume it's already a prepared dataset
        dataset = train_dataset
    
    # Create dataloader
    train_dataloader = DataLoader(
        dataset,
        batch_size=kwargs.get("batch_size", 4),
        shuffle=True,
        num_workers=0
    )
    
    logger.info(f"Training on {len(dataset)} samples")
    
    # Run distillation
    result = distiller.distill(
        train_dataloader=train_dataloader,
        num_epochs=kwargs.get("num_epochs", 3),
        learning_rate=kwargs.get("learning_rate", 5e-5),
        output_path=output_path,
    )
    
    return result

