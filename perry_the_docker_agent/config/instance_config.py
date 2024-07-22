from pydantic import BaseModel


class PerryInstanceConfig(BaseModel):
    # --- aws properties
    instance_id: str
    perry_key_path: str
    region: str
    aws_profile: str
