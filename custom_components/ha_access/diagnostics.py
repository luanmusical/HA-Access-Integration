"""Diagnóstico para baixar (Configurações, Dispositivos e serviços, HA-Access, Baixar diagnóstico):
aparelhos, versões, conexão e último sinal. Sem token nem valores pessoais."""

from __future__ import annotations

import time

from .const import PROTOCOLO, VERSAO


def _aparelho(ap):
    return {
        "nome": ap.nome, "versao_programa": ap.info.get("versao"), "modelo": ap.info.get("modelo"),
        "conectado": ap.conectado,
        "segundos_desde_o_ultimo_sinal": round(time.monotonic() - ap.ultimo_sinal) if ap.ultimo_sinal else None,
        "sensores": len(ap.info.get("sensores", [])), "comandos": len(ap.info.get("comandos", [])),
        "notificacoes": ap.info.get("notificacoes"), "media_player": ap.info.get("media_player"),
        "tem_dono": bool(ap.info.get("dono")), "entidades_criadas": len(ap.entidades),
        "valores_recebidos": len(ap.valores),
    }


async def async_get_config_entry_diagnostics(hass, entry):
    hub = entry.runtime_data
    return {"versao_integracao": VERSAO, "protocolo": PROTOCOLO,
            "aparelhos": {s[:8] + "…": _aparelho(ap) for s, ap in hub.aparelhos.items()}}


async def async_get_device_diagnostics(hass, entry, device):
    hub = entry.runtime_data
    for dominio, serial in device.identifiers:
        if dominio == "ha_access" and serial in hub.aparelhos:
            return {"versao_integracao": VERSAO, "protocolo": PROTOCOLO, "aparelho": _aparelho(hub.aparelhos[serial])}
    return {}
