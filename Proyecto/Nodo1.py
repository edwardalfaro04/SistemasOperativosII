from replicacion import (
    replicar_archivo,
    replicar_version,
    eliminar_archivo_remoto,
    procesar_pendientes
)
import socket
import threading
import os
import json
import shutil
from datetime import datetime


HOST = "0.0.0.0"
PORT = 5000

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

STORAGE_DIR = os.path.join(
    BASE_DIR,
    "almacenamiento"
)

VERSIONS_DIR = os.path.join(
    BASE_DIR,
    "versiones"
)

LOG_DIR = os.path.join(
    BASE_DIR,
    "logs"
)

LOG_FILE = os.path.join(
    LOG_DIR,
    "servidor.log"
)


os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(VERSIONS_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


# Protege el acceso simultáneo a los archivos
file_lock = threading.Lock()


def registrar_log(mensaje):

    fecha = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    texto = f"[{fecha}] {mensaje}"

    print(texto)

    with open(
        LOG_FILE,
        "a",
        encoding="utf-8"
    ) as archivo:

        archivo.write(
            texto + "\n"
        )


def enviar_mensaje(cliente, datos):

    mensaje = json.dumps(
        datos
    )

    mensaje += "\n"

    cliente.sendall(
        mensaje.encode("utf-8")
    )


def recibir_mensaje(cliente):

    datos = b""

    while b"\n" not in datos:

        parte = cliente.recv(1)

        if not parte:

            return None

        datos += parte

    linea = datos.split(
        b"\n",
        1
    )[0]

    return json.loads(
        linea.decode("utf-8")
    )


def obtener_versiones(nombre):

    versiones = []

    for archivo in os.listdir(
        VERSIONS_DIR
    ):

        if archivo.startswith(
            nombre + ".v"
        ):

            versiones.append(
                archivo
            )

    versiones.sort()

    return versiones


def crear_version(nombre):

    archivo_original = os.path.join(
        STORAGE_DIR,
        nombre
    )

    if not os.path.exists(
        archivo_original
    ):

        return None

    versiones = obtener_versiones(
        nombre
    )

    numero = len(versiones) + 1

    nombre_version = (
        f"{nombre}.v{numero}"
    )

    ruta_version = os.path.join(
        VERSIONS_DIR,
        nombre_version
    )

    shutil.copy2(
        archivo_original,
        ruta_version
    )

    return nombre_version


def listar_archivos():

    archivos = []

    for nombre in os.listdir(
        STORAGE_DIR
    ):

        ruta = os.path.join(
            STORAGE_DIR,
            nombre
        )

        if os.path.isfile(ruta):

            archivos.append(
                {
                    "nombre": nombre,
                    "tamanio": os.path.getsize(ruta)
                }
            )

    return archivos


def recibir_archivo(
    cliente,
    nombre,
    tamanio
):

    ruta = os.path.join(
        STORAGE_DIR,
        nombre
    )

    bytes_recibidos = 0

    with open(
        ruta,
        "wb"
    ) as archivo:

        while bytes_recibidos < tamanio:

            datos = cliente.recv(
                min(
                    4096,
                    tamanio - bytes_recibidos
                )
            )

            if not datos:

                break

            archivo.write(
                datos
            )

            bytes_recibidos += len(
                datos
            )

    return bytes_recibidos


def enviar_archivo(
    cliente,
    nombre
):

    ruta = os.path.join(
        STORAGE_DIR,
        nombre
    )

    if not os.path.exists(ruta):

        enviar_mensaje(
            cliente,
            {
                "estado": "error",
                "mensaje": "Archivo no encontrado"
            }
        )

        return

    tamanio = os.path.getsize(
        ruta
    )

    enviar_mensaje(
        cliente,
        {
            "estado": "ok",
            "tamanio": tamanio,
            "nombre": nombre
        }
    )

    with open(
        ruta,
        "rb"
    ) as archivo:

        while True:

            datos = archivo.read(
                4096
            )

            if not datos:

                break

            cliente.sendall(
                datos
            )


def manejar_cliente(
    cliente,
    direccion
):

    registrar_log(
        f"Cliente conectado: {direccion}"
    )

    try:

        while True:

            solicitud = recibir_mensaje(
                cliente
            )

            if solicitud is None:

                break

            comando = solicitud.get(
                "comando"
            )

            registrar_log(
                f"{direccion} -> {comando}"
            )


            # LISTAR

            if comando == "LISTAR":

                archivos = listar_archivos()

                enviar_mensaje(
                    cliente,
                    {
                        "estado": "ok",
                        "archivos": archivos
                    }
                )


            # SUBIR

            elif comando == "SUBIR":

                nombre = solicitud["nombre"]
                tamanio = solicitud["tamanio"]

                ruta = os.path.join(
                    STORAGE_DIR,
                    nombre
                )

                with file_lock:

                    version = None

                    if os.path.exists(ruta):

                        version = crear_version(
                            nombre
                        )

                    enviar_mensaje(
                        cliente,
                        {
                            "estado": "listo"
                        }
                    )

                    recibidos = recibir_archivo(
                        cliente,
                        nombre,
                        tamanio
                    )

                if recibidos == tamanio:

                    replica_ok = replicar_archivo(
                        ruta,
                        nombre
                    )

                    version_replica_ok = True

                    if version:

                        ruta_version = os.path.join(
                            VERSIONS_DIR,
                            version
                        )

                        version_replica_ok = replicar_version(
                            ruta_version,
                            version
                        )

                    enviar_mensaje(
                        cliente,
                        {
                            "estado": "ok",
                            "mensaje": "Archivo subido correctamente",
                            "version": version,
                            "replicado": replica_ok,
                            "version_replicada": version_replica_ok
                        }
                    )

                    registrar_log(
                        f"Archivo subido: {nombre}"
                    )

                    if replica_ok:

                        registrar_log(
                            f"Replicacion Nodo 1 -> Nodo 2 exitosa: {nombre}"
                        )

                    else:

                        registrar_log(
                            f"Nodo 2 no disponible. Cambio pendiente: {nombre}"
                        )

                else:

                    enviar_mensaje(
                        cliente,
                        {
                            "estado": "error",
                            "mensaje": "Transferencia incompleta"
                        }
                    )


            # REPLICAR ARCHIVO

            elif comando == "REPLICAR":

                nombre = solicitud["nombre"]
                tamanio = solicitud["tamanio"]

                enviar_mensaje(
                    cliente,
                    {
                        "estado": "listo"
                    }
                )

                recibidos = recibir_archivo(
                    cliente,
                    nombre,
                    tamanio
                )

                if recibidos == tamanio:

                    enviar_mensaje(
                        cliente,
                        {
                            "estado": "ok",
                            "mensaje": "Replica almacenada"
                        }
                    )

                    registrar_log(
                        f"Replica recibida: {nombre}"
                    )

                else:

                    enviar_mensaje(
                        cliente,
                        {
                            "estado": "error",
                            "mensaje": "Replica incompleta"
                        }
                    )


            # REPLICAR VERSION

            elif comando == "REPLICAR_VERSION":

                nombre = solicitud["nombre"]
                tamanio = solicitud["tamanio"]

                ruta_version = os.path.join(
                    VERSIONS_DIR,
                    nombre
                )

                enviar_mensaje(
                    cliente,
                    {
                        "estado": "listo"
                    }
                )

                recibidos = 0

                with open(
                    ruta_version,
                    "wb"
                ) as archivo:

                    while recibidos < tamanio:

                        datos = cliente.recv(
                            min(
                                4096,
                                tamanio - recibidos
                            )
                        )

                        if not datos:

                            break

                        archivo.write(
                            datos
                        )

                        recibidos += len(
                            datos
                        )

                if recibidos == tamanio:

                    enviar_mensaje(
                        cliente,
                        {
                            "estado": "ok",
                            "mensaje": "Version replicada"
                        }
                    )

                    registrar_log(
                        f"Version recibida: {nombre}"
                    )

                else:

                    enviar_mensaje(
                        cliente,
                        {
                            "estado": "error",
                            "mensaje": "Version incompleta"
                        }
                    )


            # DESCARGAR

            elif comando == "DESCARGAR":

                nombre = solicitud["nombre"]

                enviar_archivo(
                    cliente,
                    nombre
                )

                registrar_log(
                    f"Archivo descargado: {nombre}"
                )


            # VERSIONES

            elif comando == "VERSIONES":

                nombre = solicitud["nombre"]

                versiones = obtener_versiones(
                    nombre
                )

                enviar_mensaje(
                    cliente,
                    {
                        "estado": "ok",
                        "versiones": versiones
                    }
                )


            # ELIMINAR

            elif comando == "ELIMINAR":

                nombre = solicitud["nombre"]

                ruta = os.path.join(
                    STORAGE_DIR,
                    nombre
                )

                with file_lock:

                    if os.path.exists(ruta):

                        os.remove(ruta)

                        versiones_eliminadas = 0

                        for archivo_version in os.listdir(
                            VERSIONS_DIR
                        ):

                            if archivo_version.startswith(
                                nombre + ".v"
                            ):

                                ruta_version = os.path.join(
                                    VERSIONS_DIR,
                                    archivo_version
                                )

                                if os.path.isfile(
                                    ruta_version
                                ):

                                    os.remove(
                                        ruta_version
                                    )

                                    versiones_eliminadas += 1

                        replica_eliminada = eliminar_archivo_remoto(
                            nombre
                        )

                        enviar_mensaje(
                            cliente,
                            {
                                "estado": "ok",
                                "mensaje": "Archivo eliminado",
                                "versiones_eliminadas": versiones_eliminadas,
                                "replica_eliminada": replica_eliminada
                            }
                        )

                        registrar_log(
                            f"Archivo eliminado: {nombre}"
                        )

                        registrar_log(
                            f"Versiones eliminadas: {versiones_eliminadas}"
                        )

                        if replica_eliminada:

                            registrar_log(
                                f"Eliminacion replicada: {nombre}"
                            )

                        else:

                            registrar_log(
                                f"Eliminacion pendiente para el nodo remoto: {nombre}"
                            )

                    else:

                        enviar_mensaje(
                            cliente,
                            {
                                "estado": "error",
                                "mensaje": "Archivo no encontrado"
                            }
                        )


            # REPLICAR ELIMINACION

            elif comando == "REPLICAR_ELIMINAR":

                nombre = solicitud["nombre"]

                ruta = os.path.join(
                    STORAGE_DIR,
                    nombre
                )

                with file_lock:

                    if os.path.exists(ruta):

                        os.remove(ruta)

                        registrar_log(
                            f"Eliminacion recibida por replicacion: {nombre}"
                        )

                    versiones_eliminadas = 0

                    for archivo_version in os.listdir(
                        VERSIONS_DIR
                    ):

                        if archivo_version.startswith(
                            nombre + ".v"
                        ):

                            ruta_version = os.path.join(
                                VERSIONS_DIR,
                                archivo_version
                            )

                            if os.path.isfile(
                                ruta_version
                            ):

                                os.remove(
                                    ruta_version
                                )

                                versiones_eliminadas += 1

                    registrar_log(
                        f"Versiones eliminadas por replicacion: {nombre} ({versiones_eliminadas})"
                    )

                    enviar_mensaje(
                        cliente,
                        {
                            "estado": "ok",
                            "mensaje": "Eliminacion replicada",
                            "versiones_eliminadas": versiones_eliminadas
                        }
                    )


            # SALIR

            elif comando == "SALIR":

                enviar_mensaje(
                    cliente,
                    {
                        "estado": "ok",
                        "mensaje": "Conexion cerrada"
                    }
                )

                break


            else:

                enviar_mensaje(
                    cliente,
                    {
                        "estado": "error",
                        "mensaje": "Comando desconocido"
                    }
                )


    except Exception as error:

        registrar_log(
            f"Error con {direccion}: {error}"
        )

    finally:

        cliente.close()

        registrar_log(
            f"Cliente desconectado: {direccion}"
        )


def sincronizar_pendientes():

    while True:

        try:

            procesar_pendientes()

        except Exception as error:

            registrar_log(
                f"Error sincronizando pendientes: {error}"
            )

        threading.Event().wait(5)


def iniciar_servidor():

    servidor = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    servidor.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    servidor.bind(
        (HOST, PORT)
    )

    servidor.listen(10)

    registrar_log(
        "===================================="
    )

    registrar_log(
        "       MINI DROPBOX SERVER"
    )

    registrar_log(
        f"Servidor escuchando en {HOST}:{PORT}"
    )

    registrar_log(
        "===================================="
    )

    hilo_sincronizacion = threading.Thread(
        target=sincronizar_pendientes,
        daemon=True
    )

    hilo_sincronizacion.start()

    while True:

        cliente, direccion = servidor.accept()

        hilo = threading.Thread(
            target=manejar_cliente,
            args=(cliente, direccion),
            daemon=True
        )

        hilo.start()


if __name__ == "__main__":

    iniciar_servidor()