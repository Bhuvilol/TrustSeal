from pydantic import BaseModel
from typing import Optional


class SensorStats(BaseModel):
    shipment_id: str
    total_logs: int
    temperature_sample_count: int
    average_temperature: Optional[float] = None
    min_temperature: Optional[float] = None
    max_temperature: Optional[float] = None
    max_shock: Optional[float] = None
    first_recorded_at: Optional[str] = None
    last_recorded_at: Optional[str] = None
    has_temperature_breach: bool
