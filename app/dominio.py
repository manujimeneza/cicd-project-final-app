"""Lógica de negocio de Kuadra. Funciones puras, sin dependencias externas."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

CATEGORIAS = (
    "Mercado",
    "Comida",
    "Transporte",
    "Hogar",
    "Servicios",
    "Salud",
    "Ropa",
    "Ocio",
    "Deudas",
    "Otros",
)
TIPOS = ("gasto", "ingreso", "retiro")
MEDIOS = ("Efectivo", "Débito", "Tarjeta de crédito", "Transferencia")
MESES_CORTOS = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")

@dataclass(frozen=True)
class Movimiento:
    fecha: date
    monto: int
    descripcion: str
    categoria: str
    medio: str
    tipo: str  # gasto | ingreso | retiro

@dataclass(frozen=True)
class GastoCompartido:
    fecha: date
    monto: int
    descripcion: str
    pagado_por: str
    dividido_entre: tuple[str, ...]

@dataclass(frozen=True)
class Pago:
    fecha: date
    de: str
    para: str
    monto: int

@dataclass(frozen=True)
class Deuda:
    nombre: str
    saldo: int
    tasa_ea: float
    cuota: int
    id: str = ""

@dataclass(frozen=True)
class Grupo:
    id: str
    nombre: str
    creador: str

@dataclass(frozen=True)
class GastoRecurrente:
    nombre: str
    monto: int
    categoria: str
    frecuencia: str
    dia: int
    activo: bool = True
    id: str = ""

@dataclass(frozen=True)
class MetaAhorro:
    nombre: str
    objetivo: int
    ahorrado: int
    fecha_objetivo: date
    id: str = ""


class DatoInvalido(ValueError):
    """Un dato ingresado por el usuario no es válido."""

# ---------- Validación ----------

def validar_movimiento(mov: Movimiento) -> Movimiento:
    if mov.monto <= 0:
        raise DatoInvalido("El monto debe ser mayor que cero.")
    if mov.tipo not in TIPOS:
        raise DatoInvalido("Tipo de movimiento no válido.")
    if mov.tipo == "gasto" and mov.categoria not in CATEGORIAS:
        raise DatoInvalido("Categoría no válida.")
    if not mov.descripcion.strip():
        raise DatoInvalido("La descripción es obligatoria.")
    return mov

def validar_gasto_compartido(gasto: GastoCompartido) -> GastoCompartido:
    if gasto.monto <= 0:
        raise DatoInvalido("El monto debe ser mayor que cero.")
    if not gasto.dividido_entre:
        raise DatoInvalido("El gasto debe dividirse entre al menos una persona.")
    if len(set(gasto.dividido_entre)) != len(gasto.dividido_entre):
        raise DatoInvalido("Hay personas repetidas en la división.")
    return gasto

def _correo_valido(correo: str) -> bool:
    """Validación lineal (sin expresiones regulares con backtracking)."""
    if len(correo) > 254 or any(c.isspace() for c in correo) or correo.count("@") != 1:
        return False
    usuario, dominio = correo.split("@")
    partes = dominio.split(".")
    return bool(usuario) and len(partes) >= 2 and all(partes)


def normalizar_correo(correo: str) -> str:
    correo = correo.strip().lower()
    if not _correo_valido(correo):
        raise DatoInvalido(f"Correo no válido: {correo or '(vacío)'}")
    return correo


def leer_correos(texto: str) -> list[str]:
    """Convierte 'a@x.com, b@y.com' (comas, espacios o saltos de línea) en una lista sin repetidos."""
    partes = [p for p in re.split(r"[\s,;]+", texto or "") if p]
    correos: list[str] = []
    for parte in partes:
        correo = normalizar_correo(parte)
        if correo not in correos:
            correos.append(correo)
    return correos


def validar_nombre(nombre: str, maximo: int = 40) -> str:
    nombre = " ".join((nombre or "").split())
    if not nombre:
        raise DatoInvalido("El nombre es obligatorio.")
    if len(nombre) > maximo:
        raise DatoInvalido(f"El nombre puede tener máximo {maximo} caracteres.")
    return nombre


def validar_deuda(deuda: Deuda) -> Deuda:
    validar_nombre(deuda.nombre)
    if deuda.saldo <= 0:
        raise DatoInvalido("El saldo debe ser mayor que cero.")
    if not 0 <= deuda.tasa_ea <= 200:
        raise DatoInvalido("La tasa efectiva anual debe estar entre 0% y 200%.")
    if deuda.cuota < 0:
        raise DatoInvalido("La cuota no puede ser negativa.")
    return deuda


def validar_topes(topes: dict[str, int]) -> dict[str, int]:
    """Solo categorías conocidas y montos >= 0; 0 o vacío significa sin tope."""
    limpios = {}
    for categoria, tope in topes.items():
        if categoria not in CATEGORIAS:
            raise DatoInvalido(f"Categoría no válida: {categoria}")
        if tope < 0:
            raise DatoInvalido("Los topes no pueden ser negativos.")
        if tope > 0:
            limpios[categoria] = tope
    return limpios


def validar_pago(pago: Pago, miembros: list[str]) -> Pago:
    if pago.monto <= 0:
        raise DatoInvalido("El monto debe ser mayor que cero.")
    if pago.de == pago.para:
        raise DatoInvalido("Quien paga y quien recibe deben ser personas distintas.")
    if pago.de not in miembros or pago.para not in miembros:
        raise DatoInvalido("Ambas personas deben ser del grupo.")
    return pago

def validar_gasto_recurrente(recurrente: GastoRecurrente) -> GastoRecurrente:
    validar_nombre(recurrente.nombre)
    if recurrente.monto <= 0:
        raise DatoInvalido("El monto debe ser mayor que cero.")
    if recurrente.categoria not in CATEGORIAS:
        raise DatoInvalido("Categoría no válida.")
    if recurrente.frecuencia not in ("Mensual", "Anual"):
        raise DatoInvalido("Frecuencia no válida.")
    if not 1 <= recurrente.dia <= 31:
        raise DatoInvalido("El día debe estar entre 1 y 31.")
    return recurrente

def validar_meta_ahorro(meta: MetaAhorro) -> MetaAhorro:
    validar_nombre(meta.nombre)
    if meta.objetivo <= 0:
        raise DatoInvalido("La meta debe ser mayor que cero.")
    if meta.ahorrado < 0:
        raise DatoInvalido("Lo ahorrado no puede ser negativo.")
    if meta.ahorrado > meta.objetivo:
        raise DatoInvalido("Lo ahorrado no puede superar la meta.")
    if meta.fecha_objetivo < date.today():
        raise DatoInvalido("La fecha objetivo debe ser igual o posterior a hoy.")
    return meta


FOTO_MAX_BYTES = 300 * 1024
FIRMAS_IMAGEN = ((b"\xff\xd8\xff", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "image/png"))


def tipo_de_imagen(datos: bytes) -> str:
    """Valida por contenido (no por extensión) que sea JPEG/PNG/WebP y de tamaño razonable."""
    if not datos:
        raise DatoInvalido("Selecciona una imagen.")
    if len(datos) > FOTO_MAX_BYTES:
        raise DatoInvalido("La foto es muy pesada (máximo 300 KB).")
    for firma, tipo in FIRMAS_IMAGEN:
        if datos.startswith(firma):
            return tipo
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "image/webp"
    raise DatoInvalido("La foto debe ser JPG, PNG o WebP.")


def primer_nombre(nombre: str | None) -> str:
    return (nombre or "").split(" ")[0]


# ---------- Personal ----------

def del_mes(movimientos: list[Movimiento], anio: int, mes: int) -> list[Movimiento]:
    return [m for m in movimientos if m.fecha.year == anio and m.fecha.month == mes]

def total(movimientos: list[Movimiento], tipo: str) -> int:
    return sum(m.monto for m in movimientos if m.tipo == tipo)

def gastos_por_categoria(movimientos: list[Movimiento]) -> dict[str, int]:
    """Total gastado por categoría, de mayor a menor. Los retiros no son gasto."""
    totales: dict[str, int] = defaultdict(int)
    for m in movimientos:
        if m.tipo == "gasto":
            totales[m.categoria] += m.monto
    return dict(sorted(totales.items(), key=lambda kv: kv[1], reverse=True))

def alertas_topes(por_categoria: dict[str, int], topes: dict[str, int]) -> list[dict]:
    """Categorías que superaron su tope mensual."""
    alertas = []
    for categoria, tope in topes.items():
        gastado = por_categoria.get(categoria, 0)
        if tope > 0 and gastado > tope:
            alertas.append({"categoria": categoria, "gastado": gastado, "tope": tope, "exceso": gastado - tope})
    return sorted(alertas, key=lambda a: a["exceso"], reverse=True)

def tendencia_mensual(movimientos: list[Movimiento], hasta: date, meses: int = 6) -> list[tuple[str, int]]:
    """Total de gastos de los últimos `meses` meses, terminando en `hasta`."""
    resultado = []
    anio, mes = hasta.year, hasta.month
    for _ in range(meses):
        resultado.append((MESES_CORTOS[mes - 1], total(del_mes(movimientos, anio, mes), "gasto")))
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
    return list(reversed(resultado))

DIAS_CORTOS = ("L", "M", "M", "J", "V", "S", "D")

def gastos_por_dia(movimientos: list[Movimiento], hasta: date, dias: int = 7) -> list[tuple[str, int]]:
    """Total de gastos de cada uno de los últimos `dias` días, terminando en `hasta`."""

    totales: dict[date, int] = defaultdict(int)
    for m in movimientos:
        if m.tipo == "gasto":
            totales[m.fecha] += m.monto
    resultado = []
    for i in range(dias - 1, -1, -1):
        dia = hasta - timedelta(days=i)
        resultado.append((DIAS_CORTOS[dia.weekday()], totales.get(dia, 0)))
    return resultado

def proyeccion_topes(
    movimientos: list[Movimiento],
    topes: dict[str, int],
    hoy: date,
) -> list[dict]:
    """Proyecta el gasto de fin de mes usando el ritmo observado hasta hoy."""
    dias_mes = (date(hoy.year + (hoy.month == 12), hoy.month % 12 + 1, 1) - date(hoy.year, hoy.month, 1)).days
    dias_transcurridos = max(hoy.day, 1)
    por_categoria = gastos_por_categoria(del_mes(movimientos, hoy.year, hoy.month))
    resultado = []
    for categoria, tope in sorted(topes.items(), key=lambda x: x[0]):
        gastado = por_categoria.get(categoria, 0)
        proyectado = round(gastado / dias_transcurridos * dias_mes)
        resultado.append({
            "categoria": categoria,
            "gastado": gastado,
            "tope": tope,
            "restante": max(tope - gastado, 0),
            "proyectado": proyectado,
            "diferencia": proyectado - tope,
            "riesgo": proyectado > tope,
            "porcentaje": round(gastado * 100 / tope) if tope else 0,
        })
    return resultado

def orden_pago_deudas(deudas: list[Deuda]) -> list[Deuda]:
    """Método avalancha: primero la deuda con la tasa más alta."""
    return sorted((d for d in deudas if d.saldo > 0), key=lambda d: (-d.tasa_ea, d.saldo))

# ---------- Compartido ----------

def saldos(gastos: list[GastoCompartido], pagos: list[Pago]) -> dict[str, int]:
    """Saldo neto por persona. Positivo: le deben. Negativo: debe."""
    neto: dict[str, int] = defaultdict(int)
    for g in gastos:
        n = len(g.dividido_entre)
        parte, resto = divmod(g.monto, n)
        neto[g.pagado_por] += g.monto
        for i, persona in enumerate(g.dividido_entre):
            neto[persona] -= parte + (1 if i < resto else 0)
    for p in pagos:
        neto[p.de] += p.monto
        neto[p.para] -= p.monto
    return dict(neto)

def simplificar(saldos_netos: dict[str, int]) -> list[tuple[str, str, int]]:
    """Lista mínima de transferencias (de, para, monto) para quedar a paz y salvo."""
    deudores = sorted(([p, -s] for p, s in saldos_netos.items() if s < 0), key=lambda x: -x[1])
    acreedores = sorted(([p, s] for p, s in saldos_netos.items() if s > 0), key=lambda x: -x[1])
    transferencias = []
    i = j = 0
    while i < len(deudores) and j < len(acreedores):
        monto = min(deudores[i][1], acreedores[j][1])
        transferencias.append((deudores[i][0], acreedores[j][0], monto))
        deudores[i][1] -= monto
        acreedores[j][1] -= monto
        if deudores[i][1] == 0:
            i += 1
        if acreedores[j][1] == 0:
            j += 1
    return transferencias

# ---------- Asesor IA ----------

def resumen_para_ia(
    movimientos_mes: list[Movimiento],
    topes: dict[str, int],
    deudas: list[Deuda],
    saldo_compartido: int,
    dias_restantes_mes: int = 0,
) -> dict:
    """Resumen anónimo para el modelo de IA: sin descripciones, nombres ni medios de pago."""
    por_categoria = gastos_por_categoria(movimientos_mes)
    ingresos, gastos = total(movimientos_mes, "ingreso"), total(movimientos_mes, "gasto")
    return {
        "moneda": "COP",
        "ingresos_mes": ingresos,
        "gastos_mes": gastos,
        "balance_mes": ingresos - gastos,
        "dias_restantes_mes": dias_restantes_mes,
        "gastos_por_categoria": por_categoria,
        "topes_por_categoria": topes,
        "disponible_por_categoria": {c: t - por_categoria.get(c, 0) for c, t in topes.items()},
        "categorias_excedidas": [a["categoria"] for a in alertas_topes(por_categoria, topes)],
        "deudas_en_orden_de_pago": [
            {"deuda": f"Deuda {i}", "saldo": d.saldo, "tasa_ea": d.tasa_ea, "cuota": d.cuota}
            for i, d in enumerate(orden_pago_deudas(deudas), start=1)
        ],
        "saldo_compartido": saldo_compartido,
    }
