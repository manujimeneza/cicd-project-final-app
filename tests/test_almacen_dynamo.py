"""AlmacenDynamo contra una DynamoDB simulada (moto): mismo comportamiento que en AWS."""

from datetime import date

import boto3
import pytest
from moto import mock_aws

from app.almacen import AlmacenDynamo
from app.dominio import Deuda, GastoCompartido, GastoRecurrente, MetaAhorro, Movimiento


@pytest.fixture
def alm(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    with mock_aws():
        boto3.client("dynamodb").create_table(
            TableName="kuadra-test",
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "PK", "AttributeType": "S"},
                                  {"AttributeName": "SK", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield AlmacenDynamo.desde_nombre("kuadra-test")


def test_perfil(alm):
    assert alm.perfil("a@x.co") is None
    alm.guardar_perfil("a@x.co", "Ana")
    assert alm.perfil("a@x.co") == "Ana"


def test_movimientos_ordenados(alm):
    alm.agregar_movimiento("a@x.co", Movimiento(date(2026, 11, 1), 100, "uno", "Comida", "Efectivo", "gasto"))
    alm.agregar_movimiento("a@x.co", Movimiento(date(2026, 11, 5), 200, "dos", "Mercado", "Débito", "gasto"))
    alm.agregar_movimiento("b@x.co", Movimiento(date(2026, 11, 5), 999, "otro", "Mercado", "Débito", "gasto"))
    movs = alm.movimientos("a@x.co")
    assert [m.descripcion for m in movs] == ["dos", "uno"]
    assert movs[0].monto == 200 and isinstance(movs[0].monto, int)


def test_topes_y_deudas_vacios(alm):
    assert alm.topes("a@x.co") == {}
    assert alm.deudas("a@x.co") == []


def test_topes_y_deudas(alm):
    alm._t.put_item(Item={"PK": "USER#a@x.co", "SK": "TOPES", "topes": {"Mercado": 700000}})
    alm._t.put_item(Item={"PK": "USER#a@x.co", "SK": "DEUDA#1", "nombre": "Tarjeta", "saldo": 1000,
                          "tasa_ea": "28.6", "cuota": 100})
    assert alm.topes("a@x.co") == {"Mercado": 700000}
    assert [(x.nombre, x.saldo, x.tasa_ea, x.cuota) for x in alm.deudas("a@x.co")] == [("Tarjeta", 1000, 28.6, 100)]


def test_grupos_compartidos(alm):
    gid = alm.crear_grupo("Hermanas", "manu@x.co", ["ana@x.co"])
    assert [g.nombre for g in alm.grupos("ana@x.co")] == ["Hermanas"]
    assert alm.grupos("otra@x.co") == []
    alm.invitar(gid, "sofia@x.co")
    assert set(alm.miembros(gid)) == {"manu@x.co", "ana@x.co", "sofia@x.co"}
    assert alm.grupo(gid).creador == "manu@x.co"
    assert alm.grupo("noexiste") is None


def test_invitar_a_grupo_inexistente(alm):
    with pytest.raises(KeyError):
        alm.invitar("noexiste", "a@x.co")


def test_gastos_grupo(alm):
    gid = alm.crear_grupo("Casa", "manu@x.co", ["ana@x.co"])
    alm.agregar_gasto_grupo(gid, GastoCompartido(date(2026, 11, 2), 300, "Mercado", "manu@x.co",
                                                 ("manu@x.co", "ana@x.co")))
    gastos = alm.gastos_grupo(gid)
    assert gastos[0].dividido_entre == ("manu@x.co", "ana@x.co")
    assert alm.pagos_grupo(gid) == []


def test_pagos_grupo(alm):
    gid = alm.crear_grupo("Casa", "manu@x.co", [])
    alm._t.put_item(Item={"PK": f"GRUPO#{gid}", "SK": "PAGO#2026-11-03#1", "fecha": "2026-11-03",
                          "de": "ana@x.co", "para": "manu@x.co", "monto": 50})
    assert alm.pagos_grupo(gid)[0].monto == 50


def test_pagos_y_foto(alm):
    from app.dominio import Pago

    gid = alm.crear_grupo("Casa", "manu@x.co", ["sara@x.co"])
    alm.agregar_pago(gid, Pago(date(2026, 11, 4), "sara@x.co", "manu@x.co", 40000))
    assert alm.pagos_grupo(gid)[0].monto == 40000
    assert alm.foto("manu@x.co") is None
    alm.guardar_foto("manu@x.co", b"\xff\xd8\xffdatos", "image/jpeg")
    assert alm.foto("manu@x.co") == (b"\xff\xd8\xffdatos", "image/jpeg")


def test_deudas_y_topes_crud(alm):
    alm.fijar_topes("a@x.co", {"Mercado": 500000})
    assert alm.topes("a@x.co") == {"Mercado": 500000}
    alm.agregar_deuda("a@x.co", Deuda("Tarjeta", 1000, 28.6, 100))
    [deuda] = alm.deudas("a@x.co")
    assert deuda.nombre == "Tarjeta" and deuda.tasa_ea == 28.6 and deuda.id
    alm.eliminar_deuda("a@x.co", deuda.id)
    assert alm.deudas("a@x.co") == []


def test_recurrentes_crud(alm):
    alm.agregar_recurrente("a@x.co", GastoRecurrente("Arriendo", 1800000, "Hogar", "Mensual", 1))
    [r] = alm.recurrentes("a@x.co")
    assert (r.nombre, r.monto, r.dia, r.activo) == ("Arriendo", 1800000, 1, True) and r.id
    alm.eliminar_recurrente("a@x.co", r.id)
    assert alm.recurrentes("a@x.co") == []


def test_metas_aportes_y_eliminar(alm):
    alm.agregar_meta("a@x.co", MetaAhorro("Viaje", 1000, 100, date(2030, 1, 1)))
    [m] = alm.metas("a@x.co")
    assert m.fecha_objetivo == date(2030, 1, 1) and m.id
    alm.agregar_aporte("a@x.co", m.id, 300)
    alm.agregar_aporte("a@x.co", m.id, 5000)  # no supera el objetivo
    alm.agregar_aporte("a@x.co", "no-existe", 10)
    assert alm.metas("a@x.co")[0].ahorrado == 1000
    alm.eliminar_meta("a@x.co", m.id)
    assert alm.metas("a@x.co") == []


# ---------- Editar / anular con historial (DynamoDB) ----------

def test_crear_editar_y_anular_dejan_historial(alm):
    from app.dominio import RegistroModificado, saldos

    gid = alm.crear_grupo("Casa", "manu@x.co", ["ana@x.co"])
    gid_gasto = alm.agregar_gasto_grupo(gid, GastoCompartido(
        date(2026, 11, 2), 300, "Mercado", "manu@x.co", ("manu@x.co", "ana@x.co"), registrado_por="manu@x.co"))
    gasto = alm.registro_grupo(gid, "gasto", gid_gasto)
    assert (gasto.version, gasto.registrado_por, gasto.anulado) == (1, "manu@x.co", False)

    from dataclasses import replace
    alm.editar_registro(gid, replace(gasto, monto=500), "manu@x.co", "faltaba el domicilio")
    editado = alm.registro_grupo(gid, "gasto", gid_gasto)
    assert (editado.monto, editado.version) == (500, 2)

    with pytest.raises(RegistroModificado):  # alguien edita con una versión vieja
        alm.editar_registro(gid, replace(gasto, monto=999), "manu@x.co", "otro")

    alm.anular_registro(gid, editado, "manu@x.co", "estaba repetido")
    assert alm.registro_grupo(gid, "gasto", gid_gasto).anulado
    assert saldos(alm.gastos_grupo(gid), alm.pagos_grupo(gid)) == {}
    with pytest.raises(RegistroModificado):
        alm.anular_registro(gid, editado, "manu@x.co", "de nuevo")

    historial = alm.historial_grupo(gid)
    assert [c.accion for c in historial] == ["anuló", "editó", "creó"]
    assert historial[1].antes["monto"] == 300 and historial[1].despues["monto"] == 500
    assert historial[1].motivo == "faltaba el domicilio" and historial[0].despues is None


def test_editar_registro_antiguo_sin_version_y_pagos(alm):
    from dataclasses import replace

    gid = alm.crear_grupo("Casa", "manu@x.co", [])
    alm._t.put_item(Item={"PK": f"GRUPO#{gid}", "SK": "PAGO#2026-11-03#viejo", "fecha": "2026-11-03",
                          "de": "ana@x.co", "para": "manu@x.co", "monto": 50})
    viejo = alm.registro_grupo(gid, "pago", "viejo")
    assert (viejo.version, viejo.registrado_por) == (0, "")
    alm.editar_registro(gid, replace(viejo, monto=70), "manu@x.co", "corrección")
    assert alm.registro_grupo(gid, "pago", "viejo").monto == 70
    assert alm.registro_grupo(gid, "pago", "noexiste") is None
