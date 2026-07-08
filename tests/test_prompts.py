from app.prompts import SYSTEM_INSTRUCTION, build_user_turn


def test_system_instruction_mentions_rules():
    assert "JSON" in SYSTEM_INSTRUCTION
    assert "mandar_calendly" in SYSTEM_INSTRUCTION


def test_build_user_turn_includes_parts():
    out = build_user_turn(
        context=["Trecho A", "Trecho B"],
        lead_data={"nome": "Ana"},
        message="vocês fazem site?",
    )
    assert "Trecho A" in out
    assert "Trecho B" in out
    assert "nome=Ana" in out
    assert "vocês fazem site?" in out


def test_build_user_turn_empty_context():
    out = build_user_turn(context=[], lead_data={}, message="oi")
    assert "nenhum trecho" in out.lower()
    assert "oi" in out
    assert "(vazio)" in out


def test_build_user_turn_skips_empty_lead_fields():
    out = build_user_turn(context=[], lead_data={"nome": "Ana", "empresa": ""}, message="oi")
    assert "nome=Ana" in out
    assert "empresa=" not in out


def test_build_user_turn_includes_profile_name():
    out = build_user_turn(context=[], lead_data={}, message="oi", contact_name="Marcos")
    assert "NOME NO PERFIL DO WHATSAPP: Marcos" in out


def test_build_user_turn_omits_profile_line_when_empty():
    out = build_user_turn(context=[], lead_data={}, message="oi")
    assert "PERFIL" not in out
