"""Constantes da integração HA-Access."""

DOMAIN = "ha_access"
FABRICANTE = "L-R Productions (HA-Access)"
VERSAO = "0.2.0"                 # igual ao manifest.json
VERSAO_STORE = 1
EVENTO_ACAO = "ha_access_notification_action"

# Versão do "idioma" entre o programa e a integração. Mudou o jeito de conversar: sobe o número.
# A integração aceita programas de PROTOCOLO_MINIMO até PROTOCOLO.
PROTOCOLO = 1
PROTOCOLO_MINIMO = 1

# Sem nenhuma mensagem do programa por esse tempo (segundos), o computador fica indisponível.
# O programa manda "ha_access/vivo" a cada 30 s.
SINAL_MAXIMO = 75

ID_CONECTADO = "_conectado"      # sensor "Conectado" que todo computador ganha
ID_NOTIFICACAO = "_notificacao"  # entidade de notificação (formato novo) de cada computador

PLATAFORMAS_SENSOR = ("sensor", "binary_sensor")
PLATAFORMAS_COMANDO = ("switch", "button", "light", "lock", "siren")
PLATAFORMAS = ("sensor", "binary_sensor", "switch", "button", "light", "lock", "siren", "media_player", "notify")
