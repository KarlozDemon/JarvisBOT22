"""
JARVIS Bot — Sistema de Saludos Automáticos
Migrado y mejorado desde JarvisTeam1.py original.
"""
import random
import json
import threading
import unicodedata
from datetime import datetime
import pytz
import config


# ========================== BASE DE DATOS JSON ====================
_db = {}
_db_lock = threading.Lock()


def inicializar_db():
    global _db
    try:
        if config.DB_FILE.exists():
            with open(config.DB_FILE, 'r', encoding='utf-8') as f:
                _db = json.load(f)
            print("✅ JSON de usuarios cargado")
        else:
            _db = {}
            print("📝 JSON de usuarios creado")
    except Exception as e:
        print(f"⚠️ Error JSON: {e}")
        _db = {}


def guardar_db():
    global _db
    try:
        config.DATA_DIR.mkdir(exist_ok=True)
        with open(config.DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(_db, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Guardando JSON: {e}")


def obtener_veces(guild_id, user_id):
    with _db_lock:
        return _db.get(str(guild_id), {}).get(str(user_id), 0)


def incrementar_veces(guild_id, user_id):
    with _db_lock:
        g, u = str(guild_id), str(user_id)
        if g not in _db:
            _db[g] = {}
        _db[g][u] = _db[g].get(u, 0) + 1
        veces = _db[g][u]
        if veces % 5 == 0:
            guardar_db()
        return veces


# ========================== LIMPIEZA DE NOMBRES ===================
NOMBRES_ESPECIALES = {
    "josé is back": "José",
    "jᴏꜱᴇ ɪꜱ ʙᴀᴄᴋ": "José",
}


def limpiar_nombre(nombre):
    clave = nombre.lower()
    if clave in NOMBRES_ESPECIALES:
        return NOMBRES_ESPECIALES[clave]
    nombre = unicodedata.normalize('NFKC', nombre)
    limpio = ""
    for c in nombre:
        cat = unicodedata.category(c)
        if cat.startswith('L') or cat.startswith('N') or c.isspace():
            limpio += c
    limpio = ' '.join(w.capitalize() for w in limpio.split())
    return limpio if len(limpio) > 2 else "Invitado"


# ========================== FUNCIONES DE HORA =====================
def _ahora():
    return datetime.now(pytz.timezone(config.TIMEZONE))


def saludo_hora():
    hora = _ahora().hour
    if 5 <= hora < 12:
        return random.choice(["Buenos días", "¡Muy buenos días!", "¡Feliz mañana!"])
    elif 12 <= hora < 19:
        return random.choice(["Buenas tardes", "¡Excelente tarde!", "¡Feliz tarde!"])
    else:
        return random.choice(["Buenas noches", "¡Linda noche!", "¡Que descanses!"])


# ========================== FRASES ================================
frases_rapida = [
    "¡Vaya, {nombre}, eso sí fue una visita rápida!",
    "¡{nombre}, ni tiempo para hablar! ¡Hasta luego!",
    "¡{nombre}, entraste y saliste en un segundo!",
    "¡{nombre}, parpadeé y ya no estabas!",
    "¡{nombre}, ¿solo viniste a saludar? ¡Te fuiste!",
    "¡Eso sí fue llegar y salir, {nombre}!",
    "¡{nombre}, apenas llegaste y ya te vas!",
    "¡Te fuiste tan rápido como llegaste, {nombre}!",
]

frases_inicio_stream = [
    "¡{nombre} está transmitiendo, a mirar ese talento con aimbot!",
    "¡{nombre} está transmitiendo! Veremos cuántos kills hace hoy.",
    "¡Atención! {nombre} empezó el game en vivo, ¿Quién trae las palomitas?",
    "¡{nombre} compartiendo pantalla! Momento de juzgar su habilidad.",
    "¡Ahora veremos si {nombre} es antiguo o nuevo!",
]

frases_fin_stream = [
    "{nombre} apagó el stream, ¿será que perdió la partida?",
    "Fin de la transmisión de {nombre}. ¿GG o FF?",
    "¡Listo! {nombre} dejó de compartir, a esperar el próximo en vivo.",
    "{nombre} terminó el streaming, qué opinan, juega o no juega.",
    "¡Se acabó el espectáculo! {nombre} cortó transmisión.",
]


def frase_bienvenida(nombre, veces):
    saludo = saludo_hora()
    dia = _ahora().strftime("%A").lower()

    frases = []
    if dia == "monday":
        frases.append(f"¡{nombre}, feliz lunes! Empecemos la semana con energía.")
    elif dia == "friday":
        frases.append(f"¡{nombre}, ya es viernes! A relajarse.")
    elif dia == "sunday":
        frases.append(f"¡{nombre}, aprovecha este domingo para descansar!")

    if veces == 1:
        frases += [
            f"¡Bienvenido, {nombre}! Es tu primera vez hoy. {saludo}.",
            f"Hola, {nombre}. Primera vez aquí. {saludo} y disfruta.",
            f"¡Encantado de verte por primera vez, {nombre}! {saludo}.",
            f"¡Qué gusto recibirte, {nombre}! {saludo}.",
            f"¡Hola, {nombre}! Nos alegra mucho que estés aquí.",
            f"Un placer conocerte, {nombre}. Esperamos que la pases bien.",
            f"{nombre}, eres muy bienvenido en este lugar.",
            f"{nombre}, gracias por unirte. Esperamos que disfrutes.",
            f"¡Nos alegra contar contigo, {nombre}!",
        ]
    elif veces == 2:
        frases += [
            f"{nombre}, qué bueno verte de nuevo. Segunda vez hoy.",
            f"{nombre}, parece que te gustó estar aquí. ¡Bienvenido!",
            f"¡Bienvenido otra vez, {nombre}! Nos alegra verte de vuelta.",
            f"¡Nos volvemos a encontrar, {nombre}! {saludo}.",
            f"Re bienvenido, {nombre}! Ya es tu segunda vez hoy.",
            f"{nombre}, siempre es bueno verte por aquí.",
        ]
    elif veces == 3:
        frases += [
            f"¡{nombre}! Bienvenido otra vez.",
            f"{nombre}, esta es tu tercera visita hoy. ¡Eres muy activo!",
            f"Wow, {nombre}! Tercera vez aquí hoy. ¡Impresionante!",
            f"¡Tres veces en un día, {nombre}! Nos halaga tu presencia.",
            f"Tercera vez por aquí, {nombre}. ¡Eres de los nuestros!",
        ]
    else:
        frases += [
            f"{nombre}, ¿ya perdiste la cuenta? ¡{veces} veces hoy!",
            f"{nombre}, esta es tu visita número {veces} hoy. ¡Increíble!",
            f"{nombre}, parece que este canal es tu favorito. {veces} visitas hoy.",
            f"¡Qué alegría verte tantas veces, {nombre}!",
            f"{nombre}, tu energía es contagiosa. ¡Gracias por volver!",
        ]

    frases += [
        f"{nombre}, qué alegría tenerte aquí. {saludo}.",
        f"{nombre}, gracias por visitarnos hoy. ¡Bienvenido!",
        f"Siempre es un gusto saludarte, {nombre}.",
        f"¡{saludo}, {nombre}!",
        f"Bienvenido {nombre}, pásala genial.",
    ]
    return random.choice(frases)


def frase_despedida(nombre):
    saludo = saludo_hora()
    frases = [
        f"¡Nos vemos, {nombre}! Descansa. {saludo}.",
        f"¡Chau, {nombre}! {saludo} y pásala bien.",
        f"{nombre}, cuídate mucho. ¡Hasta la próxima! {saludo}.",
        f"¡{nombre}, vuelve pronto! {saludo}.",
        f"¡Hasta luego, {nombre}! {saludo} y éxitos.",
        f"¡Espero verte de nuevo pronto, {nombre}! {saludo}.",
        f"¡Ve tranquilo, {nombre}! Aquí te esperamos. {saludo}.",
        f"¡Nos vemos en la próxima, {nombre}! {saludo}.",
        f"¡Hasta la vista, {nombre}! {saludo}.",
        f"¡Fue un gusto compartir contigo, {nombre}! {saludo}.",
        f"Cuídate, {nombre}, y vuelve cuando quieras.",
        f"Gracias por tu compañía, {nombre}.",
        f"¡Hasta pronto, {nombre}!",
        f"Nos vemos pronto, {nombre}.",
    ]
    return random.choice(frases)
