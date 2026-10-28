"""
HA-Access: integração do Home Assistant para o programa HA-Access (Windows).

O programa se conecta pela API websocket do próprio HA (a mesma usada pelo
painel; funciona em casa e pelo link externo) e manda:

- ha_access/conectar   (assinatura) aparelho, sensores e comandos; enquanto a
                       assinatura vive o aparelho está disponível; por ela o
                       HA manda comandos, notificações e comandos de mídia;
- ha_access/definir    sensores ou comandos mudaram (lista completa);
- ha_access/estados    valores dos sensores e estado dos comandos;
- ha_access/midia      o que está tocando no computador (e a capa);
- ha_access/vivo       sinal de vida a cada 30 s (sem sinal por 75 s: indisponível);
- ha_access/acao_notificacao  botão escolhido numa notificação (vira o
                       evento ha_access_notification_action);
- ha_access/tag        etiqueta NFC lida (vira tag escaneada do HA).

Sem MQTT, sem porta aberta no computador.
"""

from __future__ import annotations

import base64
import binascii
from datetime import timedelta

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import discovery
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, EVENTO_ACAO, PLATAFORMAS, PROTOCOLO, PROTOCOLO_MINIMO, VERSAO
from .hub import Hub

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

DEF_SENSOR = vol.Schema({
    vol.Required("id"): str, vol.Required("nome"): str, vol.Optional("dominio", default="sensor"): str,
    vol.Optional("unidade"): vol.Any(str, None), vol.Optional("device_class"): vol.Any(str, None),
    vol.Optional("state_class"): vol.Any(str, None), vol.Optional("icone"): vol.Any(str, None),
    vol.Optional("sempre_disponivel", default=False): bool, vol.Optional("categoria"): vol.Any(str, None),
}, extra=vol.ALLOW_EXTRA)
DEF_COMANDO = vol.Schema({
    vol.Required("id"): str, vol.Required("nome"): str, vol.Optional("dominio", default="switch"): str,
    vol.Optional("icone"): vol.Any(str, None),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config) -> bool:
    for f in (ws_conectar, ws_definir, ws_estados, ws_midia, ws_acao_notificacao, ws_tag, ws_vivo):
        websocket_api.async_register_command(hass, f)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hub = Hub(hass, entry)
    await hub.carregar()
    entry.runtime_data = hub
    hass.data[DOMAIN] = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATAFORMAS)
    # sinal de vida: computador mudo por SINAL_MAXIMO fica indisponível
    entry.async_on_unload(async_track_time_interval(hass, hub.vigiar, timedelta(seconds=15)))
    # notify.ha_access_<aparelho>, com data (botões, imagem...), como o app do celular
    if not hass.data.get(f"{DOMAIN}_notify"):
        hass.data[f"{DOMAIN}_notify"] = True
        hass.async_create_task(discovery.async_load_platform(hass, "notify", DOMAIN, {}, {}))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hub: Hub = entry.runtime_data
    hub.desligar_todos()
    ok = await hass.config_entries.async_unload_platforms(entry, PLATAFORMAS)
    if ok:
        hass.data.pop(DOMAIN, None)
    return ok


async def async_remove_config_entry_device(hass: HomeAssistant, entry: ConfigEntry,
                                           device: dr.DeviceEntry) -> bool:
    """Apagar o aparelho pela interface: esquece o computador (volta se ele conectar de novo)."""
    hub: Hub = entry.runtime_data
    for dominio, serial in device.identifiers:
        if dominio == DOMAIN:
            await hub.esquecer(serial)
    return True


def _usuario(connection):
    u = connection.user
    return (u.id if u else None), bool(u and u.is_admin)


def _hub(hass, connection, msg, checar=True):
    """O hub, ou None (já respondeu o erro). checar: o usuário pode falar por esse computador."""
    hub = hass.data.get(DOMAIN)
    if hub is None:
        connection.send_error(msg["id"], "nao_configurado", "A integração HA-Access não está configurada")
        return None
    if checar and msg.get("serial") in hub.aparelhos and not hub.autorizado(msg["serial"], *_usuario(connection)):
        connection.send_error(msg["id"], "sem_permissao", "Este computador pertence a outro usuário do Home Assistant")
        return None
    return hub


def _issue_versao(serial):
    return f"versao_{serial}"


# -- comandos websocket -------------------------------------------------------------------------
@websocket_api.websocket_command({
    vol.Required("type"): "ha_access/conectar",
    vol.Required("serial"): str,
    vol.Required("nome"): str,
    vol.Optional("modelo", default=""): str,
    vol.Optional("versao", default=""): str,
    vol.Optional("notificacoes", default=True): bool,
    vol.Optional("media_player", default=True): bool,
    vol.Optional("sensores", default=[]): [DEF_SENSOR],
    vol.Optional("comandos", default=[]): [DEF_COMANDO],
    vol.Optional("completo", default=True): bool,
    vol.Optional("protocolo", default=0): int,
})
@websocket_api.async_response
async def ws_conectar(hass, connection, msg):
    hub = _hub(hass, connection, msg, checar=False)
    if hub is None:
        return
    serial = msg["serial"]
    ident = msg["id"]
    if not PROTOCOLO_MINIMO <= msg["protocolo"] <= PROTOCOLO:
        programa_novo = msg["protocolo"] > PROTOCOLO
        ir.async_create_issue(
            hass, DOMAIN, _issue_versao(serial), is_fixable=False, severity=ir.IssueSeverity.WARNING,
            translation_key="integracao_velha" if programa_novo else "programa_velho",
            translation_placeholders={"nome": msg["nome"], "versao": VERSAO, "versao_programa": msg["versao"]})
        connection.send_error(ident, "versao_incompativel",
                              "Atualize a integração HA-Access no Home Assistant" if programa_novo else
                              "Atualize o programa HA-Access neste computador")
        return
    ir.async_delete_issue(hass, DOMAIN, _issue_versao(serial))

    @callback
    def enviar(dados):
        connection.send_message(websocket_api.event_message(ident, dados))

    try:
        aparelho = await hub.conectar(msg, enviar, *_usuario(connection))
    except PermissionError:
        connection.send_error(ident, "sem_permissao",
                              "Este computador pertence a outro usuário do Home Assistant")
        return

    @callback
    def cancelar():
        hub.desconectar(serial, enviar)

    connection.subscriptions[ident] = cancelar
    connection.send_result(ident, {"device_id": aparelho.device_id, "protocolo": PROTOCOLO, "versao": VERSAO,
                                   "notify": f"notify.{DOMAIN}_{aparelho.alvo_notify}"})


@websocket_api.websocket_command({vol.Required("type"): "ha_access/vivo", vol.Required("serial"): str})
@callback
def ws_vivo(hass, connection, msg):
    """Sinal de vida do programa (a cada 30 s)."""
    hub = _hub(hass, connection, msg)
    if hub is None:
        return
    hub.sinal(msg["serial"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command({
    vol.Required("type"): "ha_access/definir",
    vol.Required("serial"): str,
    vol.Required("sensores"): [DEF_SENSOR],
    vol.Required("comandos"): [DEF_COMANDO],
})
@websocket_api.async_response
async def ws_definir(hass, connection, msg):
    hub = _hub(hass, connection, msg)
    if hub is None:
        return
    if not await hub.definir(msg["serial"], msg["sensores"], msg["comandos"]):
        connection.send_error(msg["id"], "desconhecido", "Aparelho não conectado")
        return
    connection.send_result(msg["id"])


@websocket_api.websocket_command({
    vol.Required("type"): "ha_access/estados",
    vol.Required("serial"): str,
    vol.Optional("sensores", default={}): {str: dict},
    vol.Optional("comandos", default={}): {str: bool},
})
@callback
def ws_estados(hass, connection, msg):
    hub = _hub(hass, connection, msg)
    if hub is None:
        return
    hub.estados(msg["serial"], msg["sensores"], msg["comandos"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command({
    vol.Required("type"): "ha_access/midia",
    vol.Required("serial"): str,
    vol.Required("estado"): dict,
    vol.Optional("capa"): vol.Any(str, None),
})
@callback
def ws_midia(hass, connection, msg):
    hub = _hub(hass, connection, msg)
    if hub is None:
        return
    capa = ...
    if "capa" in msg:
        try:
            capa = base64.b64decode(msg["capa"]) if msg["capa"] else None
        except (binascii.Error, ValueError):
            capa = None
    hub.midia(msg["serial"], msg["estado"], capa)
    connection.send_result(msg["id"])


@websocket_api.websocket_command({
    vol.Required("type"): "ha_access/acao_notificacao",
    vol.Required("serial"): str,
    vol.Required("action"): str,
    vol.Optional("input", default=""): str,
    vol.Optional("uri", default=""): str,
})
@callback
def ws_acao_notificacao(hass, connection, msg):
    hub = _hub(hass, connection, msg)
    if hub is None:
        return
    ap = hub.aparelhos.get(msg["serial"])
    hass.bus.async_fire(EVENTO_ACAO, {
        "serial": msg["serial"], "device_id": ap.device_id if ap else None,
        "device_name": ap.nome if ap else "", "action": msg["action"], "input": msg["input"], "uri": msg["uri"],
    }, context=connection.context(msg))
    connection.send_result(msg["id"])


@websocket_api.websocket_command({
    vol.Required("type"): "ha_access/tag",
    vol.Required("serial"): str,
    vol.Required("uid"): str,
})
@websocket_api.async_response
async def ws_tag(hass, connection, msg):
    hub = _hub(hass, connection, msg)
    if hub is None:
        return
    from homeassistant.components.tag import async_scan_tag
    ap = hub.aparelhos.get(msg["serial"])
    await async_scan_tag(hass, msg["uid"], ap.device_id if ap else None, connection.context(msg))
    connection.send_result(msg["id"])
