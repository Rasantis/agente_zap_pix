def build_calendly_message(lead_data: dict, calendly_url: str) -> str:
    nome = (lead_data or {}).get("nome")
    saudacao = f"Perfeito, {nome}! " if nome else "Perfeito! "
    return (
        f"{saudacao}Para a gente seguir, é só escolher o melhor horário "
        f"para uma conversa com o nosso time pelo link abaixo:\n\n"
        f"{calendly_url}\n\n"
        "Assim que você agendar, já fica confirmado. Qualquer dúvida, é só me chamar por aqui. 😊"
    )
