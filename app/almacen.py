"""Almacenamiento de datos de Kuadra.

`Almacen` es la interfaz. `AlmacenDynamo` guarda en una tabla de DynamoDB (staging y producción).
`AlmacenMemoria` se usa en pruebas y en el modo demo, con datos ficticios.

Diseño de la tabla (una sola tabla, claves PK/SK):
    USER#<correo>   PERFIL                  nombre
    USER#<correo>   MOV#<fecha>#<id>        movimiento personal
    USER#<correo>   TOPES                   topes por categoría
    USER#<correo>   DEUDA#<id>              deuda
    USER#<correo>   GRUPO#<id>              índice: grupos donde está el correo
    USER#<correo>   FOTO                    foto de perfil (binario)
    GRUPO#<id>      META                    nombre y creador del grupo
    GRUPO#<id>      MIEMBRO#<correo>        miembro
    GRUPO#<id>      GASTO#<fecha>#<id>      gasto compartido
    GRUPO#<id>      PAGO#<fecha>#<id>       pago entre miembros
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import date
from typing import Protocol

from app.dominio import (
    Deuda,
    GastoCompartido,
    GastoRecurrente,
    Grupo,
    MetaAhorro,
    Movimiento,
    Pago,
)


class Almacen(Protocol):
    def perfil(self, usuario: str) -> str | None: ...
    def guardar_perfil(self, usuario: str, nombre: str) -> None: ...
    def movimientos(self, usuario: str) -> list[Movimiento]: ...
    def agregar_movimiento(self, usuario: str, mov: Movimiento) -> None: ...
    def topes(self, usuario: str) -> dict[str, int]: ...
    def deudas(self, usuario: str) -> list[Deuda]: ...
    def fijar_topes(self, usuario: str, topes: dict[str, int]) -> None: ...
    def agregar_deuda(self, usuario: str, deuda: Deuda) -> None: ...
    def eliminar_deuda(self, usuario: str, deuda_id: str) -> None: ...
    def crear_grupo(self, nombre: str, creador: str, invitados: list[str]) -> str: ...
    def invitar(self, grupo_id: str, correo: str) -> None: ...
    def grupo(self, grupo_id: str) -> Grupo | None: ...
    def grupos(self, usuario: str) -> list[Grupo]: ...
    def miembros(self, grupo_id: str) -> list[str]: ...
    def gastos_grupo(self, grupo_id: str) -> list[GastoCompartido]: ...
    def pagos_grupo(self, grupo_id: str) -> list[Pago]: ...
    def agregar_gasto_grupo(self, grupo_id: str, gasto: GastoCompartido) -> None: ...
    def agregar_pago(self, grupo_id: str, pago: Pago) -> None: ...
    def foto(self, usuario: str) -> tuple[bytes, str] | None: ...
    def guardar_foto(self, usuario: str, datos: bytes, tipo: str) -> None: ...
    def recurrentes(self, usuario: str) -> list[GastoRecurrente]: ...
    def agregar_recurrente(self, usuario: str, recurrente: GastoRecurrente) -> None: ...
    def eliminar_recurrente(self, usuario: str, recurrente_id: str) -> None: ...
    def metas(self, usuario: str) -> list[MetaAhorro]: ...
    def agregar_meta(self, usuario: str, meta: MetaAhorro) -> None: ...
    def agregar_aporte(self, usuario: str, meta_id: str, monto: int) -> None: ...
    def eliminar_meta(self, usuario: str, meta_id: str) -> None: ...


def _nuevo_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Memoria (pruebas y demo)
# ---------------------------------------------------------------------------

class AlmacenMemoria:
    def __init__(self) -> None:
        self._perfiles: dict[str, str] = {}
        self._movimientos: dict[str, list[Movimiento]] = {}
        self._topes: dict[str, dict[str, int]] = {}
        self._deudas: dict[str, list[Deuda]] = {}
        self._grupos: dict[str, Grupo] = {}
        self._miembros: dict[str, list[str]] = {}
        self._gastos: dict[str, list[GastoCompartido]] = {}
        self._pagos: dict[str, list[Pago]] = {}
        self._fotos: dict[str, tuple[bytes, str]] = {}
        self._recurrentes: dict[str, list[GastoRecurrente]] = {}
        self._metas: dict[str, list[MetaAhorro]] = {}

    def perfil(self, usuario: str) -> str | None:
        return self._perfiles.get(usuario)

    def guardar_perfil(self, usuario: str, nombre: str) -> None:
        self._perfiles[usuario] = nombre

    def movimientos(self, usuario: str) -> list[Movimiento]:
        return sorted(self._movimientos.get(usuario, []), key=lambda m: m.fecha, reverse=True)

    def agregar_movimiento(self, usuario: str, mov: Movimiento) -> None:
        self._movimientos.setdefault(usuario, []).append(mov)

    def topes(self, usuario: str) -> dict[str, int]:
        return dict(self._topes.get(usuario, {}))

    def deudas(self, usuario: str) -> list[Deuda]:
        return list(self._deudas.get(usuario, []))

    def crear_grupo(self, nombre: str, creador: str, invitados: list[str]) -> str:
        grupo_id = _nuevo_id()
        self._grupos[grupo_id] = Grupo(grupo_id, nombre, creador)
        self._miembros[grupo_id] = [creador]
        for correo in invitados:
            self.invitar(grupo_id, correo)
        return grupo_id

    def invitar(self, grupo_id: str, correo: str) -> None:
        miembros = self._miembros.setdefault(grupo_id, [])
        if correo not in miembros:
            miembros.append(correo)

    def grupo(self, grupo_id: str) -> Grupo | None:
        return self._grupos.get(grupo_id)

    def grupos(self, usuario: str) -> list[Grupo]:
        return sorted(
            (self._grupos[g] for g, miembros in self._miembros.items() if usuario in miembros and g in self._grupos),
            key=lambda g: g.nombre,
        )

    def miembros(self, grupo_id: str) -> list[str]:
        return list(self._miembros.get(grupo_id, []))

    def gastos_grupo(self, grupo_id: str) -> list[GastoCompartido]:
        return sorted(self._gastos.get(grupo_id, []), key=lambda g: g.fecha, reverse=True)

    def pagos_grupo(self, grupo_id: str) -> list[Pago]:
        return list(self._pagos.get(grupo_id, []))

    def agregar_gasto_grupo(self, grupo_id: str, gasto: GastoCompartido) -> None:
        self._gastos.setdefault(grupo_id, []).append(gasto)

    def agregar_pago(self, grupo_id: str, pago: Pago) -> None:
        self._pagos.setdefault(grupo_id, []).append(pago)

    def foto(self, usuario: str) -> tuple[bytes, str] | None:
        return self._fotos.get(usuario)

    def guardar_foto(self, usuario: str, datos: bytes, tipo: str) -> None:
        self._fotos[usuario] = (datos, tipo)

    # Solo para datos de prueba/demo
    def fijar_topes(self, usuario: str, topes: dict[str, int]) -> None:
        self._topes[usuario] = dict(topes)

    def agregar_deuda(self, usuario: str, deuda: Deuda) -> None:
        self._deudas.setdefault(usuario, []).append(replace(deuda, id=deuda.id or _nuevo_id()))

    def eliminar_deuda(self, usuario: str, deuda_id: str) -> None:
        self._deudas[usuario] = [x for x in self._deudas.get(usuario, []) if x.id != deuda_id]

    def recurrentes(self, usuario: str) -> list[GastoRecurrente]:
        return list(self._recurrentes.get(usuario, []))

    def agregar_recurrente(self, usuario: str, recurrente: GastoRecurrente) -> None:
        self._recurrentes.setdefault(usuario, []).append(replace(recurrente, id=recurrente.id or _nuevo_id()))

    def eliminar_recurrente(self, usuario: str, recurrente_id: str) -> None:
        self._recurrentes[usuario] = [x for x in self._recurrentes.get(usuario, []) if x.id != recurrente_id]

    def metas(self, usuario: str) -> list[MetaAhorro]:
        return list(self._metas.get(usuario, []))

    def agregar_meta(self, usuario: str, meta: MetaAhorro) -> None:
        self._metas.setdefault(usuario, []).append(replace(meta, id=meta.id or _nuevo_id()))

    def agregar_aporte(self, usuario: str, meta_id: str, monto: int) -> None:
        metas = self._metas.setdefault(usuario, [])
        self._metas[usuario] = [
            replace(meta, ahorrado=min(meta.objetivo, meta.ahorrado + monto)) if meta.id == meta_id else meta
            for meta in metas
        ]

    def eliminar_meta(self, usuario: str, meta_id: str) -> None:
        self._metas[usuario] = [x for x in self._metas.get(usuario, []) if x.id != meta_id]


# ---------------------------------------------------------------------------
# DynamoDB (staging y producción)
# ---------------------------------------------------------------------------

class AlmacenDynamo:
    def __init__(self, tabla) -> None:
        """`tabla` es un recurso boto3 `dynamodb.Table`."""
        self._t = tabla

    @classmethod
    def desde_nombre(cls, nombre_tabla: str, region: str | None = None) -> AlmacenDynamo:
        import boto3

        return cls(boto3.resource("dynamodb", region_name=region).Table(nombre_tabla))

    # --- utilidades ---
    def _consultar(self, pk: str, prefijo: str) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        items, kwargs = [], {"KeyConditionExpression": Key("PK").eq(pk) & Key("SK").begins_with(prefijo)}
        while True:
            resp = self._t.query(**kwargs)
            items.extend(resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                return items
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    def _obtener(self, pk: str, sk: str) -> dict | None:
        return self._t.get_item(Key={"PK": pk, "SK": sk}).get("Item")

    # --- perfil ---
    def perfil(self, usuario: str) -> str | None:
        item = self._obtener(f"USER#{usuario}", "PERFIL")
        return item["nombre"] if item else None

    def guardar_perfil(self, usuario: str, nombre: str) -> None:
        self._t.put_item(Item={"PK": f"USER#{usuario}", "SK": "PERFIL", "nombre": nombre,
                               "creado": date.today().isoformat()})

    # --- personal ---
    def movimientos(self, usuario: str) -> list[Movimiento]:
        movs = [
            Movimiento(date.fromisoformat(i["fecha"]), int(i["monto"]), i["descripcion"], i["categoria"],
                       i["medio"], i["tipo"])
            for i in self._consultar(f"USER#{usuario}", "MOV#")
        ]
        return sorted(movs, key=lambda m: m.fecha, reverse=True)

    def agregar_movimiento(self, usuario: str, mov: Movimiento) -> None:
        self._t.put_item(Item={
            "PK": f"USER#{usuario}", "SK": f"MOV#{mov.fecha.isoformat()}#{_nuevo_id()}",
            "fecha": mov.fecha.isoformat(), "monto": mov.monto, "descripcion": mov.descripcion,
            "categoria": mov.categoria, "medio": mov.medio, "tipo": mov.tipo,
        })

    def topes(self, usuario: str) -> dict[str, int]:
        item = self._obtener(f"USER#{usuario}", "TOPES")
        return {k: int(v) for k, v in (item or {}).get("topes", {}).items()}

    def deudas(self, usuario: str) -> list[Deuda]:
        return [
            Deuda(i["nombre"], int(i["saldo"]), float(i["tasa_ea"]), int(i["cuota"]), i["SK"].removeprefix("DEUDA#"))
            for i in self._consultar(f"USER#{usuario}", "DEUDA#")
        ]

    def fijar_topes(self, usuario: str, topes: dict[str, int]) -> None:
        self._t.put_item(Item={"PK": f"USER#{usuario}", "SK": "TOPES", "topes": dict(topes)})

    def agregar_deuda(self, usuario: str, deuda: Deuda) -> None:
        self._t.put_item(Item={
            "PK": f"USER#{usuario}", "SK": f"DEUDA#{deuda.id or _nuevo_id()}", "nombre": deuda.nombre,
            "saldo": deuda.saldo, "tasa_ea": str(deuda.tasa_ea), "cuota": deuda.cuota,
        })

    def eliminar_deuda(self, usuario: str, deuda_id: str) -> None:
        self._t.delete_item(Key={"PK": f"USER#{usuario}", "SK": f"DEUDA#{deuda_id}"})

    # --- grupos ---
    def crear_grupo(self, nombre: str, creador: str, invitados: list[str]) -> str:
        grupo_id = _nuevo_id()
        self._t.put_item(Item={"PK": f"GRUPO#{grupo_id}", "SK": "META", "nombre": nombre, "creador": creador})
        for correo in [creador, *invitados]:
            self.invitar(grupo_id, correo)
        return grupo_id

    def invitar(self, grupo_id: str, correo: str) -> None:
        meta = self._obtener(f"GRUPO#{grupo_id}", "META")
        if not meta:
            raise KeyError(grupo_id)
        with self._t.batch_writer() as lote:
            lote.put_item(Item={"PK": f"GRUPO#{grupo_id}", "SK": f"MIEMBRO#{correo}", "correo": correo})
            lote.put_item(Item={"PK": f"USER#{correo}", "SK": f"GRUPO#{grupo_id}", "nombre": meta["nombre"]})

    def grupo(self, grupo_id: str) -> Grupo | None:
        meta = self._obtener(f"GRUPO#{grupo_id}", "META")
        return Grupo(grupo_id, meta["nombre"], meta["creador"]) if meta else None

    def grupos(self, usuario: str) -> list[Grupo]:
        resultado = []
        for item in self._consultar(f"USER#{usuario}", "GRUPO#"):
            grupo = self.grupo(item["SK"].removeprefix("GRUPO#"))
            if grupo:
                resultado.append(grupo)
        return sorted(resultado, key=lambda g: g.nombre)

    def miembros(self, grupo_id: str) -> list[str]:
        return [i["correo"] for i in self._consultar(f"GRUPO#{grupo_id}", "MIEMBRO#")]

    def gastos_grupo(self, grupo_id: str) -> list[GastoCompartido]:
        gastos = [
            GastoCompartido(date.fromisoformat(i["fecha"]), int(i["monto"]), i["descripcion"], i["pagado_por"],
                            tuple(i["dividido_entre"]))
            for i in self._consultar(f"GRUPO#{grupo_id}", "GASTO#")
        ]
        return sorted(gastos, key=lambda g: g.fecha, reverse=True)

    def pagos_grupo(self, grupo_id: str) -> list[Pago]:
        return [
            Pago(date.fromisoformat(i["fecha"]), i["de"], i["para"], int(i["monto"]))
            for i in self._consultar(f"GRUPO#{grupo_id}", "PAGO#")
        ]

    def agregar_gasto_grupo(self, grupo_id: str, gasto: GastoCompartido) -> None:
        self._t.put_item(Item={
            "PK": f"GRUPO#{grupo_id}", "SK": f"GASTO#{gasto.fecha.isoformat()}#{_nuevo_id()}",
            "fecha": gasto.fecha.isoformat(), "monto": gasto.monto, "descripcion": gasto.descripcion,
            "pagado_por": gasto.pagado_por, "dividido_entre": list(gasto.dividido_entre),
        })


    def agregar_pago(self, grupo_id: str, pago: Pago) -> None:
        self._t.put_item(Item={
            "PK": f"GRUPO#{grupo_id}", "SK": f"PAGO#{pago.fecha.isoformat()}#{_nuevo_id()}",
            "fecha": pago.fecha.isoformat(), "de": pago.de, "para": pago.para, "monto": pago.monto,
        })

    # --- foto de perfil (máx. ~300 KB, cabe en un ítem de DynamoDB) ---
    def foto(self, usuario: str) -> tuple[bytes, str] | None:
        item = self._obtener(f"USER#{usuario}", "FOTO")
        return (bytes(item["datos"]), item["tipo"]) if item else None

    def guardar_foto(self, usuario: str, datos: bytes, tipo: str) -> None:
        self._t.put_item(Item={"PK": f"USER#{usuario}", "SK": "FOTO", "datos": datos, "tipo": tipo})

    # --- planificación ---
    def recurrentes(self, usuario: str) -> list[GastoRecurrente]:
        return [
            GastoRecurrente(
                i["nombre"], int(i["monto"]), i["categoria"], i["frecuencia"], int(i["dia"]),
                i.get("activo", True), i["SK"].removeprefix("RECURRENTE#"),
            )
            for i in self._consultar(f"USER#{usuario}", "RECURRENTE#")
        ]

    def agregar_recurrente(self, usuario: str, recurrente: GastoRecurrente) -> None:
        recurrente_id = recurrente.id or _nuevo_id()
        self._t.put_item(Item={
            "PK": f"USER#{usuario}", "SK": f"RECURRENTE#{recurrente_id}",
            "nombre": recurrente.nombre, "monto": recurrente.monto, "categoria": recurrente.categoria,
            "frecuencia": recurrente.frecuencia, "dia": recurrente.dia, "activo": recurrente.activo,
        })

    def eliminar_recurrente(self, usuario: str, recurrente_id: str) -> None:
        self._t.delete_item(Key={"PK": f"USER#{usuario}", "SK": f"RECURRENTE#{recurrente_id}"})

    def metas(self, usuario: str) -> list[MetaAhorro]:
        return [
            MetaAhorro(
                i["nombre"], int(i["objetivo"]), int(i["ahorrado"]),
                date.fromisoformat(i["fecha_objetivo"]), i["SK"].removeprefix("META#"),
            )
            for i in self._consultar(f"USER#{usuario}", "META#")
        ]

    def agregar_meta(self, usuario: str, meta: MetaAhorro) -> None:
        meta_id = meta.id or _nuevo_id()
        self._t.put_item(Item={
            "PK": f"USER#{usuario}", "SK": f"META#{meta_id}",
            "nombre": meta.nombre, "objetivo": meta.objetivo, "ahorrado": meta.ahorrado,
            "fecha_objetivo": meta.fecha_objetivo.isoformat(),
        })

    def agregar_aporte(self, usuario: str, meta_id: str, monto: int) -> None:
        for meta in self.metas(usuario):
            if meta.id == meta_id:
                self.agregar_meta(usuario, replace(meta, ahorrado=min(meta.objetivo, meta.ahorrado + monto)))
                return

    def eliminar_meta(self, usuario: str, meta_id: str) -> None:
        self._t.delete_item(Key={"PK": f"USER#{usuario}", "SK": f"META#{meta_id}"})


# ---------------------------------------------------------------------------
# Datos ficticios del modo demo
# ---------------------------------------------------------------------------

USUARIO_DEMO = "demo@kuadra.app"


def almacen_demo(hoy: date | None = None) -> AlmacenMemoria:
    """Almacén con datos ficticios para el modo demo y las pruebas de aceptación."""
    hoy = hoy or date.today()
    a = AlmacenMemoria()

    def dia(d: int, meses_atras: int = 0) -> date:
        anio, mes = hoy.year, hoy.month - meses_atras
        while mes <= 0:
            anio, mes = anio - 1, mes + 12
        return date(anio, mes, min(d, 28))

    u = USUARIO_DEMO
    a.guardar_perfil(u, "Manuela")
    a.guardar_perfil("ana@ejemplo.com", "Ana")
    a.guardar_perfil("sara@ejemplo.com", "Sara")
    a.agregar_recurrente(u, GastoRecurrente("Arriendo", 1800000, "Hogar", "Mensual", 1))
    a.agregar_recurrente(u, GastoRecurrente("Netflix", 45000, "Ocio", "Mensual", 15))
    a.agregar_meta(u, MetaAhorro("Viaje a Cartagena", 2500000, 750000, dia(28, 2).replace(year=dia(28, 2).year + 1)))
    for atras, mercado in ((5, 610000), (4, 720000), (3, 680000), (2, 590000), (1, 750000)):
        a.agregar_movimiento(u, Movimiento(dia(1, atras), 4200000, "Salario", "Otros", "Transferencia", "ingreso"))
        a.agregar_movimiento(u, Movimiento(dia(5, atras), mercado, "Mercado del mes", "Mercado", "Débito", "gasto"))
        a.agregar_movimiento(u, Movimiento(dia(10, atras), 380000, "Servicios", "Servicios", "Débito", "gasto"))

    for mov in (
        Movimiento(dia(1), 4200000, "Salario", "Otros", "Transferencia", "ingreso"),
        Movimiento(dia(3), 520000, "Supermercado", "Mercado", "Débito", "gasto"),
        Movimiento(dia(4), 310000, "Tienda del barrio", "Mercado", "Efectivo", "gasto"),
        Movimiento(dia(5), 45000, "Almuerzo", "Comida", "Tarjeta de crédito", "gasto"),
        Movimiento(dia(6), 200000, "Cajero", "Otros", "Débito", "retiro"),
        Movimiento(dia(7), 18000, "Taxi", "Transporte", "Efectivo", "gasto"),
        Movimiento(dia(8), 165000, "Internet y celular", "Servicios", "Débito", "gasto"),
        Movimiento(dia(9), 120000, "Camiseta", "Ropa", "Tarjeta de crédito", "gasto"),
        Movimiento(dia(10), 60000, "Cine", "Ocio", "Débito", "gasto"),
        Movimiento(dia(12), 350000, "Cuota tarjeta", "Deudas", "Transferencia", "gasto"),
    ):
        a.agregar_movimiento(u, mov)

    a.fijar_topes(u, {"Mercado": 700000, "Comida": 200000, "Transporte": 150000, "Ropa": 100000, "Ocio": 150000})
    a.agregar_deuda(u, Deuda("Crédito de libre inversión", 12000000, 16.5, 450000))
    a.agregar_deuda(u, Deuda("Tarjeta de crédito", 1800000, 28.6, 350000))
    a.agregar_deuda(u, Deuda("Compra a cuotas sin interés", 600000, 0.0, 100000))

    casa = a.crear_grupo("Casa", u, ["ana@ejemplo.com", "sara@ejemplo.com"])
    miembros = tuple(a.miembros(casa))
    a.agregar_gasto_grupo(casa, GastoCompartido(dia(2), 300000, "Mercado de la casa", u, miembros))
    a.agregar_gasto_grupo(casa, GastoCompartido(dia(6), 90000, "Internet", "ana@ejemplo.com", miembros))
    a.agregar_gasto_grupo(
        casa, GastoCompartido(dia(8), 60000, "Comida de la mascota", "sara@ejemplo.com", (u, "sara@ejemplo.com"))
    )
    return a
