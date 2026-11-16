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

from .const import (CAPA_MAX, DOMAIN, EVENTO_ACAO, ITENS_MAX, PLATAFORMAS, PLATAFORMAS_COMANDO,
                    PLATAFORMAS_SENSOR, PROTOCOLO, PROTOCOLO_MINIMO, TEXTO_MAX, VERSAO)
from .hub import Hub

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Tudo o que chega do programa tem tamanho e formato limitados: um usuário comum do HA não
# consegue encher o registro de lixo nem mandar mensagens gigantes.
SERIAL = vol.All(str, vol.Match(r"^[^\x00-\x1f\x7f]{1,100}$"))   # sem caractere de controle
TEXTO = vol.All(str, vol.Length(max=TEXTO_MAX))
NOME = vol.All(str, vol.Length(min=1, max=TEXTO_MAX))
ID_ITEM = vol.All(str, vol.Match(r"^[^\x00-\x1f\x7f]{1,200}$"))
TEXTO_OPCIONAL = vol.Any(TEXTO, None)

DEF_SENSOR = vol.Schema({
    vol.Required("id"): ID_ITEM, vol.Required("nome"): NOME,
    vol.Optional("dominio", default="sensor"): vol.In(PLATAFORMAS_SENSOR),
    vol.Optional("unidade"): TEXTO_OPCIONAL, vol.Optional("device_class"): TEXTO_OPCIONAL,
    vol.Optional("state_class"): TEXTO_OPCIONAL, vol.Optional("icone"): TEXTO_OPCIONAL,
    vol.Optional("sempre_disponivel", default=False): bool, vol.Optional("categoria"): TEXTO_OPCIONAL,
}, extra=vol.REMOVE_EXTRA)
DEF_COMANDO = vol.Schema({
    vol.Required("id"): ID_ITEM, vol.Required("nome"): NOME,
    vol.Optional("dominio", default="switch"): vol.In(PLATAFORMAS_COMANDO),
    vol.Optional("icone"): TEXTO_OPCIONAL,
}, extra=vol.REMOVE_EXTRA)
SENSORES = vol.All([DEF_SENSOR], vol.Length(max=ITENS_MAX))
COMANDOS = vol.All([DEF_COMANDO], vol.Length(max=ITENS_MAX))


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
    """O hub, ou None (já respondeu o erro).

    checar: só deixa passar quem pode falar por esse computador. Computador desconhecido é
    sempre recusado: só ha_access/conectar (checar=False) apresenta um computador novo. Assim
    ninguém manda etiqueta, botão de notificação, estados, mídia ou sinal de vida em nome de
    um computador que não existe ou que é de outro usuário."""
    hub = hass.data.get(DOMAIN)
    if hub is None:
        connection.send_error(msg["id"], "nao_configurado", "A integração HA-Access não está configurada")
        return None
    if not checar:
        return hub
    serial = msg.get("serial")
    if serial not in hub.aparelhos:
        connection.send_error(msg["id"], "desconhecido",
                              "Computador desconhecido: conecte com ha_access/conectar primeiro")
        return None
    if not hub.autorizado(serial, *_usuario(connection)):
        connection.send_error(msg["id"], "sem_permissao", "Este computador pertence a outro usuário do Home Assistant")
        return None
    return hub


def _issue_versao(serial):
    return f"versao_{serial}"


# -- comandos websocket -------------------------------------------------------------------------
@websocket_api.websocket_command({
    vol.Required("type"): "ha_access/conectar",
    vol.Required("serial"): SERIAL,
    vol.Required("nome"): NOME,
    vol.Optional("modelo", default=""): TEXTO,
    vol.Optional("versao", default=""): TEXTO,
    vol.Optional("notificacoes", default=True): bool,
    vol.Optional("media_player", default=True): bool,
    vol.Optional("sensores", default=[]): SENSORES,
    vol.Optional("comandos", default=[]): COMANDOS,
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
    # permissão antes de tudo (até do aviso de versão em Reparos, que só o dono pode criar)
    try:
        hub.pode_conectar(serial, *_usuario(connection))
    except PermissionError as e:
        connection.send_error(ident, "sem_permissao", str(e))
        return
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
    except PermissionError as e:
        connection.send_error(ident, "sem_permissao",
                              str(e) or "Este computador pertence a outro usuário do Home Assistant")
        return

    @callback
    def cancelar():
        hub.desconectar(serial, enviar)

    connection.subscriptions[ident] = cancelar
    connection.send_result(ident, {"device_id": aparelho.device_id, "protocolo": PROTOCOLO, "versao": VERSAO,
                                   "notify": f"notify.{DOMAIN}_{aparelho.alvo_notify}"})


@websocket_api.websocket_command({vol.Required("type"): "ha_access/vivo", vol.Required("serial"): SERIAL})
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
    vol.Required("serial"): SERIAL,
    vol.Required("sensores"): SENSORES,
    vol.Required("comandos"): COMANDOS,
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
    vol.Required("serial"): SERIAL,
    vol.Optional("sensores", default={}): vol.All({ID_ITEM: dict}, vol.Length(max=ITENS_MAX)),
    vol.Optional("comandos", default={}): vol.All({ID_ITEM: bool}, vol.Length(max=ITENS_MAX)),
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
    vol.Required("serial"): SERIAL,
    vol.Required("estado"): dict,
    vol.Optional("capa"): vol.Any(vol.All(str, vol.Length(max=CAPA_MAX)), None),
})
@callback
def ws_midia(hass, connection, msg):
    hub = _hub(hass, connection, msg)
    if hub is None:
        return
    capa = ...
    if "capa" in msg:
        try:
            capa = base64.b64decode(msg["capa"], validate=True) if msg["capa"] else None
        except (binascii.Error, ValueError):
            capa = None
    hub.midia(msg["serial"], msg["estado"], capa)
    connection.send_result(msg["id"])


@websocket_api.websocket_command({
    vol.Required("type"): "ha_access/acao_notificacao",
    vol.Required("serial"): SERIAL,
    vol.Required("action"): vol.All(str, vol.Length(min=1, max=TEXTO_MAX)),
    vol.Optional("input", default=""): vol.All(str, vol.Length(max=4096)),
    vol.Optional("uri", default=""): vol.All(str, vol.Length(max=2048)),
})
@callback
def ws_acao_notificacao(hass, connection, msg):
    hub = _hub(hass, connection, msg)
    if hub is None:
        return
    ap = hub.aparelhos[msg["serial"]]
    hass.bus.async_fire(EVENTO_ACAO, {
        "serial": msg["serial"], "device_id": ap.device_id,
        "device_name": ap.nome, "action": msg["action"], "input": msg["input"], "uri": msg["uri"],
    }, context=connection.context(msg))
    connection.send_result(msg["id"])


@websocket_api.websocket_command({
    vol.Required("type"): "ha_access/tag",
    vol.Required("serial"): SERIAL,
    vol.Required("uid"): vol.All(str, vol.Length(min=1, max=TEXTO_MAX)),
})
@websocket_api.async_response
async def ws_tag(hass, connection, msg):
    hub = _hub(hass, connection, msg)
    if hub is None:
        return
    from homeassistant.components.tag import async_scan_tag
    ap = hub.aparelhos[msg["serial"]]
    await async_scan_tag(hass, msg["uid"], ap.device_id, connection.context(msg))
    connection.send_result(msg["id"])
