import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KnowledgeBaseView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    slug: str
    name: str
    created_at: datetime


class BootstrapContextView(BaseModel):
    owner_id: uuid.UUID
    owner_email: str
    workspace_id: uuid.UUID
    workspace_slug: str
    workspace_name: str
    knowledge_base_id: uuid.UUID
    knowledge_base_slug: str
    knowledge_base_name: str

