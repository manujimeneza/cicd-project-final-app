from datetime import date

from app import create_app
from app.almacen import USUARIO_DEMO, almacen_demo
from app.asesor import AsesorNoDisponible, GeminiModelo


def test_health(cliente):
    resp = cliente.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["estado"] == "ok"


def test_cabeceras_seguridad(cliente):
    resp = cliente.get("/bienvenida")
    assert "frame-ancestors 'none'" in resp.headers["Content-Security-Policy"]
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"


def test_sin_sesion_redirige_a_bienvenida(cliente):
    for ruta in ("/", "/analisis", "/compartido", "/asesor", "/movimientos/nuevo"):
        resp = cliente.get(ruta)
        assert resp.status_code == 302
        assert "/bienvenida" in resp.headers["Location"]


def test_demo_deshabilitado_en_produccion():
    app = create_app({"TESTING": True, "SECRET_KEY": "x", "WTF_CSRF_ENABLED": False, "MODO_DEMO": False})
    assert app.test_client().post("/demo").status_code == 404
    assert b"Probar la demo" not in app.test_client().get("/bienvenida").data


def test_csrf_activo_por_defecto():
    app = create_app({"TESTING": True, "SECRET_KEY": "x", "MODO_DEMO": True})
    assert app.test_client().post("/demo").status_code == 400


def test_paginas_principales(sesion_demo):
    paginas = (("/", "Balance del mes"), ("/analisis", "Tendencia"), ("/compartido", "Casa"))
    for ruta, texto in paginas:
        resp = sesion_demo.get(ruta)
        assert resp.status_code == 200, ruta
        assert texto in resp.get_data(as_text=True)


def test_proyeccion_en_analisis(sesion_demo):
    html = sesion_demo.get("/analisis").get_data(as_text=True)
    assert "Proyección a fin de mes" in html


def test_planificacion_recurrente_y_meta(app, sesion_demo):
    recurrente = sesion_demo.post("/planifica", data={
        "r-nombre": "Internet",
        "r-monto": "90000",
        "r-categoria": "Servicios",
        "r-frecuencia": "Mensual",
        "r-dia": "8",
    })
    assert recurrente.status_code == 302
    recurrentes = app.extensions["almacen"].recurrentes(USUARIO_DEMO)
    assert any(r.nombre == "Internet" for r in recurrentes)

    meta = sesion_demo.post("/planifica", data={
        "m-nombre": "Fondo de emergencia",
        "m-objetivo": "1000000",
        "m-ahorrado": "100000",
        "m-fecha_objetivo": "2027-12-31",
    })
    assert meta.status_code == 302
    metas = app.extensions["almacen"].metas(USUARIO_DEMO)
    fondo = next(m for m in metas if m.nombre == "Fondo de emergencia")

    aporte = sesion_demo.post(f"/planifica/meta/{fondo.id}/aporte", data={"monto": "50000"})
    assert aporte.status_code == 302
    fondo_actualizada = next(m for m in app.extensions["almacen"].metas(USUARIO_DEMO) if m.id == fondo.id)
    assert fondo_actualizada.ahorrado == 150000

    html = sesion_demo.get("/planifica").get_data(as_text=True)
    assert "Internet" in html
    assert "Fondo de emergencia" in html


def test_agregar_movimiento(app, sesion_demo):
    resp = sesion_demo.post("/movimientos/nuevo", data={
        "tipo": "gasto", "monto": "12345", "descripcion": "Helado", "categoria": "Comida",
        "medio": "Efectivo", "fecha": date.today().isoformat(),
    })
    assert resp.status_code == 302
    assert any(m.descripcion == "Helado" for m in app.extensions["almacen"].movimientos(USUARIO_DEMO))


def test_movimiento_invalido_no_se_guarda(app, sesion_demo):
    antes = len(app.extensions["almacen"].movimientos(USUARIO_DEMO))
    resp = sesion_demo.post("/movimientos/nuevo", data={
        "tipo": "gasto", "monto": "-5", "descripcion": "", "categoria": "Comida",
        "medio": "Efectivo", "fecha": date.today().isoformat(),
    })
    assert resp.status_code == 200
    assert len(app.extensions["almacen"].movimientos(USUARIO_DEMO)) == antes


def test_html_se_escapa(sesion_demo):
    sesion_demo.post("/movimientos/nuevo", data={
        "tipo": "gasto", "monto": "1", "descripcion": "<script>alert(1)</script>", "categoria": "Comida",
        "medio": "Efectivo", "fecha": date.today().isoformat(),
    })
    html = sesion_demo.get("/").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_gasto_compartido(app, sesion_demo):
    alm = app.extensions["almacen"]
    casa = alm.grupos(USUARIO_DEMO)[0].id
    miembros = alm.miembros(casa)
    resp = sesion_demo.post(f"/compartido/{casa}/gasto", data={
        "monto": "60000", "descripcion": "Aseo", "pagado_por": USUARIO_DEMO,
        "dividido_entre": miembros, "fecha": date.today().isoformat(),
    })
    assert resp.status_code == 302
    assert alm.gastos_grupo(casa)[0].descripcion == "Aseo"


def test_grupo_ajeno_da_404(sesion_demo):
    assert sesion_demo.get("/compartido/noexiste/gasto").status_code == 404


def test_asesor_responde(sesion_demo):
    resp = sesion_demo.post("/asesor", data={"pregunta": "¿Qué deuda pago primero?"}, follow_redirects=True)
    html = resp.get_data(as_text=True)
    assert "¿Qué deuda pago primero?" in html
    assert "28.6%" in html  # la deuda más cara del demo


def test_panel_asesor_en_todas_las_pantallas(sesion_demo):
    for ruta in ("/", "/analisis", "/compartido", "/movimientos/nuevo"):
        html = sesion_demo.get(ruta).get_data(as_text=True)
        assert 'id="asesor"' in html, ruta
        assert f'name="siguiente" type="hidden" value="{ruta}"' in html, ruta


def test_get_asesor_abre_panel(sesion_demo):
    resp = sesion_demo.get("/asesor")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/#asesor")


def test_asesor_vuelve_a_la_pantalla_actual(sesion_demo):
    resp = sesion_demo.post("/asesor", data={"pregunta": "hola", "siguiente": "/analisis"})
    assert resp.headers["Location"].endswith("/analisis#asesor")


def test_asesor_no_redirige_a_otro_sitio(sesion_demo):
    for malo in ("https://malo.com", "//malo.com", "/\\malo.com", ""):
        resp = sesion_demo.post("/asesor", data={"pregunta": "hola", "siguiente": malo})
        assert resp.headers["Location"].endswith("/#asesor"), malo


def test_asesor_pregunta_vacia(sesion_demo):
    resp = sesion_demo.post("/asesor", data={"pregunta": "", "siguiente": "/"}, follow_redirects=True)
    assert "Escribe una pregunta" in resp.get_data(as_text=True)


def test_asesor_limpiar(sesion_demo):
    sesion_demo.post("/asesor", data={"pregunta": "Pregunta única 123", "siguiente": "/"})
    assert "Pregunta única 123" in sesion_demo.get("/").get_data(as_text=True)
    sesion_demo.post("/asesor/limpiar", data={"siguiente": "/"})
    assert "Pregunta única 123" not in sesion_demo.get("/").get_data(as_text=True)


def test_asesor_no_disponible():
    class ModeloCaido:
        def responder(self, resumen, pregunta):
            raise AsesorNoDisponible("sin cuota")

    app = create_app({"TESTING": True, "SECRET_KEY": "x", "WTF_CSRF_ENABLED": False,
                      "ALMACEN": almacen_demo(), "MODELO_IA": ModeloCaido()})
    c = app.test_client()
    c.post("/demo")
    resp = c.post("/asesor", data={"pregunta": "¿Qué deuda pago primero?"}, follow_redirects=True)
    html = resp.get_data(as_text=True)
    assert "28.6% E.A." in html  # responde el asesor por reglas


def test_salir_cierra_sesion(sesion_demo):
    sesion_demo.post("/salir")
    assert sesion_demo.get("/").status_code == 302


def test_gemini_requiere_clave():
    import pytest

    with pytest.raises(ValueError):
        GeminiModelo("", "modelo")


def test_gemini_parsea_respuesta(monkeypatch):
    import io
    import json

    capturado = {}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def falso_urlopen(req, timeout):
        capturado["headers"] = dict(req.header_items())
        capturado["cuerpo"] = json.loads(req.data)
        return Resp(json.dumps({"candidates": [{"content": {"parts": [{"text": " Paga la tarjeta. "}]}}]}).encode())

    monkeypatch.setattr("urllib.request.urlopen", falso_urlopen)
    texto = GeminiModelo("clave-falsa", "modelo-x").responder({"gastos_mes": 1}, "¿Qué hago?")
    assert texto == "Paga la tarjeta."
    assert capturado["headers"]["X-goog-api-key"] == "clave-falsa"
    assert "clave-falsa" not in json.dumps(capturado["cuerpo"])


def test_gemini_error_de_red(monkeypatch):
    import urllib.error

    import pytest

    def falla(req, timeout):
        raise urllib.error.URLError("sin red")

    monkeypatch.setattr("urllib.request.urlopen", falla)
    with pytest.raises(AsesorNoDisponible):
        GeminiModelo("k", "m").responder({}, "hola")


def test_chat_no_desborda_la_cookie(app, sesion_demo):
    class Largo:
        def responder(self, resumen, pregunta):
            return "x" * 5000

    app.extensions["modelo_ia"] = Largo()
    for _ in range(8):
        resp = sesion_demo.post("/asesor", data={"pregunta": "p" * 500, "siguiente": "/"})
    cookie = resp.headers.get("Set-Cookie", "")
    assert len(cookie) < 4000
    with sesion_demo.session_transaction() as s:
        assert len(s["chat"]) == 4
