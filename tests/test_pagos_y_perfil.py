"""Transferencias entre miembros, saludo y foto de perfil."""

import io

import pytest

from app import dominio as d
from app.almacen import USUARIO_DEMO

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"0" * 100


def casa(app):
    return app.extensions["almacen"].grupos(USUARIO_DEMO)[0].id


# ---------- Pagos ----------

def test_transferencia_resta_la_deuda(app, sesion_demo):
    gid = casa(app)
    alm = app.extensions["almacen"]
    antes = d.saldos(alm.gastos_grupo(gid), alm.pagos_grupo(gid))["sara@ejemplo.com"]
    resp = sesion_demo.post(f"/compartido/{gid}/pago", data={
        "de": "sara@ejemplo.com", "para": USUARIO_DEMO, "monto": "40000",
    }, follow_redirects=True)
    assert "Pago registrado: Sara → Tú 40.000" in resp.get_data(as_text=True)
    despues = d.saldos(alm.gastos_grupo(gid), alm.pagos_grupo(gid))["sara@ejemplo.com"]
    assert despues == antes + 40000


def test_marcar_pagado_deja_a_paz_y_salvo(app, sesion_demo):
    gid = casa(app)
    alm = app.extensions["almacen"]
    for de, para, monto in d.simplificar(d.saldos(alm.gastos_grupo(gid), alm.pagos_grupo(gid))):
        sesion_demo.post(f"/compartido/{gid}/pago", data={"de": de, "para": para, "monto": str(monto)})
    assert all(v == 0 for v in d.saldos(alm.gastos_grupo(gid), alm.pagos_grupo(gid)).values())
    assert "A paz y salvo" in sesion_demo.get("/compartido").get_data(as_text=True)


@pytest.mark.parametrize("datos, error", [
    ({"de": USUARIO_DEMO, "para": USUARIO_DEMO, "monto": "10"}, "personas distintas"),
    ({"de": "extrano@x.co", "para": USUARIO_DEMO, "monto": "10"}, "Revisa el pago"),
    ({"de": "sara@ejemplo.com", "para": USUARIO_DEMO, "monto": "0"}, "Revisa el pago"),
])
def test_pago_invalido(app, sesion_demo, datos, error):
    gid = casa(app)
    resp = sesion_demo.post(f"/compartido/{gid}/pago", data=datos, follow_redirects=True)
    assert error in resp.get_data(as_text=True)
    assert app.extensions["almacen"].pagos_grupo(gid) == []


def test_pago_en_grupo_ajeno(sesion_demo):
    assert sesion_demo.post("/compartido/noexiste/pago", data={}).status_code == 404


def test_validar_pago_dominio():
    with pytest.raises(d.DatoInvalido):
        d.validar_pago(d.Pago(None, "a", "b", -1), ["a", "b"])
    with pytest.raises(d.DatoInvalido):
        d.validar_pago(d.Pago(None, "a", "z", 5), ["a", "b"])


# ---------- Saludo y perfil ----------

def test_saludo_con_primer_nombre(sesion_demo):
    assert "Hola, Manuela 👋" in sesion_demo.get("/").get_data(as_text=True)


def test_primer_nombre():
    assert d.primer_nombre("Manuela Jiménez") == "Manuela"
    assert d.primer_nombre(None) == ""


def test_pagina_perfil(sesion_demo):
    html = sesion_demo.get("/perfil").get_data(as_text=True)
    assert "Mi perfil" in html and "Cambiar foto" in html and USUARIO_DEMO in html


def test_perfil_muestra_insignias(sesion_demo):
    html = sesion_demo.get("/perfil").get_data(as_text=True)
    assert "Mis insignias" in html
    for nombre in ("Primer paso", "Meta cumplida", "Mes en regla"):
        assert nombre in html


def test_cambiar_nombre(app, sesion_demo):
    sesion_demo.post("/perfil", data={"n-nombre": "Manu J"})
    assert app.extensions["almacen"].perfil(USUARIO_DEMO) == "Manu J"


def test_cambiar_nombre_invalido(app, sesion_demo):
    resp = sesion_demo.post("/perfil", data={"n-nombre": "x" * 41})
    assert resp.status_code == 200
    assert app.extensions["almacen"].perfil(USUARIO_DEMO) == "Manuela"


@pytest.mark.parametrize("contenido, tipo", [(JPEG, "image/jpeg"), (PNG, "image/png"), (WEBP, "image/webp")])
def test_subir_foto(app, sesion_demo, contenido, tipo):
    resp = sesion_demo.post("/perfil", data={"f-foto": (io.BytesIO(contenido), "yo.jpg")},
                            content_type="multipart/form-data", follow_redirects=True)
    assert "Foto actualizada" in resp.get_data(as_text=True)
    foto = sesion_demo.get("/perfil/foto")
    assert foto.status_code == 200 and foto.mimetype == tipo and foto.data == contenido
    assert 'src="/perfil/foto"' in sesion_demo.get("/").get_data(as_text=True)


@pytest.mark.parametrize("contenido, error", [
    (b"<svg onload=alert(1)>", "JPG, PNG o WebP"),
    (b"\xff\xd8\xff" + b"0" * (300 * 1024), "muy pesada"),
])
def test_foto_rechazada(app, sesion_demo, contenido, error):
    resp = sesion_demo.post("/perfil", data={"f-foto": (io.BytesIO(contenido), "x.jpg")},
                            content_type="multipart/form-data", follow_redirects=True)
    assert error in resp.get_data(as_text=True)
    assert app.extensions["almacen"].foto(USUARIO_DEMO) is None


def test_foto_sin_archivo(sesion_demo):
    resp = sesion_demo.post("/perfil", data={}, content_type="multipart/form-data")
    assert "Selecciona una imagen" in resp.get_data(as_text=True)


def test_sin_foto_da_404(sesion_demo):
    assert sesion_demo.get("/perfil/foto").status_code == 404


def test_tipo_de_imagen_vacia():
    with pytest.raises(d.DatoInvalido):
        d.tipo_de_imagen(b"")
