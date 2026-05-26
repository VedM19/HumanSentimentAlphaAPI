from datetime import date

from pydantic import BaseModel, computed_field


class RepositoryRef(BaseModel):
    owner: str
    name: str

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


class WeeklyGrowthPoint(BaseModel):
    week_start: date
    star_delta: int
