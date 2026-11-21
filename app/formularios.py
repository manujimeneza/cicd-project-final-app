from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import (
    DateField,
    DecimalField,
    HiddenField,
    IntegerField,
    SelectField,
    SelectMultipleField,
    StringField,
    TextAreaField,
)
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange

from app.dominio import CATEGORIAS, MEDIOS, TIPOS


class MovimientoForm(FlaskForm):
    tipo = SelectField("Tipo", choices=[(t, t.capitalize()) for t in TIPOS])
    monto = IntegerField("Monto", validators=[DataRequired(), NumberRange(min=1, max=1_000_000_000)])
    descripcion = StringField("Descripción", validators=[DataRequired(), Length(max=80)])
    categoria = SelectField("Categoría", choices=[(c, c) for c in CATEGORIAS])
    medio = SelectField("Medio", choices=[(m, m) for m in MEDIOS])
    fecha = DateField("Fecha", validators=[DataRequired()])


class GastoGrupoForm(FlaskForm):
    monto = IntegerField("Monto", validators=[DataRequired(), NumberRange(min=1, max=1_000_000_000)])
    descripcion = StringField("Descripción", validators=[DataRequired(), Length(max=80)])
    pagado_por = SelectField("¿Quién pagó?")
    dividido_entre = SelectMultipleField("Dividir entre", validators=[DataRequired()])
    fecha = DateField("Fecha", validators=[DataRequired()])


class EditarGastoGrupoForm(GastoGrupoForm):
    fecha = None  # la fecha no se edita (forma parte de la clave del registro)
    version = HiddenField()
    motivo = StringField("Motivo del cambio", validators=[DataRequired(), Length(max=120)])


class EditarPagoForm(FlaskForm):
    monto = IntegerField("Monto", validators=[DataRequired(), NumberRange(min=1, max=1_000_000_000)])
    version = HiddenField()
    motivo = StringField("Motivo del cambio", validators=[DataRequired(), Length(max=120)])


class AnularForm(FlaskForm):
    version = HiddenField()
    motivo = StringField("Motivo", validators=[DataRequired(), Length(max=120)])


class RegistroForm(FlaskForm):
    nombre = StringField("¿Cómo te llamas?", validators=[DataRequired(), Length(max=40)])


class GrupoForm(FlaskForm):
    nombre = StringField("Nombre del grupo", validators=[DataRequired(), Length(max=40)])
    correos = TextAreaField("Correos de las personas (separados por coma)", validators=[Length(max=1000)])


class InvitarForm(FlaskForm):
    correo = StringField("Correo", validators=[DataRequired(), Length(max=254)])


class PagoForm(FlaskForm):
    de = SelectField("¿Quién pagó?")
    para = SelectField("¿A quién?")
    monto = IntegerField("Monto", validators=[DataRequired(), NumberRange(min=1, max=1_000_000_000)])


class FotoForm(FlaskForm):
    foto = FileField("Foto de perfil", validators=[FileRequired()])


class DeudaForm(FlaskForm):
    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=40)])
    saldo = IntegerField("Saldo pendiente", validators=[DataRequired(), NumberRange(min=1, max=10_000_000_000)])
    tasa_ea = DecimalField(
        "Tasa efectiva anual (%)", places=2, validators=[InputRequired(), NumberRange(min=0, max=200)]
    )
    cuota = IntegerField("Cuota mensual", validators=[InputRequired(), NumberRange(min=0, max=1_000_000_000)])


class PreguntaForm(FlaskForm):
    pregunta = TextAreaField("Pregunta", validators=[DataRequired(), Length(max=500)])
    siguiente = HiddenField()


class RecurrenteForm(FlaskForm):
    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=40)])
    monto = IntegerField("Monto", validators=[DataRequired(), NumberRange(min=1, max=1_000_000_000)])
    categoria = SelectField("Categoría", choices=[(c, c) for c in CATEGORIAS])
    frecuencia = SelectField("Frecuencia", choices=[("Mensual", "Mensual"), ("Anual", "Anual")])
    dia = IntegerField("Día del mes", validators=[DataRequired(), NumberRange(min=1, max=31)])


class MetaAhorroForm(FlaskForm):
    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=40)])
    objetivo = IntegerField("Monto objetivo", validators=[DataRequired(), NumberRange(min=1, max=10_000_000_000)])
    ahorrado = IntegerField("Ya ahorrado", validators=[InputRequired(), NumberRange(min=0, max=10_000_000_000)])
    fecha_objetivo = DateField("Fecha objetivo", validators=[DataRequired()])
