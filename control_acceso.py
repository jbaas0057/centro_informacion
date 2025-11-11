from flask import Flask, render_template, request, jsonify, session
import mysql.connector
import csv
from datetime import datetime
from flask import send_file
import io, os
import pandas as pd
import mysql.connector
from io import BytesIO

app = Flask(__name__)


# Conexión a la base de datos
conexion = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="centro_informacion"
)

# Ruta para cargar la página principal
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# Ruta para verificar matrícula (llamada desde JavaScript)
@app.route('/verificar_matricula', methods=['POST'])
def verificar_matricula():
    data = request.get_json()
    matricula = data.get("matricula")

    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT nombre, carrera, genero FROM estudiantes WHERE matricula = %s", (matricula,))
    resultado = cursor.fetchone()

    if resultado:
        return jsonify({
            "encontrado": True,
            "nombre": resultado['nombre'],
            "carrera": resultado['carrera'],
            "genero": resultado['genero']
        })
    else:
        return jsonify({"encontrado": False})

# Ruta para registrar entrada
@app.route('/registrar', methods=['POST'])
def registrar():
    matricula = request.form.get('matricula')
    nombre = request.form.get('nombre')
    carrera = request.form.get('carrera')
    genero = request.form.get('genero', None)

    ahora = datetime.now()
    fecha = ahora.date()
    hora = ahora.time()

    try:
        cursor = conexion.cursor()
        sql = "INSERT INTO registro (matricula, nombre, carrera, genero, fecha, hora) VALUES (%s, %s, %s, %s, %s, %s)"
        valores = (matricula, nombre, carrera, genero, fecha, hora)
        cursor.execute(sql, valores)
        conexion.commit()

        return jsonify({"status": "success", "message": "Registro guardado correctamente"})
    except Exception as e:
        print("⚠ Error al registrar:", e)
        return jsonify({"status": "error", "message": "No se pudo guardar el registro"})

# Página para cargar estudiantes
@app.route('/cargar_estudiantes')
def cargar_estudiantes():
    return render_template('cargar_estudiantes.html')

# Agregar estudiante de forma manual
@app.route('/agregar_estudiante', methods=['POST'])
def agregar_estudiante():
    matricula = request.form.get('matricula')
    nombre = request.form.get('nombre')
    carrera = request.form.get('carrera')
    genero = request.form.get('genero', None)
    cursor = conexion.cursor()

    cursor.execute("SELECT * FROM estudiantes WHERE matricula = %s", (matricula,))
    existe = cursor.fetchone()

    if existe:
        mensaje = "⚠ La matrícula ya está registrada."
    else:
        cursor.execute("INSERT INTO estudiantes (matricula, nombre, carrera, genero) VALUES (%s, %s, %s, %s)",
                       (matricula, nombre, carrera, genero))
        conexion.commit()
        mensaje = "✅ Estudiante agregado correctamente."

    cursor.close()
    return render_template("cargar_estudiantes.html", mensaje=mensaje)

# ✅ Carga masiva desde CSV (SIEMPRE con 4 columnas)
@app.route('/cargar_csv', methods=['POST'])
def cargar_csv():
    archivo = request.files['archivo']

    if not archivo.filename.endswith('.csv'):
        return render_template('cargar_estudiantes.html', mensaje="❌ Solo se permiten archivos .csv")

    # Leer el archivo y procesarlo
    csvfile = archivo.read().decode('utf-8').splitlines()
    lector = csv.reader(csvfile, delimiter=',')

    cursor = conexion.cursor()
    for fila in lector:
        # 📌 Asignamos cada columna correctamente
        matricula, nombre, carrera, genero = fila

        # Insertamos en la tabla estudiantes
        cursor.execute("""
            INSERT INTO estudiantes (matricula, nombre, carrera, genero)
            VALUES (%s, %s, %s, %s)
        """, (matricula, nombre, carrera, genero))

    # Guardamos cambios
    conexion.commit()
    cursor.close()

    return render_template('cargar_estudiantes.html', mensaje="✅ Archivo cargado exitosamente")

# Ruta para mostrar la página de reportes
@app.route('/reportes')
def reportes():
    return render_template('reportes.html')


# Ruta para generar el reporte
@app.route('/generar_reporte', methods=['POST'])
def generar_reporte():
    fecha_inicio = request.form['fecha_inicio']
    fecha_fin = request.form['fecha_fin']

    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM registro
        WHERE fecha BETWEEN %s AND %s
        ORDER BY fecha, hora
    """, (fecha_inicio, fecha_fin))

    registros = cursor.fetchall()
    cursor.close()

    if not registros:
        return render_template('reportes.html', mensaje="⚠ No se encontraron registros en ese periodo.")

    # Por ahora, mostramos cuántos resultados hay (luego podemos exportar a Excel o PDF)
    mensaje = f"✅ Se encontraron {len(registros)} registros entre {fecha_inicio} y {fecha_fin}."
    return render_template('reportes.html', mensaje=mensaje)

@app.route('/generar_excel', methods=['GET'])
def generar_excel():
    inicio = request.args.get('inicio')
    fin = request.args.get('fin')

    if not inicio or not fin:
        return "Faltan fechas", 400

    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT matricula, nombre, carrera, fecha, hora, genero
        FROM registro
        WHERE fecha BETWEEN %s AND %s
        ORDER BY fecha, hora
    """, (inicio, fin))
    registros = cursor.fetchall()

    if not registros:
        return "No hay registros para ese periodo", 404

    # Convertir a DataFrame de pandas
    df = pd.DataFrame(registros)

    # Crear archivo Excel en memoria
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Registros')
    output.seek(0)

    # Nombre del archivo
    nombre_archivo = f"reporte_{inicio}_a_{fin}.xlsx"

    return send_file(output, as_attachment=True, download_name=nombre_archivo,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/principal')
def principal():
    return render_template('principal.html')

# 🔹 Rutas base
RUTA_ENCABEZADO = os.path.join("static", "imagenes")
RUTA_MENU = os.path.join("static", "imagenes", "menu")

@app.route("/configuracion")
def configuracion():
    return render_template("configuracion.html")

@app.route("/subir_imagen", methods=["POST"])
def subir_imagen():
    try:
        tipo = request.form.get("tipo")
        archivo = request.files.get("imagen")

        if not archivo or archivo.filename == "":
            return jsonify({"status": "error", "mensaje": "No se seleccionó ningún archivo."})

        # 🔹 Seleccionar carpeta destino
        if tipo == "encabezado":
            ruta_destino = RUTA_ENCABEZADO
        elif tipo == "menu":
            ruta_destino = RUTA_MENU
        else:
            return jsonify({"status": "error", "mensaje": "Tipo de imagen no válido."})

        os.makedirs(ruta_destino, exist_ok=True)

        # 🔹 Si es encabezado, siempre se guarda con nombre fijo
        if tipo == "encabezado":
            archivo_destino = os.path.join(ruta_destino, "encabezado1.png")
        else:
            archivo_destino = os.path.join(ruta_destino, archivo.filename)

        # 🔁 Sobrescribir el archivo
        archivo.save(archivo_destino)

        return jsonify({
            "status": "ok",
            "mensaje": f"✅ Imagen '{archivo.filename}' actualizada correctamente."
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "mensaje": f"❌ Error al subir la imagen: {str(e)}"
        })

# ➕ Crear usuario
@app.route("/crear_usuario", methods=["POST"])
def crear_usuario():
    try:
        data = request.get_json()
        nombre = data.get("nombre")
        usuario = data.get("usuario")
        contraseña = data.get("contraseña")
        rol = data.get("rol")

        if not all([nombre, usuario, contraseña, rol]):
            return jsonify({"status": "error", "mensaje": "Todos los campos son obligatorios."})

        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="centro_informacion"
        )
        cursor = conn.cursor()

        # Insertar nuevo usuario
        sql = "INSERT INTO usuarios (nombre, usuario, contraseña, rol) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, (nombre, usuario, contraseña, rol))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"status": "ok", "mensaje": f"✅ Usuario '{nombre}' creado correctamente."})

    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Error al crear usuario: {str(e)}"})


@app.route("/obtener_usuarios")
def obtener_usuarios():
    try:
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="centro_informacion"
        )
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios")
        usuarios = cursor.fetchall()
        conexion.close()
        return jsonify({"status": "ok", "usuarios": usuarios})
    except Exception as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 500


@app.route("/actualizar_usuario", methods=["POST"])
def actualizar_usuario():
    try:
        datos = request.get_json()
        id_usuario = datos.get("id")
        nombre = datos.get("nombre")
        usuario = datos.get("usuario")
        rol = datos.get("rol")

        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="centro_informacion"
        )
        cursor = conexion.cursor()
        cursor.execute(
            "UPDATE usuarios SET nombre=%s, usuario=%s, rol=%s WHERE id=%s",
            (nombre, usuario, rol, id_usuario)
        )
        conexion.commit()
        cursor.close()
        conexion.close()

        return jsonify({"status": "ok", "mensaje": "✅ Usuario actualizado correctamente"})
    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Error al actualizar: {str(e)}"})


@app.route("/eliminar_usuario", methods=["POST"])
def eliminar_usuario():
    try:
        datos = request.get_json()
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="centro_informacion"
        )
        cursor = conexion.cursor()
        cursor.execute("DELETE FROM usuarios WHERE id = %s", (datos["id"],))
        conexion.commit()
        conexion.close()
        return jsonify({"status": "ok", "mensaje": "🗑️ Usuario eliminado correctamente."})
    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Error al eliminar: {str(e)}"}), 500

@app.route("/modificar_usuario", methods=["POST"])
def modificar_usuario():
    try:
        datos = request.get_json()
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="centro_informacion"
        )
        cursor = conexion.cursor()

        query = """
        UPDATE usuarios
        SET nombre=%s, usuario=%s, contraseña=%s, rol=%s
        WHERE id=%s
        """
        valores = (
            datos["nombre"],
            datos["usuario"],
            datos["contraseña"],
            datos["rol"],
            datos["id"]
        )

        cursor.execute(query, valores)
        conexion.commit()
        conexion.close()

        return jsonify({"status": "ok", "mensaje": "✅ Usuario actualizado correctamente."})
    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Error al modificar: {str(e)}"}), 500

@app.route("/verificar_rol")
def verificar_rol():
    from flask import session
    rol = session.get("rol", "usuario")  # valor por defecto si no hay sesión
    return jsonify({"rol": rol})

@app.route('/verificar_usuario', methods=['POST'])
def verificar_usuario():
    data = request.get_json()
    usuario = data['usuario']
    contrasena = data['contrasena']

    conexion = mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='centro_informacion'
    )
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE usuario=%s AND contrasena=%s", (usuario, contrasena))
    resultado = cursor.fetchone()

    if resultado:
        return jsonify({"status": "ok", "rol": resultado["rol"]})
    else:
        return jsonify({"status": "error", "mensaje": "Usuario o contraseña incorrectos."})

@app.route('/')
def login():
    return render_template('autorizacion.html')

@app.route("/autorizacion")
def autorizacion():
    return render_template("autorizacion.html")

@app.route("/ingreso")
def ingreso():
    return render_template("ingreso.html")


# Ejecutar aplicación
if __name__ == "__main__":
    app.run(debug=True)
