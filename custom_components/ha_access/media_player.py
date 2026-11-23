"""O que toca no computador, com controle e volume."""

from __future__ import annotations

from homeassistant.components import media_source
from homeassistant.components.media_player import (MediaPlayerEntity, MediaPlayerEntityFeature,
                                                   MediaPlayerState, MediaType, async_process_play_media_url)
from homeassistant.exceptions import HomeAssistantError

from .entity import EntidadeHaAccess, montar

_ESTADOS = {"playing": MediaPlayerState.PLAYING, "paused": MediaPlayerState.PAUSED,
            "idle": MediaPlayerState.IDLE, "off": MediaPlayerState.IDLE}


async def async_setup_entry(hass, entry, adicionar):
    await montar(hass, entry, adicionar, "media_player", PlayerHaAccess)


class PlayerHaAccess(EntidadeHaAccess, MediaPlayerEntity):
    _attr_media_content_type = MediaType.MUSIC
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PAUSE | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.VOLUME_SET | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.SEEK)

    def aplicar(self, definicao):
        super().aplicar(definicao)
        self._attr_name = None            # o player é o próprio computador

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.ap.media_player = self

    async def async_will_remove_from_hass(self):
        await super().async_will_remove_from_hass()
        if self.ap.media_player is self:
            self.ap.media_player = None

    @property
    def _m(self):
        return self.ap.midia or {}

    @property
    def state(self):
        return _ESTADOS.get(self._m.get("state"), MediaPlayerState.IDLE)

    @property
    def volume_level(self):
        v = self._m.get("volume")
        try:
            return None if v is None else max(0.0, min(1.0, float(v) / 100))
        except (TypeError, ValueError):
            return None

    @property
    def is_volume_muted(self):
        return self._m.get("muted")

    @property
    def media_title(self):
        return self._m.get("title")

    @property
    def media_artist(self):
        return self._m.get("artist")

    @property
    def media_album_name(self):
        return self._m.get("albumtitle")

    @property
    def media_album_artist(self):
        return self._m.get("albumartist")

    @property
    def media_duration(self):
        return self._m.get("duration") or None

    @property
    def media_position(self):
        return self._m.get("currentposition")

    @property
    def media_position_updated_at(self):
        return self.ap.midia_quando if self._m.get("currentposition") is not None else None

    @property
    def media_image_hash(self):
        return self.ap.capa_hash if self.ap.capa else None

    async def async_get_media_image(self):
        capa = self.ap.capa
        if not capa:
            return None, None
        if capa.startswith(b"\x89PNG"):
            return capa, "image/png"
        if capa[:4] == b"RIFF" and capa[8:12] == b"WEBP":
            return capa, "image/webp"
        return capa, "image/jpeg"

    async def _cmd(self, comando, dado=None):
        await self._checar_dono()
        dados = {"tipo": "midia", "command": comando}
        if dado is not None:
            dados["data"] = dado
        if not self.ap.mandar(dados):
            raise HomeAssistantError(f"{self.ap.nome} está desconectado")

    async def async_media_play(self):
        await self._cmd("play")

    async def async_media_pause(self):
        await self._cmd("pause")

    async def async_media_stop(self):
        await self._cmd("stop")

    async def async_media_next_track(self):
        await self._cmd("next")

    async def async_media_previous_track(self):
        await self._cmd("previous")

    async def async_set_volume_level(self, volume):
        await self._cmd("setvolume", round(volume * 100))

    async def async_mute_volume(self, mute):
        await self._cmd("mute", bool(mute))

    async def async_volume_up(self):
        await self._cmd("volumeup")

    async def async_volume_down(self):
        await self._cmd("volumedown")

    async def async_media_seek(self, position):
        await self._cmd("seek", position)

    async def async_play_media(self, media_type, media_id, **kwargs):
        if media_source.is_media_source_id(media_id):
            item = await media_source.async_resolve_media(self.hass, media_id, self.entity_id)
            media_id = item.url
        await self._cmd("playmedia", async_process_play_media_url(self.hass, media_id))
