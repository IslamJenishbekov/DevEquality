from pydantic import BaseModel, Field
from typing import List, Literal


class ChooseOperationAndGetFilename(BaseModel):
    operation: Literal[
        "create project",
        "clone project",
        "create directory",
        "create file",
        "edit file",
        "run file",
        "read file",
        "summarize file",
        "unknown"
    ] = Field(
        description="The operation the client wants to perform"
    )

    object_name: str = Field(
        description = "The name of the project, folder, or file the user intends to interact with",
        max_length=30
    )
