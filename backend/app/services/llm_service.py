"""
LLM Service using Qwen2.5-7B for natural language to SQL conversion
"""

from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
from typing import Optional
import os

class LLMService:
    """Service for generating SQL queries using Qwen2.5-1.5B-Instruct LLM"""
    
    def __init__(self):
        """Initialize the lightweight LLM model"""
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Lightweight instruction-tuned model options:
        # - Qwen/Qwen2.5-1.5B-Instruct (1.5B, ~3GB, FASTEST ⭐)
        # - Qwen/Qwen2.5-3B-Instruct (3B, ~6GB, good quality)
        # - microsoft/phi-3-mini-4k-instruct (3.8B, ~7GB, very good)
        self.model_name = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-3B-Instruct")
        
        print(f"Loading {self.model_name} on {self.device}...")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                trust_remote_code=True,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map=self.device
            )
            print("✓ Model loaded successfully!")
        except Exception as e:
            print(f"Warning: Could not load Qwen model: {e}")
            print("Falling back to pattern-based SQL generation")
            self.model = None
            self.tokenizer = None
    
    def generate_sql(self, question: str, context: dict, schema_info: str) -> str:
        """
        Generate SQL query from natural language question using LLM
        
        Args:
            question: User's natural language question
            context: Academic context (periodo_id, semestre_id, etc.)
            schema_info: Database schema information for the LLM
        
        Returns:
            SQL query string
        """
        
        if self.model is None:
            return self._fallback_template_sql(question, context)
        
        # Build the prompt for the LLM
        prompt = self._build_prompt(question, context, schema_info)
        
        try:
            # Tokenize input
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
            
            # Generate SQL
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs.input_ids,
                    max_length=500,
                    temperature=0.7,
                    top_p=0.9,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            # Decode the response
            sql_response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Extract SQL from response
            sql = self._extract_sql(sql_response)
            
            if not sql:
                return self._fallback_template_sql(question, context)
            
            return sql
            
        except Exception as e:
            print(f"Error generating SQL with LLM: {e}")
            return self._fallback_template_sql(question, context)
    
    def _build_prompt(self, question: str, context: dict, schema_info: str) -> str:
        """Build a comprehensive prompt for SQL generation"""
        
        periodo_id = context.get('periodo_id', 3)
        semestre_id = context.get('semestre_id', 2)
        
        prompt = f"""You are a SQL expert for an educational scheduling system.

DATABASE SCHEMA:
{schema_info}

CURRENT ACADEMIC CONTEXT:
- Periodo ID: {periodo_id}
- Semestre ID: {semestre_id}
- Today's Date: {context.get('date_actuelle', 'unknown')}

USER QUESTION (in French): {question}

INSTRUCTIONS:
1. Analyze the question in French
2. Generate a PostgreSQL SELECT query
3. Always join with periodes and semestres tables
4. Include periodo_id = {periodo_id} and semestre_id = {semestre_id} in WHERE clause when appropriate
5. Format the output with readable column aliases
6. Return ONLY the SQL query, no explanations

SQL QUERY:"""
        
        return prompt
    
    def _extract_sql(self, response: str) -> Optional[str]:
        """Extract SQL query from LLM response"""
        
        # Find SQL in the response
        if "SELECT" in response.upper():
            # Find the start of SELECT
            sql_start = response.upper().find("SELECT")
            sql = response[sql_start:]
            
            # Clean up
            sql = sql.replace("```sql", "").replace("```", "").strip()
            
            # Remove trailing explanations
            if ";" not in sql:
                sql = sql.split("\n")[0] if "\n" in sql else sql
            
            return sql if sql.startswith("SELECT") else None
        
        return None
    
    def _fallback_template_sql(self, question: str, context: dict) -> str:
        """Fallback to template-based SQL generation"""
        from .sql_template_generator import sql_generator
        return sql_generator.generate_sql(question, context)


# Initialize the LLM service
try:
    llm_service = LLMService()
except Exception as e:
    print(f"Warning: LLM initialization failed: {e}")
    llm_service = None
