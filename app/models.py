from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass
class ParsedMessage:
    message_id: str
    from_phone: str
    contact_name: str
    text: str
    phone_number_id: str


class DadosLead(BaseModel):
    nome: str | None = None
    empresa: str | None = None
    necessidade: str | None = None


class Classificacao(BaseModel):
    etiqueta: str = "morno"
    tema: str = ""


class TurnResult(BaseModel):
    resposta: str
    dados_lead: DadosLead = Field(default_factory=DadosLead)
    classificacao: Classificacao = Field(default_factory=Classificacao)
    acao: str = "continuar"
