#!/usr/bin/env bash
set -euo pipefail

readonly COMMAND_NAME="cardscan4linux"
readonly INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
readonly DOWNLOAD_URL="${DOWNLOAD_URL:-https://raw.githubusercontent.com/CobaltTechSA/CardScan4Linux/master/cardscan4linux.py}"
readonly TARGET_FILE="${INSTALL_DIR}/${COMMAND_NAME}"

log() { printf '[*] %s\n' "$*"; }
fail() { printf '[!] %s\n' "$*" >&2; exit 1; }

package_install_command() {
    local package="${1:-python3}"
    if command -v apt-get >/dev/null 2>&1; then
        printf 'apt-get update && apt-get install -y %q' "$package"
    elif command -v dnf >/dev/null 2>&1; then
        printf 'dnf install -y %q' "$package"
    elif command -v yum >/dev/null 2>&1; then
        printf 'yum install -y %q' "$package"
    elif command -v zypper >/dev/null 2>&1; then
        printf 'zypper --non-interactive install %q' "$package"
    elif command -v pacman >/dev/null 2>&1; then
        [[ "$package" == python3 ]] && package=python
        printf 'pacman -Sy --needed %q' "$package"
    elif command -v apk >/dev/null 2>&1; then
        printf 'apk add %q' "$package"
    else
        return 1
    fi
}

privileged() {
    if [[ ${EUID} -eq 0 ]]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        fail "Se necesitan permisos de administrador. Ejecuta este instalador como root o instala sudo."
    fi
}

offer_python_install() {
    local install_command answer
    install_command="$(package_install_command python3)" ||
        fail "Python 3 no está instalado y no se reconoció el gestor de paquetes. Instálalo y vuelve a intentarlo."

    printf '[!] Python 3 es necesario y no está instalado.\n' >&2
    printf '    Comando propuesto: %s\n' "$install_command" >&2
    [[ -t 0 ]] || fail "La entrada no es interactiva; ejecuta el comando propuesto y vuelve a intentarlo."

    read -r -p "¿Deseas instalar Python 3 ahora? [s/N] " answer
    case "$answer" in
        s|S|si|SI|sí|Sí)
            # Fixed command selected from the package-manager allow-list above.
            if [[ ${EUID} -eq 0 ]]; then
                bash -c "$install_command"
            elif command -v sudo >/dev/null 2>&1; then
                sudo bash -c "$install_command"
            else
                fail "No se encontró sudo. Ejecuta como root: ${install_command}"
            fi
            ;;
        *) fail "Instalación cancelada. Instala Python 3 y vuelve a intentarlo." ;;
    esac
}

offer_downloader_install() {
    local install_command
    install_command="$(package_install_command curl)" ||
        fail "Se necesita curl o wget. Instala uno de ellos y vuelve a intentarlo."
    fail "Se necesita curl o wget para descargar el escáner. Comando propuesto: ${install_command}"
}

check_dependencies() {
    command -v curl >/dev/null 2>&1 || command -v wget >/dev/null 2>&1 || offer_downloader_install
    command -v python3 >/dev/null 2>&1 || offer_python_install
    command -v python3 >/dev/null 2>&1 || fail "Python 3 continúa sin estar disponible."
    python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)' ||
        fail "Se requiere Python 3.8 o posterior. Versión encontrada: $(python3 --version 2>&1)"
    command -v install >/dev/null 2>&1 ||
        fail "No se encontró 'install' (normalmente incluido en coreutils)."
    command -v mktemp >/dev/null 2>&1 ||
        fail "No se encontró 'mktemp' (normalmente incluido en coreutils)."
}

download_scanner() {
    local destination="$1"
    log "Descargando ${DOWNLOAD_URL}..."
    if command -v curl >/dev/null 2>&1; then
        curl --proto '=https' --tlsv1.2 --fail --silent --show-error \
            --location "$DOWNLOAD_URL" --output "$destination"
    else
        wget --https-only --quiet --output-document="$destination" "$DOWNLOAD_URL"
    fi
    [[ -s "$destination" ]] || fail "GitHub devolvió un archivo vacío."
    python3 -c 'import sys; compile(open(sys.argv[1], "rb").read(), sys.argv[1], "exec")' \
        "$destination" || fail "El archivo descargado no es un script Python válido."
}

main() {
    local source_file
    check_dependencies
    source_file="$(mktemp "${TMPDIR:-/tmp}/cardscan4linux.XXXXXX")"
    trap "rm -f -- $(printf '%q' "$source_file")" EXIT
    download_scanner "$source_file"

    log "Instalando ${COMMAND_NAME} en ${TARGET_FILE}..."
    if mkdir -p "$INSTALL_DIR" 2>/dev/null &&
            install -m 0755 "$source_file" "$TARGET_FILE" 2>/dev/null; then
        :
    else
        privileged mkdir -p "$INSTALL_DIR"
        privileged install -m 0755 "$source_file" "$TARGET_FILE"
    fi
    [[ -x "$TARGET_FILE" ]] || fail "La instalación no produjo un comando ejecutable."

    if [[ ":${PATH}:" != *":${INSTALL_DIR}:"* ]]; then
        printf '[!] %s no está incluido en PATH. Añádelo para invocar el comando sin ruta completa.\n' "$INSTALL_DIR" >&2
    fi
    log "Instalación completada: ${TARGET_FILE}"
    log "Prueba el comando con: ${COMMAND_NAME} --help"
}

main "$@"
