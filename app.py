from flask import Flask, render_template, request, redirect, session, flash
import mysql.connector
import os

app = Flask(__name__)
app.config["PROPAGATE_EXCEPTIONS"] = True
app.secret_key = "clave_secreta"


# CONEXIÓN
def get_db():
    conexion = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT")),
        auth_plugin='mysql_native_password'
    )
    return conexion, conexion.cursor(dictionary=True)


# INICIO
@app.route("/")
def inicio():
    return render_template("inicio.html")


# FORMULARIO
@app.route("/formulario")
def formulario():

    conexion, cursor = get_db()

    cursor.execute("SELECT * FROM niveles")
    niveles = cursor.fetchall()

    cursor.execute("SELECT * FROM especialidades")
    especialidades = cursor.fetchall()

    conexion.close()

    return render_template("formulario.html",
                           niveles=niveles,
                           especialidades=especialidades)


# REGISTRO
@app.route("/inscribirse", methods=["POST"])
def inscribirse():

    nombre = request.form["nombre"]
    apellido = request.form["apellido"]
    correo = request.form["correo"]
    genero = request.form["genero"]
    nivel = request.form["nivel"]
    especialidad = request.form["especialidad"]

    if "@" not in correo or not correo.endswith("@donboscolatola.edu.ec"):
        return "Correo institucional inválido"

    conexion, cursor = get_db()

    cursor.execute("SELECT * FROM estudiantes WHERE correo_institucional=%s", (correo,))
    if cursor.fetchone():
        conexion.close()
        return "Este correo ya está registrado"

    cursor.execute("""
        INSERT INTO estudiantes
        (nombres, apellidos, correo_institucional, genero, id_nivel, id_especialidad)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (nombre, apellido, correo, genero, nivel, especialidad))

    conexion.commit()
    id_estudiante = cursor.lastrowid
    conexion.close()

    session["id_estudiante"] = id_estudiante
    session["nivel"] = nivel

    return redirect("/clubes")


# CLUBES
@app.route("/clubes")
def clubes():

    if "id_estudiante" not in session:
        return redirect("/formulario")

    nivel = session["nivel"]

    conexion, cursor = get_db()

    cursor.execute("""
        SELECT clubes.*,
        clubes.cupo_maximo - COUNT(inscripciones.id_inscripcion) AS cupos_restantes
        FROM clubes
        LEFT JOIN inscripciones
        ON clubes.id_club = inscripciones.id_club
        WHERE clubes.id_nivel = %s AND clubes.activo = 1
        GROUP BY clubes.id_club
    """, (nivel,))

    clubes = cursor.fetchall()
    conexion.close()

    return render_template("clubes.html", clubes=clubes)


# INSCRIBIR CLUB
@app.route("/inscribir_club", methods=["POST"])
def inscribir_club():

    if "id_estudiante" not in session:
        return redirect("/")

    estudiante = session["id_estudiante"]
    club = request.form["club"]

    conexion, cursor = get_db()

    cursor.execute("SELECT * FROM inscripciones WHERE id_estudiante=%s", (estudiante,))
    if cursor.fetchone():
        conexion.close()
        return "Este estudiante ya está inscrito en un club"

    cursor.execute("""
        SELECT clubes.cupo_maximo,
        COUNT(inscripciones.id_inscripcion) AS usados
        FROM clubes
        LEFT JOIN inscripciones ON clubes.id_club = inscripciones.id_club
        WHERE clubes.id_club = %s
        GROUP BY clubes.id_club
    """, (club,))

    datos = cursor.fetchone()

    if datos["usados"] >= datos["cupo_maximo"]:
        conexion.close()
        return "Este club ya no tiene cupos disponibles"

    cursor.execute("""
        INSERT INTO inscripciones (id_estudiante,id_club)
        VALUES (%s,%s)
    """, (estudiante, club))

    conexion.commit()
    conexion.close()

    session.pop("id_estudiante", None)
    session.pop("nivel", None)

    flash("Inscripción completada correctamente")
    return redirect("/")


# LOGIN ADMIN
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        usuario = request.form["usuario"]
        password = request.form["password"]

        conexion, cursor = get_db()

        cursor.execute("SELECT * FROM admin WHERE usuario=%s", (usuario,))
        admin = cursor.fetchone()

        conexion.close()

        if admin and admin["password"] == password:
            session["admin"] = True
            return redirect("/admin")

        flash("Usuario o contraseña incorrectos")
        return redirect("/login")

    return render_template("login.html")


# 🔥 ESTA ES LA QUE TE FALTABA (CAUSA DEL 404)
@app.route("/admin")
def admin():

    if "admin" not in session:
        return redirect("/login")

    conexion, cursor = get_db()

    cursor.execute("""
        SELECT clubes.*, niveles.nombre_nivel,
        COUNT(inscripciones.id_inscripcion) AS cupos_usados
        FROM clubes
        LEFT JOIN inscripciones ON clubes.id_club = inscripciones.id_club
        JOIN niveles ON clubes.id_nivel = niveles.id_nivel
        GROUP BY clubes.id_club
    """)

    clubes = cursor.fetchall()

    cursor.execute("SELECT * FROM niveles")
    niveles = cursor.fetchall()

    conexion.close()

    return render_template("admin.html",
                           clubes=clubes,
                           niveles=niveles)


# CREAR CLUB
@app.route("/crear_club", methods=["POST"])
def crear_club():

    if "admin" not in session:
        return redirect("/login")

    nombre = request.form.get("nombre")
    cupo = request.form.get("cupo")
    nivel = request.form.get("nivel")

    if not nombre or not cupo or not nivel:
        return "Faltan datos"

    try:
        cupo = int(cupo)
    except:
        return "Cupo inválido"

    if cupo <= 0:
        return "Cupo debe ser mayor a 0"

    conexion, cursor = get_db()

    cursor.execute("""
        INSERT INTO clubes (nombre_club,cupo_maximo,id_nivel,activo)
        VALUES (%s,%s,%s,1)
    """, (nombre, cupo, nivel))

    conexion.commit()
    conexion.close()

    return redirect("/admin")


# ACTIVAR / DESACTIVAR
@app.route("/desactivar/<id>")
def desactivar(id):

    if "admin" not in session:
        return redirect("/login")

    conexion, cursor = get_db()
    cursor.execute("UPDATE clubes SET activo=0 WHERE id_club=%s", (id,))
    conexion.commit()
    conexion.close()

    return redirect("/admin")


@app.route("/activar/<id>")
def activar(id):

    if "admin" not in session:
        return redirect("/login")

    conexion, cursor = get_db()
    cursor.execute("UPDATE clubes SET activo=1 WHERE id_club=%s", (id,))
    conexion.commit()
    conexion.close()

    return redirect("/admin")


# ADMIN INSCRIPCIONES
@app.route("/admin_inscripciones")
def admin_inscripciones():

    if "admin" not in session:
        return redirect("/login")

    conexion, cursor = get_db()

    cursor.execute("""
        SELECT clubes.id_nivel, clubes.nombre_club,
        estudiantes.nombres, estudiantes.apellidos,
        estudiantes.correo_institucional, estudiantes.genero,
        especialidades.nombre_especialidad
        FROM inscripciones
        JOIN estudiantes ON inscripciones.id_estudiante = estudiantes.id_estudiante
        JOIN clubes ON inscripciones.id_club = clubes.id_club
        JOIN especialidades ON estudiantes.id_especialidad = especialidades.id_especialidad
    """)

    datos = cursor.fetchall()
    conexion.close()

    primero = [e for e in datos if e["id_nivel"] == 1]
    segundo = [e for e in datos if e["id_nivel"] == 2]
    tercero = [e for e in datos if e["id_nivel"] == 3]

    return render_template("admin_inscripciones.html",
                           primero=primero,
                           segundo=segundo,
                           tercero=tercero)


# LOGOUT
@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/")


if __name__ == "__main__":
    app.run()
