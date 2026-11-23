"""
O "centro" da integração: os computadores conhecidos (aparelhos), o que cada
um tem (sensores, comandos, player de mídia), os valores atuais e a ligação
com o programa (a assinatura ha_access/conectar).

As definições ficam gravadas (.storage/ha_access): depois de reiniciar o HA as
entidades voltam na hora, indisponíveis até o computador conectar.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (APARELHOS_POR_USUARIO, ATRIBUTOS_MAX, DOMAIN, FABRICANTE, ID_CONECTADO, ID_NOTIFICACAO, PLATAFORMAS_COMANDO, PLATAFORMAS_SENSOR,
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
        self.midia_quando = None          # quando a posição da faixa chegou
        self.capa = None
        self.capa_hash = None
        self.mudo = False                 # conectado, mas sem sinal de vida há SINAL_MAXIMO (rede parada)
        self.entidades = {}               # (plataforma, id) -> entidade
        self.media_player = None
        self.usuario = None
        self.ultimo_sinal = 0.0           # hora (monotonic) da última mensagem do programa

    @property
    def nome(self):
        return self.info.get("nome", self.serial)

    @property
    def alvo_notify(self):
        # "alvo" gravado só quando o nome bate com o de outro computador (ver Hub._alvo_unico)
        return self.info.get("alvo") or slugify(self.nome)

    @property
    def conectado(self):
        return self.enviar is not None and not self.mudo

    def vivo(self):
        """Chegou mensagem do programa: está vivo (e volta a ficar disponível se estava mudo)."""
        self.ultimo_sinal = time.monotonic()
        if self.mudo:
            self.mudo = False
            _LOGGER.info("%s voltou a dar sinal", self.nome)
            self.avisar_entidades()

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

    def _dados(self):
        return {"aparelhos": {s: a.info for s, a in self.aparelhos.items()}}

    @callback
    def _gravar(self):
        self._store.async_delay_save(self._dados, 2)

    async def gravar_agora(self):
        """Ao descarregar: a gravação adiada (2 s) não pode se perder (recarregar logo depois de um
        computador conectar fazia a integração esquecê-lo)."""
        await self._store.async_save(self._dados())

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
        podem tudo. Assim um usuário não se passa pelo computador de outro. Computador
        desconhecido ou sem dono gravado: só administrador (o dono é gravado ao conectar)."""
        ap = self.aparelhos.get(serial)
        if ap is None or usuario is None:
            return False
        dono = ap.info.get("dono")
        return admin or (dono is not None and dono == usuario)

    def pode_conectar(self, serial, usuario, admin):
        """Conectar: computador novo ou do próprio usuário. Sem dono gravado (de antes de existir o dono):
        só administrador, senão o primeiro usuário qualquer que soubesse o serial ficava com ele."""
        if usuario is None:
            raise PermissionError("Conexão sem usuário do Home Assistant")
        ap = self.aparelhos.get(serial)
        if ap is None:
            if not admin and sum(1 for a in self.aparelhos.values()
                                 if a.info.get("dono") == usuario) >= APARELHOS_POR_USUARIO:
                raise PermissionError(f"Limite de {APARELHOS_POR_USUARIO} computadores por usuário atingido; "
                                      "exclua um computador antigo ou peça a um administrador")
            return
        if ap.info.get("dono") is None:
            if admin:
                return
            # (se um administrador conectasse, ele viraria o dono e o usuário de verdade ficaria de fora)
            raise PermissionError("Este computador foi cadastrado antes de existir dono no HA-Access. Peça a um "
                                  "administrador para excluir o dispositivo dele no Home Assistant; na próxima "
                                  "conexão ele entra de novo, já com você como dono")
        if self.autorizado(serial, usuario, admin):
            return
        raise PermissionError("Este computador pertence a outro usuário do Home Assistant")

    @callback
    def sinal(self, serial):
        """Sinal de vida. False: esta integração não tem a assinatura do computador (foi recarregada)."""
        ap = self.aparelhos.get(serial)
        if ap is None or ap.enviar is None:
            return False
        ap.vivo()
        return True

    @callback
    def vigiar(self, _agora=None):
        """Rede caiu "muda" (sem fechar a conexão): sem sinal por SINAL_MAXIMO, fica indisponível."""
        limite = time.monotonic() - SINAL_MAXIMO
        for ap in self.aparelhos.values():
            if ap.enviar is not None and not ap.mudo and ap.ultimo_sinal < limite:
                # fica indisponível, mas a assinatura continua: se a rede voltar, o próximo sinal de
                # vida devolve o computador (antes ficava indisponível até o programa reiniciar)
                _LOGGER.info("%s sem sinal há mais de %s s: indisponível", ap.nome, SINAL_MAXIMO)
                ap.mudo = True
                ap.avisar_entidades()

    async def conectar(self, msg, enviar, usuario, admin=False):
        serial = msg["serial"]
        novo_info = {k: msg[k] for k in ("nome", "modelo", "versao", "notificacoes", "media_player",
                                          "sensores", "comandos")}
        self.pode_conectar(serial, usuario, admin)          # PermissionError com o motivo
        ap = self.aparelhos.get(serial)
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
        self._alvo_unico(ap)
        ap.device_id = self._registrar_aparelho(ap)
        if ap.enviar is not None and ap.enviar is not enviar:
            # outra conexão do mesmo computador (reconectou antes da antiga cair)
            ap.enviar({"tipo": "substituido"})
        ap.enviar = enviar
        ap.mudo = False
        ap.usuario = usuario
        ap.ultimo_sinal = time.monotonic()
        depois = self._chaves(ap.info)
        self._remover_entidades(ap, antes - depois)
        self._novas(ap, depois - antes)
        self._atualizar_definicoes(ap)
        self._gravar()
        ap.avisar_entidades()
        if self.notify is not None:
            await self.notify.async_register_services()
        return ap

    def _alvo_unico(self, ap):
        """Dois computadores com o mesmo nome não podem dividir notify.ha_access_<nome>: senão quem
        desse ao seu computador o nome do de outra pessoa receberia as notificações dela. O que
        já tinha o nome fica com ele; o outro ganha um final com o começo do serial. Entre
        computadores do mesmo dono nada muda (o último conectado fica com o nome, como antes)."""
        ap.info.pop("alvo", None)
        base = slugify(ap.nome)
        dono = ap.info.get("dono")
        outros = {a.alvo_notify for s, a in self.aparelhos.items()
                  if s != ap.serial and a.info.get("dono") != dono}
        if base in outros:
            ap.info["alvo"] = f"{base}_{slugify(ap.serial)[:8]}"

    async def definir(self, serial, sensores, comandos):
        ap = self.aparelhos.get(serial)
        if ap is None:
            return False
        antes = self._chaves(ap.info)
        ap.info = dict(ap.info, sensores=sensores, comandos=comandos)
        depois = self._chaves(ap.info)
        self._remover_entidades(ap, antes - depois)
        self._novas(ap, depois - antes)
        self._atualizar_definicoes(ap)
        self._gravar()
        return True

    def _atualizar_definicoes(self, ap):
        """Sensor ou comando que continua, mas mudou (nome, unidade, ícone...): a entidade muda na hora,
        sem ser apagada (o nome e a área que o usuário deu no HA ficam)."""
        for (plataforma, ident), ent in list(ap.entidades.items()):
            for d in self._defs(ap, plataforma):
                if d["id"] == ident and d != ent.d:
                    ent.aplicar(d)
                    if ent.hass is not None:
                        ent.async_write_ha_state()

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
        """A integração vai descarregar (recarregar, atualizar): os programas conectam de novo."""
        for ap in self.aparelhos.values():
            try:
                ap.mandar({"tipo": "reconectar"})
            except Exception:
                pass
            ap.enviar = None

    async def esquecer(self, serial):
        ap = self.aparelhos.pop(serial, None)
        ir.async_delete_issue(self.hass, DOMAIN, f"versao_{serial}")
        ir.async_delete_issue(self.hass, DOMAIN, f"desatualizado_{serial}")
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
        ap.vivo()
        mudaram = []
        # só o que o computador declarou (um id inventado a cada mensagem enchia a memória)
        declarados = {d["id"] for d in ap.info.get("sensores", [])}
        cmds_declarados = {d["id"] for d in ap.info.get("comandos", [])}
        for ident, valor in sensores.items():
            if ident not in declarados:
                continue
            atributos = valor.get("atributos")
            if atributos:
                try:
                    grande = len(json.dumps(atributos, default=str)) > ATRIBUTOS_MAX
                except (TypeError, ValueError):
                    grande = True
                if grande:
                    valor = dict(valor, atributos=None)
            if ap.valores.get(ident) != valor:
                ap.valores[ident] = valor
                mudaram += [e for (p, i), e in ap.entidades.items() if i == ident and p in PLATAFORMAS_SENSOR]
        for ident, ligado in comandos.items():
            if ident not in cmds_declarados:
                continue
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
        ap.vivo()
        if estado:                   # programa antigo manda {} quando só a capa mudou: fica o que tocava
            ap.midia = estado
            ap.midia_quando = dt_util.utcnow()
        if capa is not ...:          # ... = a capa não mudou
            ap.capa = capa
            ap.capa_hash = hashlib.sha256(capa).hexdigest()[:16] if capa else None
        if ap.media_player is not None and ap.media_player.hass is not None:
            ap.media_player.async_write_ha_state()
