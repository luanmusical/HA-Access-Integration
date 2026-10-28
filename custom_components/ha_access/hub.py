"""
O "centro" da integração: os computadores conhecidos (aparelhos), o que cada
um tem (sensores, comandos, player de mídia), os valores atuais e a ligação
com o programa (a assinatura ha_access/conectar).

As definições ficam gravadas (.storage/ha_access): depois de reiniciar o HA as
entidades voltam na hora, indisponíveis até o computador conectar.
"""

from __future__ import annotations

import logging
import time

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import slugify

from .const import (DOMAIN, FABRICANTE, ID_CONECTADO, ID_NOTIFICACAO, PLATAFORMAS_COMANDO, PLATAFORMAS_SENSOR,
                    SINAL_MAXIMO, VERSAO_STORE)

_LOGGER = logging.getLogger(__name__)


def sinal_novas(plataforma):
    return f"{DOMAIN}_novas_{plataforma}"


class Aparelho:
    def __init__(self, serial, info):
        self.serial = serial
        self.info = info                  # nome, modelo, versao, notificacoes, media_player, sensores, comandos
        self.device_id = None
        self.enviar = None                # função que manda um evento ao programa (None = desconectado)
        self.valores = {}                 # id do sensor -> {"estado", "atributos"}
        self.comandos_ligados = {}        # id do comando -> bool
        self.midia = {}
        self.capa = None
        self.entidades = {}               # (plataforma, id) -> entidade
        self.media_player = None
        self.usuario = None
        self.ultimo_sinal = 0.0           # hora (monotonic) da última mensagem do programa

    @property
    def nome(self):
        return self.info.get("nome", self.serial)

    @property
    def alvo_notify(self):
        return slugify(self.nome)

    @property
    def conectado(self):
        return self.enviar is not None

    def mandar(self, dados):
        if self.enviar is None:
            return False
        self.enviar(dados)
        return True

    def avisar_entidades(self):
        for ent in list(self.entidades.values()):
            if ent.hass is not None:
                ent.async_write_ha_state()
        if self.media_player is not None and self.media_player.hass is not None:
            self.media_player.async_write_ha_state()


class Hub:
    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry
        self.aparelhos: dict[str, Aparelho] = {}
        self._store = Store(hass, VERSAO_STORE, DOMAIN)
        self.notify = None                # serviço de notificação (notify.py) para atualizar os alvos

    # -- gravação ---------------------------------------------------------------------
    async def carregar(self):
        dados = await self._store.async_load() or {}
        for serial, info in (dados.get("aparelhos") or {}).items():
            ap = Aparelho(serial, info)
            ap.device_id = self._registrar_aparelho(ap)
            self.aparelhos[serial] = ap

    @callback
    def _gravar(self):
        self._store.async_delay_save(
            lambda: {"aparelhos": {s: a.info for s, a in self.aparelhos.items()}}, 2)

    # -- aparelho -------------------------------------------------------------------------
    def _registrar_aparelho(self, ap):
        d = dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.entry.entry_id, identifiers={(DOMAIN, ap.serial)},
            name=ap.nome, manufacturer=FABRICANTE, model=ap.info.get("modelo") or "Windows",
            sw_version=ap.info.get("versao") or None)
        return d.id

    def definicoes(self, plataforma):
        """[(aparelho, definição)] de uma plataforma, para criar as entidades."""
        return [(ap, d) for ap in self.aparelhos.values() for d in self._defs(ap, plataforma)]

    # -- quem pode falar por um computador ------------------------------------------------
    def autorizado(self, serial, usuario, admin):
        """O computador fica preso ao usuário que o apresentou primeiro ("dono"); administradores
        podem tudo. Assim um usuário não se passa pelo computador de outro."""
        ap = self.aparelhos.get(serial)
        if ap is None:
            return False
        dono = ap.info.get("dono")
        return admin or dono is None or dono == usuario

    @callback
    def sinal(self, serial):
        ap = self.aparelhos.get(serial)
        if ap is not None:
            ap.ultimo_sinal = time.monotonic()

    @callback
    def vigiar(self, _agora=None):
        """Rede caiu "muda" (sem fechar a conexão): sem sinal por SINAL_MAXIMO, fica indisponível."""
        limite = time.monotonic() - SINAL_MAXIMO
        for ap in self.aparelhos.values():
            if ap.enviar is not None and ap.ultimo_sinal < limite:
                _LOGGER.info("%s sem sinal há mais de %s s: indisponível", ap.nome, SINAL_MAXIMO)
                ap.enviar = None
                ap.avisar_entidades()

    async def conectar(self, msg, enviar, usuario, admin=False):
        serial = msg["serial"]
        novo_info = {k: msg[k] for k in ("nome", "modelo", "versao", "notificacoes", "media_player",
                                          "sensores", "comandos")}
        ap = self.aparelhos.get(serial)
        if ap is not None and not self.autorizado(serial, usuario, admin):
            raise PermissionError(ap.nome)
        novo_info["dono"] = (ap.info.get("dono") if ap is not None else None) or usuario
        antes = set()
        if ap is None:
            ap = Aparelho(serial, novo_info)
            self.aparelhos[serial] = ap
        else:
            antes = self._chaves(ap.info)
            if not msg.get("completo", True):
                # o computador ainda não anunciou tudo: só acrescenta (nada some por pressa)
                for lista in ("sensores", "comandos"):
                    novos = {d["id"] for d in novo_info[lista]}
                    novo_info[lista] = novo_info[lista] + [d for d in ap.info.get(lista, []) if d["id"] not in novos]
            ap.info = novo_info
        ap.device_id = self._registrar_aparelho(ap)
        if ap.enviar is not None and ap.enviar is not enviar:
            # outra conexão do mesmo computador (reconectou antes da antiga cair)
            ap.enviar({"tipo": "substituido"})
        ap.enviar = enviar
        ap.usuario = usuario
        ap.ultimo_sinal = time.monotonic()
        depois = self._chaves(ap.info)
        self._remover_entidades(ap, antes - depois)
        self._novas(ap, depois - antes)
        self._gravar()
        ap.avisar_entidades()
        if self.notify is not None:
            await self.notify.async_register_services()
        return ap

    async def definir(self, serial, sensores, comandos):
        ap = self.aparelhos.get(serial)
        if ap is None:
            return False
        antes = self._chaves(ap.info)
        ap.info = dict(ap.info, sensores=sensores, comandos=comandos)
        depois = self._chaves(ap.info)
        self._remover_entidades(ap, antes - depois)
        self._novas(ap, depois - antes)
        self._gravar()
        return True

    def _novas(self, ap, novas):
        for plataforma, chaves in self._por_plataforma(novas).items():
            async_dispatcher_send(self.hass, sinal_novas(plataforma),
                                  [(ap, d) for d in self._defs(ap, plataforma) if (plataforma, d["id"]) in chaves])

    @staticmethod
    def _defs(ap, plataforma):
        if plataforma == "binary_sensor":
            fixo = [{"id": ID_CONECTADO, "nome": "Conectado", "device_class": "connectivity",
                     "sempre_disponivel": True}]
            return fixo + [d for d in ap.info.get("sensores", []) if d.get("dominio", "sensor") == plataforma]
        if plataforma == "notify":
            return [{"id": ID_NOTIFICACAO, "nome": "Notificação"}] if ap.info.get("notificacoes", True) else []
        if plataforma in PLATAFORMAS_SENSOR:
            return [d for d in ap.info.get("sensores", []) if d.get("dominio", "sensor") == plataforma]
        if plataforma in PLATAFORMAS_COMANDO:
            return [d for d in ap.info.get("comandos", []) if d.get("dominio", "switch") == plataforma]
        if plataforma == "media_player" and ap.info.get("media_player"):
            return [{"id": "media_player"}]
        return []

    @staticmethod
    def _chaves(info):
        c = {("binary_sensor", ID_CONECTADO)}
        if info.get("notificacoes", True):
            c.add(("notify", ID_NOTIFICACAO))
        c |= {(d.get("dominio", "sensor"), d["id"]) for d in info.get("sensores", [])}
        c |= {(d.get("dominio", "switch"), d["id"]) for d in info.get("comandos", [])}
        if info.get("media_player"):
            c.add(("media_player", "media_player"))
        return c

    @staticmethod
    def _por_plataforma(chaves):
        saida = {}
        for plataforma, ident in chaves:
            saida.setdefault(plataforma, set()).add((plataforma, ident))
        return saida

    def _remover_entidades(self, ap, chaves):
        if not chaves:
            return
        reg = er.async_get(self.hass)
        for plataforma, ident in chaves:
            ent = ap.entidades.pop((plataforma, ident), None)
            if plataforma == "media_player":
                ap.media_player = None
            entity_id = reg.async_get_entity_id(plataforma, DOMAIN, f"{ap.serial}_{ident}")
            if entity_id:
                reg.async_remove(entity_id)
            elif ent is not None and ent.hass is not None:
                self.hass.async_create_task(ent.async_remove())

    @callback
    def desconectar(self, serial, enviar):
        ap = self.aparelhos.get(serial)
        if ap is not None and ap.enviar is enviar:
            ap.enviar = None
            ap.avisar_entidades()

    def desligar_todos(self):
        for ap in self.aparelhos.values():
            ap.enviar = None

    async def esquecer(self, serial):
        ap = self.aparelhos.pop(serial, None)
        if ap is not None:
            ap.mandar({"tipo": "removido"})
            self._gravar()
            if self.notify is not None:
                await self.notify.async_register_services()

    # -- valores ----------------------------------------------------------------------------
    @callback
    def estados(self, serial, sensores, comandos):
        ap = self.aparelhos.get(serial)
        if ap is None:
            return
        ap.ultimo_sinal = time.monotonic()
        mudaram = []
        for ident, valor in sensores.items():
            if ap.valores.get(ident) != valor:
                ap.valores[ident] = valor
                mudaram += [e for (p, i), e in ap.entidades.items() if i == ident and p in PLATAFORMAS_SENSOR]
        for ident, ligado in comandos.items():
            if ap.comandos_ligados.get(ident) != ligado:
                ap.comandos_ligados[ident] = ligado
                mudaram += [e for (p, i), e in ap.entidades.items() if i == ident and p in PLATAFORMAS_COMANDO]
        for ent in mudaram:
            if ent.hass is not None:
                ent.async_write_ha_state()

    @callback
    def midia(self, serial, estado, capa):
        ap = self.aparelhos.get(serial)
        if ap is None:
            return
        ap.ultimo_sinal = time.monotonic()
        ap.midia = estado
        if capa is not ...:          # ... = a capa não mudou
            ap.capa = capa
        if ap.media_player is not None and ap.media_player.hass is not None:
            ap.media_player.async_write_ha_state()
