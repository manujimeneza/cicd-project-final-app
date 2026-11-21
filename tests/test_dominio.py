from datetime import date

import pytest

from app import dominio as d

HOY = date(2026, 11, 17)


def mov(monto, categoria="Mercado", tipo="gasto", fecha=HOY, descripcion="x"):
    return d.Movimiento(fecha, monto, descripcion, categoria, "Débito", tipo)


class TestValidacion:
    def test_movimiento_valido(self):
        m = mov(1000)
        assert d.validar_movimiento(m) is m

    @pytest.mark.parametrize("monto", [0, -5])
    def test_monto_no_positivo(self, monto):
        with pytest.raises(d.DatoInvalido):
            d.validar_movimiento(mov(monto))

    def test_tipo_invalido(self):
        with pytest.raises(d.DatoInvalido):
            d.validar_movimiento(mov(100, tipo="regalo"))

    def test_categoria_invalida_en_gasto(self):
        with pytest.raises(d.DatoInvalido):
            d.validar_movimiento(mov(100, categoria="Casino"))

    def test_descripcion_vacia(self):
        with pytest.raises(d.DatoInvalido):
            d.validar_movimiento(mov(100, descripcion="   "))

    def test_gasto_compartido_sin_personas(self):
        with pytest.raises(d.DatoInvalido):
            d.validar_gasto_compartido(d.GastoCompartido(HOY, 100, "x", "a", ()))

    def test_gasto_compartido_personas_repetidas(self):
        with pytest.raises(d.DatoInvalido):
            d.validar_gasto_compartido(d.GastoCompartido(HOY, 100, "x", "a", ("a", "a")))

    def test_gasto_compartido_monto_invalido(self):
        with pytest.raises(d.DatoInvalido):
            d.validar_gasto_compartido(d.GastoCompartido(HOY, 0, "x", "a", ("a",)))


class TestPersonal:
    def test_proyeccion_topes(self):
        hoy = date(2026, 11, 10)
        movs = [mov(300, "Mercado", fecha=date(2026, 11, 5)), mov(200, "Comida", fecha=date(2026, 11, 7))]
        proyeccion = d.proyeccion_topes(movs, {"Mercado": 700, "Comida": 500}, hoy)
        mercado = next(x for x in proyeccion if x["categoria"] == "Mercado")
        assert mercado["gastado"] == 300
        assert mercado["proyectado"] == 900
        assert mercado["riesgo"] is True
    def test_del_mes_filtra(self):
        movs = [mov(1, fecha=date(2026, 11, 1)), mov(2, fecha=date(2026, 10, 31))]
        assert [m.monto for m in d.del_mes(movs, 2026, 11)] == [1]

    def test_retiro_no_es_gasto(self):
        movs = [mov(100), mov(500, tipo="retiro", categoria="Otros")]
        assert d.total(movs, "gasto") == 100
        assert d.gastos_por_categoria(movs) == {"Mercado": 100}

    def test_gastos_por_categoria_ordenados(self):
        movs = [mov(100, "Comida"), mov(300, "Mercado"), mov(50, "Comida")]
        assert list(d.gastos_por_categoria(movs).items()) == [("Mercado", 300), ("Comida", 150)]

    def test_alertas_topes(self):
        alertas = d.alertas_topes({"Mercado": 800, "Comida": 100}, {"Mercado": 700, "Comida": 200, "Ocio": 0})
        assert alertas == [{"categoria": "Mercado", "gastado": 800, "tope": 700, "exceso": 100}]

    def test_tendencia_cruza_anio(self):
        movs = [mov(10, fecha=date(2025, 12, 5)), mov(20, fecha=date(2026, 1, 5))]
        assert d.tendencia_mensual(movs, date(2026, 1, 20), meses=3) == [("Nov", 0), ("Dic", 10), ("Ene", 20)]

    def test_gastos_por_dia(self):
        movs = [
            mov(100, fecha=date(2026, 11, 17)),
            mov(50, fecha=date(2026, 11, 17)),
            mov(30, fecha=date(2026, 11, 15)),
            mov(999, tipo="ingreso", fecha=date(2026, 11, 16)),
            mov(7, fecha=date(2026, 11, 1)),
        ]
        assert d.gastos_por_dia(movs, date(2026, 11, 17), dias=3) == [("D", 30), ("L", 0), ("M", 150)]

    def test_orden_avalancha(self):
        deudas = [
            d.Deuda("cero", 500, 0.0, 10),
            d.Deuda("cara", 100, 28.5, 10),
            d.Deuda("media", 1000, 15.0, 10),
            d.Deuda("pagada", 0, 40.0, 0),
        ]
        assert [x.nombre for x in d.orden_pago_deudas(deudas)] == ["cara", "media", "cero"]


class TestCompartido:
    def test_saldos_division_igual(self):
        gastos = [d.GastoCompartido(HOY, 300, "m", "ana", ("ana", "bea", "caro"))]
        assert d.saldos(gastos, []) == {"ana": 200, "bea": -100, "caro": -100}

    def test_saldos_suman_cero_con_residuo(self):
        gastos = [d.GastoCompartido(HOY, 100, "m", "ana", ("ana", "bea", "caro"))]
        netos = d.saldos(gastos, [])
        assert sum(netos.values()) == 0

    def test_pago_reduce_deuda(self):
        gastos = [d.GastoCompartido(HOY, 200, "m", "ana", ("ana", "bea"))]
        pagos = [d.Pago(HOY, "bea", "ana", 100)]
        assert d.saldos(gastos, pagos) == {"ana": 0, "bea": 0}

    def test_quien_paga_no_participa(self):
        gastos = [d.GastoCompartido(HOY, 100, "regalo", "ana", ("bea",))]
        assert d.saldos(gastos, []) == {"ana": 100, "bea": -100}

    def test_simplificar(self):
        transf = d.simplificar({"ana": 200, "bea": -150, "caro": -50})
        assert sorted(transf) == [("bea", "ana", 150), ("caro", "ana", 50)]

    def test_simplificar_a_paz_y_salvo(self):
        assert d.simplificar({"ana": 0, "bea": 0}) == []

    def test_simplificar_varios_acreedores(self):
        netos = {"a": 100, "b": 50, "c": -120, "d": -30}
        transf = d.simplificar(netos)
        for persona, saldo in netos.items():
            recibido = sum(m for _, para, m in transf if para == persona)
            pagado = sum(m for de, _, m in transf if de == persona)
            assert recibido - pagado == saldo
        assert len(transf) <= len(netos) - 1


class TestResumenIA:
    def test_resumen_no_incluye_datos_sensibles(self):
        movs = [mov(100, descripcion="Farmacia secreta")]
        resumen = d.resumen_para_ia(movs, {"Mercado": 50}, [d.Deuda("Banco XYZ cuenta 1234", 1000, 20.0, 100)], -30)
        texto = str(resumen)
        assert "Farmacia secreta" not in texto
        assert "XYZ" not in texto and "1234" not in texto
        assert "Débito" not in texto
        assert resumen["categorias_excedidas"] == ["Mercado"]
        primera = resumen["deudas_en_orden_de_pago"][0]
        assert primera == {"deuda": "Deuda 1", "saldo": 1000, "tasa_ea": 20.0, "cuota": 100}
        assert resumen["saldo_compartido"] == -30


class TestCorreosYNombres:
    def test_leer_correos(self):
        assert d.leer_correos(" Ana@Gmail.com, sofia@gmail.com;ana@gmail.com\nx@y.co ") == [
            "ana@gmail.com", "sofia@gmail.com", "x@y.co"
        ]

    def test_leer_correos_vacio(self):
        assert d.leer_correos("") == []

    @pytest.mark.parametrize("malo", ["sin-arroba", "a@b", "a@@b.co", "@b.co"])
    def test_correo_invalido(self, malo):
        with pytest.raises(d.DatoInvalido):
            d.normalizar_correo(malo)

    def test_validar_nombre(self):
        assert d.validar_nombre("  Manu   Jiménez ") == "Manu Jiménez"
        with pytest.raises(d.DatoInvalido):
            d.validar_nombre("x" * 41)


class TestPlanificacion:
    def recurrente(self, **cambios):
        base = {"nombre": "Internet", "monto": 90000, "categoria": "Servicios", "frecuencia": "Mensual", "dia": 8}
        return d.GastoRecurrente(**{**base, **cambios})

    def meta(self, **cambios):
        base = {"nombre": "Viaje", "objetivo": 1000, "ahorrado": 100, "fecha_objetivo": date(2999, 1, 1)}
        return d.MetaAhorro(**{**base, **cambios})

    def test_recurrente_valido(self):
        r = self.recurrente()
        assert d.validar_gasto_recurrente(r) is r

    @pytest.mark.parametrize("cambios", [
        {"monto": 0}, {"categoria": "Inventada"}, {"frecuencia": "Semanal"}, {"dia": 0}, {"dia": 32},
    ])
    def test_recurrente_invalido(self, cambios):
        with pytest.raises(d.DatoInvalido):
            d.validar_gasto_recurrente(self.recurrente(**cambios))

    def test_meta_valida(self):
        m = self.meta()
        assert d.validar_meta_ahorro(m) is m

    @pytest.mark.parametrize("cambios", [
        {"objetivo": 0}, {"ahorrado": -1}, {"ahorrado": 2000}, {"fecha_objetivo": date(2000, 1, 1)},
    ])
    def test_meta_invalida(self, cambios):
        with pytest.raises(d.DatoInvalido):
            d.validar_meta_ahorro(self.meta(**cambios))


class TestInsignias:
    META = d.MetaAhorro("Viaje", 1000, 100, date(2999, 1, 1))
    MES_PASADO = date(2026, 10, 5)

    def ganadas(self, movimientos=(), topes=None, metas=(), hoy=HOY):
        insignias = d.calcular_insignias(list(movimientos), topes or {}, list(metas), hoy)
        return {i.nombre for i in insignias if i.ganada}

    def test_sin_datos_no_hay_insignias(self):
        assert self.ganadas() == set()

    def test_primer_paso_con_una_meta(self):
        assert self.ganadas(metas=[self.META]) == {"Primer paso"}

    def test_meta_cumplida(self):
        cumplida = d.MetaAhorro("Bici", 500, 500, date(2999, 1, 1))
        assert self.ganadas(metas=[self.META, cumplida]) == {"Primer paso", "Meta cumplida"}

    def test_mes_en_regla(self):
        movs = [mov(900, "Comida", fecha=self.MES_PASADO), mov(5000, "Comida")]  # el mes actual no cuenta
        assert self.ganadas(movs, topes={"Comida": 1000}) == {"Mes en regla"}

    def test_mes_pasado_con_tope_excedido(self):
        movs = [mov(1500, "Comida", fecha=self.MES_PASADO)]
        assert "Mes en regla" not in self.ganadas(movs, topes={"Comida": 1000})

    def test_mes_en_regla_exige_topes_y_gastos(self):
        assert "Mes en regla" not in self.ganadas([mov(900, fecha=self.MES_PASADO)])
        assert "Mes en regla" not in self.ganadas(topes={"Comida": 1000})

    def test_en_enero_revisa_diciembre(self):
        movs = [mov(900, "Comida", fecha=date(2025, 12, 20))]
        assert self.ganadas(movs, topes={"Comida": 1000}, hoy=date(2026, 1, 10)) == {"Mes en regla"}
