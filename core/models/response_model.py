from pydantic import BaseModel

class ResponseModel(BaseModel):
    topic: str
    final:str