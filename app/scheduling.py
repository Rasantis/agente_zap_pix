def build_calendly_message(lead_data: dict, calendly_url: str) -> str:
    nome = (lead_data or {}).get("nome")
    inicio = f"{nome}, segue" if nome else "Segue"
    return (
        f"{inicio} a agenda do nosso time — é só escolher o horário que funcionar melhor pra você:\n\n"
        f"{calendly_url}\n\n"
        "Qualquer dúvida antes da conversa, é só me chamar por aqui."
    )
