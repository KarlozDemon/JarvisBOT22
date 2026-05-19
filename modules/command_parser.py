"""
JARVIS Bot — Parser de Comandos por Voz (COMPLETO)
60+ comandos de administración de Discord en español.
"""
import re
from difflib import get_close_matches
from datetime import datetime
import pytz
import config

COMMAND_PATTERNS = {
    # ==================== USUARIOS: VOZ ====================
    "mute": [r"(?:mutea|silencia|calla|mute)\s+a?\s*(.+)"],
    "unmute": [r"(?:desmutea|dessilencia|unmute|desmute)\s+a?\s*(.+)"],
    "deafen": [r"(?:ensordece|deafen|sordo)\s+a?\s*(.+)"],
    "undeafen": [r"(?:desensordece|undeafen)\s+a?\s*(.+)"],
    "disconnect_user": [r"(?:desconecta|saca\s+de\s+voz|quita\s+de\s+voz|desconectar)\s+a?\s*(.+)"],
    "move": [r"(?:mueve|pasa|lleva|manda|transfiere)\s+a?\s*(.+?)\s+(?:a|al|hacia|para)\s+(?:el\s+)?(?:canal\s+)?(.+)"],

    # ==================== USUARIOS: MODERACIÓN ====================
    "kick": [r"(?:kickea|saca|expulsa|echa|kick|bota)\s+a?\s*(.+?)(?:\s+del\s+(?:servidor|server))?$"],
    "ban": [r"(?:banea|ban|proh[ií]be|veta)\s+a?\s*(.+?)(?:\s+del\s+(?:servidor|server))?$"],
    "unban": [r"(?:desbanea|unban|perdona|levanta\s+(?:el\s+)?ban)\s+a?\s*(.+)"],
    "timeout": [r"(?:timeout|castiga|silencia\s+temporalmente?|pon\s+timeout)\s+a?\s*(.+?)\s+(?:por\s+)?(\d+)\s*(?:minutos?|mins?|m)", r"(?:timeout|castiga)\s+a?\s*(.+)"],
    "untimeout": [r"(?:quita\s+(?:el\s+)?timeout|quita\s+(?:el\s+)?castigo|libera|untimeout)\s+a?\s*(.+)"],
    "warn": [r"(?:advierte|avisa|warn|alerta)\s+a?\s*(.+?)(?:\s+(?:que|por)\s+(.+))?$"],
    "dm": [r"(?:manda|env[ií]a|escr[ií]be)\s+(?:un\s+)?(?:mensaje|dm|privado)\s+a\s+(.+?)\s+(?:que\s+diga|diciendo|con)\s+(.+)"],

    # ==================== USUARIOS: INFO ====================
    "user_info": [r"(?:info|informaci[oó]n|datos)\s+(?:de|del|sobre)\s+(?:el\s+)?(?:usuario\s+)?(.+)", r"(?:qui[eé]n\s+es|dime\s+sobre)\s+(.+)"],
    "avatar": [r"(?:avatar|foto|imagen)\s+(?:de|del)\s+(.+)", r"(?:mu[eé]stra|ense[ñn]a)\s+(?:el\s+)?avatar\s+(?:de\s+)?(.+)"],

    # ==================== USUARIOS: MASIVOS ====================
    "mute_all": [r"(?:mutea|silencia|calla)\s+a?\s*(?:todos|all|a\s+todos)"],
    "unmute_all": [r"(?:desmutea|dessilencia)\s+a?\s*(?:todos|all|a\s+todos)"],
    "deafen_all": [r"(?:ensordece)\s+a?\s*(?:todos|all|a\s+todos)"],
    "undeafen_all": [r"(?:desensordece)\s+a?\s*(?:todos|all|a\s+todos)"],
    "disconnect_all": [r"(?:desconecta|saca)\s+a?\s*(?:todos|all|a\s+todos)\s*(?:de\s+voz)?"],
    "move_all": [r"(?:mueve|pasa|lleva)\s+a?\s*(?:todos|all|a\s+todos)\s+(?:a|al|hacia)\s+(?:el\s+)?(?:canal\s+)?(.+)"],

    # ==================== APODOS ====================
    "change_nickname": [r"(?:cambia|pon|c[aá]mbiale)\s+(?:el\s+)?(?:nombre|nick|apodo)\s+(?:de\s+)?(.+?)\s+(?:a|por)\s+(.+)"],
    "reset_nickname": [r"(?:resetea|restablece|quita)\s+(?:el\s+)?(?:nombre|nick|apodo)\s+(?:de\s+)?(.+)"],

    # ==================== CANALES: CREAR/ELIMINAR ====================
    "create_voice_channel": [r"(?:crea|crear|haz|hazme)\s+(?:un\s+)?canal\s+(?:de\s+)?voz\s+(?:llamado\s+|que\s+se\s+llame\s+)?(.+)", r"(?:crea|crear|haz)\s+(?:un\s+)?(?:canal\s+)?(?:de\s+voz\s+)?(?:llamado\s+)?(.+)"],
    "create_text_channel": [r"(?:crea|crear|haz)\s+(?:un\s+)?canal\s+(?:de\s+)?texto\s+(?:llamado\s+|que\s+se\s+llame\s+)?(.+)"],
    "delete_channel": [r"(?:elimina|borra|destruye|delete)\s+(?:el\s+)?(?:canal\s+)?(.+)"],
    "create_category": [r"(?:crea|crear|haz)\s+(?:una?\s+)?categor[ií]a\s+(?:llamada?\s+|que\s+se\s+llame\s+)?(.+)"],

    # ==================== CANALES: MODIFICAR ====================
    "rename_channel": [r"(?:renombra|cambia\s+(?:el\s+)?nombre)\s+(?:del?\s+)?(?:canal\s+)?(.+?)\s+(?:a|por)\s+(.+)"],
    "lock_channel": [r"(?:bloquea|cierra|lock)\s+(?:el\s+)?(?:canal\s+)?(.+)?"],
    "unlock_channel": [r"(?:desbloquea|abre|unlock)\s+(?:el\s+)?(?:canal\s+)?(.+)?"],
    "hide_channel": [r"(?:oculta|esconde|hide)\s+(?:el\s+)?(?:canal\s+)?(.+)?"],
    "unhide_channel": [r"(?:muestra|desoculta|unhide|revela)\s+(?:el\s+)?(?:canal\s+)?(.+)?"],
    "set_topic": [r"(?:pon|cambia|establece)\s+(?:el\s+)?(?:tema|topic|descripci[oó]n)\s+(?:del?\s+)?(?:canal\s+)?(?:a\s+)?(.+)"],
    "set_user_limit": [r"(?:pon|establece|limita)\s+(?:el\s+)?l[ií]mite\s+(?:de\s+)?(?:usuarios?\s+)?(?:a|en|de)\s+(\d+)(?:\s+en\s+(?:el\s+)?(?:canal\s+)?(.+))?"],
    "set_bitrate": [r"(?:pon|cambia|establece)\s+(?:el\s+)?bitrate\s+(?:a|en)\s+(\d+)(?:\s+en\s+(.+))?"],
    "list_channels": [r"(?:lista|mu[eé]stra|dime)\s+(?:los\s+)?canales"],
    "channel_info": [r"(?:info|informaci[oó]n|datos)\s+(?:del?\s+)?(?:canal\s+)?(.+)"],

    # ==================== ROLES ====================
    "add_role": [r"(?:dale|asigna|pon|ponle)\s+(?:el\s+)?rol\s+(.+?)\s+a\s+(.+)", r"(?:asigna|dale)\s+a\s+(.+?)\s+(?:el\s+)?rol\s+(?:de\s+)?(.+)"],
    "remove_role": [r"(?:quita|remueve|elimina|saca)\s+(?:el\s+)?rol\s+(.+?)\s+(?:a|de)\s+(.+)"],
    "create_role": [r"(?:crea|crear|haz)\s+(?:un\s+)?(?:el\s+)?rol\s+(?:llamado\s+|que\s+se\s+llame\s+)?(.+)"],
    "delete_role": [r"(?:elimina|borra|destruye)\s+(?:el\s+)?rol\s+(.+)"],
    "role_color": [r"(?:cambia|pon)\s+(?:el\s+)?color\s+(?:del?\s+)?rol\s+(.+?)\s+(?:a|por)\s+(.+)"],
    "role_info": [r"(?:info|informaci[oó]n)\s+(?:del?\s+)?rol\s+(.+)"],
    "list_roles": [r"(?:lista|mu[eé]stra|dime)\s+(?:los\s+)?roles"],

    # ==================== MENSAJES ====================
    "purge_messages": [r"(?:borra|elimina|limpia)\s+(\d+)\s+mensajes?", r"(?:borra|elimina|limpia)\s+mensajes?\s+(\d+)"],
    "slowmode": [r"(?:pon|activa|establece)\s+(?:el\s+)?(?:modo\s+lento|slowmode)\s+(?:en\s+)?(\d+)\s*(?:segundos?)?", r"(?:quita|desactiva|saca)\s+(?:el\s+)?(?:modo\s+lento|slowmode)"],
    "say": [r"(?:di|repite|anuncia|proclama|lee)\s+(.+)", r"(?:di\s+en\s+voz\s+alta|anuncia\s+que)\s+(.+)"],
    "announce": [r"(?:haz\s+(?:un\s+)?anuncio|publica|escribe\s+en\s+(?:el\s+)?chat)\s+(?:que\s+diga\s+)?(.+)"],

    # ==================== SERVIDOR ====================
    "server_info": [r"(?:info|informaci[oó]n|datos|estad[ií]sticas|stats)\s+(?:del?\s+)?(?:servidor|server)", r"(?:dime|dame|mu[eé]stra)\s+(?:info|datos)\s+(?:del?\s+)?(?:servidor|server)"],
    "list_bans": [r"(?:lista|mu[eé]stra|dime)\s+(?:los\s+)?(?:baneados|bans|baneos)"],
    "create_invite": [r"(?:crea|genera|haz|dame)\s+(?:una?\s+)?(?:invitaci[oó]n|invite|link)"],
    "set_server_name": [r"(?:cambia|pon)\s+(?:el\s+)?nombre\s+(?:del?\s+)?(?:servidor|server)\s+(?:a|por)\s+(.+)"],
    "set_afk_channel": [r"(?:pon|establece|cambia)\s+(?:el\s+)?(?:canal\s+)?afk\s+(?:a|en)\s+(.+)"],
    "set_afk_timeout": [r"(?:pon|establece)\s+(?:el\s+)?timeout\s+afk\s+(?:a|en)\s+(\d+)\s*(?:minutos?|mins?|segundos?|segs?)?"],
    "set_verification": [r"(?:pon|establece|cambia)\s+(?:el\s+)?(?:nivel\s+(?:de\s+)?)?verificaci[oó]n\s+(?:a|en)\s+(\w+)"],

    # ==================== EMOJIS ====================
    "list_emojis": [r"(?:lista|mu[eé]stra|dime)\s+(?:los\s+)?emojis?"],
    "delete_emoji": [r"(?:elimina|borra|quita)\s+(?:el\s+)?emoji\s+(.+)"],

    # ==================== BOT SELF ====================
    "bot_status": [r"(?:cambia|pon|establece)\s+(?:tu\s+)?(?:estado|status)\s+(?:a|en|como)\s+(.+)"],
    "bot_nick": [r"(?:cambia|pon)\s+(?:tu\s+)?(?:nombre|nick|apodo)\s+(?:a|por)\s+(.+)"],
    "set_volume": [r"(?:pon|cambia|sube|baja)\s+(?:el\s+)?volumen\s+(?:a|en|al)?\s*(\d+)"],
    "change_voice": [r"(?:cambia|pon)\s+(?:tu\s+)?(?:voz|voice)\s+(?:a\s+)?(?:masculina|femenina|hombre|mujer)"],

    # ==================== INFO / CONSULTAS ====================
    "list_connected": [r"(?:qui[eé]ne?s?)\s+(?:est[aá]n?)\s+(?:conectad|en\s+(?:el\s+)?(?:canal|voz))", r"(?:lista|dime|mu[eé]stra)\s+(?:los?\s+)?(?:conectados|usuarios|miembros)", r"qui[eé]n\s+(?:hay|est[aá])\s+(?:aqu[ií]|en\s+(?:el\s+)?canal)"],
    "count_members": [r"(?:cu[aá]ntos)\s+(?:somos|hay|est[aá]n|son|miembros)", r"(?:cantidad|n[uú]mero)\s+(?:de\s+)?(?:usuarios|miembros|personas)"],
    "time": [r"(?:qu[eé])\s+hora\s+(?:es|son)", r"(?:dime|dame)\s+la\s+hora", r"hora\s+(?:actual|es)"],
    "uptime": [r"(?:cu[aá]nto\s+(?:llevas|tienes)|uptime|tiempo\s+(?:en\s+)?l[ií]nea|desde\s+cu[aá]ndo\s+est[aá]s)"],
    "ping": [r"(?:ping|latencia|velocidad)"],
    "random_user": [r"(?:elige|escoge|selecciona|random)\s+(?:un?\s+)?(?:usuario|persona|miembro)\s+(?:al\s+)?(?:azar|random|aleatorio)?", r"(?:qui[eé]n\s+(?:va|le\s+toca|sigue)|al\s+azar)"],

    # ==================== EVENTOS ====================
    "create_event": [r"(?:crea|crear|programa)\s+(?:un\s+)?evento\s+(?:llamado\s+)?(.+?)\s+(?:para|el|a\s+las?)\s+(.+)"],
    "list_events": [r"(?:lista|mu[eé]stra|dime)\s+(?:los\s+)?eventos"],

    # ==================== THREADS ====================
    "create_thread": [r"(?:crea|crear|abre)\s+(?:un\s+)?(?:hilo|thread)\s+(?:llamado\s+|que\s+se\s+llame\s+)?(.+)"],

    # ==================== HELP ====================
    "help": [r"(?:ayuda|help|comandos|qu[eé]\s+(?:puedes|sabes)\s+hacer)", r"(?:qu[eé]\s+comandos\s+(?:tienes|hay))", r"(?:lista\s+(?:de\s+)?comandos)"],
}


def parse_command(text: str) -> dict | None:
    text = text.strip().lower()
    for alias in [config.ACTIVATION_WORD] + config.ACTIVATION_ALIASES:
        if text.startswith(alias):
            text = text[len(alias):].strip().lstrip(",.:;!¡¿? ")
            break
    if not text:
        return {"action": "greeting", "params": {}, "raw": text}

    for action, patterns in COMMAND_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                params = _extract_params(action, match.groups(), text)
                return {"action": action, "params": params, "raw": text}

    return {"action": "conversation", "params": {"text": text}, "raw": text}


def _extract_params(action: str, groups: tuple, raw: str) -> dict:
    p = {}
    # Single target commands
    single_target = ("mute", "unmute", "deafen", "undeafen", "kick", "ban",
                     "unban", "disconnect_user", "untimeout", "reset_nickname",
                     "user_info", "avatar")
    if action in single_target:
        p["target_name"] = groups[0].strip() if groups else ""

    elif action == "timeout":
        p["target_name"] = groups[0].strip() if groups else ""
        p["minutes"] = int(groups[1]) if len(groups) > 1 and groups[1] else 5

    elif action == "warn":
        p["target_name"] = groups[0].strip() if groups else ""
        p["reason"] = groups[1].strip() if len(groups) > 1 and groups[1] else "Comportamiento inadecuado"

    elif action == "dm":
        p["target_name"] = groups[0].strip() if groups else ""
        p["message"] = groups[1].strip() if len(groups) > 1 else ""

    elif action == "move":
        p["target_name"] = groups[0].strip() if len(groups) > 0 else ""
        p["channel_name"] = groups[1].strip() if len(groups) > 1 else ""

    elif action in ("create_voice_channel", "create_text_channel", "create_category",
                     "delete_channel", "create_role", "delete_role", "create_thread"):
        p["name"] = groups[0].strip() if groups else ""

    elif action == "add_role":
        p["role_name"] = groups[0].strip() if len(groups) > 0 else ""
        p["target_name"] = groups[1].strip() if len(groups) > 1 else ""

    elif action == "remove_role":
        p["role_name"] = groups[0].strip() if len(groups) > 0 else ""
        p["target_name"] = groups[1].strip() if len(groups) > 1 else ""

    elif action in ("change_nickname", "rename_channel", "role_color"):
        p["target_name"] = groups[0].strip() if len(groups) > 0 else ""
        p["new_value"] = groups[1].strip() if len(groups) > 1 else ""

    elif action == "purge_messages":
        try:
            p["count"] = int(groups[0]) if groups else 10
        except ValueError:
            p["count"] = 10

    elif action == "slowmode":
        if groups and groups[0]:
            try:
                p["seconds"] = int(groups[0])
            except ValueError:
                p["seconds"] = 0
        else:
            p["seconds"] = 0

    elif action in ("say", "announce", "bot_status", "bot_nick"):
        p["text"] = groups[0].strip() if groups else ""

    elif action == "set_volume":
        try:
            p["volume"] = int(groups[0]) if groups else 100
        except ValueError:
            p["volume"] = 100

    elif action == "change_voice":
        p["voice"] = "female" if any(w in raw for w in ("femenina", "mujer")) else "male"

    elif action in ("lock_channel", "unlock_channel", "hide_channel", "unhide_channel"):
        p["channel_name"] = groups[0].strip() if groups and groups[0] else ""

    elif action == "set_topic":
        p["topic"] = groups[0].strip() if groups else ""

    elif action == "set_user_limit":
        p["limit"] = int(groups[0]) if groups else 0
        p["channel_name"] = groups[1].strip() if len(groups) > 1 and groups[1] else ""

    elif action == "set_bitrate":
        p["bitrate"] = int(groups[0]) * 1000 if groups else 64000
        p["channel_name"] = groups[1].strip() if len(groups) > 1 and groups[1] else ""

    elif action == "move_all":
        p["channel_name"] = groups[0].strip() if groups else ""

    elif action == "set_server_name":
        p["name"] = groups[0].strip() if groups else ""

    elif action in ("set_afk_channel", "channel_info", "role_info", "delete_emoji"):
        p["name"] = groups[0].strip() if groups else ""

    elif action == "set_afk_timeout":
        try:
            p["timeout"] = int(groups[0]) * 60 if groups else 300
        except ValueError:
            p["timeout"] = 300

    elif action == "set_verification":
        p["level"] = groups[0].strip() if groups else "medium"

    elif action == "create_event":
        p["name"] = groups[0].strip() if groups else ""
        p["time"] = groups[1].strip() if len(groups) > 1 else ""

    return p


# ========================== UTILIDADES DE BÚSQUEDA ================

def find_member(guild, name_query: str):
    if not name_query:
        return None
    name_query = name_query.strip().lower()
    members = {m.display_name.lower(): m for m in guild.members if not m.bot}

    if name_query in members:
        return members[name_query]
    for name, member in members.items():
        if name_query in name or name in name_query:
            return member
    matches = get_close_matches(name_query, members.keys(), n=1, cutoff=0.4)
    return members[matches[0]] if matches else None


def find_channel(guild, name_query: str, channel_type=None):
    if not name_query:
        return None
    name_query = name_query.strip().lower()
    channels = {}
    for ch in guild.channels:
        if channel_type and ch.type != channel_type:
            continue
        channels[ch.name.lower()] = ch

    if name_query in channels:
        return channels[name_query]
    for name, ch in channels.items():
        if name_query in name or name in name_query:
            return ch
    matches = get_close_matches(name_query, channels.keys(), n=1, cutoff=0.4)
    return channels[matches[0]] if matches else None


def find_role(guild, name_query: str):
    if not name_query:
        return None
    name_query = name_query.strip().lower()
    roles = {r.name.lower(): r for r in guild.roles if r.name != "@everyone"}

    if name_query in roles:
        return roles[name_query]
    for name, role in roles.items():
        if name_query in name or name in name_query:
            return role
    matches = get_close_matches(name_query, roles.keys(), n=1, cutoff=0.4)
    return roles[matches[0]] if matches else None


def get_time_response() -> str:
    ahora = datetime.now(pytz.timezone(config.TIMEZONE))
    hora = ahora.strftime("%I:%M %p")
    fecha = ahora.strftime("%A %d de %B")
    return f"Son las {hora}, {fecha}, señor."
