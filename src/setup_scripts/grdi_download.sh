#!/bin/bash

GREP_OPTIONS=''

cookiejar=$(mktemp cookies.XXXXXXXXXX)
netrc=$(mktemp netrc.XXXXXXXXXX)
chmod 0600 "$cookiejar" "$netrc"
function finish {
  rm -rf "$cookiejar" "$netrc"
}

trap finish EXIT
WGETRC="$wgetrc"

# Use command-line arguments for username, password, and optional directory
username=$1
password=$2
download_dir=$3

if [ -z "$username" ] || [ -z "$password" ]; then
  echo "Usage: $0 <username> <password> [download_dir]"
  exit 1
fi

# If no download directory is provided, use the current directory
if [ -z "$download_dir" ]; then
  download_dir="."
fi

# Ensure the directory exists
mkdir -p "$download_dir" || { echo "Failed to create directory: $download_dir"; exit 1; }

echo "machine urs.earthdata.nasa.gov login $username password $password" >> $netrc

exit_with_error() {
    echo
    echo "Unable to Retrieve Data"
    echo
    echo $1
    echo
    echo "https://sedac.ciesin.columbia.edu/downloads/data/povmap/povmap-grdi-v1/povmap-grdi-v1-vnl-2020-geotiff.zip"
    echo
    exit 1
}

detect_app_approval() {
    approved=$(curl -s -b "$cookiejar" -c "$cookiejar" -L --max-redirs 5 --netrc-file "$netrc" https://sedac.ciesin.columbia.edu/downloads/data/povmap/povmap-grdi-v1/povmap-grdi-v1-vnl-2020-geotiff.zip -w '\n%{http_code}' | tail -1)
    if [ "$approved" -ne "200" ] && [ "$approved" -ne "301" ] && [ "$approved" -ne "302" ]; then
        exit_with_error "Please ensure that you have authorized the remote application by visiting the link below."
    fi
}

setup_auth_curl() {
    status=$(curl -s -z "$(date)" -w '\n%{http_code}' https://sedac.ciesin.columbia.edu/downloads/data/povmap/povmap-grdi-v1/povmap-grdi-v1-vnl-2020-geotiff.zip | tail -1)
    if [[ "$status" -ne "200" && "$status" -ne "304" ]]; then
        detect_app_approval
    fi
}

setup_auth_wget() {
    touch ~/.netrc
    chmod 0600 ~/.netrc
    credentials=$(grep 'machine urs.earthdata.nasa.gov' ~/.netrc)
    if [ -z "$credentials" ]; then
        cat "$netrc" >> ~/.netrc
    fi
}

fetch_urls() {
  if command -v curl >/dev/null 2>&1; then
      setup_auth_curl
      while read -r line; do
        filename="${line##*/}"
        stripped_query_params="${filename%%\?*}"

        curl -f -b "$cookiejar" -c "$cookiejar" -L --netrc-file "$netrc" -g -o "$download_dir/$stripped_query_params" -- $line && echo || exit_with_error "Command failed with error. Please retrieve the data manually."
      done;
  elif command -v wget >/dev/null 2>&1; then
      setup_auth_wget
      while read -r line; do
        filename="${line##*/}"
        stripped_query_params="${filename%%\?*}"

        wget --load-cookies "$cookiejar" --save-cookies "$cookiejar" --output-document "$download_dir/$stripped_query_params" --keep-session-cookies -- $line && echo || exit_with_error "Command failed with error. Please retrieve the data manually."
      done;
  else
      exit_with_error "Error: Could not find a command-line downloader. Please install curl or wget."
  fi
}

fetch_urls <<'EDSCEOF'
https://sedac.ciesin.columbia.edu/downloads/data/povmap/povmap-grdi-v1/povmap-grdi-v1-geotiff.zip
EDSCEOF
