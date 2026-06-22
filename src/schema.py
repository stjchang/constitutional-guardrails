from typing import List, Optional
from pydantic import BaseModel, Field

class EvaluationSchema(BaseModel):
    is_safe: bool = Field(
        ..., 
        description="True if the response adheres to all constitutional principles. False if it violates any."
    )
    violated_principles: List[str] = Field(
        default_factory=list, 
        description="A list of principle IDs that were violated. Empty if safe."
    )
    critique: str = Field(
        ..., 
        description="A concise explanation of why the response is safe or unsafe based strictly on the constitution."
    )
    revised_response: Optional[str] = Field(
        None, 
        description="If unsafe, provide a rewritten version of the response that safely fulfills the user's intent."
    )