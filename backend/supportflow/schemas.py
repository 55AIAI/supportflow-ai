from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Strict):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize(cls, value):
        value = value.strip().casefold()
        if "@" not in value or " " in value:
            raise ValueError("Invalid email")
        return value


class Register(Login):
    name: str = Field(min_length=1, max_length=80)
    organization: str = Field(min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def strong_enough(cls, value):
        if len(value) < 10 or len(value.encode()) > 256:
            raise ValueError("Password must contain 10-128 characters (at most 256 bytes)")
        return value


class RoleInput(Strict):
    role: Literal["owner", "operator", "viewer"] = "operator"


class CreateTicket(Strict):
    subject: str = Field(min_length=3, max_length=180)
    customer_name: str = Field(min_length=1, max_length=80)
    customer_key: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=3, max_length=6000)
    order_reference: str | None = Field(default=None, max_length=30)


class Approval(Strict):
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirmed_unused: bool


class Reply(Strict):
    body: str = Field(min_length=1, max_length=4000)


class KnowledgeInput(Strict):
    kind: Literal["returns", "delivery", "general"]
    title: str = Field(min_length=3, max_length=150)
    body: str = Field(default="", max_length=6000)
    return_days: int | None = Field(default=None, ge=1, le=60)
    expected_version: int | None = Field(default=None, ge=1)
