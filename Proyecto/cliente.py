
import socket
import os
import json


HOST = "127.0.0.1"

SERVIDORES = [
    ("127.0.0.1", 5000),
    ("127.0.0.1", 5001)
]

DESCARGAS_DIR = os.path.join(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    ),
    "descargas"
)

os.makedirs(
    DESCARGAS_DIR,
    exist_ok=True
)


def conectar():

    for host, port in SERVIDORES:

        try:

            cliente = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            )

            cliente.settimeout(3)

            cliente.connect(
                (host, port)
            )

            cliente.settimeout(None)

            print(
                f"Conectado al servidor {host}:{port}"
            )

            return cliente

        except ConnectionRefusedError:

            print(
                f"Servidor {host}:{port} no disponible"
            )

        except socket.timeout:

            print(
                f"Tiempo de espera agotado: {host}:{port}"
            )

    raise ConnectionError(
        "No hay servidores disponibles"
    )


def enviar_mensaje(
    cliente,
    datos
):

    mensaje = json.dumps(
        datos
    ) + "\n"

    cliente.sendall(
        mensaje.encode("utf-8")
    )


def recibir_mensaje(
    cliente
):

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



def crear_archivo():

    nombre = input(
        "Nombre del archivo: "
    ).strip()

    if not nombre:

        print(
            "El nombre del archivo no puede estar vacio."
        )

        return

    if os.path.basename(nombre) != nombre:

        print(
            "Ingrese solamente el nombre del archivo."
        )

        return

    contenido = input(
        "Contenido del archivo: "
    )

    ruta = os.path.join(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        ),
        nombre
    )

    with open(
        ruta,
        "w",
        encoding="utf-8"
    ) as archivo:

        archivo.write(
            contenido
        )

    print(
        f"Archivo creado correctamente: {nombre}"
    )


def subir_archivo():

    ruta = input(
        "Ruta del archivo: "
    )

    if not os.path.exists(ruta):

        print(
            "El archivo no existe."
        )

        return

    nombre = os.path.basename(
        ruta
    )

    tamanio = os.path.getsize(
        ruta
    )

    cliente = conectar()

    enviar_mensaje(
        cliente,
        {
            "comando": "SUBIR",
            "nombre": nombre,
            "tamanio": tamanio
        }
    )

    respuesta = recibir_mensaje(
        cliente
    )

    if respuesta["estado"] != "listo":

        print(
            "El servidor no esta listo."
        )

        cliente.close()

        return

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

    respuesta = recibir_mensaje(
        cliente
    )

    print(
        respuesta["mensaje"]
    )

    if respuesta.get("version"):

        print(
            f"Version anterior guardada como: "
            f"{respuesta['version']}"
        )

    cliente.close()


def listar_archivos():

    cliente = conectar()

    enviar_mensaje(
        cliente,
        {
            "comando": "LISTAR"
        }
    )

    respuesta = recibir_mensaje(
        cliente
    )

    cliente.close()

    print(
        "\n--- ARCHIVOS DEL SERVIDOR ---"
    )

    if not respuesta["archivos"]:

        print(
            "No hay archivos."
        )

        return

    for archivo in respuesta["archivos"]:

        print(
            f"- {archivo['nombre']} "
            f"({archivo['tamanio']} bytes)"
        )


def descargar_archivo():

    nombre = input(
        "Nombre del archivo: "
    )

    cliente = conectar()

    enviar_mensaje(
        cliente,
        {
            "comando": "DESCARGAR",
            "nombre": nombre
        }
    )

    respuesta = recibir_mensaje(
        cliente
    )

    if respuesta["estado"] == "error":

        print(
            respuesta["mensaje"]
        )

        cliente.close()

        return

    tamanio = respuesta["tamanio"]

    ruta = os.path.join(
        DESCARGAS_DIR,
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

    cliente.close()

    print(
        f"Archivo descargado: {ruta}"
    )

    print(
        f"Bytes recibidos: {bytes_recibidos}"
    )


def mostrar_versiones():

    nombre = input(
        "Nombre del archivo: "
    )

    cliente = conectar()

    enviar_mensaje(
        cliente,
        {
            "comando": "VERSIONES",
            "nombre": nombre
        }
    )

    respuesta = recibir_mensaje(
        cliente
    )

    cliente.close()

    print(
        "\n--- VERSIONES ---"
    )

    if not respuesta["versiones"]:

        print(
            "No existen versiones."
        )

        return

    for version in respuesta["versiones"]:

        print(
            f"- {version}"
        )


def eliminar_archivo():

    nombre = input(
        "Nombre del archivo: "
    )

    cliente = conectar()

    enviar_mensaje(
        cliente,
        {
            "comando": "ELIMINAR",
            "nombre": nombre
        }
    )

    respuesta = recibir_mensaje(
        cliente
    )

    cliente.close()

    print(
        respuesta["mensaje"]
    )


def menu():

    while True:

        print()
        print("================================")
        print("          MINI DROPBOX")
        print("================================")
        print("1. Crear archivo")
        print("2. Subir archivo")
        print("3. Listar archivos")
        print("4. Descargar archivo")
        print("5. Ver versiones")
        print("6. Eliminar archivo")
        print("7. Salir")
        print("================================")

        opcion = input(
            "Seleccione una opcion: "
        )

        if opcion == "1":

            crear_archivo()

        elif opcion == "2":

            subir_archivo()

        elif opcion == "3":

            listar_archivos()

        elif opcion == "4":

            descargar_archivo()

        elif opcion == "5":

            mostrar_versiones()

        elif opcion == "6":

            eliminar_archivo()

        elif opcion == "7":

            cliente = conectar()

            enviar_mensaje(
                cliente,
                {
                    "comando": "SALIR"
                }
            )

            cliente.close()

            print(
                "Cliente cerrado."
            )

            break

        else:

            print(
                "Opcion invalida."
            )


if __name__ == "__main__":

    menu()