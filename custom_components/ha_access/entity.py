"""Base das entidades e montagem das plataformas."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityCategory

from .const import DOMAIN, OPCAO_SO_DONO
from .hub import sinal_novas


async def montar(hass, entry, adicionar, plataforma, classe):
    """Cria as entidades conhecidas e as que chegarem quando um computador conectar."""
    hub = entry.runtime_data
    adicionar([classe(ap, d, plataforma) for ap, d in hub.definicoes(plataforma)])
    @callback          # sem isto o HA roda numa thread à parte e recusa criar as entidades
    def novas(itens):
        adicionar([classe(ap, d, plataforma) for ap, d in itens])

    entry.async_on_unload(async_dispatcher_connect(hass, sinal_novas(plataforma), novas))
    # (a ação ha_access.enviar_texto é registrada uma vez só, em __init__.async_setup)


class EntidadeHaAccess(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, aparelho, definicao, plataforma):
        self.ap = aparelho
        self.plataforma = plataforma
        self.ident = definicao["id"]
        self._attr_unique_id = f"{aparelho.serial}_{self.ident}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, aparelho.serial)})
        self.aplicar(definicao)

    def aplicar(self, d):
        """A definição que o computador mandou (também quando ela muda com a entidade já criada)."""
        self.d = d
        if not getattr(self, "_attr_translation_key", None):   # nome traduzido: vem do strings.json
            self._attr_name = d.get("nome")
        self._attr_icon = d.get("icone") or None
        if d.get("categoria"):
            try:
                self._attr_entity_category = EntityCategory(d["categoria"])
            except ValueError:
                pass

    @property
    def available(self):
        return self.ap.conectado or bool(self.d.get("sempre_disponivel"))

    async def async_added_to_hass(self):
        self.ap.entidades[(self.plataforma, self.ident)] = self

    async def async_will_remove_from_hass(self):
        if self.ap.entidades.get((self.plataforma, self.ident)) is self:
            self.ap.entidades.pop((self.plataforma, self.ident), None)

    async def _checar_dono(self, contexto=None, sempre=False):
        """Opção "só o dono controla" (ou sempre=True): usuário que não é administrador nem o dono do
        computador é recusado. Automação e script sem usuário passam (quem os criou foi um admin)."""
        contexto = contexto or self._context
        if not (sempre or self.ap_opcao(OPCAO_SO_DONO)):
            return
        if contexto is None or not contexto.user_id:
            return
        usuario = await self.hass.auth.async_get_user(contexto.user_id)
        if usuario is None or not (usuario.is_admin or usuario.id == self.ap.info.get("dono")):
            raise Unauthorized(context=contexto)

    def ap_opcao(self, chave):
        entrada = self.platform.config_entry if self.platform is not None else None
        return bool(entrada is not None and entrada.options.get(chave, False))


class ComandoHaAccess(EntidadeHaAccess):
    """Comando do computador: o HA manda, o programa executa e devolve o estado."""

    @property
    def ligado(self):
        return self.ap.comandos_ligados.get(self.ident)

    async def _mandar(self, acao, texto=None, contexto=None):
        await self._checar_dono(contexto, sempre=texto is not None)
        dados = {"tipo": "comando", "id": self.ident, "acao": acao}
        if texto is not None:
            dados["texto"] = texto
        if not self.ap.mandar(dados):
            raise HomeAssistantError(f"{self.ap.nome} está desconectado")

    async def async_enviar_texto(self, texto, contexto=None):
        """Texto livre: sempre só administrador ou o dono do computador (automação sem usuário também pode)."""
        await self._mandar("texto", texto, contexto)
