from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


@dataclass
class ParsedMessage:
    message_id: str
    from_phone: str
    contact_name: str
    text: str
    phone_number_id: str
    msg_type: str = "text"
    media_id: str = ""  # id da mídia na Meta (preenchido quando msg_type == "audio")


class DadosLead(BaseModel):
    nome: str | None = None
    empresa: str | None = None
    necessidade: str | None = None


class Classificacao(BaseModel):
    etiqueta: Literal["quente", "morno", "frio"] = "morno"
    tema: str = ""


class TurnResult(BaseModel):
    resposta: str
    dados_lead: DadosLead = Field(default_factory=DadosLead)
    classificacao: Classificacao = Field(default_factory=Classificacao)
    acao: str = "continuar"


# Modelos "wire": o schema enviado ao Gemini. SEM defaults — a API do Gemini
# rejeita "default" no response_schema (ValueError em versões novas do SDK).
# Todos os campos são obrigatórios; os anuláveis aceitam null explícito.
class DadosLeadWire(BaseModel):
    nome: str | None
    empresa: str | None
    necessidade: str | None


class ClassificacaoWire(BaseModel):
    etiqueta: Literal["quente", "morno", "frio"]
    tema: str


class TurnResultWire(BaseModel):
    resposta: str
    dados_lead: DadosLeadWire
    classificacao: ClassificacaoWire
    acao: Literal["continuar", "mandar_calendly", "reenviar_link"]
