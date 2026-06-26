from app.models import ParsedMessage, TurnResult


def test_parsed_message_fields():
    m = ParsedMessage(
        message_id="wamid.1",
        from_phone="5511999",
        contact_name="Ana",
        text="oi",
        phone_number_id="106",
    )
    assert m.from_phone == "5511999"


def test_turn_result_defaults():
    t = TurnResult(resposta="olá")
    assert t.acao == "continuar"
    assert t.dados_lead.nome is None
    assert t.classificacao.etiqueta == "morno"


def test_turn_result_from_dict():
    t = TurnResult(
        resposta="vamos agendar",
        dados_lead={"nome": "Ana", "necessidade": "site"},
        classificacao={"etiqueta": "quente", "tema": "site institucional"},
        acao="mandar_calendly",
    )
    assert t.dados_lead.nome == "Ana"
    assert t.acao == "mandar_calendly"
