"""Constantes da integração HA-Access."""

DOMAIN = "ha_access"
FABRICANTE = "L-R Productions (HA-Access)"
VERSAO = "0.2.1"                 # igual ao manifest.json
VERSAO_STORE = 1
EVENTO_ACAO = "ha_access_notification_action"

# Versão do "idioma" entre o programa e a integração. Mudou o jeito de conversar: sobe o número.
# A integração aceita programas de PROTOCOLO_MINIMO até PROTOCOLO.
PROTOCOLO = 1
PROTOCOLO_MINIMO = 1

# Sem nenhuma mensagem do programa por esse tempo (segundos), o computador fica indisponível.
# O programa manda "ha_access/vivo" a cada 30 s.
SINAL_MAXIMO = 75

TEXTO_MAX = 255                  # nomes, versões, ids de etiqueta e de ação
ITENS_MAX = 500                  # sensores ou comandos de um computador
CAPA_MAX = 3_000_000             # capa do player em base64 (uns 2 MB de imagem)
APARELHOS_POR_USUARIO = 20       # computadores que um usuário comum pode apresentar (admin: sem limite)

ID_CONECTADO ="_conectado"      # sensor "Conectado" que todo computador ganha
ID_NOTIFICACAO = "_notificacao"  # entidade de notificação (formato novo) de cada computador

PLATAFORMAS_SENSOR = ("sensor", "binary_sensor")
PLATAFORMAS_COMANDO = ("switch", "button", "light", "lock", "siren")
PLATAFORMAS = ("sensor", "binary_sensor", "switch", "button", "light", "lock", "siren", "media_player", "notify")
