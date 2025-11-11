from flask import Flask, render_template, request, jsonify, session, send_file
import mysql.connector
import csv
from datetime import datetime
import io, os
import pandas as pd

app = Flask(__name__)

# ✅ Conexión a la base de datos en Railway
conexion = mysql.connector.connect(
    host="ballast.proxy.rlwy.net",
    user="root",
    password="vXHqCOqIIRnoGkbQUChYlJHRwGreYPMo",
    database="railway",
    port=55572
)

# ------------------- RUTAS PRINCIPALES -------------------

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/verificar_matricula', methods=['POST'])
def verificar_matricula():
    data = request.get_json()
    matricula = data.get("matricula")

    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT nombre, carrera, genero FROM estudiantes WHERE matricula = %s", (matricula,))
    resultado = cursor.fetchone()

    cursor.close()

    if resultado:
        return jsonify({
            "encontrado": True,
            "nombre": resultado['nombre'],
            "carrera": resultado['carrera'],
            "genero": resultado['genero']
        })
    else:
        return jsonify({"encontrado": False})

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
        cursor.close()
        return jsonify({"status": "success", "message": "Registro guardado correctamente"})
    except Exception as e:
        print("⚠ Error al registrar:", e)
        return jsonify({"status": "error", "message": "No se pudo guardar el registro"})

# ------------------- CARGA DE ESTUDIANTES -------------------

@app.route('/cargar_estudiantes')
def cargar_estudiantes():
    return render_template('cargar_estudiantes.html')

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

@app.route('/cargar_csv', methods=['POST'])
def cargar_csv():
    archivo = request.files['archivo']

    if not archivo.filename.endswith('.csv'):
        return render_template('cargar_estudiantes.html', mensaje="❌ Solo se permiten archivos .csv")

    csvfile = archivo.read().decode('utf-8').splitlines()
    lector = csv.reader(csvfile, delimiter=',')

    cursor = conexion.cursor()
    for fila in lector:
        matricula, nombre, carrera, genero = fila
        cursor.execute("""
            INSERT INTO estudiantes (matricula, nombre, carrera, genero)
            VALUES (%s, %s, %s, %s)
        """, (matricula, nombre, carrera, genero))
    conexion.commit()
    cursor.close()

    return render_template('cargar_estudiantes.html', mensaje="✅ Archivo cargado exitosamente")

# ------------------- REPORTES -------------------

@app.route('/reportes')
def reportes():
    return render_template('reportes.html')

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
    cursor.close()

    if not registros:
        return "No hay registros para ese periodo", 404

    df = pd.DataFrame(registros)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Registros')
    output.seek(0)

    nombre_archivo = f"reporte_{inicio}_a_{fin}.xlsx"

    return send_file(output, as_attachment=True, download_name=nombre_archivo,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# ------------------- CONFIGURACIÓN Y USUARIOS -------------------

@app.route("/configuracion")
def configuracion():
    return render_template("configuracion.html")

@app.route("/obtener_usuarios")
def obtener_usuarios():
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios")
    usuarios = cursor.fetchall()
    cursor.close()
    return jsonify({"status": "ok", "usuarios": usuarios})

@app.route("/crear_usuario", methods=["POST"])
def crear_usuario():
    data = request.get_json()
    nombre = data.get("nombre")
    usuario = data.get("usuario")
    contrasena = data.get("contraseña")
    rol = data.get("rol")

    cursor = conexion.cursor()
    cursor.execute(
        "INSERT INTO usuarios (nombre, usuario, contrasena, rol) VALUES (%s, %s, %s, %s)",
        (nombre, usuario, contrasena, rol)
    )
    conexion.commit()
    cursor.close()
    return jsonify({"status": "ok", "mensaje": "✅ Usuario creado correctamente."})

@app.route('/verificar_usuario', methods=['POST'])
def verificar_usuario():
    data = request.get_json()
    usuario = data['usuario']
    contrasena = data['contrasena']

    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE usuario=%s AND contrasena=%s", (usuario, contrasena))
    resultado = cursor.fetchone()
    cursor.close()

    if resultado:
        return jsonify({"status": "ok", "rol": resultado["rol"]})
    else:
        return jsonify({"status": "error", "mensaje": "Usuario o contraseña incorrectos."})

# ------------------- PÁGINAS HTML -------------------

@app.route("/autorizacion")
def autorizacion():
    return render_template("autorizacion.html")

@app.route("/ingreso")
def ingreso():
    return render_template("ingreso.html")

# ------------------- EJECUCIÓN -------------------

if __name__ == "__main__":
    app.run(debug=True)
